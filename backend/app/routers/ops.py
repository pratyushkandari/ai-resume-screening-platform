"""Health, readiness and metrics endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..cache import redis_connection
from ..config import settings
from ..db import get_db
from ..ml_utils import embedding_model
from ..observability import metrics
from ..schema import ensure_schema

router = APIRouter(tags=["Observability"])
logger = logging.getLogger("ops")


@router.get("/healthz")
def health_check() -> dict:
    """Liveness: the process is up and serving requests."""
    return {"status": "ok", "service": "resume-screener", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/readyz")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe: can this instance serve traffic right now?

    Ready means the database answers, its tables exist, and (when
    ``REQUIRE_EMBEDDING_MODEL`` is on) the embedding model is loaded. Load
    balancers and Kubernetes stop routing to an instance that returns 503.
    """
    body = {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        db.execute(text("SELECT 1"))
        body["database"] = "connected"
    except Exception:
        logger.exception("Readiness check: database unavailable")
        body.update(status="unavailable", database="unavailable")
        return JSONResponse(status_code=503, content=body)
    if not ensure_schema():  # retries table creation if the DB was down at start-up
        body.update(status="unavailable", database="schema not ready")
        return JSONResponse(status_code=503, content=body)

    model_ready = embedding_model.loaded  # loading is started at startup, never inside a probe
    body["ml_model"] = "active" if model_ready else "unavailable"
    body["cache"] = "redis" if redis_connection.available else "disabled"
    if settings.require_embedding_model and not model_ready:
        body["status"] = "unavailable"
        return JSONResponse(status_code=503, content=body)
    return body


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    """Prometheus text format (per process)."""
    return metrics.render({"embedding_model_loaded": 1 if embedding_model.loaded else 0})
