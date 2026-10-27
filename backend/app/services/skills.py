"""The shared skills vocabulary (``skills`` table).

Skills are stored in the canonical form returned by ``ml_utils.normalize_skill``
(lowercase, single spaces). Every skill a recruiter adds to a job becomes part
of the vocabulary used to scan future resumes.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..ml_utils import normalize_skill

logger = logging.getLogger("skills")


def load_skill_index(db: Session) -> Dict[str, models.Skill]:
    """Map canonical name -> Skill row for the whole vocabulary (one query)."""
    index: Dict[str, models.Skill] = {}
    for skill in db.query(models.Skill).order_by(models.Skill.skill_id):
        index.setdefault(normalize_skill(skill.skill_name or ""), skill)
    index.pop("", None)
    return index


def get_or_create_skills(db: Session, names: Iterable[str], index: Dict[str, models.Skill]) -> List[models.Skill]:
    """Return Skill rows for ``names`` (canonical, de-duplicated), creating missing ones.

    Creation runs in a savepoint so a concurrent insert of the same skill
    (unique violation) is resolved by re-reading the existing row.
    """
    rows: List[models.Skill] = []
    for name in dict.fromkeys(normalize_skill(n) for n in names if n and n.strip()):
        skill = index.get(name)
        if skill is None:
            try:
                with db.begin_nested():
                    skill = models.Skill(skill_name=name, canonical_name=name)
                    db.add(skill)
            except IntegrityError:
                skill = db.query(models.Skill).filter(models.Skill.skill_name == name).one()
            index[name] = skill
        rows.append(skill)
    return rows


def merge_duplicate_skills(db: Session) -> int:
    """Startup maintenance: merge rows whose names normalize to the same skill.

    Older versions stored e.g. ``"Docker"`` and ``"docker"`` separately. Links
    are moved to the oldest row (dropping links that would become duplicates)
    and the duplicate rows are deleted. Returns the number of rows removed.

    Runs on every start-up, so it first reads only ids and names, and loads the
    (potentially very many) resume/job links only for rows that need changing.
    """
    names: Dict[str, List[Tuple[int, str]]] = {}
    for skill_id, skill_name in db.query(models.Skill.skill_id, models.Skill.skill_name):
        names.setdefault(normalize_skill(skill_name or ""), []).append((skill_id, skill_name))
    affected = [
        skill_id
        for name, rows in names.items()
        if name and (len(rows) > 1 or rows[0][1] != name)
        for skill_id, _ in rows
    ]
    if not affected:
        return 0

    skills = (
        db.query(models.Skill)
        .options(selectinload(models.Skill.resume_links), selectinload(models.Skill.job_links))
        .filter(models.Skill.skill_id.in_(affected))
        .order_by(models.Skill.skill_id)
        .all()
    )
    groups: Dict[str, List[models.Skill]] = {}
    for skill in skills:
        groups.setdefault(normalize_skill(skill.skill_name or ""), []).append(skill)

    removed = 0
    for name, rows in groups.items():
        keeper, duplicates = rows[0], rows[1:]
        if not name:
            continue
        for dup in duplicates:
            linked_resumes = {link.resume_id for link in keeper.resume_links}
            for link in list(dup.resume_links):
                if link.resume_id in linked_resumes:
                    dup.resume_links.remove(link)  # orphan -> deleted by cascade
                else:
                    link.skill = keeper
                    linked_resumes.add(link.resume_id)
            linked_jobs = {link.job_id for link in keeper.job_links}
            for link in list(dup.job_links):
                if link.job_id in linked_jobs:
                    dup.job_links.remove(link)
                else:
                    link.skill = keeper
                    linked_jobs.add(link.job_id)
            db.flush()
            db.delete(dup)
            removed += 1
        if duplicates or keeper.skill_name != name:
            db.flush()
            keeper.skill_name = name
            keeper.canonical_name = name
    db.commit()
    if removed:
        logger.info("[SKILLS] Merged %s duplicate skill rows.", removed)
    return removed
