"""Pydantic response models (request bodies are parsed in the routers)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    """Returned by register and login. ``access_token`` goes in ``Authorization: Bearer``."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    role: str
    expires_in: int = Field(description="Token lifetime in seconds")


class UserOut(BaseModel):
    """Public profile of the signed-in user (never includes the password hash)."""

    user_id: int
    name: str
    email: str
    role: str


class JobOut(BaseModel):
    """A job as shown to candidates and recruiters; ``skills`` are canonical names in display order."""

    job_id: int
    title: str
    description: Optional[str] = None
    created_by: Optional[int] = None
    skills: List[str] = Field(default_factory=list)


class ParsedResume(BaseModel):
    """Contacts and skills extracted from one resume (best effort; any field may be missing)."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str] = Field(default_factory=list)


class ResumeUploadResult(BaseModel):
    """Outcome for one uploaded file: ``processed`` with ids, or ``failed`` with a reason."""

    filename: str
    status: str  # "processed" | "failed"
    resume_id: Optional[int] = None
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    parsed: Optional[ParsedResume] = None
    error: Optional[str] = None


class BatchUploadOut(BaseModel):
    """Batch upload response: totals plus one ``ResumeUploadResult`` per file, in request order."""

    job_id: int
    total_files: int
    successful: int
    failed: int
    results: List[ResumeUploadResult]


class RankOut(BaseModel):
    """Result of ``POST /rank``: how many resumes were scored and when the snapshot was saved."""

    status: str = "done"
    ranked: int
    ranked_at: Optional[datetime] = None


class RankingOut(BaseModel):
    """One row of the saved rankings snapshot."""

    ranking_id: int
    resume_id: int
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    score: float
    status: str


class SkillCount(BaseModel):
    """A skill and how many candidates have it (used by the dashboard charts)."""

    skill_name: str
    matches: int


class CandidateSummary(BaseModel):
    """One candidate on the dashboard (their best-scoring resume for this job).

    ``score`` = 0.7 x ``skill_score`` + 0.3 x ``semantic`` (+0.05 bonus), capped at 1.
    ``coverage_vector`` has one 1/0 entry per required skill, in ``job_skills`` order.
    """

    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    resume_id: int
    filename: Optional[str] = None
    semantic: float
    skill_score: float
    score: float
    status: str
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    coverage_vector: List[int] = Field(default_factory=list)
    coverage_percent: int = 0


class JobSummaryOut(BaseModel):
    """Everything the recruiter dashboard shows for one job."""

    job_id: int
    title: str
    job_skills: List[str] = Field(default_factory=list)
    job_skill_counts: List[SkillCount] = Field(default_factory=list)
    top_skills: List[SkillCount] = Field(default_factory=list, description="Most common skills among this job's applicants")
    candidates: List[CandidateSummary] = Field(default_factory=list)
    semantic_available: bool = Field(description="False if any score used the neutral 0.5 semantic value because an embedding was missing")
    last_ranked_at: Optional[datetime] = None
