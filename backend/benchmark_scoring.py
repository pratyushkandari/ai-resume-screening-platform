"""Micro-benchmark of the scoring function (``ml_utils.score_candidates``).

What it measures: CPU time to score N in-memory candidates (random 384-d vectors
and random skill lists) against one job. What it does NOT measure: database
loading, HTTP, text extraction or model inference. Use a load-testing tool
(k6, Locust) against the API for end-to-end numbers.

    python benchmark_scoring.py            # 1,000 and 10,000 candidates
    python benchmark_scoring.py 50000
"""

from __future__ import annotations

import random
import sys
import time

import numpy as np

from app.ml_utils import EMBEDDING_DIM, ResumeFeatures, embed_batch, score_candidates

SKILLS_POOL = [
    "python", "c++", "docker", "kubernetes", "fastapi", "react", "postgresql", "redis", "pytorch",
    "transformers", "aws", "gcp", "grpc", "graphql", "sql", "linux", "git", "ci/cd", "rest api", "nlp",
]
JOB_SKILLS = ["python", "docker", "pytorch", "fastapi", "postgresql", "kubernetes"]


def _unit(rng: np.random.Generator) -> list:
    """A random unit-length vector shaped like a real embedding."""
    v = rng.standard_normal(EMBEDDING_DIM)
    return (v / np.linalg.norm(v)).tolist()


def bench_scoring(n: int, runs: int = 20) -> None:
    """Time ``score_candidates`` on ``n`` synthetic resumes and print p50/p95 latency."""
    rng = np.random.default_rng(42)
    random.seed(42)
    job = _unit(rng)
    resumes = [ResumeFeatures(_unit(rng), random.sample(SKILLS_POOL, k=random.randint(2, 7))) for _ in range(n)]
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        score_candidates(job, JOB_SKILLS, resumes)
        timings.append((time.perf_counter() - start) * 1000)
    p50, p95 = np.percentile(timings, [50, 95])
    print(f"score_candidates  N={n:>7,}  p50={p50:8.2f} ms  p95={p95:8.2f} ms  (~{n / (p50 / 1000):,.0f} candidates/s, single thread)")


def bench_embeddings(n: int = 64) -> None:
    """Time one batched embedding call (skipped when the model is unavailable)."""
    texts = [f"Software engineer {i} with Python, Docker and PyTorch experience building APIs." for i in range(n)]
    start = time.perf_counter()
    vectors = embed_batch(texts)
    elapsed = (time.perf_counter() - start) * 1000
    if vectors and vectors[0] is None:
        print("embed_batch       skipped: embedding model unavailable (install sentence-transformers / allow download)")
    else:
        print(f"embed_batch       N={n}  {elapsed:.1f} ms  ({n / (elapsed / 1000):.1f} docs/s, includes first-call model load)")


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:]] or [1_000, 10_000]
    for size in sizes:
        bench_scoring(size)
    bench_embeddings()
