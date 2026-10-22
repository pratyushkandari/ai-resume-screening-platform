"""Recruiter-only evaluation endpoints. Every route checks the HR role and job ownership."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_owned_job, require_hr
from ..db import get_db
from ..schemas import JobSummaryOut, RankingOut, RankOut
from ..services import ranking

router = APIRouter(prefix="/api/jobs", tags=["Rankings"])


@router.get("/{job_id}/summary", response_model=JobSummaryOut)
def job_summary(
    job_id: int,
    response: Response,
    current_user: models.User = Depends(require_hr),
    db: Session = Depends(get_db),
) -> dict:
    """Dashboard analytics with live scores, one entry per candidate. Cached (``X-Cache`` header)."""
    job = get_owned_job(job_id, current_user, db)
    summary = ranking.build_summary(db, job)
    response.headers["X-Cache"] = summary.pop("_cache", "MISS")
    return summary


@router.post("/{job_id}/rank", response_model=RankOut)
def rank_job(job_id: int, current_user: models.User = Depends(require_hr), db: Session = Depends(get_db)) -> dict:
    """Re-score all resumes for the job, fill in any missing embeddings and save a rankings snapshot."""
    job = get_owned_job(job_id, current_user, db)
    return ranking.rank_job(db, job)


@router.get("/{job_id}/rankings", response_model=List[RankingOut])
def get_rankings(job_id: int, current_user: models.User = Depends(require_hr), db: Session = Depends(get_db)) -> list:
    """The last saved rankings snapshot (one row per resume), highest score first."""
    get_owned_job(job_id, current_user, db)
    return ranking.list_rankings(db, job_id)
