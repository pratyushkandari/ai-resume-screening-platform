"""Operations: health/readiness probes, metrics, request IDs, error responses, CORS and configuration safety."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app import schema
from app.config import ConfigurationError, load_settings
from app.db import normalize_database_url
from app.main import app
from app.routers import ops
from tests.conftest import create_job


def test_health_check(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_readiness_reports_components(client):
    body = client.get("/readyz").json()
    assert body["status"] == "ready" and body["database"] == "connected"
    assert body["ml_model"] == "unavailable" and body["cache"] == "disabled"


def test_readiness_fails_when_model_required(client, monkeypatch):
    monkeypatch.setattr(ops, "settings", replace(ops.settings, require_embedding_model=True))
    assert client.get("/readyz").status_code == 503


def test_readiness_ok_with_model(client, fake_model, monkeypatch):
    monkeypatch.setattr(ops, "settings", replace(ops.settings, require_embedding_model=True))
    assert client.get("/readyz").json()["ml_model"] == "active"


def test_metrics_use_route_templates(client, hr):
    job = create_job(client, hr["headers"])
    client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"])
    text = client.get("/metrics").text
    assert 'path="/api/jobs/{job_id}/summary"' in text
    assert f"/api/jobs/{job['job_id']}/summary" not in text
    assert "http_request_duration_seconds_count" in text and "app_uptime_seconds" in text


def test_request_id_and_security_headers(client):
    r = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
    assert float(r.headers["X-Response-Time-MS"]) >= 0
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    bad = client.get("/healthz", headers={"X-Request-ID": "<script>"})
    assert bad.headers["X-Request-ID"] != "<script>"


def test_cors_allows_configured_origin_only(client):
    ok = client.options("/api/jobs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    evil = client.options("/api/jobs", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil.headers


def test_production_refuses_insecure_jwt_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REQUIRE_EMBEDDING_MODEL")  # production default: model required
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-super-secret-key-change-in-production-resume-matcher-2026")
    with pytest.raises(ConfigurationError):
        load_settings()
    monkeypatch.delenv("JWT_SECRET_KEY")
    with pytest.raises(ConfigurationError):
        load_settings()
    monkeypatch.setenv("JWT_SECRET_KEY", "a-private-random-value-for-this-deployment-0123456789")
    assert load_settings().require_embedding_model is True


def test_development_generates_ephemeral_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET_KEY")
    assert len(load_settings().jwt_secret_key) >= 32


@pytest.mark.parametrize(
    "url, expected",
    [
        ("postgresql://u:p@h/db", "postgresql+psycopg2://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg2://u:p@h/db"),
        ("postgresql+psycopg2://u:p@h/db", "postgresql+psycopg2://u:p@h/db"),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ],
)
def test_database_url_normalization(url, expected):
    assert normalize_database_url(url) == expected


def test_unexpected_error_is_json_with_cors_and_security_headers(client, monkeypatch):
    def boom(*_args, **_kwargs):
        """Stand-in for a route that crashes."""
        raise RuntimeError("simulated failure")

    monkeypatch.setattr("app.routers.jobs._query_jobs", boom)
    with TestClient(app, raise_server_exceptions=False) as tolerant:
        r = tolerant.get("/api/jobs", headers={"Origin": "http://localhost:5173", "X-Request-ID": "req-42"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error.", "request_id": "req-42"}  # no internals leaked
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"  # browser can read the error
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Request-ID"] == "req-42"
    assert 'path="/api/jobs",status="500"' in client.get("/metrics").text


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_invalid_numeric_settings_fail_fast(monkeypatch, value):
    monkeypatch.setenv("MAX_UPLOAD_MB", value)
    with pytest.raises(ConfigurationError, match="MAX_UPLOAD_MB"):
        load_settings()


def test_rate_limit_zero_disables_limit(monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT_PER_MINUTE", "0")
    assert load_settings().login_rate_limit_per_minute == 0


def test_readiness_retries_schema_creation(client, monkeypatch):
    """If tables could not be created at start-up, /readyz stays 503 and retries."""
    real_create_all = schema.Base.metadata.create_all
    database_up = False

    def create_all(**kwargs):
        """Fail until the simulated database comes back up."""
        if not database_up:
            raise OSError("database not reachable")
        real_create_all(**kwargs)

    monkeypatch.setattr(schema, "_ready", False)
    monkeypatch.setattr(schema.Base.metadata, "create_all", create_all)
    assert client.get("/readyz").json()["database"] == "schema not ready"
    database_up = True
    assert client.get("/readyz").status_code == 200 and schema._ready is True
