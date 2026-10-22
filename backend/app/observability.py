"""Request tracing middleware and a small, thread-safe Prometheus-style metrics registry.

Metrics are per process. In a multi-replica deployment Prometheus scrapes each
pod and aggregates; nothing here is shared across processes.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("api")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
QUIET_PATHS = {"/healthz", "/readyz", "/metrics"}


class Metrics:
    """In-memory counters rendered in the Prometheus text format at ``/metrics``.

    A lock guards updates because FastAPI serves requests from several threads.
    """

    def __init__(self) -> None:
        """Create empty counters and remember the start time for ``app_uptime_seconds``."""
        self._lock = threading.Lock()
        self.started = time.time()
        self.requests: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self.duration_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self.duration_count: Dict[Tuple[str, str], int] = defaultdict(int)
        self.counters: Dict[str, int] = defaultdict(int)

    def observe(self, method: str, path: str, status_code: int, seconds: float) -> None:
        """Record one finished request: count it by method/route/status and add its latency."""
        with self._lock:
            self.requests[(method, path, status_code)] += 1
            self.duration_sum[(method, path)] += seconds
            self.duration_count[(method, path)] += 1

    def inc(self, name: str, amount: int = 1) -> None:
        """Increase the free-form counter ``name`` (e.g. cache hits) by ``amount``."""
        with self._lock:
            self.counters[name] += amount

    def render(self, gauges: Dict[str, float]) -> str:
        """Return all metrics, plus the given gauges, in Prometheus exposition format."""
        with self._lock:
            lines = [
                "# HELP http_requests_total HTTP requests by method, route and status.",
                "# TYPE http_requests_total counter",
            ]
            for (method, path, code), n in sorted(self.requests.items()):
                lines.append(f'http_requests_total{{method="{method}",path="{path}",status="{code}"}} {n}')
            lines += [
                "# HELP http_request_duration_seconds Request latency (sum and count per route).",
                "# TYPE http_request_duration_seconds summary",
            ]
            for (method, path), total in sorted(self.duration_sum.items()):
                lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}')
                lines.append(
                    f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {self.duration_count[(method, path)]}'
                )
            for name, value in sorted(self.counters.items()):
                lines += [f"# TYPE {name} counter", f"{name} {value}"]
        lines += ["# TYPE app_uptime_seconds gauge", f"app_uptime_seconds {int(time.time() - self.started)}"]
        for name, value in gauges.items():
            lines += [f"# TYPE {name} gauge", f"{name} {value}"]
        return "\n".join(lines) + "\n"


metrics = Metrics()


async def trace_requests(request: Request, call_next):
    """Attach/propagate ``X-Request-ID``, add ``X-Response-Time-MS`` and record metrics.

    Unexpected exceptions are logged with the request ID and turned into a JSON
    500 here, so the response still passes through the CORS and security-header
    middleware and the client can show (and report) the request ID.
    """
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("[%s] Unhandled error on %s %s", request_id, request.method, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error.", "request_id": request_id})
    elapsed = time.perf_counter() - start
    path = _route_template(request)
    metrics.observe(request.method, path, response.status_code, elapsed)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-MS"] = f"{elapsed * 1000:.2f}"
    if request.url.path not in QUIET_PATHS:
        logger.info("[%s] %s %s -> %s (%.1fms)", request_id, request.method, path, response.status_code, elapsed * 1000)
    return response


def _route_template(request: Request) -> str:
    """Use the route pattern (``/api/jobs/{job_id}``) so metric labels stay low-cardinality."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"
