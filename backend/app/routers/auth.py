"""Registration, login and the current-user profile."""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    ROLE_CANDIDATE,
    ROLE_HR,
    create_access_token,
    dummy_password_hash,
    get_current_user,
    hash_password,
    validate_email_format,
    validate_password_strength,
    verify_password,
)
from ..config import settings
from ..db import get_db
from ..rate_limit import rate_limit
from ..schemas import TokenOut, UserOut
from ..text_utils import clean_text

router = APIRouter(prefix="/api", tags=["Auth"])
logger = logging.getLogger("auth")


async def _read_body(request: Request) -> Dict[str, Any]:
    """Accept JSON (the web app) or form data (curl, Swagger, tests)."""
    content_type = request.headers.get("content-type", "").lower()
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = dict(await request.form())
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Malformed request body.") from None
    if not isinstance(data, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Request body must be an object.")
    return data


def _token_response(user: models.User) -> TokenOut:
    """Response body shared by registration and login: a fresh token plus profile basics."""
    return TokenOut(
        access_token=create_access_token(user),
        user_id=user.user_id,
        name=user.name,
        role=user.role,
        expires_in=settings.access_token_expire_minutes * 60,
    )


def _register(db: Session, name: str, email: str, password: str, role: str, signup_code: str) -> models.User:
    """Validate the input and create a user (runs in a worker thread because bcrypt is slow).

    Raises:
        HTTPException: 400 invalid name/email/password/role, 403 recruiter sign-up
            disabled or wrong access code, 409 email already registered.
    """
    clean_name = clean_text(name)
    if not 2 <= len(clean_name) <= 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Full name must be between 2 and 100 characters.")
    ok, email_or_error = validate_email_format(email)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=email_or_error)
    ok, message = validate_password_strength(password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)
    if role not in (ROLE_HR, ROLE_CANDIDATE):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Role must be 'hr' or 'candidate'.")
    if role == ROLE_HR:
        if not settings.hr_signup_code:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Recruiter self-registration is disabled. Ask an administrator to create your account.",
            )
        if not secrets.compare_digest(signup_code.encode(), settings.hr_signup_code.encode()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid recruiter access code.")

    if db.query(models.User).filter(func.lower(models.User.email) == email_or_error).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An account with this email already exists. Please sign in.")
    user = models.User(name=clean_name, email=email_or_error, password=hash_password(password), role=role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An account with this email already exists. Please sign in.") from None
    logger.info("Registered user_id=%s role=%s", user.user_id, role)
    return user


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", lambda: settings.register_rate_limit_per_minute))],
)
async def register(request: Request, db: Session = Depends(get_db)) -> TokenOut:
    """Create an account and return a token. ``role="hr"`` requires ``access_code`` == ``HR_SIGNUP_CODE``."""
    data = await _read_body(request)
    user = await run_in_threadpool(
        _register,
        db,
        str(data.get("name") or ""),
        str(data.get("email") or ""),
        str(data.get("password") or ""),
        str(data.get("role") or ROLE_CANDIDATE).strip().lower(),
        str(data.get("access_code") or ""),
    )
    return _token_response(user)


def _authenticate(db: Session, email: str, password: str) -> models.User:
    """Return the user for valid credentials, or raise one uniform 401.

    The same message is used for an unknown email and a wrong password so the
    response does not reveal which emails have accounts.
    """
    ok, normalized = validate_email_format(email)
    if not ok or not password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    user = db.query(models.User).filter(func.lower(models.User.email) == normalized).first()
    # Always run one bcrypt check so unknown emails are not answered faster.
    password_ok = verify_password(password, user.password if user else dummy_password_hash())
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return user


@router.post(
    "/login",
    response_model=TokenOut,
    dependencies=[Depends(rate_limit("login", lambda: settings.login_rate_limit_per_minute))],
)
async def login(request: Request, db: Session = Depends(get_db)) -> TokenOut:
    """Sign in with email and password (JSON or form) and receive a token. Rate limited per IP."""
    data = await _read_body(request)
    # bcrypt is CPU-bound (~0.25 s); run it off the event loop.
    user = await run_in_threadpool(_authenticate, db, str(data.get("email") or ""), str(data.get("password") or ""))
    logger.info("Login user_id=%s", user.user_id)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)) -> UserOut:
    """Profile of the signed-in user; API clients can call it to check that a token is still valid."""
    return UserOut(user_id=current_user.user_id, name=current_user.name, email=current_user.email, role=current_user.role)
