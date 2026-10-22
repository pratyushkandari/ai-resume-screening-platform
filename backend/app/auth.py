"""Authentication and authorization: validation, bcrypt, JWT and FastAPI dependencies."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Callable, Iterable, Optional, Tuple

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .db import get_db

ROLE_HR = "hr"
ROLE_CANDIDATE = "candidate"
ROLES = (ROLE_HR, ROLE_CANDIDATE)

BCRYPT_ROUNDS = 12
_bearer = HTTPBearer(auto_error=False)

COMMON_WEAK_PASSWORDS = {
    "password", "12345678", "123456789", "qwerty123", "admin123",
    "password123", "welcome123", "letmein123", "iloveyou123", "testing123",
}
# Pragmatic syntax check (not a full RFC 5322 parser).
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$")
SPECIAL_CHARS = re.compile(r"[!@#$%^&*(),.?\":{}|<>\-_=+~`\[\]\\/;']")


# --------------------------------------------------------------------------- validation
def validate_email_format(email: str) -> Tuple[bool, str]:
    """Return ``(True, normalized_email)`` or ``(False, error_message)``."""
    if not email or not isinstance(email, str):
        return False, "Email address is required"
    cleaned = email.strip().lower()
    if not 5 <= len(cleaned) <= 254:
        return False, "Email address must be between 5 and 254 characters"
    if not EMAIL_REGEX.match(cleaned):
        return False, "Invalid email address format (e.g. user@company.com)"
    domain = cleaned.split("@", 1)[1]
    if domain.startswith(("-", ".")) or ".." in domain:
        return False, "Invalid domain structure in email address"
    return True, cleaned


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """8–128 chars, upper, lower, digit, special character, not a common password."""
    if not password or not isinstance(password, str):
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if len(password) > 128:
        return False, "Password must not exceed 128 characters"
    if len(password.encode("utf-8")) > 72:
        return False, "Password must not exceed 72 bytes (bcrypt limit)"
    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False, "Password is too common and easily guessed. Please choose a stronger password."
    checks = [
        (r"[A-Z]", "at least one uppercase letter (A-Z)"),
        (r"[a-z]", "at least one lowercase letter (a-z)"),
        (r"[0-9]", "at least one numeric digit (0-9)"),
    ]
    for pattern, message in checks:
        if not re.search(pattern, password):
            return False, f"Password must contain {message}"
    if not SPECIAL_CHARS.search(password):
        return False, "Password must contain at least one special character (!@#$%^&*...)"
    return True, "Password meets all security criteria"


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    """Hash ``password`` with bcrypt and a fresh random salt.

    The cost factor (``BCRYPT_ROUNDS``, 12 in production) makes each guess slow
    for an attacker; tests lower it to keep the suite fast.

    Args:
        password: The plaintext password (already validated, at most 72 bytes).

    Returns:
        The bcrypt hash as text, e.g. ``$2b$12$...`` (salt included).
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time bcrypt check. Anything that is not a valid bcrypt hash fails."""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:  # malformed hash (e.g. a legacy plaintext row)
        return False


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """Return a throwaway hash to check when the email is unknown.

    A failed login then costs one bcrypt check whether or not the account
    exists, so response time does not reveal which emails are registered.
    """
    return hash_password(secrets.token_urlsafe(16))


# --------------------------------------------------------------------------- tokens
def create_access_token(user: models.User, expires_delta: Optional[timedelta] = None) -> str:
    """Issue a signed JWT (HS256) for ``user``.

    Claims: ``sub`` (user id as a string), ``role`` and ``name`` (for display
    only; authorization re-reads the role from the database), ``iat`` and ``exp``.

    Args:
        user: The authenticated user.
        expires_delta: Lifetime override; defaults to ``ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        The encoded token string for the ``Authorization: Bearer`` header.
    """
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": str(user.user_id), "role": user.role, "name": user.name, "iat": now, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify a JWT's signature and expiry and return its claims.

    Raises:
        HTTPException: 401 if the token is expired, tampered with, signed with
            another key, or missing the required ``exp``/``sub`` claims.
    """
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], options={"require": ["exp", "sub"]}
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session token has expired. Please log in again.") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid authentication credentials.") from None


def _unauthorized(detail: str) -> HTTPException:
    """Build a 401 response with the ``WWW-Authenticate: Bearer`` header (RFC 6750)."""
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


# --------------------------------------------------------------------------- dependencies
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve the user from the bearer token. The role always comes from the database."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Authentication token required. Please log in.")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized("Invalid token payload.") from None
    user = db.get(models.User, user_id)
    if user is None:
        raise _unauthorized("User account not found or deactivated.")
    return user


def require_role(allowed_roles: Iterable[str]) -> Callable[..., models.User]:
    """Dependency factory for role-based access control, e.g. ``Depends(require_role(["hr"]))``."""
    allowed = {r.lower() for r in allowed_roles}

    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        """Return the signed-in user, or raise 403 if their role is not allowed."""
        if (current_user.role or "").lower() not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action.")
        return current_user

    return role_checker


require_hr = require_role([ROLE_HR])


def get_owned_job(job_id: int, current_user: models.User, db: Session) -> models.Job:
    """Load a job that belongs to ``current_user`` or raise 404/403."""
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job opening not found.")
    if job.created_by != current_user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You can only access your own job requisitions.")
    return job
