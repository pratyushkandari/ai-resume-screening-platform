"""Access rules over HTTP: candidates, other recruiters, anonymous callers and sign-in."""

from e2e.conftest import PASSWORD


def recruiter_only_urls(evaluation_jobs, summaries) -> list:
    """Every recruiter endpoint for the backend evaluation job and one of its resumes."""
    job = evaluation_jobs["ids"]["backend"]
    resume = summaries["backend"]["candidates"][0]["resume_id"]
    return [("GET", f"/api/jobs/{job}/summary"), ("POST", f"/api/jobs/{job}/rank"),
            ("GET", f"/api/jobs/{job}/rankings"), ("GET", f"/api/resumes/{resume}/download")]


def test_candidates_cannot_see_dashboards_or_files(api, candidate, evaluation_jobs, summaries):
    for method, url in recruiter_only_urls(evaluation_jobs, summaries):
        assert api.call(method, url, headers=candidate["headers"]).status_code == 403, url


def test_recruiters_cannot_use_each_others_jobs(api, other_recruiter, evaluation_jobs, summaries):
    for method, url in recruiter_only_urls(evaluation_jobs, summaries):
        assert api.call(method, url, headers=other_recruiter["headers"]).status_code == 403, url
    upload = api.call("POST", "/api/resumes/upload", headers=other_recruiter["headers"],
                      data={"job_id": str(evaluation_jobs["ids"]["backend"])},
                      files={"file": ("cv.txt", b"Pat Doe\npat@example.com\nPython developer with SQL.", "text/plain")})
    assert upload.status_code == 403


def test_anonymous_and_invalid_tokens_get_401(api, recruiter, evaluation_jobs, summaries):
    for method, url in recruiter_only_urls(evaluation_jobs, summaries):
        assert api.call(method, url).status_code == 401, url
        assert api.call(method, url, headers={"Authorization": "Bearer not-a-token"}).status_code == 401, url
    me = api.call("GET", "/api/me", headers=recruiter["headers"])
    assert me.status_code == 200 and me.json()["role"] == "hr"


def test_login_works_and_wrong_passwords_get_one_message(api, recruiter):
    ok = api.call("POST", "/api/login", json={"email": recruiter["email"].upper(), "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["role"] == "hr"
    wrong = api.call("POST", "/api/login", json={"email": recruiter["email"], "password": "Wr0ng!Pass"})
    unknown = api.call("POST", "/api/login", json={"email": "nobody.e2e@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json()["detail"] == unknown.json()["detail"]


def test_recruiter_sign_up_needs_the_access_code(api, run_id):
    body = {"name": "No Code", "email": f"nocode.{run_id}@example.com", "password": PASSWORD, "role": "hr", "access_code": "wrong"}
    assert api.call("POST", "/api/register", json=body).status_code == 403


def test_job_list_is_public(api):
    assert api.call("GET", "/api/jobs").status_code == 200
