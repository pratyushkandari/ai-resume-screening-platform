"""Database engine, session factory and the request-scoped session dependency."""

from __future__ import annotations

import logging
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

logger = logging.getLogger("db")


def normalize_database_url(url: str) -> str:
    """Pin the PostgreSQL driver explicitly.

    ``postgresql://`` means psycopg2 on SQLAlchemy 2.0 but psycopg 3 on 2.1+.
    The project ships psycopg2, so make the choice explicit to keep both working.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def build_engine(url: str) -> Engine:
    """Create the SQLAlchemy engine for ``url``.

    PostgreSQL gets a connection pool (10 + 20 overflow) with ``pool_pre_ping``
    so connections dropped by the server are replaced transparently. SQLite
    allows use from FastAPI's worker threads, and an in-memory database uses a
    single shared connection (``StaticPool``) so every session sees the same data.
    """
    url = normalize_database_url(url)
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # one shared in-memory database
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()

logger.info("[DB] Using %s", make_url(normalize_database_url(settings.database_url)).render_as_string(hide_password=True))


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
