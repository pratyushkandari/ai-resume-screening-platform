"""Jobs over HTTP: validation errors, pasted skill lists, who may create jobs and who sees them."""

import pytest

DESCRIPTION = "A long enough description for the job posting."


@pytest.mark.parametrize(
    "title, description, skills, message",
    [
        ("QA", DESCRIPTION, "python", "Job title must be between 3 and 120 characters."),
        ("Valid title", "too short", "python", "Job description must be between 20 and 10,000 characters."),
        ("Valid title", DESCRIPTION, " , , ", "Specify at least one required skill"),
        ("Valid title", DESCRIPTION, ",".join(f"skill{i}" for i in range(31)), "Specify at most 30 required skills."),
    ],
)
def test_invalid_jobs_are_rejected_with_a_message(api, recruiter, title, description, skills, message):
    r = api.call("POST", "/api/jobs", headers=recruiter["headers"], data={"title": title, "description": description, "skills": skills})
    assert r.status_code == 400 and message in r.json()["detail"]


def test_pasted_comma_separated_skills_become_separate_skills(api, recruiter):
    r = api.call("POST", "/api/jobs", headers=recruiter["headers"],
                 data={"title": "Pasted skills check", "description": DESCRIPTION, "skills": "Python, Docker, SQL"})
    assert r.status_code == 201 and r.json()["skills"] == ["python", "docker", "sql"]


def test_only_signed_in_recruiters_can_create_jobs(api, recruiter, candidate):
    body = {"title": "Backend Engineer", "description": DESCRIPTION, "skills": "python"}
    assert api.call("POST", "/api/jobs", data=body).status_code == 401
    assert api.call("POST", "/api/jobs", data=body, headers=candidate["headers"]).status_code == 403
    tampered = {"Authorization": recruiter["headers"]["Authorization"] + "x"}
    assert api.call("POST", "/api/jobs", data=body, headers=tampered).status_code == 401


def test_public_list_and_my_jobs(api, recruiter, other_recruiter, evaluation_jobs):
    ours = set(evaluation_jobs["ids"].values())
    public = {job["job_id"] for job in api.call("GET", "/api/jobs", params={"limit": 100}).json()}
    assert ours <= public  # newest first, so this run's jobs are on the first page
    mine = {job["job_id"] for job in api.call("GET", "/api/jobs/mine", headers=recruiter["headers"]).json()}
    assert ours <= mine
    theirs = {job["job_id"] for job in api.call("GET", "/api/jobs/mine", headers=other_recruiter["headers"]).json()}
    assert not ours & theirs
