"""Application settings, read once from the environment.

Values come from real environment variables first, then from ``backend/.env``
(python-dotenv never overrides variables that are already set), then from the
defaults below. Insecure configurations fail fast when ``APP_ENV=production``.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

logger = logging.getLogger("config")

# Secrets that have been published in this repository at some point. They must
# never be used to sign real tokens.
KNOWN_PUBLIC_SECRETS = {
    "prod-super-secret-key-change-in-production-resume-matcher-2026",
    "change-this-to-a-secure-random-secret-key-in-production",
}


def _bool(name: str, default: bool) -> bool:
    """Read a boolean flag: ``1/true/yes/on`` (any case) is True; unset or empty uses ``default``."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class ConfigurationError(RuntimeError):
    """Raised when the service is started with an invalid or unsafe configuration."""


def _int(name: str, default: int, minimum: int = 1) -> int:
    """Read a whole-number setting, failing fast with a clear message.

    Args:
        name: Environment variable name.
        default: Value used when the variable is unset or empty.
        minimum: Smallest accepted value (0 allows "disabled" for rate limits).

    Raises:
        ConfigurationError: The value is not an integer or is below ``minimum``.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigurationError(f"{name} must be a whole number, got {raw!r}.") from None
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}, got {value}.")
    return value


def _list(name: str, default: List[str]) -> List[str]:
    """Read a comma-separated list, ignoring blanks; unset or empty uses ``default``."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable, typed view of every setting the application reads.

    Created once at import time (``settings``) so all modules share one
    validated configuration. See ``.env.example`` for each variable.
    """
    app_env: str
    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    hr_signup_code: str
    upload_dir: Path
    max_upload_bytes: int
    max_batch_files: int
    cors_origins: List[str]
    require_embedding_model: bool
    embedding_model_name: str
    login_rate_limit_per_minute: int
    register_rate_limit_per_minute: int
    upload_rate_limit_per_minute: int
    summary_cache_ttl_seconds: int
    allowed_extensions: tuple = field(default=(".pdf", ".docx", ".txt"))


def load_settings() -> Settings:
    """Build ``Settings`` from the environment, applying defaults and safety checks.

    In production a missing or publicly known ``JWT_SECRET_KEY`` is fatal. In
    development a random per-process key is generated instead (tokens then stop
    working after a restart, which is acceptable locally).

    Raises:
        ConfigurationError: Unsafe or invalid configuration.
    """
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    production = app_env == "production"

    jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not jwt_secret or jwt_secret in KNOWN_PUBLIC_SECRETS:
        if production:
            raise ConfigurationError(
                "JWT_SECRET_KEY must be set to a private random value in production "
                "(e.g. python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
            )
        reason = "is not set" if not jwt_secret else "uses a value published in the repository"
        logger.warning("JWT_SECRET_KEY %s; using a random per-process key (tokens reset on restart).", reason)
        jwt_secret = secrets.token_urlsafe(48)

    upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
    if not upload_dir.is_absolute():
        upload_dir = BACKEND_DIR / upload_dir

    return Settings(
        app_env=app_env,
        # No credentials in code: without DATABASE_URL a local SQLite file is used.
        database_url=os.getenv("DATABASE_URL") or f"sqlite:///{(BACKEND_DIR / 'dev.db').as_posix()}",
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        jwt_secret_key=jwt_secret,
        jwt_algorithm="HS256",
        access_token_expire_minutes=_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60),
        hr_signup_code=os.getenv("HR_SIGNUP_CODE", "").strip(),
        upload_dir=upload_dir,
        max_upload_bytes=_int("MAX_UPLOAD_MB", 15) * 1024 * 1024,
        max_batch_files=_int("MAX_BATCH_FILES", 25),
        cors_origins=_list(
            "CORS_ORIGINS",
            ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost", "http://localhost:4173"],
        ),
        require_embedding_model=_bool("REQUIRE_EMBEDDING_MODEL", production),
        embedding_model_name=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        # 0 disables the limit (useful for load tests); negative values are rejected.
        login_rate_limit_per_minute=_int("LOGIN_RATE_LIMIT_PER_MINUTE", 10, minimum=0),
        register_rate_limit_per_minute=_int("REGISTER_RATE_LIMIT_PER_MINUTE", 5, minimum=0),
        # Per signed-in account; a batch upload counts as one request.
        upload_rate_limit_per_minute=_int("UPLOAD_RATE_LIMIT_PER_MINUTE", 10, minimum=0),
        summary_cache_ttl_seconds=_int("SUMMARY_CACHE_TTL_SECONDS", 300),
    )


settings = load_settings()
