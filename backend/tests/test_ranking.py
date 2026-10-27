"""Unit tests for the scoring model in ``ml_utils``."""

import math
import random

import numpy as np
import pytest

from app.ml_utils import NEUTRAL_SEMANTIC, ResumeFeatures, normalize_skill, score_candidates, semantic_scores


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


def _reference_score(job_embedding, job_skills, features):
    """Plain one-candidate implementation of the documented formula, used as an oracle."""
    required = list(dict.fromkeys(normalize_skill(s) for s in job_skills if s and s.strip()))
    have = {normalize_skill(s) for s in features.skills if s and s.strip()}
    semantic = NEUTRAL_SEMANTIC
    vec = features.embedding
    if job_embedding and vec is not None and len(vec) == len(job_embedding) and any(job_embedding):
        dot = sum(a * b for a, b in zip(job_embedding, vec, strict=True))
        norm_job = math.sqrt(sum(a * a for a in job_embedding))
        norm_vec = math.sqrt(sum(b * b for b in vec)) or 1.0
        semantic = min(1.0, max(0.0, (dot / (norm_job * norm_vec) + 1) / 2))
    matched = [s for s in required if s in have]
    skill_score = len(matched) / len(required) if required else NEUTRAL_SEMANTIC
    final = min(1.0, 0.7 * skill_score + 0.3 * semantic + (0.05 if skill_score >= 0.7 else 0.0))
    return {
        "semantic": semantic,
        "skill_score": round(skill_score, 4),
        "final_score": final,
        "status": "accepted" if final >= 0.6 else "rejected",
        "matched_skills": sorted(matched),
        "missing_skills": [s for s in required if s not in have],
        "coverage_vector": [1 if s in have else 0 for s in required],
        "coverage_percent": round(100 * len(matched) / len(required)) if required else 0,
    }


@pytest.mark.parametrize("job_skills", [["Python", "docker", "SQL", "python ", "Machine-Learning", "c++"], []])
def test_vectorized_scoring_matches_reference_formula(job_skills):
    # Guards the optimized implementation: messy skill spellings, duplicates, blank
    # names, and missing, zero or wrong-length embeddings must score exactly as the
    # plain formula does.
    rng = np.random.default_rng(42)
    pick = random.Random(42)
    pool = ["python", "PYTHON", "Docker", "sql", "machine learning", "machine_learning", "C++", "java", "", "  ", "rust"]
    job = rng.standard_normal(384).tolist()
    resumes = []
    for i in range(400):
        embedding = [None, [0.0] * 384, [1.0, 2.0]][i % 3] if i % 10 == 0 else rng.standard_normal(384).tolist()
        resumes.append(ResumeFeatures(embedding, pick.sample(pool, k=pick.randint(0, 7))))
    for got, features in zip(score_candidates(job, job_skills, resumes), resumes, strict=True):
        want = _reference_score(job, job_skills, features)
        assert got["semantic"] == pytest.approx(want["semantic"], abs=1e-4)
        assert got["final_score"] == pytest.approx(want["final_score"], abs=1e-4)
        assert {k: got[k] for k in want if k not in ("semantic", "final_score")} == {
            k: v for k, v in want.items() if k not in ("semantic", "final_score")
        }
