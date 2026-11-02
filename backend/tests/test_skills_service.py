"""The shared skill vocabulary: canonical names, reuse, and start-up merging of duplicates."""

from sqlalchemy import event

from app import models
from app.db import engine
from app.services.skills import get_or_create_skills, load_skill_index, merge_duplicate_skills


def _statements_during(action):
    """Run ``action`` and return the SQL statements it executed."""
    statements = []

    def listener(_conn, _cursor, statement, *_args):
        """SQLAlchemy event hook: record one executed statement."""
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", listener)
    try:
        action()
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    return statements


def test_get_or_create_reuses_and_normalizes(db):
    index = load_skill_index(db)
    first = get_or_create_skills(db, ["Python", "machine-learning", "python"], index)
    db.commit()
    assert [s.skill_name for s in first] == ["python", "machine learning"]
    again = get_or_create_skills(db, ["PYTHON"], load_skill_index(db))
    assert again[0].skill_id == first[0].skill_id


def test_merge_duplicate_skills_moves_links(db):
    candidate = models.Candidate(full_name="X", email="x@x.com")
    job = models.Job(title="Job", description="d" * 20)
    upper, lower = models.Skill(skill_name="Docker"), models.Skill(skill_name="docker")
    db.add_all([candidate, job, upper, lower])
    db.flush()
    resume = models.Resume(candidate=candidate, job_id=job.job_id, filename="f", upload_path="f")
    db.add(resume)
    db.flush()
    db.add_all([
        models.ResumeSkill(resume=resume, skill=upper),
        models.ResumeSkill(resume=resume, skill=lower),  # would become a duplicate link
        models.JobSkill(job=job, skill=lower),
    ])
    db.commit()

    assert merge_duplicate_skills(db) == 1
    rows = db.query(models.Skill).all()
    assert [s.skill_name for s in rows] == ["docker"]
    assert db.query(models.ResumeSkill).count() == 1
    assert db.query(models.JobSkill).one().skill_id == rows[0].skill_id


def test_startup_merge_skips_link_tables_when_nothing_needs_merging(db):
    # Runs on every start-up: with a clean vocabulary it must not load every resume/job link.
    candidate = models.Candidate(full_name="X", email="x@x.com")
    python = models.Skill(skill_name="python")
    db.add_all([candidate, python])
    db.flush()
    resume = models.Resume(candidate=candidate, filename="f", upload_path="f")
    db.add_all([resume, models.ResumeSkill(resume=resume, skill=python)])
    db.commit()

    statements = _statements_during(lambda: merge_duplicate_skills(db))
    assert not any("resume_skills" in s or "job_skills" in s for s in statements)


def test_startup_merge_canonicalizes_a_single_legacy_name(db):
    db.add(models.Skill(skill_name="Machine-Learning"))
    db.commit()
    assert merge_duplicate_skills(db) == 0
    db.expire_all()
    assert [s.skill_name for s in db.query(models.Skill)] == ["machine learning"]


def test_merge_moves_links_found_only_on_the_duplicate_and_drops_repeated_job_links(db):
    candidate = models.Candidate(full_name="Y", email="y@y.com")
    job = models.Job(title="Job", description="d" * 20)
    upper, lower = models.Skill(skill_name="Kubernetes"), models.Skill(skill_name="kubernetes")
    db.add_all([candidate, job, upper, lower])
    db.flush()
    resume = models.Resume(candidate=candidate, job_id=job.job_id, filename="f", upload_path="f")
    db.add(resume)
    db.flush()
    db.add_all([
        models.ResumeSkill(resume=resume, skill=lower),  # only the duplicate has this resume
        models.JobSkill(job=job, skill=upper),
        models.JobSkill(job=job, skill=lower),  # would become a duplicate link
    ])
    db.commit()

    assert merge_duplicate_skills(db) == 1
    keeper = db.query(models.Skill).one()
    assert keeper.skill_name == "kubernetes"
    assert db.query(models.ResumeSkill).one().skill_id == keeper.skill_id
    assert db.query(models.JobSkill).one().skill_id == keeper.skill_id


def test_get_or_create_returns_a_skill_that_exists_but_is_not_in_the_index(db):
    """Another request may have created the skill after this request loaded its index."""
    db.add(models.Skill(skill_name="terraform", canonical_name="terraform"))
    db.commit()
    [skill] = get_or_create_skills(db, ["Terraform"], index={})
    assert skill.skill_name == "terraform" and db.query(models.Skill).count() == 1
