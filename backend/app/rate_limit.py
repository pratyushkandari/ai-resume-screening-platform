"""Fixed-window rate limiting for sensitive endpoints (login, registration).

Counters live in Redis when it is reachable (shared across replicas) and in
process memory otherwise. Exceeding the limit returns 429 with ``Retry-After``.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, Tuple

from fastapi import HTTPException, Request, status

from .cache import redis_connection

WINDOW_SECONDS = 60
_memory: Dict[Tuple[str, str, int], int] = {}
_memory_lock = threading.Lock()


def _client_id(request: Request) -> str:
    """Client IP address used as the rate-limit key.

    Behind a proxy Uvicorn sets it from ``X-Forwarded-For`` only when the proxy
    is trusted (``FORWARDED_ALLOW_IPS``), so clients cannot choose their own key.
    """
    return request.client.host if request.client else "unknown"


def _hit(scope: str, client: str, window: int) -> int:
    """Count one attempt for ``(scope, client, window)`` and return the new total.

    Uses Redis (``INCR`` + ``EXPIRE`` in one round trip, shared by all replicas)
    when available, otherwise an in-process dictionary whose old windows are
    pruned on each call.
    """
    redis_client = redis_connection.client()
    if redis_client is not None:
        key = f"ratelimit:{scope}:{client}:{window}"
        try:
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, WINDOW_SECONDS + 5)  # counters clean themselves up after the window
            count, _ = pipe.execute()
            return int(count)
        except Exception as exc:
            redis_connection.mark_down(exc)
    with _memory_lock:
        for stale in [k for k in _memory if k[2] < window]:
            del _memory[stale]
        key = (scope, client, window)
        _memory[key] = _memory.get(key, 0) + 1
        return _memory[key]


def reset_memory_counters() -> None:
    """Used by tests."""
    with _memory_lock:
        _memory.clear()


def rate_limit(scope: str, limit_per_minute: Callable[[], int]):
    """Dependency factory: ``Depends(rate_limit("login", lambda: settings.login_rate_limit_per_minute))``."""

    def dependency(request: Request) -> None:
        """Raise 429 with ``Retry-After`` when this client exceeded the limit this minute."""
        limit = limit_per_minute()
        if limit <= 0:
            return
        # Fixed window: every attempt in the same minute shares one counter.
        window = int(time.time() // WINDOW_SECONDS)
        if _hit(scope, _client_id(request), window) > limit:
            retry_after = WINDOW_SECONDS - int(time.time() % WINDOW_SECONDS)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a minute and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
