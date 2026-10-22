"""Authentication: input validation, bcrypt, JWT handling, registration/login rules and rate limits."""

from dataclasses import replace
from pathlib import Path
from datetime import timedelta

import pytest

from app import auth, models
from app.routers import auth as auth_router
from tests.conftest import PASSWORD, make_user


# ----------------------------------------------------------------------------- unit
def test_password_hash_roundtrip_and_malformed_hash():
    hashed = auth.hash_password(PASSWORD)
    assert hashed != PASSWORD and hashed.startswith("$2")
    assert auth.verify_password(PASSWORD, hashed)
    assert not auth.verify_password("Wr0ng!Password", hashed)
    assert not auth.verify_password(PASSWORD, PASSWORD)  # a plaintext "hash" never matches
    assert not auth.verify_password("", hashed)


def test_production_cost_factor_is_12():
    # conftest lowers the cost for speed; the shipped default must stay 12.
    assert "BCRYPT_ROUNDS = 12" in Path(auth.__file__).read_text()


@pytest.mark.parametrize(
    "password, ok",
    [
        ("Short1!", False),
        ("password123!", False),   # no uppercase
        ("PasswordOnly!", False),  # no digit
        ("Password123", False),    # no special character
        ("password123", False),    # common password
        ("A1!" + "a" * 70, False),  # over bcrypt's 72-byte limit
        (PASSWORD, True),
    ],
)
def test_password_strength(password, ok):
    assert auth.validate_password_strength(password)[0] is ok


@pytest.mark.parametrize(
    "email, ok",
    [("alex@company.com", True), ("John.Doe+hr@sub.domain.org", True), ("invalid-email", False),
     ("@missing-user.com", False), ("user@.com", False), ("user@domain", False)],
)
def test_email_validation(email, ok):
    assert auth.validate_email_format(email)[0] is ok


def test_token_roundtrip_expiry_and_tampering(db):
    user = models.User(user_id=42, name="Alice", email="a@b.co", password="x", role="hr")
    payload = auth.decode_access_token(auth.create_access_token(user))
    assert payload["sub"] == "42" and payload["role"] == "hr" and "exp" in payload
    expired = auth.create_access_token(user, expires_delta=timedelta(seconds=-5))
    with pytest.raises(Exception) as exc:
        auth.decode_access_token(expired)
    assert exc.value.status_code == 401
    with pytest.raises(Exception) as exc:
        auth.decode_access_token(auth.create_access_token(user) + "x")
    assert exc.value.status_code == 401


# ----------------------------------------------------------------------------- API
def test_register_candidate_json_returns_token(client):
    r = client.post("/api/register", json={"name": "New Candidate", "email": "New@Example.com", "password": PASSWORD})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "candidate" and body["access_token"]
    me = client.get("/api/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["email"] == "new@example.com"


def test_register_form_data_and_duplicate_email(client):
    data = {"name": "Form User", "email": "form@example.com", "password": PASSWORD}
    assert client.post("/api/register", data=data).status_code == 201
    assert client.post("/api/register", data={**data, "email": "FORM@example.com"}).status_code == 409


@pytest.mark.parametrize("payload, code", [
    ({"name": "Weak", "email": "weak@example.com", "password": "123"}, 400),
    ({"name": "X", "email": "x@example.com", "password": PASSWORD}, 400),
    ({"name": "Bad Mail", "email": "nope", "password": PASSWORD}, 400),
    ({"name": "Bad Role", "email": "role@example.com", "password": PASSWORD, "role": "admin"}, 400),
])
def test_register_validation(client, payload, code):
    assert client.post("/api/register", json=payload).status_code == code


def test_hr_registration_requires_access_code(client):
    base = {"name": "Mallory", "email": "mallory@evil.com", "password": PASSWORD, "role": "hr"}
    assert client.post("/api/register", json=base).status_code == 403
    assert client.post("/api/register", json={**base, "access_code": "guess"}).status_code == 403
    ok = client.post("/api/register", json={**base, "access_code": "test-hr-code"})
    assert ok.status_code == 201 and ok.json()["role"] == "hr"


def test_hr_registration_disabled_without_configured_code(client, monkeypatch):
    monkeypatch.setattr(auth_router, "settings", replace(auth_router.settings, hr_signup_code=""))
    r = client.post("/api/register", json={"name": "Jane HR", "email": "jane@acme.com", "password": PASSWORD,
                                           "role": "hr", "access_code": ""})
    assert r.status_code == 403


def test_login_success_and_uniform_failures(client):
    make_user("hr", "login@acme.com")
    ok = client.post("/api/login", json={"email": "LOGIN@acme.com", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["role"] == "hr" and ok.json()["expires_in"] > 0
    wrong = client.post("/api/login", json={"email": "login@acme.com", "password": "Wr0ng!Pass"})
    unknown = client.post("/api/login", data={"email": "ghost@acme.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_stored_hash_cannot_be_used_as_password(client, db):
    make_user("hr", "victim@acme.com")
    stored_hash = db.query(models.User).filter_by(email="victim@acme.com").one().password
    assert client.post("/api/login", json={"email": "victim@acme.com", "password": stored_hash}).status_code == 401
    assert client.post("/api/login", json={"email": "victim@acme.com", "password": PASSWORD}).status_code == 200


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(auth_router, "settings", replace(auth_router.settings, login_rate_limit_per_minute=3))
    codes = [client.post("/api/login", json={"email": "x@acme.com", "password": "Wr0ng!Pass"}).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]


def test_me_requires_valid_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_token_for_deleted_user_is_rejected(client, db):
    user = make_user("candidate", "gone@example.com")
    db.query(models.User).filter_by(user_id=user["id"]).delete()
    db.commit()
    assert client.get("/api/me", headers=user["headers"]).status_code == 401


def test_unknown_email_still_runs_a_password_check(client, monkeypatch):
    """Failed logins cost one bcrypt check whether or not the account exists."""
    checked = []
    real_verify = auth_router.verify_password
    monkeypatch.setattr(auth_router, "verify_password", lambda pw, hashed: checked.append(hashed) or real_verify(pw, hashed))
    r = client.post("/api/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid email or password."
    assert checked == [auth.dummy_password_hash()]
