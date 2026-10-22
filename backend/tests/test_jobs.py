"""Job requisitions: who may create them, input validation, skill parsing and listings."""

import pytest

from tests.conftest import create_job


def test_hr_creates_job_with_normalized_skills(client, hr):
    job = create_job(client, hr["headers"], skills="Python, Docker, docker , Machine-Learning, CI/CD")
    assert job["created_by"] == hr["id"]
    assert job["skills"] == ["python", "docker", "machine learning", "ci/cd"]


def test_created_by_cannot_be_spoofed(client, hr, other_hr):
    r = client.post(
        "/api/jobs",
        data={"title": "Spoof", "description": "x" * 30, "skills": "python", "created_by": str(other_hr["id"])},
        headers=hr["headers"],
    )
    assert r.status_code == 201 and r.json()["created_by"] == hr["id"]


@pytest.mark.parametrize("who, code", [("anonymous", 401), ("candidate", 403)])
def test_only_hr_can_create_jobs(client, candidate, hr, who, code):
    headers = {} if who == "anonymous" else candidate["headers"]
    data = {"title": "Unauthorized Job", "description": "x" * 30, "skills": "python", "created_by": str(hr["id"])}
    assert client.post("/api/jobs", data=data, headers=headers).status_code == code


@pytest.mark.parametrize(
    "data",
    [
        {"title": "AB", "description": "x" * 30, "skills": "python"},
        {"title": "Valid title", "description": "Too short", "skills": "python"},
        {"title": "Valid title", "description": "x" * 30, "skills": " , ,"},
        {"title": "Valid title", "description": "x" * 30, "skills": ",".join(f"skill{i}" for i in range(31))},
    ],
)
def test_job_validation(client, hr, data):
    assert client.post("/api/jobs", data=data, headers=hr["headers"]).status_code == 400


def test_public_listing_and_pagination(client, hr):
    for i in range(3):
        create_job(client, hr["headers"], title=f"Role {i}")
    jobs = client.get("/api/jobs").json()
    assert [j["title"] for j in jobs] == ["Role 2", "Role 1", "Role 0"]
    assert len(client.get("/api/jobs", params={"page": 2, "limit": 2}).json()) == 1
    assert client.get("/api/jobs", params={"limit": 500}).status_code == 422


def test_mine_returns_only_own_jobs(client, hr, other_hr, candidate):
    create_job(client, hr["headers"], title="Mine")
    create_job(client, other_hr["headers"], title="Theirs")
    assert [j["title"] for j in client.get("/api/jobs/mine", headers=hr["headers"]).json()] == ["Mine"]
    assert client.get("/api/jobs/mine", headers=candidate["headers"]).status_code == 403
    assert client.get("/api/jobs/mine").status_code == 401
