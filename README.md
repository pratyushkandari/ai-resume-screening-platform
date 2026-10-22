# TalentFlow — AI Resume Screening & Candidate Ranking

A full-stack application that ranks job applicants. Recruiters post jobs with
required skills; candidates upload resumes (PDF, DOCX, TXT); the backend extracts
text, contacts and skills, embeds the text with a sentence-transformer model, and
scores every applicant with a transparent formula. Recruiters see ranked
candidates, skill gaps and comparison charts for **their own** jobs.

**Stack:** FastAPI · SQLAlchemy 2 · PostgreSQL (SQLite for dev/tests) · Redis (optional) ·
sentence-transformers `all-MiniLM-L6-v2` · NumPy · React 18 · Vite · Chart.js · Docker · Nginx

Documentation: [Architecture](docs/ARCHITECTURE.md) · [API reference](docs/API_REFERENCE.md) ·
[Deployment (AWS EC2 + Docker)](docs/DEPLOYMENT.md) · [Operations runbook](docs/RUNBOOK.md) ·
[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

**Deployment:** production runs on an AWS EC2 instance with Docker Compose (Nginx,
FastAPI, PostgreSQL, Redis). Kubernetes and Render templates are included as alternatives.

---

## How scoring works

```
skill_score = |required skills found in the resume| / |required skills|
semantic    = (cos(job_embedding, resume_embedding) + 1) / 2        # 0.5 if an embedding is missing
final       = min(1, 0.70 · skill_score + 0.30 · semantic + 0.05 · [skill_score ≥ 0.70])
status      = "accepted" (shown as Shortlisted) if final ≥ 0.60, else "rejected" (shown as Under Review)
```

* Skills are matched against a shared vocabulary (seed skills plus every skill a
  recruiter has used) with boundary-aware regular expressions, a small alias table
  (`k8s` → kubernetes, `Postgres` → postgresql, …) and stricter rules for
  ambiguous names (`R`, `C`, `Go`).
* The job embedding comes from its title and description; the resume embedding
  from the extracted text.
* One implementation (`ml_utils.score_candidates`) is used by both the live
  dashboard and the saved rankings snapshot.
* The weights and threshold are hand-chosen defaults, not learned from data. See
  [ARCHITECTURE.md](docs/ARCHITECTURE.md#limitations) for the known limitations.

## Roles and access

| Role | Can do |
|---|---|
| Candidate | Register, browse open jobs, upload one or more versions of their own resume to a job (the dashboard shows their best-scoring version) |
| Recruiter (`hr`) | Everything a candidate can, plus create jobs and view/evaluate/download candidates **for jobs they created** |

Recruiter self-registration requires the access code in `HR_SIGNUP_CODE`.
If it is empty, recruiter sign-up is disabled and accounts are created with
`python manage.py create-user --role hr`.

## Quick start (local development)

Requirements: Python 3.11+, Node.js 20+. PostgreSQL and Redis are optional.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
cp ../.env.example .env          # Windows: copy ..\.env.example .env
# edit .env: set JWT_SECRET_KEY and HR_SIGNUP_CODE; set DATABASE_URL (or delete it to use backend/dev.db SQLite)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000     # API docs: http://127.0.0.1:8000/docs

# 2. Frontend (second terminal)
cd frontend
npm ci
npm run dev                      # http://localhost:5173 (proxies /api to the backend)
```

The embedding model (~90 MB) downloads from Hugging Face on first start. Until it
is available, semantic scores are neutral (0.5), the dashboard says so, and
**Evaluate Candidates** fills in the missing embeddings once the model is loaded.

## Docker Compose

```bash
cp .env.example .env    # set POSTGRES_PASSWORD, JWT_SECRET_KEY, HR_SIGNUP_CODE
docker compose up --build
```

UI on http://localhost, API docs on http://localhost/docs. The backend image
bakes in the embedding model, so containers start without internet access.
The same stack runs in production on AWS EC2; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
for the instance setup, HTTPS, updates, backups and the upgrade steps from version 2.

## Tests and quality checks

```bash
cd backend && pytest -q                     # 157 tests, in-memory SQLite, no network needed
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db pytest -q   # same suite on PostgreSQL
cd frontend && npm run lint && npm run build
```

The suite covers validation, password hashing and JWTs, an authorization matrix
for every recruiter endpoint (anonymous / candidate / other recruiter / owner),
applicant identity (a candidate cannot attach resumes to someone else), uploads
(type, signature, size, batch limits, path traversal, clean-up on failure),
parsing edge cases (PDF, DOCX headers, UTF-16 text, ambiguous skills), the
scoring formula, query counts (no N+1), the Redis cache and rate limiter (with a
fake Redis), configuration safety and observability endpoints. CI runs it on
SQLite and PostgreSQL with warnings treated as errors.

`python benchmark_scoring.py` micro-benchmarks the scoring function only (not
the API or database); use a load-testing tool for end-to-end throughput.

## Project layout

```
backend/
  app/
    main.py            app factory: middleware, routers, startup
    config.py          settings from environment (fail-fast on invalid/unsafe values)
    schema.py          creates missing tables at start-up (retried by /readyz)
    db.py, models.py   SQLAlchemy engine and 8 ORM tables
    auth.py            password hashing, JWT, role + ownership checks
    ml_utils.py        text extraction, contact/skill parsing, embeddings, scoring
    services/          ingestion, ranking/summary, skill vocabulary
    routers/           auth, jobs, resumes, rankings, ops (health/metrics)
    cache.py           optional Redis client (summary cache, rate-limit counters)
    rate_limit.py      login/registration throttling
    observability.py   request IDs, latency headers, Prometheus metrics
  manage.py            create-user / reset-password
  tests/               pytest suite
frontend/src/          React app (components/, hooks/useUpload.js, api.js, session.js)
sql/seed.sql           idempotent PostgreSQL schema + starter skills
k8s/, render.yaml      deployment templates (see RUNBOOK)
```

## License

MIT — see [LICENSE](LICENSE).
