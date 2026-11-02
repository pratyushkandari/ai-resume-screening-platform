"""Rate limits on the real stack (Redis counters), at the default limits of docker-compose.yml.

The limiter counts requests per calendar minute, so each test starts at the beginning of a
fresh minute: otherwise a minute boundary in the middle of the loop would reset the count,
and earlier sign-ins in the same minute would use up part of the login limit. The login
test blocks sign-in from this machine for the rest of that minute; the browser suite waits
for that before it signs in.
"""

import time

UPLOAD_LIMIT_PER_MINUTE = 10  # UPLOAD_RATE_LIMIT_PER_MINUTE default
LOGIN_LIMIT_PER_MINUTE = 10  # LOGIN_RATE_LIMIT_PER_MINUTE default


def wait_for_a_new_minute() -> None:
    """Sleep until just after the next minute starts (the stack and the tests share a clock)."""
    time.sleep(60 - time.time() % 60 + 0.5)


def test_uploads_are_limited_per_account(api, recruiter, run_id):
    job = api.call("POST", "/api/jobs", headers=recruiter["headers"],
                   data={"title": "Rate limit check", "description": "Python developer for the upload rate limit.", "skills": "python"})
    assert job.status_code == 201, job.text
    uploader = api.register("Sam Uploader", f"sam.{run_id}@example.com")
    body = b"Sam Uploader\nsam@example.com\nPython developer with SQL and Docker."
    wait_for_a_new_minute()
    codes = [api.call("POST", "/api/resumes/upload", retry_429=False, headers=uploader["headers"],
                      data={"job_id": str(job.json()["job_id"])}, files={"file": ("cv.txt", body, "text/plain")}).status_code
             for _ in range(UPLOAD_LIMIT_PER_MINUTE + 1)]
    assert codes == [201] * UPLOAD_LIMIT_PER_MINUTE + [429]


def test_failed_logins_are_limited_per_ip(api):
    wait_for_a_new_minute()
    codes = [api.call("POST", "/api/login", retry_429=False, json={"email": "nobody.e2e@example.com", "password": "Wr0ng!Pass"}).status_code
             for _ in range(LOGIN_LIMIT_PER_MINUTE + 1)]
    assert codes == [401] * LOGIN_LIMIT_PER_MINUTE + [429]
