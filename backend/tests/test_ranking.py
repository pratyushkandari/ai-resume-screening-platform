"""Unit tests for the scoring model in ``ml_utils``."""

import numpy as np
import pytest

from app.ml_utils import NEUTRAL_SEMANTIC, ResumeFeatures, score_candidates, semantic_scores


def score_candidate(job_embedding, resume_embedding, job_skills, resume_skills):
    """Score a single resume (test helper around the batch ``score_candidates``)."""
    return score_candidates(job_embedding, job_skills, [ResumeFeatures(resume_embedding, resume_skills)])[0]

E1 = [1.0] + [0.0] * 383
E2 = [0.0, 1.0] + [0.0] * 382
NEG = [-1.0] + [0.0] * 383


def test_semantic_scores_mapping():
    scores = semantic_scores(E1, [E1, E2, NEG, None, [1.0, 0.0]])
    assert scores.tolist() == pytest.approx([1.0, 0.5, 0.0, NEUTRAL_SEMANTIC, NEUTRAL_SEMANTIC])
    assert semantic_scores(None, [E1]).tolist() == [NEUTRAL_SEMANTIC]
    assert semantic_scores(E1, []).size == 0


def test_perfect_match():
    r = score_candidate(E1, E1, ["python", "docker", "sql"], ["Python", "docker", "SQL", "go"])
    assert (r["skill_score"], r["semantic"], r["final_score"], r["status"]) == (1.0, 1.0, 1.0, "accepted")
    assert r["coverage_vector"] == [1, 1, 1] and r["coverage_percent"] == 100 and r["missing_skills"] == []


@pytest.mark.parametrize(
    "matched, semantic_vec, expected_final, status",
    [
        (7, E2, 0.7 * 1.0 + 0.3 * 0.5 + 0.05, "accepted"),    # full coverage, unrelated text
        (5, E2, 0.7 * 5 / 7 + 0.3 * 0.5 + 0.05, "accepted"),  # 71% coverage -> bonus applies
        (4, E1, 0.7 * 4 / 7 + 0.3 * 1.0, "accepted"),         # 57% + perfect semantics
        (4, E2, 0.7 * 4 / 7 + 0.3 * 0.5, "rejected"),         # 57% + unrelated -> 0.55
        (0, E1, 0.3, "rejected"),
    ],
)
def test_formula_and_threshold(matched, semantic_vec, expected_final, status):
    required = ["python", "sql", "fastapi", "docker", "pytorch", "kubernetes", "aws"]
    r = score_candidate(E1, semantic_vec, required, required[:matched])
    assert r["final_score"] == pytest.approx(min(1.0, expected_final), abs=1e-4)
    assert r["status"] == status


def test_missing_embedding_is_neutral_not_random():
    a = score_candidate(E1, None, ["python"], ["python"])
    b = score_candidate(E1, None, ["python"], ["python"])
    assert a == b and a["semantic"] == NEUTRAL_SEMANTIC


def test_batch_scoring_matches_one_by_one_and_order():
    rng = np.random.default_rng(0)
    job = rng.standard_normal(384).tolist()
    resumes = [ResumeFeatures(rng.standard_normal(384).tolist(), skills) for skills in (["python"], ["java"], [], ["python", "sql"])]
    batch = score_candidates(job, ["python", "sql"], resumes)
    singles = [score_candidate(job, r.embedding, ["python", "sql"], r.skills) for r in resumes]
    assert batch == singles
    assert batch[3]["coverage_vector"] == [1, 1] and batch[0]["missing_skills"] == ["sql"]


def test_duplicate_required_skills_counted_once():
    r = score_candidate(None, None, ["Python", "python ", "SQL"], ["python"])
    assert r["skill_score"] == 0.5 and r["coverage_vector"] == [1, 0]
