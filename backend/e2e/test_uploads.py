"""Uploads over HTTP: repeat uploads by one candidate, rejected files and unusual file names."""

import io

import pytest

from e2e.conftest import text_pdf

BODY = b"Casey Candidate\ncasey@example.com\nPython developer with SQL and Docker experience in production."


@pytest.fixture(scope="module")
def upload_job(api, recruiter, dataset) -> int:
    """A copy of the backend evaluation job, so these uploads do not change the evaluation jobs."""
    job = next(j for j in dataset["jobs"] if j["id"] == "backend")
    r = api.call("POST", "/api/jobs", headers=recruiter["headers"],
                 data={"title": job["title"], "description": job["description"], "skills": ",".join(job["skills"])})
    assert r.status_code == 201, r.text
    return r.json()["job_id"]


def upload(api, user, job_id, name, data, content_type="text/plain"):
    """Upload one file as ``user`` and return the response."""
    return api.call("POST", "/api/resumes/upload", headers=user["headers"], data={"job_id": str(job_id)},
                    files={"file": (name, data, content_type)})


def test_a_candidate_who_uploads_twice_appears_once_with_the_better_version(api, recruiter, candidate, upload_job, dataset):
    weak = upload(api, candidate, upload_job, "casey_v1.txt", b"Casey Candidate\nJunior developer who knows some Python and SQL from university projects.")
    strong = upload(api, candidate, upload_job, "casey_v2.txt", dataset["resumes"]["r01"].replace("Arjun Mehta", "Casey Candidate").encode())
    assert weak.status_code == strong.status_code == 201
    assert weak.json()["candidate_id"] == strong.json()["candidate_id"]
    summary = api.call("GET", f"/api/jobs/{upload_job}/summary", headers=recruiter["headers"]).json()
    mine = [c for c in summary["candidates"] if c["candidate_id"] == weak.json()["candidate_id"]]
    assert len(mine) == 1 and mine[0]["resume_id"] == strong.json()["resume_id"]


BAD_FILES = [
    ("virus.exe", b"MZ\x90\x00binary", "application/octet-stream", 400, "Unsupported file type '.exe'"),
    ("empty.txt", b"", "text/plain", 400, "Uploaded file is empty."),
    ("huge.txt", b"A" * (16 * 1024 * 1024), "text/plain", 413, "File exceeds the 15 MB limit."),
    ("corrupt.pdf", b"%PDF-1.4 this is not really a pdf", "application/pdf", 422, "could not be read"),
    ("corrupt.docx", b"PK\x03\x04 not really a zip archive", "application/octet-stream", 422, "could not be opened"),
    ("fake.pdf", b"plain text pretending to be a pdf", "application/pdf", 400, "not a valid PDF"),
    ("image_only.pdf", text_pdf(""), "application/pdf", 422, "No readable text found"),
]


# Named by file: pytest puts the test id in an environment variable, and 16 MB does not fit.
@pytest.mark.parametrize("name, data, content_type, status, message", BAD_FILES, ids=[f[0] for f in BAD_FILES])
def test_bad_files_are_rejected_with_a_message(api, candidate, upload_job, name, data, content_type, status, message):
    r = upload(api, candidate, upload_job, name, data, content_type)
    assert r.status_code == status and message in r.json()["detail"], r.text


def test_password_protected_pdf_is_rejected_with_a_message(api, candidate, upload_job, dataset):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(text_pdf(dataset["resumes"]["r01"]))))
    writer.encrypt(user_password="secret", owner_password="owner", algorithm="AES-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    r = upload(api, candidate, upload_job, "locked.pdf", buffer.getvalue(), "application/pdf")
    assert r.status_code == 422 and r.json()["detail"] == "Password-protected PDFs are not supported."


@pytest.mark.parametrize("name", ["Résumé – José Müller.txt", 'cv: "final" <v2>?.txt'])
def test_unusual_file_names_are_accepted_and_downloadable(api, recruiter, candidate, upload_job, name):
    r = upload(api, candidate, upload_job, name, BODY)
    assert r.status_code == 201, r.text
    download = api.call("GET", f"/api/resumes/{r.json()['resume_id']}/download", headers=recruiter["headers"])
    assert download.status_code == 200 and download.content == BODY


def test_batch_upload_reports_each_file_and_enforces_the_file_limit(api, recruiter, upload_job):
    files = [("files", ("a.txt", b"Alex Smith\nalex@example.com\nPython and SQL developer with Docker.", "text/plain")),
             ("files", ("bad.exe", b"MZ", "application/octet-stream"))]
    r = api.call("POST", "/api/resumes/batch-upload", headers=recruiter["headers"], data={"job_id": str(upload_job)}, files=files)
    assert r.status_code == 200 and [x["status"] for x in r.json()["results"]] == ["processed", "failed"]
    too_many = [("files", (f"{i}.txt", BODY, "text/plain")) for i in range(26)]  # MAX_BATCH_FILES is 25
    r = api.call("POST", "/api/resumes/batch-upload", headers=recruiter["headers"], data={"job_id": str(upload_job)}, files=too_many)
    assert r.status_code == 400
