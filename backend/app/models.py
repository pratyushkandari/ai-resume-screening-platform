"""SQLAlchemy ORM models.

Columns, constraints and indexes match ``sql/seed.sql`` so a database created by
either ``Base.metadata.create_all`` or the seed script has the same shape.
Deletes are handled by the database (``ON DELETE CASCADE`` / ``SET NULL``); only
relationships that the code actually navigates are declared.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .db import Base

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite in tests).
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime (stored in ``timestamptz`` columns)."""
    return datetime.now(timezone.utc)


class User(Base):
    """Login identity. ``role`` is either ``"hr"`` or ``"candidate"``."""

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password = Column(Text, nullable=False)  # bcrypt hash, never plaintext
    role = Column(Text, default="candidate", server_default="candidate", nullable=False)


class Candidate(Base):
    """Applicant profile (one per email address)."""

    __tablename__ = "candidates"

    candidate_id = Column(Integer, primary_key=True)
    full_name = Column(Text)
    email = Column(Text, unique=True)
    phone = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())


class Job(Base):
    """A job requisition created by a recruiter. ``embedding`` encodes title + description."""

    __tablename__ = "jobs"

    job_id = Column(Integer, primary_key=True)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    title = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    embedding = Column(JSON_TYPE)  # 384 floats, or NULL when the model was unavailable

    job_skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan", order_by="JobSkill.id")


class Resume(Base):
    """One uploaded file for one job, with its extracted text, parsed contacts and embedding."""

    __tablename__ = "resumes"

    resume_id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id", ondelete="CASCADE"))
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="SET NULL"), nullable=True)
    filename = Column(Text, nullable=False)       # stored file name (random prefix + original name)
    upload_path = Column(Text, nullable=False)    # path relative to UPLOAD_DIR
    uploaded_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())
    raw_text = Column(Text)
    parsed_json = Column(JSON_TYPE)               # audit copy: {"parsed": {name, email, phone}, "skills": [...]}
    embedding = Column(JSON_TYPE)

    candidate = relationship("Candidate")
    resume_skills = relationship("ResumeSkill", back_populates="resume", cascade="all, delete-orphan")


class Skill(Base):
    """One entry of the shared skill vocabulary, stored in canonical form (lower case, single spaces)."""

    __tablename__ = "skills"

    skill_id = Column(Integer, primary_key=True)
    skill_name = Column(Text, unique=True, nullable=False)  # canonical form, see ml_utils.normalize_skill
    canonical_name = Column(Text)  # kept equal to skill_name; column retained for existing databases

    resume_links = relationship("ResumeSkill", back_populates="skill", cascade="all, delete-orphan")
    job_links = relationship("JobSkill", back_populates="skill", cascade="all, delete-orphan")


class ResumeSkill(Base):
    """Link: this skill was found in this resume, with a match confidence (0.85–0.95)."""

    __tablename__ = "resume_skills"
    __table_args__ = (UniqueConstraint("resume_id", "skill_id", name="uix_resume_skill"),)

    id = Column(Integer, primary_key=True)
    resume_id = Column(Integer, ForeignKey("resumes.resume_id", ondelete="CASCADE"))
    skill_id = Column(Integer, ForeignKey("skills.skill_id", ondelete="CASCADE"))
    confidence = Column(Float, default=1.0, server_default=text("1.0"))

    resume = relationship("Resume", back_populates="resume_skills")
    skill = relationship("Skill", back_populates="resume_links")


class JobSkill(Base):
    """Link: this skill is required by this job. Insertion order is the display order."""

    __tablename__ = "job_skills"
    __table_args__ = (UniqueConstraint("job_id", "skill_id", name="uix_job_skill"),)

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"))
    skill_id = Column(Integer, ForeignKey("skills.skill_id", ondelete="CASCADE"))
    required_level = Column(Integer, default=1, server_default=text("1"))  # always 1 today; column retained for existing databases

    job = relationship("Job", back_populates="job_skills")
    skill = relationship("Skill", back_populates="job_links")


class Ranking(Base):
    """Persisted snapshot written by ``POST /api/jobs/{id}/rank``."""

    __tablename__ = "rankings"
    __table_args__ = (UniqueConstraint("job_id", "resume_id", name="uix_job_resume"),)

    ranking_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"))
    resume_id = Column(Integer, ForeignKey("resumes.resume_id", ondelete="CASCADE"))
    score = Column(Float, nullable=False)
    status = Column(Text, default="pending", server_default="pending")  # "accepted" | "rejected"
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now())

    resume = relationship("Resume")


# Secondary indexes (same names as sql/seed.sql). Logins and candidate matching
# look rows up by lower(email); the rest support the joins in services/ranking.py.
# Composite unique constraints above already index (job_id, ...) and (resume_id, ...).
Index("idx_users_email_lower", func.lower(User.email))
Index("idx_candidates_email_lower", func.lower(Candidate.email))
Index("idx_jobs_created_by", Job.created_by)
Index("idx_resumes_candidate_id", Resume.candidate_id)
Index("idx_resumes_job_id", Resume.job_id)
Index("idx_resume_skills_skill_id", ResumeSkill.skill_id)
