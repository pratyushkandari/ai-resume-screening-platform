-- =============================================================================
--  AI Resume Screening & Ranking System - Production Database Schema & Seed
-- =============================================================================

DROP TABLE IF EXISTS rankings CASCADE;
DROP TABLE IF EXISTS job_skills CASCADE;
DROP TABLE IF EXISTS resume_skills CASCADE;
DROP TABLE IF EXISTS resumes CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS hr_users CASCADE;

-- -----------------------------------------------------------------------------
-- 1. USERS TABLE (Single Source of Truth for Auth & RBAC)
-- -----------------------------------------------------------------------------
CREATE TABLE users (
  user_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password TEXT NOT NULL,               -- Bcrypt hashed password
  role TEXT NOT NULL DEFAULT 'candidate', -- 'hr' or 'candidate'
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_email ON users (lower(email));

-- -----------------------------------------------------------------------------
-- 2. CANDIDATES TABLE (Applicant Profile Metadata)
-- -----------------------------------------------------------------------------
CREATE TABLE candidates (
  candidate_id SERIAL PRIMARY KEY,
  full_name TEXT,
  email TEXT UNIQUE,
  phone TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_candidates_email ON candidates (lower(email));

-- -----------------------------------------------------------------------------
-- 3. SKILLS TABLE (Normalized Skill Registry)
-- -----------------------------------------------------------------------------
CREATE TABLE skills (
  skill_id SERIAL PRIMARY KEY,
  skill_name TEXT UNIQUE NOT NULL,
  canonical_name TEXT,                  -- Normalized lowercase version
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_skills_lower_name ON skills (lower(skill_name));

-- -----------------------------------------------------------------------------
-- 4. JOBS TABLE (Recruitment Openings)
-- -----------------------------------------------------------------------------
CREATE TABLE jobs (
  job_id SERIAL PRIMARY KEY,
  created_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  embedding JSONB                       -- 384-dim dense semantic vector (SentenceTransformer)
);

CREATE INDEX idx_jobs_created_by ON jobs (created_by);

-- -----------------------------------------------------------------------------
-- 5. RESUMES TABLE (Uploaded Documents & Extracted Metadata)
-- -----------------------------------------------------------------------------
CREATE TABLE resumes (
  resume_id SERIAL PRIMARY KEY,
  candidate_id INTEGER REFERENCES candidates(candidate_id) ON DELETE CASCADE,
  job_id INTEGER REFERENCES jobs(job_id) ON DELETE SET NULL,
  filename TEXT NOT NULL,
  upload_path TEXT NOT NULL,
  uploaded_at TIMESTAMPTZ DEFAULT now(),
  raw_text TEXT,                        -- Extracted plain text (PDF/DOCX/TXT)
  parsed_json JSONB,                    -- Structured parsed data (contacts, skill list)
  embedding JSONB                       -- 384-dim dense semantic vector
);

CREATE INDEX idx_resumes_job_id ON resumes (job_id);
CREATE INDEX idx_resumes_candidate_id ON resumes (candidate_id);

-- -----------------------------------------------------------------------------
-- 6. RESUME_SKILLS (Many-to-Many: Resumes <-> Skills)
-- -----------------------------------------------------------------------------
CREATE TABLE resume_skills (
  id SERIAL PRIMARY KEY,
  resume_id INTEGER REFERENCES resumes(resume_id) ON DELETE CASCADE,
  skill_id INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
  confidence DOUBLE PRECISION DEFAULT 1.0,
  UNIQUE(resume_id, skill_id)
);

-- -----------------------------------------------------------------------------
-- 7. JOB_SKILLS (Many-to-Many: Jobs <-> Skills)
-- -----------------------------------------------------------------------------
CREATE TABLE job_skills (
  id SERIAL PRIMARY KEY,
  job_id INTEGER REFERENCES jobs(job_id) ON DELETE CASCADE,
  skill_id INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
  required_level INTEGER DEFAULT 1,
  UNIQUE(job_id, skill_id)
);

-- -----------------------------------------------------------------------------
-- 8. RANKINGS TABLE (Evaluated Candidate Match Scores)
-- -----------------------------------------------------------------------------
CREATE TABLE rankings (
  ranking_id SERIAL PRIMARY KEY,
  job_id INTEGER REFERENCES jobs(job_id) ON DELETE CASCADE,
  resume_id INTEGER REFERENCES resumes(resume_id) ON DELETE CASCADE,
  score DOUBLE PRECISION NOT NULL,      -- Final composite match score (0.0–1.0)
  status TEXT DEFAULT 'pending',        -- 'accepted' (score >= 0.6) or 'rejected'
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (job_id, resume_id)
);

CREATE INDEX idx_rankings_job_score ON rankings (job_id, score DESC);

-- =============================================================================
-- SAMPLE SEED DATA
-- =============================================================================

-- 1. SEED USERS (Password for all demo accounts: "password123")
-- bcrypt hash for "password123"
INSERT INTO users (name, email, password, role) VALUES
('Alice Recruiter', 'alice@company.com', '$2b$12$4mU8e/l4k1pI4o35eBfVqOD4O6t.p6hX9I2eE8fLzN6BwLh2jZ5uq', 'hr'),
('Bob Talent', 'bob@company.com', '$2b$12$4mU8e/l4k1pI4o35eBfVqOD4O6t.p6hX9I2eE8fLzN6BwLh2jZ5uq', 'hr'),
('Pratyush Candidate', 'pratyush@example.com', '$2b$12$4mU8e/l4k1pI4o35eBfVqOD4O6t.p6hX9I2eE8fLzN6BwLh2jZ5uq', 'candidate');

-- 2. SEED CANDIDATES
INSERT INTO candidates (full_name, email, phone) VALUES
('Pratyush Kandari', 'pratyush@example.com', '+91-90000-00001'),
('Ravi Sharma', 'ravi@example.com', '+91-90000-00002'),
('Kavya Iyer', 'kavya@example.com', '+91-90000-00003'),
('Ananya Gupta', 'ananya@example.com', '+91-90000-00004');

-- 3. SEED SKILLS
INSERT INTO skills (skill_name, canonical_name) VALUES
('python', 'python'),
('fastapi', 'fastapi'),
('docker', 'docker'),
('postgresql', 'postgresql'),
('sql', 'sql'),
('machine learning', 'machine learning'),
('react', 'react'),
('nlp', 'nlp'),
('pytorch', 'pytorch'),
('kubernetes', 'kubernetes');

-- 4. SEED JOBS
INSERT INTO jobs (created_by, title, description) VALUES
(1, 'Machine Learning Engineer', 'Looking for ML Engineer skilled in Python, PyTorch, NLP, Docker, and FastAPI'),
(1, 'Backend Developer', 'Experienced Backend Developer with PostgreSQL, SQL, FastAPI, and Docker');

-- 5. SEED JOB SKILLS
INSERT INTO job_skills (job_id, skill_id)
SELECT 1, skill_id FROM skills WHERE skill_name IN ('python', 'machine learning', 'nlp', 'pytorch', 'fastapi', 'docker');

INSERT INTO job_skills (job_id, skill_id)
SELECT 2, skill_id FROM skills WHERE skill_name IN ('python', 'sql', 'postgresql', 'fastapi', 'docker');

-- 6. SEED RESUMES
INSERT INTO resumes (candidate_id, job_id, filename, upload_path, raw_text, parsed_json) VALUES
(1, 1, 'resume_pratyush.pdf', 'uploads/resume_pratyush.pdf', 'Pratyush resume with Python, PyTorch, NLP, and FastAPI skills', '{"skills": ["python", "pytorch", "nlp", "fastapi"], "email": "pratyush@example.com"}'),
(2, 1, 'resume_ravi.pdf', 'uploads/resume_ravi.pdf', 'Ravi resume with Python, Machine Learning, and Docker skills', '{"skills": ["python", "machine learning", "docker"], "email": "ravi@example.com"}'),
(3, 2, 'resume_kavya.pdf', 'uploads/resume_kavya.pdf', 'Kavya resume with SQL, PostgreSQL, Python, and FastAPI skills', '{"skills": ["sql", "postgresql", "python", "fastapi"], "email": "kavya@example.com"}'),
(4, 2, 'resume_ananya.pdf', 'uploads/resume_ananya.pdf', 'Ananya resume with Docker, React, and Python skills', '{"skills": ["docker", "react", "python"], "email": "ananya@example.com"}');

-- 7. SEED RESUME SKILLS
INSERT INTO resume_skills (resume_id, skill_id, confidence)
SELECT 1, skill_id, 0.95 FROM skills WHERE skill_name IN ('python', 'pytorch', 'nlp', 'fastapi');

INSERT INTO resume_skills (resume_id, skill_id, confidence)
SELECT 2, skill_id, 0.90 FROM skills WHERE skill_name IN ('python', 'machine learning', 'docker');

INSERT INTO resume_skills (resume_id, skill_id, confidence)
SELECT 3, skill_id, 0.95 FROM skills WHERE skill_name IN ('sql', 'postgresql', 'python', 'fastapi');

INSERT INTO resume_skills (resume_id, skill_id, confidence)
SELECT 4, skill_id, 0.85 FROM skills WHERE skill_name IN ('docker', 'react', 'python');

-- 8. SEED RANKINGS
INSERT INTO rankings (job_id, resume_id, score, status) VALUES
(1, 1, 0.88, 'accepted'),
(1, 2, 0.72, 'accepted'),
(2, 3, 0.92, 'accepted'),
(2, 4, 0.58, 'rejected');
