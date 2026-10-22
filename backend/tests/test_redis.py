"""Redis-backed behaviour (summary cache and shared rate-limit counters) against a fake Redis."""

import fakeredis
import pytest

from app import cache
from tests.conftest import PASSWORD, create_job, upload_text


@pytest.fixture
def redis_server(monkeypatch):
    """Point the shared Redis connection at an in-memory fake server."""
    server = fakeredis.FakeServer()
    connection = cache.RedisConnection("redis://fake")
    connection._client = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr(cache, "redis_connection", connection)
    monkeypatch.setattr("app.rate_limit.redis_connection", connection)
    monkeypatch.setattr("app.routers.ops.redis_connection", connection)
    return server


def test_summary_is_cached_and_invalidated(client, hr, redis_server):
    job = create_job(client, hr["headers"])
    url = f"/api/jobs/{job['job_id']}/summary"
    assert client.get(url, headers=hr["headers"]).headers["X-Cache"] == "MISS"
    cached = client.get(url, headers=hr["headers"])
    assert cached.headers["X-Cache"] == "HIT" and cached.json()["candidates"] == []

    upload_text(client, hr["headers"], job["job_id"], "Pat Doe\npat@x.com\nPython and SQL developer for APIs.")
    fresh = client.get(url, headers=hr["headers"])  # the upload invalidated the cached summary
    assert fresh.headers["X-Cache"] == "MISS" and len(fresh.json()["candidates"]) == 1

    client.post(f"/api/jobs/{job['job_id']}/rank", headers=hr["headers"])
    ranked = client.get(url, headers=hr["headers"])  # ranking invalidated it again
    assert ranked.headers["X-Cache"] == "MISS" and ranked.json()["last_ranked_at"]
    assert "summary_cache_hits_total" in client.get("/metrics").text


def test_readiness_reports_redis(client, redis_server):
    assert client.get("/readyz").json()["cache"] == "redis"


def test_login_rate_limit_uses_redis_counters(client, redis_server):
    for _ in range(10):
        assert client.post("/api/login", json={"email": "x@example.com", "password": PASSWORD}).status_code == 401
    blocked = client.post("/api/login", json={"email": "x@example.com", "password": PASSWORD})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    keys = fakeredis.FakeRedis(server=redis_server).keys("ratelimit:login:*")
    assert len(keys) == 1  # one shared counter, visible to every API replica


def test_redis_failure_falls_back_without_errors(client, hr, redis_server):
    redis_server.connected = False  # Redis goes down mid-operation
    job = create_job(client, hr["headers"])
    r = client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"])
    assert r.status_code == 200 and r.headers["X-Cache"] == "MISS"
    assert client.post("/api/login", json={"email": "x@example.com", "password": PASSWORD}).status_code == 401
