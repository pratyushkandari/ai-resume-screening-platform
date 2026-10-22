"""Optional Redis client shared by the summary cache and the rate limiter.

If Redis is unreachable the app keeps working: cache calls become no-ops and
rate limiting falls back to an in-process counter. After a failure the client
waits ``RETRY_AFTER_SECONDS`` before trying Redis again, so a Redis restart is
picked up without restarting the API.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

from .config import settings

logger = logging.getLogger("cache")
RETRY_AFTER_SECONDS = 30


class RedisConnection:
    """Lazily created, self-healing Redis client.

    The first call connects (0.5 s timeouts). After any failure the connection is
    marked down for ``RETRY_AFTER_SECONDS`` so a missing Redis costs at most one
    slow call per window instead of one per request.
    """

    def __init__(self, url: str) -> None:
        """Remember the URL; no network call happens until ``client()`` is used."""
        self._url = url
        self._client = None
        self._down_until = 0.0
        self._lock = threading.Lock()

    def client(self):
        """Return a live client or ``None`` while Redis is considered down."""
        if time.monotonic() < self._down_until:
            return None
        with self._lock:
            if self._client is None:
                try:
                    import redis

                    client = redis.Redis.from_url(
                        self._url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5
                    )
                    client.ping()
                    self._client = client
                    logger.info("[CACHE] Redis connection established.")
                except Exception as exc:  # redis missing, refused, timeout…
                    self.mark_down(exc)
                    return None
            return self._client

    def mark_down(self, exc: Exception) -> None:
        """Drop the client and stop using Redis for ``RETRY_AFTER_SECONDS``.

        Logs once per outage rather than on every failed call.
        """
        if self._down_until <= time.monotonic():
            logger.warning("[CACHE] Redis unavailable (%s); retrying in %ss.", exc.__class__.__name__, RETRY_AFTER_SECONDS)
        self._client = None
        self._down_until = time.monotonic() + RETRY_AFTER_SECONDS

    @property
    def available(self) -> bool:
        """True if Redis is reachable right now (used by the readiness probe)."""
        return self.client() is not None


redis_connection = RedisConnection(settings.redis_url)


class CacheService:
    """Cache-aside helpers storing JSON values with a TTL."""

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Return the cached JSON value for ``key``, or ``None`` on a miss or Redis error."""
        client = redis_connection.client()
        if client is None:
            return None
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            redis_connection.mark_down(exc)
            return None

    @staticmethod
    def set(key: str, value: Any, ttl_seconds: int) -> bool:
        """Store ``value`` as JSON under ``key`` for ``ttl_seconds``.

        Returns:
            True if stored; False when Redis is unavailable (callers just skip caching).
        """
        client = redis_connection.client()
        if client is None:
            return False
        try:
            client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
            return True
        except Exception as exc:
            redis_connection.mark_down(exc)
            return False

    @staticmethod
    def delete(*keys: str) -> int:
        """Delete ``keys``; returns how many existed (0 when Redis is unavailable)."""
        client = redis_connection.client()
        if client is None or not keys:
            return 0
        try:
            return int(client.delete(*keys))
        except Exception as exc:
            redis_connection.mark_down(exc)
            return 0


def job_summary_key(job_id: int) -> str:
    """Cache key of a job's dashboard summary (invalidated by uploads and ranking)."""
    return f"job:summary:{job_id}"
