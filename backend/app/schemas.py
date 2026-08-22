# backend/app/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ResumeUploadResponse(BaseModel):
    """
    Returned after a resume file is successfully uploaded and processed.
    """
    resume_id: int
    candidate_id: int
    job_id: Optional[int] = None
    parsed: Dict[str, Any]


class CandidateOut(BaseModel):
    """
    Candidate details in API responses.
    """
    candidate_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class JobCreate(BaseModel):
    """
    Payload when creating a new job posting.
    """
    title: str
    description: Optional[str] = None
    skills: Optional[List[str]] = Field(default_factory=list)


class JobOut(BaseModel):
    """
    Job list item returned from GET /api/jobs.
    """
    job_id: int
    title: str
    description: Optional[str] = None
    created_by: Optional[int] = None
    skills: List[str] = Field(default_factory=list)


class RankingOut(BaseModel):
    """
    Job candidate ranking item returned from GET /api/jobs/{job_id}/rankings.
    """
    ranking_id: int
    resume_id: int
    candidate_id: int
    candidate_name: Optional[str] = None
    score: float
    status: str = "pending"


class JobSkillCount(BaseModel):
    """
    Skill frequency counter for dashboard charts.
    """
    skill_name: str
    matches: int


class CandidateSummary(BaseModel):
    """
    Evaluation summary for a single candidate under a specific job.
    """
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    resume_id: int
    semantic: float
    skill_score: float
    score: float
    status: str = "pending"
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    coverage_vector: List[int] = Field(default_factory=list)
    coverage_percent: int = 0


class JobSummaryOut(BaseModel):
    """
    Dashboard response payload containing statistics and ranked candidates.
    """
    job_id: int
    title: str
    job_skills: List[str] = Field(default_factory=list)
    job_skill_counts: List[JobSkillCount] = Field(default_factory=list)
    top_skills: List[JobSkillCount] = Field(default_factory=list)
    candidates: List[CandidateSummary] = Field(default_factory=list)
