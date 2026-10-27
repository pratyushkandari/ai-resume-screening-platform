"""Candidate evaluation for a job: dashboard summary and persisted rankings.

Both use ``ml_utils.score_candidates`` (one scoring implementation). Data is
loaded with a constant number of queries regardless of the number of resumes.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..cache import CacheService, job_summary_key
from ..config import settings
from ..ml_utils import ResumeFeatures, embed_batch, embed_text, normalize_skill, score_candidates
from ..observability import metrics

logger = logging.getLogger("ranking")


def job_skill_names(db: Session, job: models.Job) -> List[str]:
    """The job's required skills in canonical form and display order, without duplicates."""
    links = (
        db.query(models.JobSkill)
        .options(selectinload(models.JobSkill.skill))
        .filter(models.JobSkill.job_id == job.job_id)
        .order_by(models.JobSkill.id)
        .all()
    )
    return list(dict.fromkeys(normalize_skill(l.skill.skill_name) for l in links if l.skill and l.skill.skill_name))


def load_job_resumes(db: Session, job_id: int) -> List[models.Resume]:
    """All resumes of a job with candidates and skills eagerly loaded (constant query count)."""
    return (
        db.query(models.Resume)
        .options(
            selectinload(models.Resume.candidate),
            selectinload(models.Resume.resume_skills).selectinload(models.ResumeSkill.skill),
        )
        .filter(models.Resume.job_id == job_id)
        .order_by(models.Resume.uploaded_at.desc(), models.Resume.resume_id.desc())
        .all()
    )


def _resume_skills(resume: models.Resume) -> List[str]:
    """Skill names linked to a resume."""
    return [link.skill.skill_name for link in resume.resume_skills if link.skill and link.skill.skill_name]


def _evaluate(job: models.Job, skills: List[str], resumes: List[models.Resume]) -> List[Dict]:
    """Score ``resumes`` against ``job`` with the shared ``score_candidates`` implementation."""
    features = [ResumeFeatures(r.embedding, _resume_skills(r)) for r in resumes]
    return score_candidates(job.embedding, skills, features)


def last_ranked_at(db: Session, job_id: int) -> Optional[datetime]:
    """When ``POST /rank`` last saved a snapshot for this job (timezone-aware UTC), or ``None``."""
    value = db.query(func.max(models.Ranking.created_at)).filter(models.Ranking.job_id == job_id).scalar()
    # SQLite drops the time zone of stored datetimes. Values are always written in UTC,
    # and without the zone browsers would read the time as local time.
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _iso(value: Optional[datetime]) -> Optional[str]:
    """ISO-8601 text for JSON caching (``None`` stays ``None``)."""
    return value.isoformat() if value else None


def build_summary(db: Session, job: models.Job) -> Dict:
    """Dashboard payload: one entry per candidate (their best-scoring resume), sorted by score."""
    cache_key = job_summary_key(job.job_id)
    cached = CacheService.get(cache_key)
    if cached is not None:
        metrics.inc("summary_cache_hits_total")
        cached["_cache"] = "HIT"
        return cached
    metrics.inc("summary_cache_misses_total")

    skills = job_skill_names(db, job)
    resumes = load_job_resumes(db, job.job_id)
    evaluations = _evaluate(job, skills, resumes)

    best: Dict[int, Dict] = {}
    for resume, ev in zip(resumes, evaluations, strict=True):
        # Group by applicant; a resume without an applicant gets its own (negative) key.
        key = resume.candidate_id if resume.candidate_id is not None else -resume.resume_id
        entry = {
            "candidate_id": resume.candidate_id,
            "candidate_name": resume.candidate.full_name if resume.candidate else None,
            "resume_id": resume.resume_id,
            # Stored as "<random12>_<original>"; show the original name.
            "filename": resume.filename.split("_", 1)[-1] if resume.filename else None,
            "semantic": ev["semantic"],
            "skill_score": ev["skill_score"],
            "score": ev["final_score"],
            "status": ev["status"],
            "matched_skills": ev["matched_skills"],
            "missing_skills": ev["missing_skills"],
            "coverage_vector": ev["coverage_vector"],
            "coverage_percent": ev["coverage_percent"],
        }
        # Keep each applicant's best-scoring resume (they may upload several versions).
        if key not in best or entry["score"] > best[key]["score"]:
            best[key] = entry
    # Highest score first; ties broken by resume id so the order is stable between requests.
    candidates = sorted(best.values(), key=lambda c: (-c["score"], c["resume_id"]))

    coverage = Counter(skill for c in candidates for skill in c["matched_skills"])
    applicant_skills = Counter()
    best_resume_ids = {c["resume_id"] for c in candidates}
    for resume in resumes:
        if resume.resume_id in best_resume_ids:
            applicant_skills.update(set(normalize_skill(s) for s in _resume_skills(resume)))

    result = {
        "job_id": job.job_id,
        "title": job.title,
        "job_skills": skills,
        "job_skill_counts": [{"skill_name": s, "matches": coverage.get(s, 0)} for s in skills],
        "top_skills": [{"skill_name": s, "matches": n} for s, n in applicant_skills.most_common(10)],
        "candidates": candidates,
        "semantic_available": bool(job.embedding) and all(r.embedding for r in resumes),
        "last_ranked_at": _iso(last_ranked_at(db, job.job_id)),
    }
    CacheService.set(cache_key, result, settings.summary_cache_ttl_seconds)
    result["_cache"] = "MISS"
    return result


