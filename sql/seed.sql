-- =============================================================================
--  AI Resume Screening & Ranking System - Production Database Schema
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

-- -----------------------------------------------------------------------------
-- BASE SKILL DICTIONARY (Standard Technical Taxonomy)
-- -----------------------------------------------------------------------------
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
('kubernetes', 'kubernetes'),
('redis', 'redis'),
('aws', 'aws'),
('git', 'git'),
('javascript', 'javascript'),
('typescript', 'typescript'),
('node.js', 'node.js'),
('ci/cd', 'ci/cd'),
('rest api', 'rest api'),
('tensorflow', 'tensorflow'),
('pandas', 'pandas'),
('numpy', 'numpy')
ON CONFLICT (skill_name) DO NOTHING;
