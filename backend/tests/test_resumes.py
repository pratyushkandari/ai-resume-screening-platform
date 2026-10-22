"""Resume uploads and downloads: validation, applicant identity, batch behaviour, clean-up and access control."""

import io
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.main import app
from app.services import ingestion
from tests.conftest import SAMPLE_RESUMES, create_job, upload_text

RESUME = "Alice Kumar\nalice@example.com\n+91 98765 43210\nPython and FastAPI developer. Built Docker images and SQL reports."


def test_upload_requires_login_and_existing_job(client, hr, candidate):
    job = create_job(client, hr["headers"])
    assert upload_text(client, {}, job["job_id"], RESUME).status_code == 401
    assert upload_text(client, candidate["headers"], 9999, RESUME).status_code == 404
    missing_job = client.post("/api/resumes/upload", files={"file": ("r.txt", io.BytesIO(b"x" * 40), "text/plain")},
                              headers=candidate["headers"])
    assert missing_job.status_code == 422


def test_upload_parses_contacts_and_skills(client, hr, candidate, db):
    job = create_job(client, hr["headers"])
    r = upload_text(client, candidate["headers"], job["job_id"], RESUME)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["parsed"]["name"] == "Alice Kumar"
    assert body["parsed"]["email"] == "alice@example.com"
    assert body["parsed"]["phone"] == "+91 98765 43210"
    assert body["parsed"]["skills"] == ["docker", "fastapi", "python", "sql"]
    resume = db.get(models.Resume, body["resume_id"])
    assert resume.job_id == job["job_id"] and resume.embedding is None  # no model in tests -> NULL, not random
    stored = settings.upload_dir / resume.upload_path
    assert stored.is_file() and stored.parent == settings.upload_dir


def test_same_email_reuses_candidate(client, hr, candidate):
    job = create_job(client, hr["headers"])
    first = upload_text(client, candidate["headers"], job["job_id"], RESUME).json()
    second = upload_text(client, candidate["headers"], job["job_id"], RESUME.replace("Python", "Python, Redis")).json()
    assert first["candidate_id"] == second["candidate_id"] and first["resume_id"] != second["resume_id"]


def test_candidate_email_fallback_only_for_own_upload(client, hr, candidate):
    job = create_job(client, hr["headers"])
    no_email = "Jordan Lee\nBackend developer with Python and SQL experience across many projects."
    mine = upload_text(client, candidate["headers"], job["job_id"], no_email).json()
    assert mine["parsed"]["email"] is None and mine["candidate_name"] == "Jordan Lee"
    by_hr = upload_text(client, hr["headers"], job["job_id"], no_email).json()
    assert by_hr["candidate_id"] != mine["candidate_id"]  # HR's own email is never attached to applicants


def test_candidate_cannot_attach_resumes_to_another_applicant(client, hr, candidate, db):
    job = create_job(client, hr["headers"])
    victim = upload_text(client, hr["headers"], job["job_id"], "Vera Victim\nvera@x.com\nPython engineer.").json()
    forged = "Mallory Fake\nvera@x.com\nPython, Docker, SQL and FastAPI expert."
    attacker = upload_text(client, candidate["headers"], job["job_id"], forged).json()
    assert attacker["candidate_id"] != victim["candidate_id"]
    assert db.get(models.Candidate, victim["candidate_id"]).full_name == "Vera Victim"  # not renamed
    assert db.get(models.Candidate, attacker["candidate_id"]).email == candidate["email"]


@pytest.mark.parametrize(
    "filename, content, code",
    [
        ("malware.exe", b"MZ binary payload", 400),
        ("legacy.doc", b"\xd0\xcf\x11\xe0 old word", 400),
        ("empty.txt", b"", 400),
        ("fake.pdf", b"this is not a pdf at all", 400),
        ("fake.docx", b"plain text pretending", 400),
        ("binary.txt", b"abc\x00def" * 10, 400),
        ("short.txt", b"Hi", 422),
    ],
)
def test_upload_rejections(client, hr, candidate, filename, content, code):
    job = create_job(client, hr["headers"])
    r = client.post("/api/resumes/upload", files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
                    data={"job_id": str(job["job_id"])}, headers=candidate["headers"])
    assert r.status_code == code, r.text
    assert list(settings.upload_dir.glob(f"*_{filename}")) == []  # nothing left on disk


def test_upload_size_limit(client, hr, candidate, monkeypatch):
    job = create_job(client, hr["headers"])
    monkeypatch.setattr(ingestion, "settings", replace(settings, max_upload_bytes=1024))
    r = upload_text(client, candidate["headers"], job["job_id"], "A" * 5000, filename="big.txt")
    assert r.status_code == 413


