"""Shared fixtures.

The environment is configured *before* the app is imported: an in-memory SQLite
database (or ``TEST_DATABASE_URL``, e.g. a PostgreSQL service in CI), a
temporary upload folder, no embedding model and an unreachable Redis, so the
suite is fast, offline and never touches real data.
"""

import io
import os
import secrets
import tempfile
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or "sqlite:///:memory:"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="resume-test-uploads-")
os.environ["HR_SIGNUP_CODE"] = "test-hr-code"
os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["EMBEDDING_MODEL"] = "none"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
os.environ["REQUIRE_EMBEDDING_MODEL"] = "false"

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth, models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.ml_utils import EMBEDDING_DIM, embedding_model  # noqa: E402
from app.rate_limit import reset_memory_counters  # noqa: E402

auth.BCRYPT_ROUNDS = 4  # fast hashing in tests; production uses 12
SAMPLE_RESUMES = Path(__file__).resolve().parents[2] / "sample_test_resumes"
PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Create all tables once for the whole test session and drop them at the end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_state():
    """Give every test an empty database, fresh rate-limit counters and no model."""
    reset_memory_counters()
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    reset_memory_counters()
    embedding_model._model = None


@pytest.fixture
def client():
    """An HTTP client that calls the FastAPI app in-process (runs start-up and shutdown hooks)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    """A database session for tests that inspect or prepare rows directly."""
    with SessionLocal() as session:
        yield session


def make_user(role: str, email: str, name: str = "Test User") -> dict:
    """Create a user directly in the database and return its id, email and auth headers."""
    with SessionLocal() as session:
        user = models.User(name=name, email=email, password=auth.hash_password(PASSWORD), role=role)
        session.add(user)
        session.commit()
        token = auth.create_access_token(user)
        return {"id": user.user_id, "email": email, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def hr():
    """A recruiter who owns the jobs created in a test."""
    return make_user("hr", "hr.owner@acme.com", "Owner Recruiter")


@pytest.fixture
def other_hr():
    """A second recruiter, used to prove recruiters cannot see each other's jobs."""
    return make_user("hr", "hr.other@acme.com", "Other Recruiter")


@pytest.fixture
def candidate():
    """A candidate account."""
    return make_user("candidate", "cand@example.com", "Casey Candidate")


def create_job(client, headers, title="Backend Engineer", skills="python, docker, sql, fastapi",
               description="Build and operate Python APIs with Docker and SQL databases."):
    """Create a job through the API as the given user and return its JSON."""
    response = client.post("/api/jobs", data={"title": title, "description": description, "skills": skills}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def upload_text(client, headers, job_id, text, filename="resume.txt"):
    """Upload ``text`` as a .txt resume to ``job_id`` through the API and return the response."""
    return client.post(
        "/api/resumes/upload",
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")},
        data={"job_id": str(job_id)},
        headers=headers,
    )


class FakeModel:
    """Deterministic stand-in for SentenceTransformer: bag-of-words hashed into 384 dims."""

    def encode(self, texts, **_):
        """Hash each word into one of 384 buckets and L2-normalise, like a tiny bag-of-words model."""
        out = []
        for text in texts:
            vec = np.zeros(EMBEDDING_DIM)
            for word in text.lower().split():
                vec[sum(map(ord, word)) % EMBEDDING_DIM] += 1.0
            norm = np.linalg.norm(vec)
            out.append(vec / norm if norm else vec)
        return np.array(out)


@pytest.fixture
def fake_model():
    """Install ``FakeModel`` as the loaded embedding model for one test."""
    embedding_model._model = FakeModel()
    yield embedding_model._model
    embedding_model._model = None
