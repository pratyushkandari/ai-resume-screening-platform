-- =============================================================================
--  PostgreSQL schema + starter skill vocabulary.
--  Mirrors backend/app/models.py. Safe to run more than once (no DROP statements):
--    psql "$DATABASE_URL" -f sql/seed.sql
--  docker compose runs it automatically when the database volume is first created.
-- =============================================================================

-- Login accounts (recruiters and candidates). Emails are matched case-insensitively.
CREATE TABLE IF NOT EXISTS users (
  user_id   SERIAL PRIMARY KEY,
  name      TEXT NOT NULL,
  email     TEXT NOT NULL UNIQUE,
  password  TEXT NOT NULL,                       -- bcrypt hash
  role      TEXT NOT NULL DEFAULT 'candidate'    -- 'hr' | 'candidate'
);
CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users (lower(email));

-- Applicant profiles, one per email. Candidate uploads use the signed-in account's email.
CREATE TABLE IF NOT EXISTS candidates (
  candidate_id SERIAL PRIMARY KEY,
  full_name    TEXT,
  email        TEXT UNIQUE,
  phone        TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_candidates_email_lower ON candidates (lower(email));

-- Shared skill vocabulary scanned in every resume; recruiters' new skills are added here.
CREATE TABLE IF NOT EXISTS skills (
  skill_id       SERIAL PRIMARY KEY,
  skill_name     TEXT NOT NULL UNIQUE,           -- canonical lowercase name
  canonical_name TEXT
);

-- Job requisitions; only the creating recruiter can see their applicants.
CREATE TABLE IF NOT EXISTS jobs (
  job_id      SERIAL PRIMARY KEY,
  created_by  INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  embedding   JSONB                              -- 384 floats, NULL if the model was unavailable
);
CREATE INDEX IF NOT EXISTS idx_jobs_created_by ON jobs (created_by);

-- One uploaded file for one job, with extracted text and its embedding.
CREATE TABLE IF NOT EXISTS resumes (
  resume_id    SERIAL PRIMARY KEY,
  candidate_id INTEGER REFERENCES candidates(candidate_id) ON DELETE CASCADE,
  job_id       INTEGER REFERENCES jobs(job_id) ON DELETE SET NULL,
  filename     TEXT NOT NULL,
  upload_path  TEXT NOT NULL,                    -- relative to UPLOAD_DIR
  uploaded_at  TIMESTAMPTZ DEFAULT now(),
  raw_text     TEXT,
  parsed_json  JSONB,                            -- {"parsed": {name,email,phone}, "skills": [...]}
  embedding    JSONB
);
CREATE INDEX IF NOT EXISTS idx_resumes_job_id ON resumes (job_id);
CREATE INDEX IF NOT EXISTS idx_resumes_candidate_id ON resumes (candidate_id);

-- Skills found in each resume (many-to-many), with match confidence.
CREATE TABLE IF NOT EXISTS resume_skills (
  id         SERIAL PRIMARY KEY,
  resume_id  INTEGER REFERENCES resumes(resume_id) ON DELETE CASCADE,
  skill_id   INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
  confidence DOUBLE PRECISION DEFAULT 1.0,
  CONSTRAINT uix_resume_skill UNIQUE (resume_id, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_resume_skills_skill_id ON resume_skills (skill_id);

-- Skills required by each job (many-to-many), in display order (id).
CREATE TABLE IF NOT EXISTS job_skills (
  id             SERIAL PRIMARY KEY,
  job_id         INTEGER REFERENCES jobs(job_id) ON DELETE CASCADE,
  skill_id       INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
  required_level INTEGER DEFAULT 1,
  CONSTRAINT uix_job_skill UNIQUE (job_id, skill_id)
);

-- Snapshot saved by POST /api/jobs/{id}/rank ("Evaluate Candidates"); replaced on each run.
CREATE TABLE IF NOT EXISTS rankings (
  ranking_id SERIAL PRIMARY KEY,
  job_id     INTEGER REFERENCES jobs(job_id) ON DELETE CASCADE,
  resume_id  INTEGER REFERENCES resumes(resume_id) ON DELETE CASCADE,
  score      DOUBLE PRECISION NOT NULL,          -- composite score 0.0–1.0
  status     TEXT DEFAULT 'pending',             -- 'accepted' (>= 0.60) | 'rejected'
  created_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT uix_job_resume UNIQUE (job_id, resume_id)
);

-- Starter vocabulary. Every skill a recruiter adds to a job is added here too.
INSERT INTO skills (skill_name, canonical_name) VALUES
  ('python', 'python'), ('fastapi', 'fastapi'), ('docker', 'docker'), ('postgresql', 'postgresql'),
  ('sql', 'sql'), ('machine learning', 'machine learning'), ('react', 'react'), ('nlp', 'nlp'),
  ('pytorch', 'pytorch'), ('kubernetes', 'kubernetes'), ('redis', 'redis'), ('aws', 'aws'),
  ('git', 'git'), ('javascript', 'javascript'), ('typescript', 'typescript'), ('node.js', 'node.js'),
  ('ci/cd', 'ci/cd'), ('rest api', 'rest api'), ('tensorflow', 'tensorflow'), ('pandas', 'pandas'),
  ('numpy', 'numpy')
ON CONFLICT (skill_name) DO NOTHING;
