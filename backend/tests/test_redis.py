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


class BrokenRedis:
    """A Redis client whose server drops every command."""

    def set(self, *_args, **_kwargs):
        """Fail like a dropped connection."""
        raise ConnectionError("redis went away")

    delete = set

    def pipeline(self):
        """Return a pipeline that fails on execute."""
        broken = self

        class Pipeline:
            """Queues commands and fails when they are sent."""

            def incr(self, _key):
                """Queue INCR."""

            def expire(self, _key, _seconds):
                """Queue EXPIRE."""

            def execute(self):
                """Fail like a dropped connection."""
                return broken.set()

        return Pipeline()


@pytest.fixture
def broken_redis(monkeypatch):
    """A shared Redis connection whose client fails on every command."""
    connection = cache.RedisConnection("redis://fake")
    connection._client = BrokenRedis()
    monkeypatch.setattr(cache, "redis_connection", connection)
    monkeypatch.setattr("app.rate_limit.redis_connection", connection)
    return connection


def test_failed_cache_writes_and_deletes_mark_redis_down(broken_redis):
    assert cache.CacheService.set("job:summary:1", {"a": 1}, 60) is False
    assert broken_redis._client is None  # stop calling Redis until the retry window passes
    broken_redis._client, broken_redis._down_until = BrokenRedis(), 0.0  # the retry window has passed
    assert cache.CacheService.delete("job:summary:1") == 0
    assert broken_redis._client is None


def test_rate_limit_falls_back_to_process_counters_when_redis_fails(client, broken_redis):
    codes = [client.post("/api/login", json={"email": "x@example.com", "password": PASSWORD}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429  # the limit still holds without Redis


def test_redis_connection_is_opened_lazily_and_reused(monkeypatch):
    import redis

    server = fakeredis.FakeServer()
    opened = []

    def from_url(url, **kwargs):
        """Open a fake Redis instead of connecting over the network."""
        opened.append(url)
        return fakeredis.FakeRedis(server=server, **kwargs)

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(from_url))
    connection = cache.RedisConnection("redis://cache:6379/0")
    assert opened == []  # nothing happens until the first use
    first = connection.client()
    assert first is not None and connection.client() is first and opened == ["redis://cache:6379/0"]


def test_in_process_counters_forget_old_windows():
    from app import rate_limit

    assert rate_limit._hit("login", "10.0.0.1", window=1) == 1
    assert rate_limit._hit("login", "10.0.0.1", window=1) == 2
    assert rate_limit._hit("login", "10.0.0.1", window=2) == 1  # a new minute starts from zero
    assert ("login", "10.0.0.1", 1) not in rate_limit._memory  # and the old counter is dropped
