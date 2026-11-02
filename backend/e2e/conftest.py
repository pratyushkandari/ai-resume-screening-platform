"""Fixtures for the end-to-end suite: a running stack, test accounts and the graded dataset.

The suite talks to the stack over HTTP only, the way the browser does (through Nginx by
default). Start the stack first (``docker compose up -d --build``) and point the tests at it:

    E2E_BASE_URL=http://localhost E2E_HR_SIGNUP_CODE=<HR_SIGNUP_CODE of the stack> pytest e2e

Every run creates its own accounts and jobs (unique emails), so the suite can run again
against the same database. It expects the stack's default rate limits.
"""

import csv
import io
import json
import os
import time
import uuid
from pathlib import Path

import httpx2
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost").rstrip("/")
HR_SIGNUP_CODE = os.environ.get("E2E_HR_SIGNUP_CODE", "")
PASSWORD = "E2e!Passw0rd-2026"
EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"


class Api:
    """HTTP client for the stack that waits out 429 responses unless told not to."""

    def __init__(self, base_url: str) -> None:
        self.http = httpx2.Client(base_url=base_url, timeout=600)

    def call(self, method: str, url: str, retry_429: bool = True, **kwargs) -> httpx2.Response:
        """Send one request; on 429, sleep for ``Retry-After`` and try again."""
        while True:
            response = self.http.request(method, url, **kwargs)
            if response.status_code != 429 or not retry_429:
                return response
            time.sleep(int(response.headers.get("retry-after", "5")) + 1)

    def register(self, name: str, email: str, role: str = "candidate") -> dict:
        """Create an account through the API and return its id and auth headers."""
        body = {"name": name, "email": email, "password": PASSWORD, "role": role}
        if role == "hr":
            body["access_code"] = HR_SIGNUP_CODE
        response = self.call("POST", "/api/register", json=body)
        assert response.status_code == 201, response.text
        data = response.json()
        return {"id": data["user_id"], "email": email, "headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.fixture(scope="session")
def api():
    """A client for a stack that is up and ready (fails fast with instructions otherwise)."""
    client = Api(BASE_URL)
    try:
        ready = client.http.get("/readyz", timeout=10)
    except httpx2.HTTPError as exc:
        pytest.exit(f"No stack at {BASE_URL} ({exc}). Start it with `docker compose up -d --build` "
                    "and set E2E_BASE_URL.", returncode=1)
    if ready.status_code != 200:
        pytest.exit(f"{BASE_URL}/readyz returned {ready.status_code}: {ready.text}", returncode=1)
    if not HR_SIGNUP_CODE:
        pytest.exit("Set E2E_HR_SIGNUP_CODE to the stack's HR_SIGNUP_CODE.", returncode=1)
    yield client
    client.http.close()


@pytest.fixture(scope="session")
def run_id() -> str:
    """A short random tag that keeps this run's accounts apart from earlier runs."""
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def recruiter(api, run_id) -> dict:
    """The recruiter who owns the evaluation jobs."""
    return api.register("Recruiter Alpha", f"alpha.{run_id}@example.com", "hr")


@pytest.fixture(scope="session")
def other_recruiter(api, run_id) -> dict:
    """A second recruiter, who must not see the first one's jobs."""
    return api.register("Recruiter Beta", f"beta.{run_id}@example.com", "hr")


@pytest.fixture(scope="session")
def candidate(api, run_id) -> dict:
    """A candidate account."""
    return api.register("Casey Candidate", f"casey.{run_id}@example.com")


@pytest.fixture(scope="session")
def dataset() -> dict:
    """The graded evaluation set: 5 jobs, 50 resumes and a 0-3 grade per (job, resume)."""
    jobs = json.loads((EVALUATION / "jobs.json").read_text(encoding="utf-8"))
    resumes = {p.stem: p.read_text(encoding="utf-8") for p in sorted((EVALUATION / "resumes").glob("*.txt"))}
    with open(EVALUATION / "labels.csv", newline="", encoding="utf-8") as fh:
        labels = {(row["job_id"], row["resume_id"]): int(row["grade"]) for row in csv.DictReader(fh)}
    return {"jobs": jobs, "resumes": resumes, "labels": labels}


def text_pdf(text: str) -> bytes:
    """A one-page PDF with one text line per input line (text that pypdf can extract)."""

    def escape(line: str) -> str:
        """Escape PDF string delimiters and keep the text in Latin-1."""
        line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return line.encode("latin-1", "replace").decode("latin-1")

    lines = " T* ".join(f"({escape(line)}) Tj" for line in text.splitlines())
    stream = f"BT /F1 9 Tf 11 TL 40 800 Td {lines} ET".encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def docx_bytes(text: str) -> bytes:
    """A .docx file with one paragraph per input line."""
    import docx

    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def resume_file(resume_id: str, text: str) -> tuple:
    """The upload tuple for a resume: TXT for r01-r20, PDF for r21-r35, DOCX for r36-r50."""
    number = int(resume_id[1:])
    if number <= 20:
        return f"{resume_id}.txt", text.encode("utf-8"), "text/plain"
    if number <= 35:
        return f"{resume_id}.pdf", text_pdf(text), "application/pdf"
    return f"{resume_id}.docx", docx_bytes(text), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(scope="session")
def evaluation_jobs(api, recruiter, dataset) -> dict:
    """The 5 evaluation jobs, each with all 50 resumes uploaded in two batches by the recruiter.

    Returns the job ids, the files sent (to compare downloads) and every batch response.
    """
    files = {rid: resume_file(rid, text) for rid, text in dataset["resumes"].items()}
    job_ids, batches = {}, []
    for job in dataset["jobs"]:
        created = api.call("POST", "/api/jobs", headers=recruiter["headers"],
                           data={"title": job["title"], "description": job["description"], "skills": ",".join(job["skills"])})
        assert created.status_code == 201, created.text
        job_ids[job["id"]] = created.json()["job_id"]
        ids = sorted(files)
        for chunk in (ids[:25], ids[25:]):  # MAX_BATCH_FILES is 25
            response = api.call("POST", "/api/resumes/batch-upload", headers=recruiter["headers"],
                                data={"job_id": str(job_ids[job["id"]])}, files=[("files", files[rid]) for rid in chunk])
            assert response.status_code == 200, response.text
            batches.append(response.json())
    return {"ids": job_ids, "files": files, "batches": batches}


@pytest.fixture(scope="session")
def summaries(api, recruiter, evaluation_jobs) -> dict:
    """The dashboard summary of every evaluation job, keyed by dataset job id."""
    out = {}
    for job_id, api_id in evaluation_jobs["ids"].items():
        response = api.call("GET", f"/api/jobs/{api_id}/summary", headers=recruiter["headers"])
        assert response.status_code == 200, response.text
        out[job_id] = response.json()
    return out
