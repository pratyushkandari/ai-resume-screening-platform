"""The shared skill vocabulary: canonical names, reuse, and start-up merging of duplicates."""

from app import models
from app.services.skills import get_or_create_skills, load_skill_index, merge_duplicate_skills


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
