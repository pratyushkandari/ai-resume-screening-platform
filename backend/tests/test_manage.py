"""Administrative commands in manage.py: create-user, reset-password and seed-load-test."""

import argparse
import sys

import pytest

import manage
from app import auth, models
from app.config import settings
from tests.conftest import PASSWORD, make_user


@pytest.fixture
def typed_passwords(monkeypatch):
    """Answer the hidden password prompts with the given values, in order."""

    def answer(*values):
        """Queue ``values`` as the next answers to ``getpass``."""
        queue = list(values)
        monkeypatch.setattr(manage.getpass, "getpass", lambda _prompt: queue.pop(0))

    return answer


def run(monkeypatch, *argv):
    """Run ``manage.py`` with the given command line."""
    monkeypatch.setattr(sys, "argv", ["manage.py", *argv])
    manage.main()


def test_create_user_stores_a_hashed_password(monkeypatch, typed_passwords, db, capsys):
    typed_passwords(PASSWORD, PASSWORD)
    run(monkeypatch, "create-user", "--name", "Jane Recruiter", "--email", "Jane@Acme.com", "--role", "hr")
    user = db.query(models.User).filter_by(email="jane@acme.com").one()
    assert user.role == "hr" and user.password != PASSWORD and auth.verify_password(PASSWORD, user.password)
    assert "Created hr user jane@acme.com" in capsys.readouterr().out


@pytest.mark.parametrize(
    "name, email, passwords, message",
    [
        ("J", "jane@acme.com", (), "Name must be between 2 and 100 characters."),
        ("Jane", "not-an-email", (), "Invalid email address format"),
        ("Jane", "jane@acme.com", (PASSWORD, PASSWORD + "x"), "Passwords do not match."),
        ("Jane", "jane@acme.com", ("Bluesky2026Go", "Bluesky2026Go"), "Password must contain at least one special character"),
    ],
)
def test_create_user_rejects_bad_input(monkeypatch, typed_passwords, db, name, email, passwords, message):
    typed_passwords(*passwords)
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "create-user", "--name", name, "--email", email)
    assert message in str(exc.value)
    assert db.query(models.User).count() == 0


def test_create_user_refuses_an_existing_email(monkeypatch, typed_passwords):
    make_user("candidate", "taken@example.com")
    typed_passwords(PASSWORD, PASSWORD)
    with pytest.raises(SystemExit, match="already exists"):
        run(monkeypatch, "create-user", "--name", "Someone", "--email", "TAKEN@example.com")


def test_reset_password(monkeypatch, typed_passwords, db):
    user = make_user("hr", "reset@acme.com")
    new_password = "N3w!Passw0rd-2026"
    typed_passwords(new_password, new_password)
    run(monkeypatch, "reset-password", "--email", "reset@acme.com")
    stored = db.get(models.User, user["id"]).password
    assert auth.verify_password(new_password, stored) and not auth.verify_password(PASSWORD, stored)
    with pytest.raises(SystemExit, match="No user with this email."):
        run(monkeypatch, "reset-password", "--email", "ghost@acme.com")
    with pytest.raises(SystemExit, match="Invalid email"):
        run(monkeypatch, "reset-password", "--email", "ghost")


def test_seed_load_test_adds_generated_applicants_through_ingestion(monkeypatch, db, capsys):
    recruiter = make_user("hr", "load@acme.com")
    run(monkeypatch, "seed-load-test", "--email", "load@acme.com", "--resumes", "3")
    job = db.query(models.Job).filter_by(created_by=recruiter["id"]).one()
    resumes = db.query(models.Resume).filter_by(job_id=job.job_id).all()
    assert len(resumes) == 3 and all((settings.upload_dir / r.upload_path).is_file() for r in resumes)
    assert all(r.raw_text and r.candidate_id for r in resumes)
    assert {s.skill.skill_name for s in job.job_skills} >= {"python", "docker"}
    assert f"Job {job.job_id} now has 3 applicants" in capsys.readouterr().out


@pytest.mark.parametrize(
    "email, resumes, message",
    [
        ("load@acme.com", "0", "--resumes must be at least 1."),
        ("bad-email", "5", "Invalid email"),
        ("nobody@acme.com", "5", "No recruiter with this email."),
        ("applicant@example.com", "5", "No recruiter with this email."),
    ],
)
def test_seed_load_test_rejects_bad_arguments(monkeypatch, db, email, resumes, message):
    make_user("hr", "load@acme.com")
    make_user("candidate", "applicant@example.com")
    with pytest.raises(SystemExit) as exc:
        manage.seed_load_test(argparse.Namespace(email=email, resumes=int(resumes)))
    assert message in str(exc.value)
    assert db.query(models.Job).count() == 0
