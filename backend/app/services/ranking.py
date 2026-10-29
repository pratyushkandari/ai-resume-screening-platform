"""Candidate evaluation for a job: dashboard summary and persisted rankings.

Both use ``ml_utils.score_candidates`` (one scoring implementation). Data is
loaded with a constant number of queries regardless of the number of resumes,
and without resume text or embeddings: each resume's semantic score is stored
when it is computed, because loading 10,000 JSON embeddings took about 4 s.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..cache import CacheService, job_summary_key
from ..config import settings
from ..ml_utils import (
    STATUS_ACCEPTED,
    ResumeFeatures,
    embed_batch,
    embed_text,
    normalize_skill,
    score_candidates,
    stored_semantic_scores,
)
from ..observability import metrics

logger = logging.getLogger("ranking")
# The dashboard lists the best candidates only; totals still cover every applicant,
# and GET /rankings returns the full list. Rendering 10,000 cards froze the browser.
SUMMARY_TOP_CANDIDATES = 100
# Display tier above the shortlist cut-off: on the evaluation set, scores from about
# 0.80 up are mostly strong fits (grade 3).
STRONG_FIT_SCORE = 0.80


@dataclass(frozen=True)
class ResumeRow:
    """The fields of one resume that scoring and the dashboard need (no text, no embedding)."""

    resume_id: int
    candidate_id: Optional[int]
    candidate_name: Optional[str]
    filename: Optional[str]
    features: ResumeFeatures


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


def load_job_rows(db: Session, job_id: int) -> List[ResumeRow]:
    """Every resume of a job as plain rows (three queries, no ORM objects), newest first.

    Embeddings are loaded only for resumes without a stored semantic score: rows
    from before the score was stored, or uploaded while the model was unavailable.
    """
    rows = (
        db.query(
            models.Resume.resume_id,
            models.Resume.candidate_id,
            models.Candidate.full_name,
            models.Resume.filename,
            models.Resume.semantic_score,
        )
        .outerjoin(models.Candidate, models.Candidate.candidate_id == models.Resume.candidate_id)
        .filter(models.Resume.job_id == job_id)
        .order_by(models.Resume.uploaded_at.desc(), models.Resume.resume_id.desc())
        .all()
    )
    skills: Dict[int, List[str]] = defaultdict(list)
    skill_rows = (
        db.query(models.ResumeSkill.resume_id, models.Skill.skill_name)
        .join(models.Skill, models.Skill.skill_id == models.ResumeSkill.skill_id)
        .join(models.Resume, models.Resume.resume_id == models.ResumeSkill.resume_id)
        .filter(models.Resume.job_id == job_id)
    )
    for resume_id, skill_name in skill_rows:
        skills[resume_id].append(skill_name)
    unscored = dict(
        db.query(models.Resume.resume_id, models.Resume.embedding)
        .filter(models.Resume.job_id == job_id, models.Resume.semantic_score.is_(None))
        .all()
    )
    return [
        ResumeRow(
            row.resume_id,
            row.candidate_id,
            row.full_name,
            row.filename,
            ResumeFeatures(unscored.get(row.resume_id), skills[row.resume_id], row.semantic_score),
        )
        for row in rows
    ]


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
    """Dashboard payload: the best ``SUMMARY_TOP_CANDIDATES`` candidates plus totals over all of them.

    Each candidate appears once, with their best-scoring resume.
    """
    cache_key = job_summary_key(job.job_id)
    cached = CacheService.get(cache_key)
    if cached is not None:
        metrics.inc("summary_cache_hits_total")
        cached["_cache"] = "HIT"
        return cached
    metrics.inc("summary_cache_misses_total")

    skills = job_skill_names(db, job)
    rows = load_job_rows(db, job.job_id)
    evaluations = score_candidates(job.embedding, skills, [row.features for row in rows])

    best: Dict[int, Dict] = {}
    for row, ev in zip(rows, evaluations, strict=True):
        # Group by applicant; a resume without an applicant gets its own (negative) key.
        key = row.candidate_id if row.candidate_id is not None else -row.resume_id
        entry = {
            "candidate_id": row.candidate_id,
            "candidate_name": row.candidate_name,
            "resume_id": row.resume_id,
            # Stored as "<random12>_<original>"; show the original name.
            "filename": row.filename.split("_", 1)[-1] if row.filename else None,
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
    for row in rows:
        if row.resume_id in best_resume_ids:
            applicant_skills.update(set(normalize_skill(s) for s in row.features.skills))
    shortlisted = [c for c in candidates if c["status"] == STATUS_ACCEPTED]

    result = {
        "job_id": job.job_id,
        "title": job.title,
        "job_skills": skills,
        "job_skill_counts": [{"skill_name": s, "matches": coverage.get(s, 0)} for s in skills],
        "top_skills": [{"skill_name": s, "matches": n} for s, n in applicant_skills.most_common(10)],
        "candidates": candidates[:SUMMARY_TOP_CANDIDATES],
        "total_candidates": len(candidates),
        "shortlisted_candidates": len(shortlisted),
        "strong_fits": sum(c["score"] >= STRONG_FIT_SCORE for c in shortlisted),
        "average_score": round(mean(c["score"] for c in candidates), 4) if candidates else 0.0,
        "semantic_available": bool(job.embedding)
        and all(row.features.semantic is not None or row.features.embedding for row in rows),
        "last_ranked_at": _iso(last_ranked_at(db, job.job_id)),
    }
    CacheService.set(cache_key, result, settings.summary_cache_ttl_seconds)
    result["_cache"] = "MISS"
    return result


def backfill_semantic_scores(db: Session, job: models.Job) -> int:
    """Fill in what was missing at upload time: embeddings and stored semantic scores.

    Only resumes without a semantic score are loaded (with their text), so this is
    cheap once a job is up to date. Returns how many embeddings were computed.
    """
    filled = 0
    if not job.embedding:
        vector = embed_text(f"{job.title}\n{job.description or ''}")
        if vector is not None:
            job.embedding = vector
            filled += 1
    if not job.embedding:
        return filled  # model still unavailable: scores stay neutral
    pending = (
        db.query(models.Resume)
        .filter(models.Resume.job_id == job.job_id, models.Resume.semantic_score.is_(None))
        .all()
    )
    missing = [r for r in pending if not r.embedding and r.raw_text]
    if missing:
        for resume, vector in zip(missing, embed_batch([r.raw_text for r in missing]), strict=True):
            if vector is not None:
                resume.embedding = vector
                filled += 1
    for resume, score in zip(pending, stored_semantic_scores(job.embedding, [r.embedding for r in pending]), strict=True):
        resume.semantic_score = score
    db.flush()  # the session does not autoflush; the scoring query below must see these
    return filled


def rank_job(db: Session, job: models.Job) -> Dict:
    """Recompute scores for every resume of ``job`` and store a fresh rankings snapshot."""
    # Lock the job row (PostgreSQL) so two simultaneous "Evaluate" requests run one
    # after the other instead of colliding on the (job_id, resume_id) unique key.
    db.query(models.Job).filter(models.Job.job_id == job.job_id).with_for_update().one()
    filled = backfill_semantic_scores(db, job)
    skills = job_skill_names(db, job)
    rows = load_job_rows(db, job.job_id)
    evaluations = score_candidates(job.embedding, skills, [row.features for row in rows])

    now = datetime.now(timezone.utc)
    db.query(models.Ranking).filter(models.Ranking.job_id == job.job_id).delete(synchronize_session=False)
    db.add_all(
        models.Ranking(job_id=job.job_id, resume_id=row.resume_id, score=ev["final_score"], status=ev["status"], created_at=now)
        for row, ev in zip(rows, evaluations, strict=True)
    )
    db.commit()
    CacheService.delete(job_summary_key(job.job_id))
    logger.info("Ranked %s resumes for job %s (backfilled %s embeddings)", len(rows), job.job_id, filled)
    return {"status": "done", "ranked": len(rows), "ranked_at": now if rows else None}


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
