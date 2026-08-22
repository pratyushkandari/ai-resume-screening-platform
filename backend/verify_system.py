# backend/verify_system.py
import os
import tempfile
from app import ml_utils, schemas, auth

def run_tests():
    print("=" * 60)
    print("[TEST SUITE] RUNNING COMPREHENSIVE BACKEND VERIFICATION")
    print("=" * 60)

    # 1. Auth Hash & Verify
    pw = "Secret123"
    hashed = auth.hash_password(pw)
    assert auth.verify_password(pw, hashed) is True, "Password verification failed"
    assert auth.verify_password("wrong", hashed) is False, "False positive in password verification"
    print("[PASSED] 1. Auth Hashing & Verification: SUCCESS")

    # 2. Text Extraction on TXT
    sample_text = "John Doe\njohn.doe@example.com\n+1-555-0199\nExperienced in Python, C++, Docker, PyTorch, and NLP."
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        f.write(sample_text)
        txt_path = f.name

    try:
        extracted = ml_utils.extract_text(txt_path)
        assert "Python" in extracted, "Text extraction failed"
        print("[PASSED] 2. Text Extraction (TXT/Generic): SUCCESS")
    finally:
        if os.path.exists(txt_path):
            os.unlink(txt_path)

    # 3. Contact Parsing
    contacts = ml_utils.parse_contacts(sample_text)
    assert contacts["email"] == "john.doe@example.com", f"Unexpected email: {contacts.get('email')}"
    assert "John Doe" in contacts["name"], f"Unexpected name: {contacts.get('name')}"
    print(f"[PASSED] 3. Contact Parser: SUCCESS -> {contacts}")

    # 4. Word-boundary Skill Extraction
    skills_registry = ["python", "c", "c++", "docker", "pytorch", "nlp", "r", "ai"]
    detected = ml_utils.extract_skills(sample_text, skills_registry)
    detected_names = [s[0] for s in detected]
    assert "python" in detected_names, "Python skill not detected"
    assert "c++" in detected_names, "C++ skill not detected"
    assert "r" not in detected_names, "False positive detected for 'r'"
    assert "ai" not in detected_names, "False positive detected for 'ai'"
    print(f"[PASSED] 4. Word-Boundary Skill Extractor: SUCCESS -> Detected: {detected_names}")

    # 5. Composite Scoring Engine
    job_skills = ["python", "pytorch", "nlp", "docker", "fastapi"]
    cand_skills = ["python", "pytorch", "docker"]
    job_emb = ml_utils.embed_text("Looking for ML Engineer skilled in Python, PyTorch, and Docker")
    cand_emb = ml_utils.embed_text("Experienced Python and PyTorch ML developer with Docker knowledge")

    match = ml_utils.calculate_candidate_match(
        job_embedding=job_emb,
        resume_embedding=cand_emb,
        job_skill_names=job_skills,
        resume_skill_names=cand_skills
    )

    assert 0.0 <= match["final_score"] <= 1.0, "Score out of range"
    assert match["status"] in ["accepted", "rejected"], "Invalid status"
    assert len(match["matched_skills"]) == 3, f"Unexpected matched skills count: {len(match['matched_skills'])}"
    assert len(match["missing_skills"]) == 2, f"Unexpected missing skills count: {len(match['missing_skills'])}"
    print(f"[PASSED] 5. Composite Scoring Engine: SUCCESS -> Score: {match['final_score']} (Status: {match['status']})")

    print("=" * 60)
    print("[ALL TESTS PASSED] SYSTEM IS FULLY FUNCTIONAL AND VERIFIED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
