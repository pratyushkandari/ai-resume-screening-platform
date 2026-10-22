"""Database schema preparation: create missing tables and merge duplicate skills.

Runs at start-up. If the database is not reachable yet (for example it starts
after the API), the readiness probe calls ``ensure_schema`` again until it
succeeds, so the API never serves requests against a database without tables.
"""

from __future__ import annotations

import logging
import threading

from . import models  # noqa: F401  (registers tables on Base.metadata)
from .db import Base, SessionLocal, engine
from .services.skills import merge_duplicate_skills

logger = logging.getLogger("schema")
_ready = False
_lock = threading.Lock()


def ensure_schema() -> bool:
    """Prepare the schema once per process; return whether it is ready."""
    global _ready
    if _ready:
        return True
    with _lock:
        if not _ready:
            try:
                Base.metadata.create_all(bind=engine)  # creates missing tables; never alters existing ones
                with SessionLocal() as db:
                    merge_duplicate_skills(db)
                _ready = True
                logger.info("[SCHEMA] Database schema verified.")
            except Exception:
                logger.exception("[SCHEMA] Database not reachable; will retry on the next readiness check.")
    return _ready