def test_path_traversal_filename_is_neutralized(client, hr, candidate):
    job = create_job(client, hr["headers"])
    r = upload_text(client, candidate["headers"], job["job_id"], RESUME, filename="../../etc/evil.txt")
    assert r.status_code == 201
    assert list(settings.upload_dir.glob("*_evil.txt"))


def test_docx_sample_resume(client, hr, candidate):
    job = create_job(client, hr["headers"], skills="python, fastapi, docker, kubernetes, aws")
    sample = SAMPLE_RESUMES / "1_Aarav_Sharma_FullStack_AI_Lead.docx"
    with sample.open("rb") as fh:
        r = client.post("/api/resumes/upload", files={"file": (sample.name, fh, "application/octet-stream")},
                        data={"job_id": str(job["job_id"])}, headers=candidate["headers"])
    assert r.status_code == 201, r.text
    parsed = r.json()["parsed"]
    assert parsed["name"] == "Aarav Sharma" and parsed["email"] == "aarav.sharma@example.com"
    assert {"python", "fastapi", "docker", "kubernetes"} <= set(parsed["skills"])


def test_batch_upload_reports_each_file(client, hr, candidate):
    job = create_job(client, hr["headers"])
    files = [
        ("files", ("a.txt", io.BytesIO(b"Alex Smith\nalex@test.com\nPython and SQL expert with 5 years experience."), "text/plain")),
        ("files", ("bad.exe", io.BytesIO(b"MZ"), "application/octet-stream")),
        ("files", ("b.txt", io.BytesIO(b"Beth Jones\nbeth@test.com\nDocker and Python developer, 4 years experience."), "text/plain")),
    ]
    r = client.post("/api/resumes/batch-upload", files=files, data={"job_id": str(job["job_id"])}, headers=hr["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["total_files"], body["successful"], body["failed"]) == (3, 2, 1)
    assert [x["filename"] for x in body["results"]] == ["a.txt", "bad.exe", "b.txt"]
    assert [x["status"] for x in body["results"]] == ["processed", "failed", "processed"]


def test_batch_upload_limit(client, hr, monkeypatch):
    from app.routers import resumes as resumes_router

    job = create_job(client, hr["headers"])
    monkeypatch.setattr(resumes_router, "settings", replace(settings, max_batch_files=2))
    files = [("files", (f"{i}.txt", io.BytesIO(b"x" * 50), "text/plain")) for i in range(3)]
    r = client.post("/api/resumes/batch-upload", files=files, data={"job_id": str(job["job_id"])}, headers=hr["headers"])
    assert r.status_code == 400


def test_download_is_restricted_to_owning_recruiter(client, hr, other_hr, candidate):
    job = create_job(client, hr["headers"])
    resume_id = upload_text(client, candidate["headers"], job["job_id"], RESUME, filename="alice.txt").json()["resume_id"]
    url = f"/api/resumes/{resume_id}/download"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=candidate["headers"]).status_code == 403
    assert client.get(url, headers=other_hr["headers"]).status_code == 403
    ok = client.get(url, headers=hr["headers"])
    assert ok.status_code == 200 and ok.content.decode() == RESUME
    assert 'filename="alice.txt"' in ok.headers["content-disposition"]
    assert client.get("/api/resumes/999999/download", headers=hr["headers"]).status_code == 404


def test_legacy_absolute_upload_path_still_downloads(client, hr, candidate, db, tmp_path):
    job = create_job(client, hr["headers"])
    resume_id = upload_text(client, candidate["headers"], job["job_id"], RESUME).json()["resume_id"]
    legacy = tmp_path / "legacy_resume.txt"
    legacy.write_text("legacy content")
    db.get(models.Resume, resume_id).upload_path = str(legacy)
    db.commit()
    assert client.get(f"/api/resumes/{resume_id}/download", headers=hr["headers"]).text == "legacy content"
    assert Path(settings.upload_dir).exists()


def test_files_are_removed_when_saving_the_batch_fails(client, hr, monkeypatch):
    job = create_job(client, hr["headers"])
    before = set(settings.upload_dir.iterdir())

    def failing_commit(self):
        """Simulate the database failing at the final commit."""
        raise RuntimeError("database went away")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", failing_commit)
    with TestClient(app, raise_server_exceptions=False) as tolerant:
        r = upload_text(tolerant, hr["headers"], job["job_id"], RESUME)
    assert r.status_code == 500
    assert set(settings.upload_dir.iterdir()) == before  # no orphaned files left behind
