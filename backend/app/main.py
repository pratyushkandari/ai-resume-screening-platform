"""FastAPI application: wiring of middleware, routers and startup tasks.

Run locally with ``uvicorn app.main:app --reload`` from the ``backend`` folder.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .ml_utils import embedding_model
from .observability import trace_requests
from .routers import auth, jobs, ops, rankings, resumes
from .schema import ensure_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start-up and shutdown hook run by FastAPI around the application's life.

    Start-up never blocks on slow dependencies: schema creation failures are
    retried by ``/readyz``, and the embedding model loads in a daemon thread.
    """
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    ensure_schema()  # on failure /readyz reports 503 and retries
    # Load the embedding model in the background so start-up and probes stay fast.
    threading.Thread(target=embedding_model.get, name="embedding-warmup", daemon=True).start()
    yield
    logger.info("[SHUTDOWN] Application stopped.")


app = FastAPI(
    title="AI Resume Screening & Matching API",
    version="3.1.0",
    description="Upload resumes, extract skills and contacts, and rank candidates per job with "
    "skill overlap plus sentence-embedding similarity.",
    lifespan=lifespan,
)


async def security_headers(request: Request, call_next):
    """Add defensive HTTP headers to every API response.

    ``nosniff`` stops browsers guessing content types, ``no-referrer`` avoids
    leaking URLs, and ``DENY`` blocks the API from being framed.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


# Middleware runs outermost-last-added. The order below gives:
#   CORS -> security headers -> tracing (request ID, metrics, JSON 500s) -> routes
# so every response, including an unexpected 500, carries CORS and security
# headers and the browser can read the error message.
app.middleware("http")(trace_requests)
app.middleware("http")(security_headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # auth uses the Authorization header, not cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Response-Time-MS", "X-Cache", "Content-Disposition"],
)

for module in (ops, auth, jobs, resumes, rankings):
    app.include_router(module.router)
