"""Measure how well the ranking agrees with graded labels, and tune its weights.

Run from the ``backend`` folder (needs the embedding model; about 90 MB is downloaded on first use)::

    python -m evaluation.evaluate

Every resume in ``evaluation/resumes`` is scored against every job in ``jobs.json``
with the production code: text extraction, skill matching, MiniLM embeddings and
``score_candidates``. That gives each (job, resume) pair a skill score and a semantic
score once; the setups compared below only recombine those two numbers.

Tuned weights are cross-validated: the resumes are split into 5 folds and every
resume is scored with weights (and a shortlist threshold) chosen on the other 4
folds, so no resume helps choose the weights it is scored with.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

from app.ml_utils import (
    ACCEPT_THRESHOLD,
    SEMANTIC_WEIGHT,
    SKILL_WEIGHT,
    ResumeFeatures,
    embed_batch,
    embedding_model,
    extract_skills,
    extract_text,
    normalize_skill,
    score_candidates,
)

from .metrics import RELEVANT_GRADE, f1_score, ndcg_at_k, precision_at_k

DATA_DIR = Path(__file__).resolve().parent
FOLDS = 5
SEED = 42
WEIGHT_GRID = [i / 20 for i in range(21)]  # skill weight 0.00 to 1.00; the semantic weight is the rest
THRESHOLD_GRID = [i / 100 for i in range(30, 91)]
# The previous formula added this bonus once 70% of the required skills were found.
BONUS_MIN_SKILL_SCORE = 0.70

Pair = Tuple[str, str]  # (job id, resume id)


@dataclass(frozen=True)
class Setup:
    """One way to combine the skill and semantic scores into a final score."""

    skill_weight: float
    bonus: float = 0.0
    threshold: Optional[float] = None  # shortlist cut-off, when the setup is used to shortlist


# Hand-picked values the project used before this evaluation, kept for comparison.
PREVIOUS = Setup(skill_weight=0.70, bonus=0.05, threshold=0.60)
PRODUCTION = Setup(skill_weight=SKILL_WEIGHT, threshold=ACCEPT_THRESHOLD)
BONUS_GRID = [0.0, PREVIOUS.bonus]


def final_score(skill: float, semantic: float, skill_weight: float, bonus: float = 0.0) -> float:
    """``score_candidates``' formula with adjustable weights (they add up to 1) and the old optional bonus."""
    extra = bonus if skill >= BONUS_MIN_SKILL_SCORE else 0.0
    return min(1.0, skill_weight * skill + (1 - skill_weight) * semantic + extra)


def load_dataset() -> Tuple[List[dict], Dict[str, str], Dict[Pair, int]]:
    """Return the jobs, resume texts by id, and grades by (job id, resume id)."""
    jobs = json.loads((DATA_DIR / "jobs.json").read_text(encoding="utf-8"))
    resumes = {path.stem: extract_text(path) for path in sorted((DATA_DIR / "resumes").glob("*.txt"))}
    with open(DATA_DIR / "labels.csv", newline="", encoding="utf-8") as fh:
        grades = {(row["job_id"], row["resume_id"]): int(row["grade"]) for row in csv.DictReader(fh)}
    return jobs, resumes, grades


def signal_scores(jobs: List[dict], resumes: Dict[str, str]) -> Dict[Pair, Tuple[float, float]]:
    """Skill score and semantic score of every (job, resume) pair, from the production code.

    Raises:
        SystemExit: The embedding model cannot be loaded (semantic scores would all be 0.5).
    """
    if embedding_model.get() is None:
        raise SystemExit(f"The embedding model is not available: {embedding_model.last_error}")
    ids = sorted(resumes)
    vocabulary = sorted({normalize_skill(skill) for job in jobs for skill in job["skills"]})
    found = {rid: [name for name, _ in extract_skills(resumes[rid], vocabulary)] for rid in ids}
    resume_vectors = embed_batch([resumes[rid] for rid in ids])
    # Same text the API embeds when a recruiter creates a job.
    job_vectors = embed_batch([f"{job['title']}\n{job['description']}" for job in jobs])
    features = [ResumeFeatures(vector, found[rid]) for rid, vector in zip(ids, resume_vectors, strict=True)]
    scores = {}
    for job, job_vector in zip(jobs, job_vectors, strict=True):
        for rid, result in zip(ids, score_candidates(job_vector, job["skills"], features), strict=True):
            scores[(job["id"], rid)] = (result["skill_score"], result["semantic"])
    return scores