def backfill_embeddings(db: Session, job: models.Job, resumes: List[models.Resume]) -> int:
    """Compute embeddings that are missing because the model was unavailable at upload time."""
    filled = 0
    if not job.embedding:
        vector = embed_text(f"{job.title}\n{job.description or ''}")
        if vector is not None:
            job.embedding = vector
            filled += 1
    missing = [r for r in resumes if not r.embedding and r.raw_text]
    if missing:
        for resume, vector in zip(missing, embed_batch([r.raw_text for r in missing]), strict=True):
            if vector is not None:
                resume.embedding = vector
                filled += 1
    return filled


def rank_job(db: Session, job: models.Job) -> Dict:
    """Recompute scores for every resume of ``job`` and store a fresh rankings snapshot."""
    # Lock the job row (PostgreSQL) so two simultaneous "Evaluate" requests run one
    # after the other instead of colliding on the (job_id, resume_id) unique key.
    db.query(models.Job).filter(models.Job.job_id == job.job_id).with_for_update().one()
    skills = job_skill_names(db, job)
    resumes = load_job_resumes(db, job.job_id)
    filled = backfill_embeddings(db, job, resumes)
    evaluations = _evaluate(job, skills, resumes)

    now = datetime.now(timezone.utc)
    db.query(models.Ranking).filter(models.Ranking.job_id == job.job_id).delete(synchronize_session=False)
    db.add_all(
        models.Ranking(job_id=job.job_id, resume_id=r.resume_id, score=ev["final_score"], status=ev["status"], created_at=now)
        for r, ev in zip(resumes, evaluations, strict=True)
    )
    db.commit()
    CacheService.delete(job_summary_key(job.job_id))
    logger.info("Ranked %s resumes for job %s (backfilled %s embeddings)", len(resumes), job.job_id, filled)
    return {"status": "done", "ranked": len(resumes), "ranked_at": now if resumes else None}


def list_rankings(db: Session, job_id: int) -> List[Dict]:
    """The saved snapshot, highest score first, with candidate names (constant query count)."""
    rows = (
        db.query(models.Ranking)
        .options(selectinload(models.Ranking.resume).selectinload(models.Resume.candidate))
        .filter(models.Ranking.job_id == job_id)
        .order_by(models.Ranking.score.desc(), models.Ranking.ranking_id)
        .all()
    )
    out = []
    for row in rows:
        candidate = row.resume.candidate if row.resume else None
        out.append(
            {
                "ranking_id": row.ranking_id,
                "resume_id": row.resume_id,
                "candidate_id": candidate.candidate_id if candidate else None,
                "candidate_name": candidate.full_name if candidate else None,
                "score": row.score,
                "status": row.status,
            }
        )
    return out
