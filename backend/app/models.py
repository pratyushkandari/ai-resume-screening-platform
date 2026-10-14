# backend/app/models.py

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Text, Float, ForeignKey, DateTime, UniqueConstraint, String, JSON
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .db import Base

# Multi-dialect JSON type (Native JSONB on PostgreSQL, standard JSON on SQLite/MySQL)
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


# =============================================================================
#  Candidate TABLE
# =============================================================================
class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(Text)
    email = Column(Text, unique=True, index=True)
    phone = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    resumes = relationship(
        "Resume",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )


# =============================================================================
#  Resume TABLE
# =============================================================================
class Resume(Base):
    __tablename__ = "resumes"

    resume_id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id", ondelete="CASCADE"), index=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="SET NULL"), nullable=True, index=True)

    filename = Column(Text, nullable=False)
    upload_path = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    raw_text = Column(Text)
    parsed_json = Column(JSON_TYPE)
    embedding = Column(JSON_TYPE)

    candidate = relationship("Candidate", back_populates="resumes")
    resume_skills = relationship(
        "ResumeSkill",
        back_populates="resume",
        cascade="all, delete-orphan"
    )
    rankings = relationship(
        "Ranking",
        back_populates="resume",
        cascade="all, delete-orphan"
    )


# =============================================================================
#  Skill TABLE
# =============================================================================
class Skill(Base):
    __tablename__ = "skills"

    skill_id = Column(Integer, primary_key=True, index=True)
    skill_name = Column(Text, unique=True, nullable=False, index=True)
    canonical_name = Column(Text)

    resume_links = relationship(
        "ResumeSkill",
        back_populates="skill",
        cascade="all, delete-orphan"
    )
    job_links = relationship(
        "JobSkill",
        back_populates="skill",
        cascade="all, delete-orphan"
    )


# =============================================================================
#  ResumeSkill TABLE
# =============================================================================
class ResumeSkill(Base):
    __tablename__ = "resume_skills"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.resume_id", ondelete="CASCADE"), index=True)
    skill_id = Column(Integer, ForeignKey("skills.skill_id", ondelete="CASCADE"), index=True)
    confidence = Column(Float, default=1.0)

    resume = relationship("Resume", back_populates="resume_skills")
    skill = relationship("Skill", back_populates="resume_links")


# =============================================================================
#  Job TABLE
# =============================================================================
class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), index=True)

    title = Column(Text, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    embedding = Column(JSON_TYPE)

    user = relationship("User")
    job_skills = relationship(
        "JobSkill",
        back_populates="job",
        cascade="all, delete-orphan"
    )
    rankings = relationship(
        "Ranking",
        back_populates="job",
        cascade="all, delete-orphan"
    )


# =============================================================================
#  JobSkill TABLE
# =============================================================================
class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"), index=True)
    skill_id = Column(Integer, ForeignKey("skills.skill_id", ondelete="CASCADE"), index=True)
    required_level = Column(Integer, default=1)

    job = relationship("Job", back_populates="job_skills")
    skill = relationship("Skill", back_populates="job_links")


# =============================================================================
#  Ranking TABLE
# =============================================================================
class Ranking(Base):
    __tablename__ = "rankings"

    ranking_id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id", ondelete="CASCADE"), index=True)
    resume_id = Column(Integer, ForeignKey("resumes.resume_id", ondelete="CASCADE"), index=True)

    score = Column(Float, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    job = relationship("Job", back_populates="rankings")
    resume = relationship("Resume", back_populates="rankings")

    __table_args__ = (
        UniqueConstraint("job_id", "resume_id", name="uix_job_resume"),
    )


# =============================================================================
#  User TABLE
# =============================================================================
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="candidate", nullable=False)  # "hr" or "candidate"