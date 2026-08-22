# backend/tests/test_ranking.py

import io
import pytest
from app import ml_utils


def test_cosine_similarity_calculation():
    """Verify vector cosine math."""
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    vec_c = [0.0, 1.0, 0.0]

    assert ml_utils.cosine_sim(vec_a, vec_b) == 1.0
    assert ml_utils.cosine_sim(vec_a, vec_c) == 0.0
    assert ml_utils.cosine_sim([], []) == 0.0


def test_composite_scoring_engine():
    """Verify composite weighting: 70% skill + 30% semantic + bonus."""
    job_skills = ["python", "docker", "sql"]
    cand_skills = ["python", "docker", "sql"]  # 100% skill match

    eval_res = ml_utils.calculate_candidate_match(
        job_embedding=[0.5] * 384,
        resume_embedding=[0.5] * 384,
        job_skill_names=job_skills,
        resume_skill_names=cand_skills
    )

    assert eval_res["skill_score"] == 1.0
    assert eval_res["semantic"] == 1.0
    assert eval_res["final_score"] == 1.0
    assert eval_res["status"] == "accepted"
    assert eval_res["coverage_percent"] == 100


def test_vectorized_candidate_ranking():
    """Verify batch vectorized matrix ranking produces accurate match metrics."""
    job_vec = [0.5] * 384
    cand_matrix = [[0.5] * 384, [0.0] * 384]
    job_skills = ["python", "docker"]
    cand_skills = [["python", "docker"], ["java"]]

    ranked = ml_utils.vectorized_candidate_ranking(
        job_embedding=job_vec,
        resume_embeddings=cand_matrix,
        job_skill_names=job_skills,
        resume_skill_list=cand_skills
    )

    assert len(ranked) == 2
    assert ranked[0]["final_score"] > ranked[1]["final_score"]
    assert ranked[0]["status"] == "accepted"
    assert ranked[1]["status"] == "rejected"


def test_ranking_and_summary_flow(client, hr_user):
    """End-to-end test: Create Job -> Upload Resume -> Rank -> Get Summary."""
    # 1. Create Job
    job_res = client.post("/api/jobs", data={
        "title": "Full Stack Lead",
        "description": "Python, React, Docker, FastAPI",
        "skills": "python, react, docker, fastapi",
        "created_by": hr_user["user"].user_id
    }, headers=hr_user["headers"])
    job_id = job_res.json()["job_id"]

    # 2. Upload Resume
    resume_text = b"John Engineer\nEmail: john.eng@example.com\nExpert in Python, React, Docker, and FastAPI."
    upload_res = client.post(
        "/api/resumes/upload",
        files={"file": ("resume_john.txt", io.BytesIO(resume_text), "text/plain")},
        data={"job_id": str(job_id)}
    )
    assert upload_res.status_code == 200

    # 3. Generate Rankings
    rank_res = client.post(f"/api/jobs/{job_id}/rank", headers=hr_user["headers"])
    assert rank_res.status_code == 200
    assert rank_res.json()["ranked"] >= 1

    # 4. Get Summary
    summary_res = client.get(
        f"/api/jobs/{job_id}/summary",
        params={"user_id": hr_user["user"].user_id, "role": "hr"},
        headers=hr_user["headers"]
    )
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["job_id"] == job_id
    assert len(summary_data["candidates"]) >= 1
    assert summary_data["candidates"][0]["status"] == "accepted"
