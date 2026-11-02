"""The offline ranking evaluation: metrics, dataset integrity, tuning and cross-validation."""

import math

import pytest

from app.ml_utils import ACCEPT_THRESHOLD, SKILL_WEIGHT, ResumeFeatures, score_candidates
from evaluation.evaluate import (
    PRODUCTION,
    Setup,
    cross_validate,
    final_score,
    finals_for,
    load_dataset,
    ranking_quality,
    tune,
)
from evaluation.metrics import dcg, f1_score, ndcg_at_k, precision_at_k


def test_dcg_and_ndcg_known_values():
    assert dcg([3, 2, 0]) == pytest.approx(7 + 3 / math.log2(3))
    assert ndcg_at_k([3, 2, 0], 10) == 1.0  # already in the ideal order
    assert ndcg_at_k([0, 2, 3], 10) == pytest.approx((3 / math.log2(3) + 7 / 2) / (7 + 3 / math.log2(3)))
    assert ndcg_at_k([0, 0, 0], 10) == 0.0  # nothing relevant to rank
    assert ndcg_at_k([0, 3], 1) == 0.0  # the only strong fit is below the cut-off


def test_precision_at_k_and_f1():
    assert precision_at_k([3, 1, 2, 0, 2, 3], 5) == 0.6
    assert precision_at_k([2], 5) == 0.2  # missing slots count as misses
    assert f1_score([True, True, False, False], [True, False, True, False]) == 0.5
    assert f1_score([False, False], [True, True]) == 0.0


def test_dataset_is_complete_and_graded_on_the_rubric():
    jobs, resumes, grades = load_dataset()
    assert len(jobs) == 5 and len(resumes) == 50
    assert all({"id", "title", "description", "skills"} <= job.keys() for job in jobs)
    assert set(grades) == {(job["id"], rid) for job in jobs for rid in resumes}
    assert set(grades.values()) <= {0, 1, 2, 3}
    for job in jobs:  # enough good candidates for Precision@5 to mean something
        assert sum(grades[(job["id"], rid)] >= 2 for rid in resumes) >= 5
    assert all(len(text.split()) >= 50 for text in resumes.values())


def test_evaluation_formula_matches_production_scoring():
    job, close, far = [1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 1.0, 0.0]
    features = [ResumeFeatures(close, ["python"]), ResumeFeatures(far, ["python", "sql"])]
    for result in score_candidates(job, ["python", "sql"], features):
        expected = final_score(result["skill_score"], result["semantic"], PRODUCTION.skill_weight)
        assert result["final_score"] == pytest.approx(expected, abs=1e-4)
        assert result["status"] == ("accepted" if expected >= ACCEPT_THRESHOLD else "rejected")
    assert PRODUCTION == Setup(SKILL_WEIGHT, 0.0, ACCEPT_THRESHOLD)


def _synthetic(resume_count=10):
    """One job whose grades follow the skill score exactly, while the semantic score points the other way."""
    resume_ids = [f"r{i:02d}" for i in range(resume_count)]
    grades = {("job", rid): i % 4 for i, rid in enumerate(resume_ids)}
    scores = {("job", rid): (grade / 3, 1 - grade / 3) for (_, rid), grade in grades.items()}
    return ["job"], resume_ids, scores, grades


def test_tune_follows_the_signal_that_matches_the_labels():
    job_ids, resume_ids, scores, grades = _synthetic()
    setup = tune(job_ids, resume_ids, scores, grades)
    # Any skill weight above 0.5 ranks perfectly here; ties go to the value nearest the previous 0.70.
    assert setup.skill_weight > 0.5
    finals = finals_for(setup, list(grades), scores)
    assert ranking_quality(job_ids, resume_ids, finals, grades) == (1.0, 0.8)  # only 4 relevant of 10
    assert 0.3 <= setup.threshold <= 0.9


def test_cross_validation_scores_every_pair_exactly_once():
    job_ids, resume_ids, scores, grades = _synthetic(resume_count=20)
    finals, thresholds, chosen = cross_validate(job_ids, resume_ids, scores, grades)
    assert set(finals) == set(thresholds) == set(grades)
    assert len(chosen) == 5


def test_signal_scores_stops_without_the_embedding_model():
    from evaluation.evaluate import signal_scores

    jobs, resumes, _ = load_dataset()
    with pytest.raises(SystemExit, match="embedding model is not available"):
        signal_scores(jobs, resumes)


def test_main_prints_the_comparison_table(fake_model, capsys):
    from evaluation.evaluate import main

    main()  # the whole pipeline on the real dataset, with the bag-of-words stand-in model
    out = capsys.readouterr().out
    assert "Ranking quality: 5 jobs x 50 resumes" in out
    for row in ("| Skills only |", "| Semantic only |", "| Previous hand-picked weights | 0.70 / 0.30 |",
                "| Cross-validated tuning (held out) |", f"| Production (tuned on all resumes) | {SKILL_WEIGHT:.2f} / "):
        assert row in out
    assert out.count("  fold ") == 5 and f"production uses {SKILL_WEIGHT:.2f}, no bonus, {ACCEPT_THRESHOLD:.2f}" in out


def test_main_refuses_incomplete_labels_or_weights_that_do_not_add_up(fake_model, monkeypatch):
    from evaluation import evaluate

    jobs, resumes, grades = load_dataset()
    incomplete = dict(grades)
    incomplete.pop(next(iter(incomplete)))
    monkeypatch.setattr(evaluate, "load_dataset", lambda: (jobs, resumes, incomplete))
    with pytest.raises(SystemExit, match="labels.csv has no grade for 1 pairs"):
        evaluate.main()
    monkeypatch.setattr(evaluate, "load_dataset", lambda: (jobs, resumes, grades))
    monkeypatch.setattr(evaluate, "SEMANTIC_WEIGHT", 0.5)
    with pytest.raises(SystemExit, match="must add up to 1"):
        evaluate.main()
