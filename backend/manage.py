"""Administrative commands.

Usage (from the backend folder):
    python manage.py create-user --name "Jane Recruiter" --email jane@acme.com --role hr
    python manage.py reset-password --email jane@acme.com
    python manage.py seed-load-test --email jane@acme.com --resumes 10000

Passwords are prompted for (never passed on the command line) and must meet the
same strength rules as the API.
"""

from __future__ import annotations

import argparse
import getpass
import random
import sys
import time
import uuid

from sqlalchemy import func

from app import models
from app.auth import ROLE_HR, ROLES, hash_password, validate_email_format, validate_password_strength
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.ml_utils import embed_text
from app.services.ingestion import StoredUpload, process_uploads
from app.services.skills import get_or_create_skills, load_skill_index


def _prompt_password() -> str:
    """Ask for a new password twice (hidden input) and enforce the API's strength rules."""
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    ok, message = validate_password_strength(password)
    if not ok:
        sys.exit(message)
    return password


def create_user(args: argparse.Namespace) -> None:
    """``create-user``: add a recruiter or candidate account (creates tables if needed)."""
    name = args.name.strip()
    if not 2 <= len(name) <= 100:
        sys.exit("Name must be between 2 and 100 characters.")
    ok, email = validate_email_format(args.email)
    if not ok:
        sys.exit(email)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(models.User).filter(func.lower(models.User.email) == email).first():
            sys.exit("A user with this email already exists.")
        user = models.User(name=name, email=email, password=hash_password(_prompt_password()), role=args.role)
        db.add(user)
        db.commit()
        print(f"Created {args.role} user {email} (id {user.user_id}).")


def reset_password(args: argparse.Namespace) -> None:
    """``reset-password``: set a new password, e.g. for accounts from before version 3."""
    ok, email = validate_email_format(args.email)
    if not ok:
        sys.exit(email)
    with SessionLocal() as db:
        user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
        if user is None:
            sys.exit("No user with this email.")
        user.password = hash_password(_prompt_password())
        db.commit()
        print(f"Password updated for {email}.")


LOAD_TEST_JOB = {
    "title": "Backend Engineer (load test)",
    "description": "Build and operate REST APIs in Python with FastAPI, model data in PostgreSQL, "
    "cache with Redis and ship services with Docker. You will own them in production.",
    "skills": ["python", "fastapi", "postgresql", "redis", "docker", "rest api"],
}
FIRST_NAMES = ["Aarav", "Diya", "Kabir", "Isha", "Vivaan", "Anika", "Rohan", "Meera", "Arjun", "Sara",
               "Daniel", "Emma", "Lucas", "Mia", "Noah", "Olivia", "Liam", "Zara", "Omar", "Elena"]
LAST_NAMES = ["Sharma", "Patel", "Iyer", "Khan", "Singh", "Rao", "Gupta", "Nair", "Mehta", "Das",
              "Smith", "Garcia", "Muller", "Rossi", "Kim", "Silva", "Novak", "Haddad", "Okafor", "Tanaka"]
# (job title, experience lines, skills) per kind of applicant, so the job gets a realistic mix.
PROFILES = [
    ("Backend Engineer",
     ["Built REST APIs in Python with FastAPI for payments", "Tuned PostgreSQL queries and indexes for reporting",
      "Added a Redis cache in front of slow lookups", "Packaged services with Docker and ran them on-call"],
     ["python", "fastapi", "postgresql", "redis", "docker", "rest api", "sql", "git"]),
    ("Frontend Developer",
     ["Built React and TypeScript screens for a booking app", "Wrote responsive CSS and accessible HTML",
      "Integrated REST APIs with loading and error states", "Reduced bundle size with code splitting"],
     ["react", "typescript", "javascript", "css", "html", "git"]),
    ("Data Analyst",
     ["Wrote SQL against the warehouse for weekly reporting", "Analysed A/B tests with Python and pandas",
      "Built Tableau dashboards for sales teams", "Automated Excel reports for finance"],
     ["sql", "python", "pandas", "tableau", "excel", "statistics"]),
    ("DevOps Engineer",
     ["Ran Kubernetes clusters on AWS", "Wrote Terraform modules for networking and databases",
      "Built CI/CD pipelines that ship Docker images", "Hardened Linux hosts and managed alerts"],
     ["aws", "kubernetes", "terraform", "docker", "linux", "ci/cd"]),
    ("Machine Learning Engineer",
     ["Trained PyTorch models for text classification", "Built NLP pipelines for search queries",
      "Pulled training data with SQL", "Served models in Docker containers"],
     ["python", "pytorch", "machine learning", "nlp", "sql", "docker"]),
    ("Customer Support Specialist",
     ["Resolved customer tickets by phone and email", "Wrote help-centre articles",
      "Trained new team members", "Reported common issues to the product team"],
     ["excel", "communication", "customer service"]),
]


