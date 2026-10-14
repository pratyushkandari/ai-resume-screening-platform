# backend/tests/test_observability.py

from app import ml_utils


def test_health_check(client):
    """Test GET /healthz liveness probe returns 200 OK."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "resume-screener"


def test_readiness_check(client):
    """Test GET /readyz readiness probe returns 200 OK with db and model status."""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "connected" in data["database"]
    assert data["ml_model"] in ["active", "fallback_mode"]


def test_prometheus_metrics(client):
    """Test GET /metrics returns standard Prometheus RED metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "app_uptime_seconds" in response.text
