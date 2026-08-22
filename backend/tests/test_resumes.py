# backend/tests/test_resumes.py

import io
import os
import pytest
from app import ml_utils


def test_contact_parsing_regex():
    """Verify name, email, and phone parsing from resume text."""
    sample_text = (
        "Alice Johnson\n"
        "alice.j@domain.org\n"
        "+1 (555) 234-5678\n"
        "Senior Software Engineer with 6 years experience."
    )
    parsed = ml_utils.parse_contacts(sample_text)
    assert parsed["email"] == "alice.j@domain.org"
    assert "Alice Johnson" in parsed["name"]
    assert "234-5678" in parsed["phone"]


def test_word_boundary_skill_extraction():
    """Verify word-boundary skill extraction without false positives."""
    text = "We program in Python and C++ to design AI neural networks using PyTorch and Docker containers."
    canonical = ["python", "c", "c++", "ai", "docker", "pytorch", "r", "go", "java"]

    detected = ml_utils.extract_skills(text, canonical)
    detected_skills = [s[0] for s in detected]

    assert "python" in detected_skills
    assert "c++" in detected_skills
    assert "docker" in detected_skills
    assert "pytorch" in detected_skills
    assert "r" not in detected_skills
    assert "go" not in detected_skills


def test_upload_resume_api(client, hr_user):
    """Test POST /api/resumes/upload handles file upload, text extraction, and DB records."""
    # Create a job first
    job_res = client.post("/api/jobs", data={
        "title": "ML Platform Engineer",
        "description": "Python, Docker, PyTorch machine learning engineering scope.",
        "skills": "python, docker, pytorch",
        "created_by": hr_user["user"].user_id
    }, headers=hr_user["headers"])
    job_id = job_res.json()["job_id"]

    # Mock resume file content
    file_content = b"Candidate Resume\nEmail: candidate.ml@example.com\nPhone: +1-555-9001\nSkills: Python, Docker, PyTorch, Kubernetes"
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/resumes/upload",
        files={"file": ("resume_candidate.txt", file_obj, "text/plain")},
        data={"job_id": str(job_id)}
    )

    assert response.status_code == 200
    data = response.json()
    assert "resume_id" in data
    assert "candidate_id" in data
    assert data["job_id"] == job_id


def test_upload_resume_invalid_extension_fails(client, hr_user):
    """Test POST /api/resumes/upload rejects unsupported file extensions."""
    file_obj = io.BytesIO(b"binary payload")
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("malicious_script.exe", file_obj, "application/octet-stream")},
        data={"job_id": "1"}
    )
    assert response.status_code == 400


def test_upload_resume_empty_file_fails(client, hr_user):
    """Test POST /api/resumes/upload rejects empty (0-byte) files."""
    file_obj = io.BytesIO(b"")
    response = client.post(
        "/api/resumes/upload",
        files={"file": ("empty_resume.txt", file_obj, "text/plain")},
        data={"job_id": "1"}
    )
    assert response.status_code == 400


def test_batch_upload_resumes_api(client, hr_user):
    """Test POST /api/resumes/batch-upload handles multiple files concurrently."""
    job_res = client.post("/api/jobs", data={
        "title": "Data Engineering Specialist",
        "description": "SQL, Python, Spark data engineering specialist position.",
        "skills": "sql, python, spark",
        "created_by": hr_user["user"].user_id
    }, headers=hr_user["headers"])
    job_id = job_res.json()["job_id"]

    file1 = ("resume_a.txt", io.BytesIO(b"Alex Smith\nalex@test.com\nPython and SQL expert with 5 years experience."), "text/plain")
    file2 = ("resume_b.txt", io.BytesIO(b"Beth Jones\nbeth@test.com\nSpark and Python developer with 4 years experience."), "text/plain")

    response = client.post(
        "/api/resumes/batch-upload",
        files=[("files", file1), ("files", file2)],
        data={"job_id": str(job_id)}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 2
    assert data["successful"] == 2
    assert len(data["results"]) == 2