def finals_for(setup: Setup, pairs: Sequence[Pair], scores: Dict[Pair, Tuple[float, float]]) -> Dict[Pair, float]:
    """Final score of each pair under ``setup``."""
    return {pair: final_score(*scores[pair], setup.skill_weight, setup.bonus) for pair in pairs}


def ranking_quality(
    job_ids: Sequence[str], resume_ids: Sequence[str], finals: Dict[Pair, float], grades: Dict[Pair, int]
) -> Tuple[float, float]:
    """Mean NDCG@10 and Precision@5 over the jobs when each job ranks ``resume_ids`` by ``finals``.

    Ties are broken by resume id so every run gives the same ranking.
    """
    ndcg, precision = [], []
    for job_id in job_ids:
        ranked = sorted(resume_ids, key=lambda rid: (-finals[(job_id, rid)], rid))
        ranked_grades = [grades[(job_id, rid)] for rid in ranked]
        ndcg.append(ndcg_at_k(ranked_grades, 10))
        precision.append(precision_at_k(ranked_grades, 5))
    return mean(ndcg), mean(precision)


def shortlist_f1(finals: Dict[Pair, float], thresholds: Dict[Pair, float], grades: Dict[Pair, int]) -> float:
    """F1 of "shortlisted" (final score at or above the threshold) against "relevant" (grade 2 or 3)."""
    pairs = sorted(finals)
    return f1_score([finals[p] >= thresholds[p] for p in pairs], [grades[p] >= RELEVANT_GRADE for p in pairs])


def tune(
    job_ids: Sequence[str], resume_ids: Sequence[str], scores: Dict[Pair, Tuple[float, float]], grades: Dict[Pair, int]
) -> Setup:
    """Choose the weights with the best mean NDCG@10 on these resumes, then the threshold with the best F1.

    Ties prefer a higher Precision@5, then values closest to the previous hand-picked ones.
    """
    pairs = [(job_id, rid) for job_id in job_ids for rid in resume_ids]
    candidates = [Setup(weight, bonus) for weight in WEIGHT_GRID for bonus in BONUS_GRID]
    best = max(
        candidates,
        key=lambda s: (*ranking_quality(job_ids, resume_ids, finals_for(s, pairs, scores), grades),
                       -abs(s.skill_weight - PREVIOUS.skill_weight)),
    )
    finals = finals_for(best, pairs, scores)
    threshold = max(
        THRESHOLD_GRID,
        key=lambda t: (shortlist_f1(finals, dict.fromkeys(pairs, t), grades), -abs(t - PREVIOUS.threshold)),
    )
    return Setup(best.skill_weight, best.bonus, threshold)


def cross_validate(
    job_ids: Sequence[str], resume_ids: Sequence[str], scores: Dict[Pair, Tuple[float, float]], grades: Dict[Pair, int]
) -> Tuple[Dict[Pair, float], Dict[Pair, float], List[Setup]]:
    """Out-of-fold final scores and thresholds: each resume is scored by a setup tuned without it."""
    shuffled = sorted(resume_ids)
    random.Random(SEED).shuffle(shuffled)
    finals: Dict[Pair, float] = {}
    thresholds: Dict[Pair, float] = {}
    chosen = []
    for fold in range(FOLDS):
        held_out = shuffled[fold::FOLDS]
        setup = tune(job_ids, [rid for rid in resume_ids if rid not in held_out], scores, grades)
        chosen.append(setup)
        held_out_pairs = [(job_id, rid) for job_id in job_ids for rid in held_out]
        finals.update(finals_for(setup, held_out_pairs, scores))
        thresholds.update(dict.fromkeys(held_out_pairs, setup.threshold))
    return finals, thresholds, chosen


