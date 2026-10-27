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
| Candidate | Register, browse open jobs (newest 50), upload one or more versions of their own resume to any job (the dashboard shows their best-scoring version) |
| Recruiter (`hr`) | Create jobs; view, evaluate, compare and download candidates **for jobs they created**. Through the API they can also upload resumes on applicants' behalf to those jobs (the web app does not offer this) |

Recruiter self-registration requires the access code in `HR_SIGNUP_CODE`.
If it is empty, recruiter sign-up is disabled and accounts are created with
`python manage.py create-user --role hr`. Login, registration and uploads are rate limited.

## Architecture and data flow

```
React SPA (Vite) ──/api──► Nginx (Docker) or Vite dev proxy ──► FastAPI (backend/app)
                                                                 ├─ routers/  HTTP, auth and ownership checks
                                                                 ├─ services/ ingestion · ranking · skills
                                                                 ├─ ml_utils  text extraction, parsing, embeddings, scoring
                                                                 ├─ PostgreSQL (SQLite in dev/tests) via SQLAlchemy
                                                                 ├─ Redis (optional): summary cache, rate-limit counters
                                                                 └─ UPLOAD_DIR: original resume files
```

1. **Upload** (`routers/resumes.py` → `services/ingestion.py`): the file is checked
   (extension, content signature, size), streamed to `UPLOAD_DIR`, its text extracted
   (pypdf / python-docx / TXT), contacts and vocabulary skills parsed, and all files of
   the request embedded in one model call. Each resume is saved in its own savepoint;
   the job's cached summary is invalidated.
2. **Dashboard** (`routers/rankings.py` → `services/ranking.py`): loads the job's
   skills and resumes in a constant number of queries, scores them with
   `ml_utils.score_candidates`, keeps each applicant's best resume and caches the
   result in Redis.
3. **Evaluate**: fills in embeddings that were missing at upload time, re-scores
   every resume and saves a snapshot in `rankings`.

Details, the data model and the security model: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## API

All routes are under `/api` except the operational ones. Full request/response
examples: [docs/API_REFERENCE.md](docs/API_REFERENCE.md); interactive docs at `/docs`.

| Method | Path | Who |
|---|---|---|
| POST | `/api/register`, `/api/login` | public (rate limited) |
| GET | `/api/me` | signed in |
| GET | `/api/jobs` | public |
| GET | `/api/jobs/mine` · POST `/api/jobs` | recruiter |
| POST | `/api/resumes/upload`, `/api/resumes/batch-upload` | candidate (any job) or recruiter (own jobs), rate limited |
| GET | `/api/resumes/{id}/download` | recruiter who owns the job |
| GET / POST / GET | `/api/jobs/{id}/summary` · `/rank` · `/rankings` | recruiter who owns the job |
| GET | `/healthz`, `/readyz`, `/metrics` | operations |

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

Shortcuts: `make help` (Linux/macOS/WSL), `./deploy.sh` or `.\deploy.ps1` (install,
test and build in one step).

## Configuration

Settings are read from environment variables, then `backend/.env` (local runs) or
`./.env` (Docker Compose). [`.env.example`](.env.example) documents each one;
invalid values stop start-up with a message naming the variable.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` (`production` in Compose) | `production` rejects a missing/published `JWT_SECRET_KEY` and requires the model for readiness |
| `DATABASE_URL` | `sqlite:///backend/dev.db` | PostgreSQL (`postgresql://…` or `postgresql+psycopg2://…`) or SQLite |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | — | Compose only: database container credentials |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional; the app runs without Redis |
| `JWT_SECRET_KEY` | random per process (dev) | Token signing key; required in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `HR_SIGNUP_CODE` | empty (recruiter sign-up off) | Access code for recruiter self-registration |
| `LOGIN_RATE_LIMIT_PER_MINUTE` / `REGISTER_RATE_LIMIT_PER_MINUTE` | `10` / `5` | Per client IP; `0` disables |
| `UPLOAD_RATE_LIMIT_PER_MINUTE` | `10` | Upload requests per account (a batch counts once); `0` disables |
| `UPLOAD_DIR` | `uploads` (relative to `backend/`) | Where resume files are stored |
| `MAX_UPLOAD_MB` / `MAX_BATCH_FILES` | `15` / `25` | Per-file size and per-request file count |
| `CORS_ORIGINS` | local dev origins | Comma-separated browser origins allowed to call the API |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local runs only (the Docker image bakes in MiniLM); `none` disables it |
| `REQUIRE_EMBEDDING_MODEL` | `true` in production, else `false` | `/readyz` returns 503 until the model is loaded |
| `SUMMARY_CACHE_TTL_SECONDS` | `300` | Dashboard cache lifetime in Redis |
| `FORWARDED_ALLOW_IPS` | private networks (Docker image) | Proxies trusted to set the client IP (read by Uvicorn) |
| `VITE_API_URL` | empty (same origin) | Frontend build: API origin when the UI is hosted separately |

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
cd backend && pytest -q                     # 165 tests, in-memory SQLite, no network needed
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db pytest -q   # same suite on PostgreSQL
cd frontend && npm run lint && npm run build
```

The suite covers validation, password hashing and JWTs, an authorization matrix
for every recruiter endpoint (anonymous / candidate / other recruiter / owner),
applicant identity (a candidate cannot attach resumes to someone else; a recruiter
cannot upload to another recruiter's job or rename an applicant), uploads (type,
signature, size, batch and rate limits, path traversal, unusual file names, clean-up on failure),
parsing edge cases (PDF, DOCX headers, UTF-16 text, ambiguous skills), the
scoring formula, query counts (no N+1), the Redis cache and rate limiter (with a
fake Redis), configuration safety and observability endpoints. CI runs it on
SQLite and PostgreSQL with warnings treated as errors. The frontend has no automated
tests or type checking; ESLint and the production build are its checks.

`python benchmark_scoring.py` micro-benchmarks the scoring function only (not
the API or database); use a load-testing tool for end-to-end throughput.

## Project layout

```
backend/
  app/
    main.py            FastAPI app: middleware, routers, start-up
    config.py          settings from environment (fail-fast on invalid/unsafe values)
    schema.py          creates missing tables at start-up (retried by /readyz)
    db.py, models.py   SQLAlchemy engine and 8 ORM tables
    auth.py            password hashing, JWT, role + ownership checks
    ml_utils.py        text extraction, contact/skill parsing, embeddings, scoring
    services/          ingestion, ranking/summary, skill vocabulary
    routers/           auth, jobs, resumes, rankings, ops (health/metrics)
    cache.py           optional Redis client (summary cache, rate-limit counters)
    rate_limit.py      login/registration (per IP) and upload (per account) throttling
    observability.py   request IDs, latency headers, Prometheus metrics
  manage.py            create-user / reset-password
  tests/               pytest suite
frontend/src/          React app (components/, hooks/useUpload.js, api.js, session.js)
sql/seed.sql           idempotent PostgreSQL schema + starter skills
k8s/, render.yaml      deployment templates (see RUNBOOK)
```

## License

MIT — see [LICENSE](LICENSE).