def _generated_resume(rng: random.Random, index: int) -> str:
    """One synthetic plain-text resume; ``index`` keeps names and emails unique."""
    title, lines, skills = rng.choice(PROFILES)
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    years = rng.randint(1, 12)
    experience = "\n".join(f"- {line}." for line in rng.sample(lines, k=3))
    return (
        f"{first} {last}\n{first.lower()}.{last.lower()}.{index}@example.com | +91 9{rng.randint(10**8, 10**9 - 1)}\n\n"
        f"SUMMARY\n{title} with {years} years of experience.\n\n"
        f"EXPERIENCE\n{title}, Company {index % 500} ({2025 - years} - Present)\n{experience}\n\n"
        f"SKILLS\n{', '.join(rng.sample(skills, k=min(len(skills), rng.randint(3, 6))))}\n"
    )


def seed_load_test(args: argparse.Namespace) -> None:
    """``seed-load-test``: create a job owned by a recruiter and give it N generated applicants.

    The resumes are written to ``UPLOAD_DIR`` and go through the same ingestion code
    as real uploads (text extraction, contact and skill parsing, embeddings), in
    batches and without HTTP, so the data matches what the API would have stored.
    """
    if args.resumes < 1:
        sys.exit("--resumes must be at least 1.")
    ok, email = validate_email_format(args.email)
    if not ok:
        sys.exit(email)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        recruiter = (
            db.query(models.User)
            .filter(func.lower(models.User.email) == email, models.User.role == ROLE_HR)
            .first()
        )
        if recruiter is None:
            sys.exit("No recruiter with this email. Create one first: python manage.py create-user --role hr ...")
        job = models.Job(
            title=LOAD_TEST_JOB["title"],
            description=LOAD_TEST_JOB["description"],
            created_by=recruiter.user_id,
            embedding=embed_text(f"{LOAD_TEST_JOB['title']}\n{LOAD_TEST_JOB['description']}"),
        )
        db.add(job)
        for skill in get_or_create_skills(db, LOAD_TEST_JOB["skills"], load_skill_index(db)):
            job.job_skills.append(models.JobSkill(skill=skill))
        db.commit()

        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        rng = random.Random(7)  # same applicants on every run
        started = time.perf_counter()
        for start in range(0, args.resumes, 250):
            batch = []
            for i in range(start, min(start + 250, args.resumes)):
                upload = StoredUpload(f"applicant_{i:05d}.txt", f"{uuid.uuid4().hex[:12]}_applicant_{i:05d}.txt")
                upload.path.write_text(_generated_resume(rng, i), encoding="utf-8")
                batch.append(upload)
            process_uploads(db, job, batch, recruiter)
            print(f"  {start + len(batch)}/{args.resumes} resumes", flush=True)
        print(f"Job {job.job_id} now has {args.resumes} applicants ({time.perf_counter() - started:.0f} s).")


def main() -> None:
    """Parse the command line and run the chosen sub-command."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="Create an HR or candidate account")
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--role", choices=ROLES, default="hr")
    create.set_defaults(func=create_user)
    reset = sub.add_parser("reset-password", help="Set a new password for an existing account")
    reset.add_argument("--email", required=True)
    reset.set_defaults(func=reset_password)
    seed = sub.add_parser("seed-load-test", help="Create a job with generated applicants for load testing")
    seed.add_argument("--email", required=True, help="Recruiter who will own the job")
    seed.add_argument("--resumes", type=int, default=10_000)
    seed.set_defaults(func=seed_load_test)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
