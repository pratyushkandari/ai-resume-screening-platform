"""Job requisitions: public listing, a recruiter's own jobs, and creation."""

from __future__ import annotations

import logging
import re
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..auth import require_hr
from ..db import get_db
from ..ml_utils import embed_text, normalize_skill
from ..schemas import JobOut
from ..services.skills import get_or_create_skills, load_skill_index
from ..text_utils import clean_text

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])
logger = logging.getLogger("jobs")
MAX_SKILLS = 30
SKILL_ALLOWED = re.compile(r"[^a-z0-9+#./ ]")


def _to_out(job: models.Job) -> JobOut:
    """Convert a ``Job`` row (with skills eagerly loaded) into the response model."""
    skills = [link.skill.skill_name for link in job.job_skills if link.skill]
    return JobOut(job_id=job.job_id, title=job.title, description=job.description, created_by=job.created_by, skills=skills)


def _query_jobs(db: Session):
    """Base query that loads each job's skills in two extra queries total (no N+1)."""
    return db.query(models.Job).options(selectinload(models.Job.job_skills).selectinload(models.JobSkill.skill))


def parse_skills(raw: str) -> List[str]:
    """Turn ``"Python, Machine-Learning, C#"`` into canonical, unique skill names.

    Characters other than letters, digits and ``+ # . /`` are dropped; names
    longer than 50 characters are ignored. Order is kept (it is the display order).
    """
    skills: List[str] = []
    for part in (raw or "").split(","):
        skill = SKILL_ALLOWED.sub("", normalize_skill(part)).strip()
        if skill and len(skill) <= 50 and skill not in skills:
            skills.append(skill)
    return skills


@router.get("", response_model=List[JobOut])
def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[JobOut]:
    """Open positions, newest first (public: candidates browse these)."""
    jobs = _query_jobs(db).order_by(models.Job.created_at.desc(), models.Job.job_id.desc()).offset((page - 1) * limit).limit(limit)
    return [_to_out(j) for j in jobs]


@router.get("/mine", response_model=List[JobOut])
def list_my_jobs(current_user: models.User = Depends(require_hr), db: Session = Depends(get_db)) -> List[JobOut]:
    """Jobs created by the signed-in recruiter (the dashboard's job selector)."""
    jobs = _query_jobs(db).filter(models.Job.created_by == current_user.user_id).order_by(models.Job.created_at.desc(), models.Job.job_id.desc())
    return [_to_out(j) for j in jobs]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    title: str = Form(...),
    description: str = Form(...),
    skills: str = Form(..., description="Comma-separated required skills, e.g. 'python, docker, sql'"),
    current_user: models.User = Depends(require_hr),
    db: Session = Depends(get_db),
) -> JobOut:
    """Create a job owned by the signed-in recruiter (form fields: title, description, skills).

    The job text is embedded immediately (``NULL`` if the model is not loaded yet;
    ``POST /rank`` fills it in later).
    """
    clean_title = clean_text(title)
    if not 3 <= len(clean_title) <= 120:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Job title must be between 3 and 120 characters.")
    clean_description = clean_text(description)
    if not 20 <= len(clean_description) <= 10_000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Job description must be between 20 and 10,000 characters.")
    skill_names = parse_skills(skills)
    if not skill_names:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Specify at least one required skill (e.g. python, docker).")
    if len(skill_names) > MAX_SKILLS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Specify at most {MAX_SKILLS} required skills.")

    job = models.Job(
        title=clean_title,
        description=clean_description,
        created_by=current_user.user_id,
        embedding=embed_text(f"{clean_title}\n{clean_description}"),
    )
    db.add(job)
    for skill in get_or_create_skills(db, skill_names, load_skill_index(db)):
        job.job_skills.append(models.JobSkill(skill=skill, required_level=1))
    db.commit()
    logger.info("Created job %s by user %s", job.job_id, current_user.user_id)
    return JobOut(job_id=job.job_id, title=job.title, description=job.description, created_by=job.created_by, skills=skill_names)
