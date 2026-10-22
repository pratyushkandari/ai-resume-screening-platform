"""Authorization matrix and behaviour of the recruiter evaluation endpoints."""

import pytest
from sqlalchemy import event

from app.db import engine
from tests.conftest import create_job, upload_text

STRONG = "Alex Strong\nalex@x.com\nPython, Docker, SQL and FastAPI engineer building APIs."
WEAK = "Bea Weak\nbea@x.com\nGraphic designer with Figma and branding experience across agencies."
ENDPOINTS = [("get", "summary"), ("post", "rank"), ("get", "rankings")]


@pytest.fixture
def job(client, hr):
    """A job with two applicants, uploaded by the recruiter on their behalf."""
    job = create_job(client, hr["headers"])
    upload_text(client, hr["headers"], job["job_id"], STRONG)
    upload_text(client, hr["headers"], job["job_id"], WEAK)
    return job


@pytest.mark.parametrize("method, path", ENDPOINTS)
def test_authorization_matrix(client, job, hr, other_hr, candidate, method, path):
    url = f"/api/jobs/{job['job_id']}/{path}"
    call = getattr(client, method)
    assert call(url).status_code == 401
    assert call(url, params={"role": "hr", "user_id": hr["id"]}).status_code == 401  # query params grant nothing
    assert call(url, headers=candidate["headers"]).status_code == 403
    assert call(url, headers=candidate["headers"], params={"role": "hr"}).status_code == 403
    assert call(url, headers=other_hr["headers"]).status_code == 403
    assert call(url, headers=hr["headers"]).status_code == 200
    assert call("/api/jobs/9999/" + path, headers=hr["headers"]).status_code == 404


def test_summary_ranks_candidates(client, job, hr):
    r = client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"])
    body = r.json()
    assert r.headers["X-Cache"] == "MISS"  # Redis unreachable in tests
    assert [c["candidate_name"] for c in body["candidates"]] == ["Alex Strong", "Bea Weak"]
    top = body["candidates"][0]
    assert top["status"] == "accepted" and top["skill_score"] == 1.0 and top["filename"] == "resume.txt"
    assert body["candidates"][1]["status"] == "rejected"
    assert body["job_skills"] == ["python", "docker", "sql", "fastapi"]
    assert {s["skill_name"]: s["matches"] for s in body["job_skill_counts"]} == {"python": 1, "docker": 1, "sql": 1, "fastapi": 1}
    assert body["semantic_available"] is False and body["last_ranked_at"] is None


def test_summary_keeps_best_resume_per_candidate(client, hr, candidate):
    job = create_job(client, hr["headers"])
    upload_text(client, candidate["headers"], job["job_id"], "Sam Same\nsam@x.com\nPython developer with ten years of work.")
    upload_text(client, candidate["headers"], job["job_id"], "Sam Same\nsam@x.com\nPython, Docker, SQL, FastAPI developer.")
    candidates = client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"]).json()["candidates"]
    assert len(candidates) == 1 and candidates[0]["skill_score"] == 1.0


def test_top_skills_are_scoped_to_the_job(client, hr, candidate):
    job_a = create_job(client, hr["headers"], title="Job A", skills="python")
    job_b = create_job(client, hr["headers"], title="Job B", skills="kubernetes")
    upload_text(client, candidate["headers"], job_a["job_id"], "Ann A\nann@x.com\nPython engineer for data pipelines.")
    upload_text(client, candidate["headers"], job_b["job_id"], "Ben B\nben@x.com\nKubernetes operator with cluster expertise.")
    top = client.get(f"/api/jobs/{job_a['job_id']}/summary", headers=hr["headers"]).json()["top_skills"]
    assert [s["skill_name"] for s in top] == ["python"]


def test_rank_saves_snapshot_and_backfills_embeddings(client, job, hr, fake_model):
    before = client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"]).json()
    assert before["semantic_available"] is False
    ranked = client.post(f"/api/jobs/{job['job_id']}/rank", headers=hr["headers"]).json()
    assert ranked["ranked"] == 2 and ranked["ranked_at"]
    after = client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"]).json()
    assert after["semantic_available"] is True and after["last_ranked_at"]
    rows = client.get(f"/api/jobs/{job['job_id']}/rankings", headers=hr["headers"]).json()
    assert [r["candidate_name"] for r in rows] == ["Alex Strong", "Bea Weak"]
    assert rows[0]["score"] == pytest.approx(after["candidates"][0]["score"])
    # Ranking twice replaces the snapshot instead of duplicating it
    client.post(f"/api/jobs/{job['job_id']}/rank", headers=hr["headers"])
    assert len(client.get(f"/api/jobs/{job['job_id']}/rankings", headers=hr["headers"]).json()) == 2


def test_summary_uses_constant_number_of_queries(client, hr, candidate):
    job = create_job(client, hr["headers"])

    def count_summary_queries():
        """Load the summary once and return how many SQL statements it ran."""
        statements = []

        def listener(*_args, **_kwargs):
            """SQLAlchemy event hook: count one executed statement."""
            statements.append(1)

        event.listen(engine, "before_cursor_execute", listener)
        try:
            assert client.get(f"/api/jobs/{job['job_id']}/summary", headers=hr["headers"]).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return len(statements)

    for i in range(3):
        upload_text(client, candidate["headers"], job["job_id"], f"Person {i} Name\np{i}@x.com\nPython and SQL developer here.")
    few = count_summary_queries()
    for i in range(3, 15):
        upload_text(client, candidate["headers"], job["job_id"], f"Person {i} Name\np{i}@x.com\nPython and SQL developer here.")
    many = count_summary_queries()
    assert few == many <= 10
