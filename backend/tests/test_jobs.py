# backend/tests/test_jobs.py

import pytest


def test_create_job_by_hr(client, hr_user):
    """Test HR user can successfully create a job with skills."""
    payload = {
        "title": "Staff AI Engineer",
        "description": "Building LLM infrastructure and neural search systems.",
        "skills": "python, pytorch, transformers, fastapi, docker",
        "created_by": hr_user["user"].user_id
    }
    response = client.post("/api/jobs", data=payload, headers=hr_user["headers"])
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "Staff AI Engineer"
    assert "python" in data["skills"]
    assert "pytorch" in data["skills"]


def test_create_job_short_description_fails(client, hr_user):
    """Test job creation fails if description is less than 20 characters."""
    payload = {
        "title": "Valid Job Title",
        "description": "Too short",
        "skills": "python, docker",
        "created_by": hr_user["user"].user_id
    }
    response = client.post("/api/jobs", data=payload, headers=hr_user["headers"])
    assert response.status_code == 400


def test_create_job_missing_skills_fails(client, hr_user):
    """Test job creation fails if no valid skills are provided."""
    payload = {
        "title": "Valid Job Title",
        "description": "Building high-performance distributed systems at scale.",
        "skills": "",
        "created_by": hr_user["user"].user_id
    }
    response = client.post("/api/jobs", data=payload, headers=hr_user["headers"])
    assert response.status_code == 400


def test_create_job_by_candidate_forbidden(client, candidate_user):
    """Test candidates are forbidden from creating jobs."""
    payload = {
        "title": "Unauthorized Job",
        "description": "This should fail because role is candidate.",
        "skills": "python",
        "created_by": candidate_user["user"].user_id
    }
    response = client.post("/api/jobs", data=payload, headers=candidate_user["headers"])
    assert response.status_code == 403


def test_list_jobs_for_candidate(client, hr_user, candidate_user):
    """Test candidates can list all open positions."""
    # First create a job as HR
    client.post("/api/jobs", data={
        "title": "Backend Architect",
        "description": "Distributed systems and cloud infrastructure development.",
        "skills": "python, postgresql, docker",
        "created_by": hr_user["user"].user_id
    }, headers=hr_user["headers"])

    # List jobs as candidate
    response = client.get("/api/jobs", params={"role": "candidate"})
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) >= 1
    assert any(j["title"] == "Backend Architect" for j in jobs)


def test_list_jobs_pagination(client, hr_user):
    """Test pagination limits on job queries."""
    response = client.get("/api/jobs", params={"role": "candidate", "page": 1, "limit": 2})
    assert response.status_code == 200
    assert len(response.json()) <= 2
