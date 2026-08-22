# backend/tests/test_auth.py

import pytest
from app import auth


def test_password_hashing():
    """Verify Bcrypt password hashing and validation."""
    raw_password = "SecurePassword123!"
    hashed = auth.hash_password(raw_password)

    assert hashed != raw_password
    assert auth.verify_password(raw_password, hashed) is True
    assert auth.verify_password("WrongPassword123!", hashed) is False


def test_password_strength_validator():
    """Verify multi-criteria password strength analyzer."""
    # Weak - too short
    ok, err = auth.validate_password_strength("Short1!")
    assert ok is False

    # Weak - missing uppercase
    ok, err = auth.validate_password_strength("password123!")
    assert ok is False

    # Weak - missing number
    ok, err = auth.validate_password_strength("PasswordOnly!")
    assert ok is False

    # Weak - missing special char
    ok, err = auth.validate_password_strength("Password123")
    assert ok is False

    # Weak - dictionary word
    ok, err = auth.validate_password_strength("password123")
    assert ok is False

    # Strong - meets all criteria
    ok, err = auth.validate_password_strength("Str0ng!Passw0rd")
    assert ok is True


def test_email_format_validator():
    """Verify RFC 5322 email syntax and domain checking."""
    # Valid emails
    assert auth.validate_email_format("alex@company.com")[0] is True
    assert auth.validate_email_format("john.doe+hr@sub.domain.org")[0] is True

    # Invalid emails
    assert auth.validate_email_format("invalid-email")[0] is False
    assert auth.validate_email_format("@missing-user.com")[0] is False
    assert auth.validate_email_format("user@.com")[0] is False


def test_jwt_generation_and_decoding():
    """Verify JWT access token encoding, payload decoding, and validity."""
    payload = {"user_id": 42, "role": "hr", "name": "Alice"}
    token = auth.create_access_token(payload)

    decoded = auth.decode_access_token(token)
    assert decoded["user_id"] == 42
    assert decoded["role"] == "hr"
    assert decoded["name"] == "Alice"
    assert "exp" in decoded


def test_user_registration_api(client):
    """Test POST /api/register creates user and returns JWT token."""
    payload = {
        "name": "New Candidate",
        "email": "new.candidate@example.com",
        "password": "SecurePassword123!",
        "role": "candidate"
    }
    response = client.post("/api/register", data=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["role"] == "candidate"
    assert data["name"] == "New Candidate"


def test_user_registration_weak_password_fails(client):
    """Test POST /api/register with weak password returns 400."""
    payload = {
        "name": "Weak User",
        "email": "weak.user@example.com",
        "password": "123",
        "role": "candidate"
    }
    response = client.post("/api/register", data=payload)
    assert response.status_code == 400


def test_user_login_api(client, hr_user):
    """Test POST /api/login authenticates user and returns JWT token."""
    login_data = {
        "email": "hr.test@company.com",
        "password": "password123"
    }
    response = client.post("/api/login", data=login_data)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["role"] == "hr"


def test_login_invalid_credentials(client, hr_user):
    """Test POST /api/login with invalid password returns 401."""
    login_data = {
        "email": "hr.test@company.com",
        "password": "WrongPassword999"
    }
    response = client.post("/api/login", data=login_data)
    assert response.status_code == 401


def test_get_me_profile_authenticated(client, hr_user):
    """Test GET /api/me with valid Bearer token returns profile."""
    response = client.get("/api/me", headers=hr_user["headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "hr.test@company.com"
    assert data["role"] == "hr"


def test_get_me_unauthenticated(client):
    """Test GET /api/me without token returns 401."""
    response = client.get("/api/me")
    assert response.status_code == 401
