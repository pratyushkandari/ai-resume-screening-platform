# backend/tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

# Ensure JSONB maps to JSON on SQLite
@compiles(JSONB, 'sqlite')
def compile_jsonb_sqlite(type_, compiler, **kw):
    return 'JSON'

from app.main import app
from app.db import Base
from app.auth import get_db, hash_password, create_access_token
from app import models

# In-memory SQLite for isolated unit and integration tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test tables before tests and drop after session."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db_session():
    """Yield an isolated database session per test with automatic rollback."""
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def hr_user(db_session):
    """Creates and returns a test HR user with pre-generated JWT token."""
    user = models.User(
        name="Test Recruiter",
        email="hr.test@company.com",
        password=hash_password("password123"),
        role="hr"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"user_id": user.user_id, "role": user.role, "name": user.name})
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def candidate_user(db_session):
    """Creates and returns a test Candidate user with pre-generated JWT token."""
    user = models.User(
        name="Test Candidate",
        email="candidate.test@example.com",
        password=hash_password("password123"),
        role="candidate"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"user_id": user.user_id, "role": user.role, "name": user.name})
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