def main() -> None:
    """Score the dataset, compare the setups and print Markdown tables."""
    jobs, resumes, grades = load_dataset()
    job_ids = [job["id"] for job in jobs]
    resume_ids = sorted(resumes)
    pairs = [(job_id, rid) for job_id in job_ids for rid in resume_ids]
    missing = [pair for pair in pairs if pair not in grades]
    if missing:
        raise SystemExit(f"labels.csv has no grade for {len(missing)} pairs, for example {missing[0]}")
    scores = signal_scores(jobs, resumes)
    if abs(SKILL_WEIGHT + SEMANTIC_WEIGHT - 1) > 1e-9:
        raise SystemExit("SKILL_WEIGHT and SEMANTIC_WEIGHT in app/ml_utils.py must add up to 1")

    def weights(setup: Setup) -> str:
        """Table cell such as "0.10 / 0.90"."""
        return f"{setup.skill_weight:.2f} / {1 - setup.skill_weight:.2f}"

    previous_finals = finals_for(PREVIOUS, pairs, scores)
    production_finals = finals_for(PRODUCTION, pairs, scores)
    tuned_finals, tuned_thresholds, chosen = cross_validate(job_ids, resume_ids, scores, grades)
    rows = [
        ("Skills only", "1.00 / 0.00", "-", finals_for(Setup(1.0), pairs, scores), None),
        ("Semantic only", "0.00 / 1.00", "-", finals_for(Setup(0.0), pairs, scores), None),
        ("Previous hand-picked weights", weights(PREVIOUS), f"+{PREVIOUS.bonus:.2f} bonus, cut-off {PREVIOUS.threshold:.2f}",
         previous_finals, dict.fromkeys(pairs, PREVIOUS.threshold)),
        ("Cross-validated tuning (held out)", "chosen per fold", "chosen per fold", tuned_finals, tuned_thresholds),
        ("Production (tuned on all resumes)", weights(PRODUCTION), f"cut-off {PRODUCTION.threshold:.2f}",
         production_finals, dict.fromkeys(pairs, PRODUCTION.threshold)),
    ]

    print(f"Ranking quality: {len(job_ids)} jobs x {len(resume_ids)} resumes, metrics averaged over jobs\n")
    print("| Setup | Skill / semantic weight | Bonus and shortlist cut-off | NDCG@10 | Precision@5 | Shortlist F1 |")
    print("|---|---|---|---|---|---|")
    for name, weight_text, extras, finals, thresholds in rows:
        ndcg, precision = ranking_quality(job_ids, resume_ids, finals, grades)
        f1 = f"{shortlist_f1(finals, thresholds, grades):.3f}" if thresholds else "-"
        print(f"| {name} | {weight_text} | {extras} | {ndcg:.3f} | {precision:.3f} | {f1} |")

    print("\nSetups chosen on the training folds:")
    for fold, setup in enumerate(chosen, 1):
        print(f"  fold {fold}: skill weight {setup.skill_weight:.2f}, bonus {setup.bonus:.2f}, cut-off {setup.threshold:.2f}")
    final = tune(job_ids, resume_ids, scores, grades)
    print(f"Tuned on all {len(resume_ids)} resumes: skill weight {final.skill_weight:.2f}, bonus {final.bonus:.2f}, "
          f"cut-off {final.threshold:.2f} (production uses {SKILL_WEIGHT:.2f}, no bonus, {ACCEPT_THRESHOLD:.2f})")

    print("\nNDCG@10 per job, previous weights -> cross-validated tuning:")
    for job_id in job_ids:
        before = ranking_quality([job_id], resume_ids, previous_finals, grades)[0]
        after = ranking_quality([job_id], resume_ids, tuned_finals, grades)[0]
        print(f"  {job_id:<9} {before:.3f} -> {after:.3f}")

    for title, finals in (("Previous weights", previous_finals), ("Production", production_finals)):
        print(f"\n{title}: weak fits (grade 0-1) ranked in a job's top 5:")
        for job_id in job_ids:
            top = sorted(resume_ids, key=lambda rid: (-finals[(job_id, rid)], rid))[:5]
            for rank, rid in enumerate(top, 1):
                if grades[(job_id, rid)] < RELEVANT_GRADE:
                    skill, semantic = scores[(job_id, rid)]
                    print(f"  {job_id:<9} #{rank} {rid} grade {grades[(job_id, rid)]}: "
                          f"skill {skill:.2f}, semantic {semantic:.2f}, final {finals[(job_id, rid)]:.2f}")


if __name__ == "__main__":
    main()
