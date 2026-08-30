# backend/app/auth.py

import os
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .db import SessionLocal
from . import models


# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "prod-super-secret-key-change-in-production-resume-matcher-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# Security Bearer scheme
security = HTTPBearer(auto_error=False)

# Common weak passwords blacklist
COMMON_WEAK_PASSWORDS = {
    "password", "12345678", "123456789", "qwerty123", "admin123",
    "password123", "welcome123", "letmein123", "iloveyou123", "testing123"
}

# Strict RFC 5322 Email Validation Pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# =============================================================================
#  VALIDATION & SANITIZATION LOGIC
# =============================================================================
def validate_email_format(email: str) -> Tuple[bool, str]:
    """
    Validates email against strict RFC 5322 standards.
    Checks syntax, domain structure, and length bounds.
    """
    if not email or not isinstance(email, str):
        return False, "Email address is required"

    cleaned = email.strip().lower()

    if len(cleaned) < 5 or len(cleaned) > 254:
        return False, "Email address must be between 5 and 254 characters"

    if not EMAIL_REGEX.match(cleaned):
        return False, "Invalid email address format (e.g. user@company.com)"

    # Check domain has valid dot-separated TLD
    parts = cleaned.split("@")
    if len(parts) != 2 or "." not in parts[1]:
        return False, "Email must have a valid domain and extension"

    domain = parts[1]
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False, "Invalid domain structure in email address"

    return True, cleaned


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Industry-standard Password Strength Validator:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 numeric digit
    - At least 1 special character (!@#$%^&*...)
    - Not in common weak passwords dictionary
    """
    if not password or not isinstance(password, str):
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 128:
        return False, "Password must not exceed 128 characters"

    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False, "Password is too common and easily guessed. Please choose a stronger password."

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)"

    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one numeric digit (0-9)"

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+~`\[\]]", password):
        return False, "Password must contain at least one special character (!@#$%^&*...)"

    return True, "Password meets all security criteria"


# =============================================================================
#  PASSWORD HASHING & VERIFICATION (Bcrypt)
# =============================================================================
def hash_password(password: str) -> str:
    """Hash password with direct bcrypt (truncated safely to 72 bytes)."""
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify password with bcrypt and legacy plaintext fallback."""
    if not hashed:
        return False
    try:
        pwd_bytes = password.encode('utf-8')[:72]
        hashed_bytes = hashed.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        # Fallback for plain passwords migration
        return password == hashed



# =============================================================================
#  JWT TOKEN OPERATIONS
# =============================================================================
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate RFC 7519 compliant signed JSON Web Token."""
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now_utc})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT access token signature & expiration."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
#  FASTAPI DEPENDENCIES
# =============================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """
    FastAPI dependency to extract and verify the current authenticated user from Bearer token.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id: Optional[int] = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    Optional authentication dependency for endpoints supporting both guest and logged-in users.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("user_id")
        if user_id:
            return db.query(models.User).filter(models.User.user_id == user_id).first()
    except Exception:
        return None
    return None


def require_role(allowed_roles: List[str]):
    """
    Role-Based Access Control (RBAC) dependency factory.
    Example: Depends(require_role(["hr"]))
    """
    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        user_role = (current_user.role or "").strip().lower()
        if user_role not in [r.lower() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted. Operation requires one of the following roles: {allowed_roles}"
            )
        return current_user
    return role_checker