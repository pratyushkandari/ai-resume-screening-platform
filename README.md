# TalentFlow

[![CI](https://github.com/pratyushkandari/ai-resume-screening-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/pratyushkandari/ai-resume-screening-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

TalentFlow screens and ranks job applicants. A recruiter posts a job with the skills
it needs, candidates upload their resumes, and the API scores every applicant on two
things: how many of the required skills the resume covers, and how close the resume is
to the job description in meaning (sentence embeddings). Recruiters only see applicants
for the jobs they created.

- **Backend:** FastAPI, SQLAlchemy 2, PostgreSQL (SQLite for development and tests), Redis, sentence-transformers (`all-MiniLM-L6-v2`), NumPy
- **Frontend:** React 18, Vite, React Router, Chart.js
- **Infrastructure:** Docker, Nginx, Docker Compose (production on AWS EC2), Kubernetes and Render manifests, GitHub Actions

## Features

- Resume upload (PDF, DOCX, TXT), one file or a batch of up to 25, with a result per file
- Text, contact and skill extraction, including DOCX headers, UTF-16 text files and
  common aliases (`k8s`, `Postgres`, `sklearn`)
- A dashboard per job: ranked applicants, matched and missing skills, four charts,
  side-by-side comparison and resume download
- "Evaluate" re-scores a job, fills in embeddings that were missing at upload time and
  saves a snapshot of the ranking
- Candidate and recruiter roles with JWT authentication; recruiters need an access code to sign up
- Rate limits on login, registration and uploads, a Redis cache for dashboards,
  Prometheus metrics and health checks

## How ranking works

```text
skill_score = required skills found in the resume / required skills
semantic    = (cosine(job_embedding, resume_embedding) + 1) / 2      # 0.5 if an embedding is missing
final       = min(1, 0.7 * skill_score + 0.3 * semantic + (0.05 if skill_score >= 0.7 else 0))
```

An applicant with a final score of 0.60 or more is shortlisted. Skills are matched
against a shared vocabulary (the seed list plus every skill a recruiter has used) with
word-boundary rules, so `java` does not match `javascript`, and "Go beyond targets" is
not the Go language. The job embedding comes from its title and description, the resume
embedding from the extracted text. The weights are hand-picked defaults rather than
learned from data; see [Limitations](#limitations).

All cosine similarities for a job come from a single NumPy matrix-vector product. On one
core of a laptop CPU (Intel i5-12500H), `score_candidates` ranks 1,000 applicants in
about 13 ms and 10,000 in about 150 ms. You can reproduce this with
`python benchmark_scoring.py` in `backend/`; it measures the scoring function only, not
the database or HTTP.

## Architecture

```text
React SPA ──/api──> Nginx (Docker) or the Vite dev proxy ──> FastAPI (backend/app)
                                                               ├── routers/   HTTP, auth and ownership checks
                                                               ├── services/  ingestion, ranking, skills
                                                               ├── ml_utils   extraction, parsing, embeddings, scoring
                                                               ├── PostgreSQL through SQLAlchemy
                                                               ├── Redis (optional): dashboard cache, rate-limit counters
                                                               └── UPLOAD_DIR: the original resume files
```

1. **Upload** (`routers/resumes.py`, `services/ingestion.py`): each file is checked
   (extension, content signature, size) and streamed to `UPLOAD_DIR`. Its text is
   extracted, contacts and skills are parsed, and all files in the request are embedded
   in one model call. Every resume is saved in its own savepoint, so one bad file never
   affects the others. The job's cached dashboard is invalidated.
2. **Dashboard** (`routers/rankings.py`, `services/ranking.py`): the job's skills and
   resumes are loaded in a fixed number of queries, scored with
   `ml_utils.score_candidates`, reduced to each applicant's best resume and cached in Redis.
3. **Evaluate:** fills in missing embeddings, re-scores every resume and replaces the
   job's snapshot in the `rankings` table.

The embedding model runs inside the API process and loads in a background thread at
start-up. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) covers the data model and the
security model in more detail.

## Getting started

You need Python 3.11+ and Node.js 20+. PostgreSQL and Redis are optional for local
development.

### Run locally

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env            # then set JWT_SECRET_KEY and HR_SIGNUP_CODE
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend, in a second terminal
cd frontend
npm ci
npm run dev                        # http://localhost:5173, proxies /api to port 8000
```

Without a `DATABASE_URL` the API uses a SQLite file (`backend/dev.db`). The embedding
model (about 90 MB) downloads on first start. Until it is available, semantic scores are
neutral (0.5), the dashboard says so, and "Evaluate Candidates" fills them in later.

`make help` (Linux, macOS, WSL), `./deploy.sh` and `.\deploy.ps1` wrap the same steps.

### Run with Docker Compose

```bash
cp .env.example .env               # set POSTGRES_PASSWORD, JWT_SECRET_KEY and HR_SIGNUP_CODE
docker compose up --build
```

The UI is at http://localhost and the API docs at http://localhost/docs. The backend
image includes the embedding model, so the containers start without internet access.
Compose runs the API in production mode.

## Configuration

Settings come from environment variables, then `backend/.env` for local runs or `./.env`
for Docker Compose. [`.env.example`](.env.example) lists all of them. An invalid value
stops the API at start-up with a message that names the variable.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` (`production` in Compose) | Production refuses to start without a private `JWT_SECRET_KEY` and waits for the model before reporting ready |
| `DATABASE_URL` | SQLite file `backend/dev.db` | `postgresql://...` or `sqlite:///...` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | none | Compose only: credentials for the database container |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional. Without Redis there is no dashboard cache and rate limits are per process |
| `JWT_SECRET_KEY` | random per process in development | Signs access tokens; required in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `HR_SIGNUP_CODE` | empty, which disables recruiter sign-up | Access code for recruiter registration |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Per client IP; `0` disables |
| `REGISTER_RATE_LIMIT_PER_MINUTE` | `5` | Per client IP; `0` disables |
| `UPLOAD_RATE_LIMIT_PER_MINUTE` | `10` | Upload requests per account (a batch counts once); `0` disables |
| `UPLOAD_DIR` | `uploads`, relative to `backend/` | Where resume files are stored |
| `MAX_UPLOAD_MB`, `MAX_BATCH_FILES` | `15`, `25` | Size limit per file and file limit per request |
| `CORS_ORIGINS` | local development origins | Comma-separated browser origins allowed to call the API |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local runs only (the Docker image ships MiniLM); `none` turns the model off |
| `REQUIRE_EMBEDDING_MODEL` | `true` in production | `/readyz` returns 503 until the model has loaded |
| `SUMMARY_CACHE_TTL_SECONDS` | `300` | How long a dashboard stays cached in Redis |
| `FORWARDED_ALLOW_IPS` | private networks (set in the image) | Proxies allowed to pass the client IP to Uvicorn |
| `VITE_API_URL` | empty (same origin) | Frontend build: the API origin when the UI is hosted separately |

## API

Interactive documentation is served at `/docs`. Request and response examples are in
[docs/API_REFERENCE.md](docs/API_REFERENCE.md).

| Method | Path | Access |
|---|---|---|
| POST | `/api/register`, `/api/login` | Public, rate limited |
| GET | `/api/me` | Signed-in users |
| GET | `/api/jobs` | Public |
| GET | `/api/jobs/mine` | Recruiters |
| POST | `/api/jobs` | Recruiters |
| POST | `/api/resumes/upload`, `/api/resumes/batch-upload` | Candidates (any job) and recruiters (their own jobs), rate limited |
| GET | `/api/resumes/{resume_id}/download` | The recruiter who owns the job |
| GET | `/api/jobs/{job_id}/summary` | The recruiter who owns the job |
| POST | `/api/jobs/{job_id}/rank` | The recruiter who owns the job |
| GET | `/api/jobs/{job_id}/rankings` | The recruiter who owns the job |
| GET | `/healthz`, `/readyz`, `/metrics` | Operations |

## Tests

```bash
cd backend
pytest -q                                                    # 167 tests, in-memory SQLite, no network
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db pytest -q
ruff check .

cd frontend
npm run lint && npm run build
```

The backend suite covers input validation, password hashing and JWTs, an authorization
matrix for every recruiter endpoint, applicant identity rules, upload limits and file
handling, document parsing edge cases, the scoring formula (including a check of the
optimized implementation against a plain reference version), query counts, the Redis
cache and rate limiter (against fakeredis) and the health endpoints. CI runs it on SQLite
and PostgreSQL with warnings treated as errors. The frontend has no automated tests;
ESLint and the production build are its checks.

## Deployment

Production runs on a single AWS EC2 instance with Docker Compose.
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) walks through the instance, HTTPS, updates and
backups, and [docs/RUNBOOK.md](docs/RUNBOOK.md) covers configuration and common
incidents. Kubernetes manifests (`k8s/`, with a HorizontalPodAutoscaler) and a Render
blueprint (`render.yaml`) are included as starting points for other setups.

## Project structure

```text
backend/
  app/
    main.py            FastAPI app: middleware, routers, start-up
    config.py          settings from the environment, validated at start-up
    schema.py          creates missing tables at start-up (retried by /readyz)
    db.py, models.py   SQLAlchemy engine and the 8 tables
    auth.py            password hashing, JWT, role and ownership checks
    ml_utils.py        text extraction, contact and skill parsing, embeddings, scoring
    services/          ingestion, ranking, skill vocabulary
    routers/           auth, jobs, resumes, rankings, ops
    cache.py           Redis client (dashboard cache, rate-limit counters)
    rate_limit.py      per-IP and per-account rate limits
    observability.py   request IDs, latency headers, Prometheus metrics
  manage.py            create-user and reset-password commands
  benchmark_scoring.py scoring micro-benchmark
  tests/
frontend/src/          React app: components/, hooks/useUpload.js, api.js, session.js
sql/seed.sql           PostgreSQL schema and starter skills (safe to re-run)
k8s/, render.yaml      alternative deployment manifests
docs/                  architecture, API reference, deployment guide, runbook
```

## Limitations

- The score weights (0.7, 0.3, 0.05) and the 0.6 threshold are not tuned on labelled data.
- Skill matching is lexical: aliases cover common variants, and context such as
  "no experience with Java" is not understood.
- MiniLM truncates long inputs, so long resumes are embedded mostly from their beginning.
- Uploads are processed while the request waits; there is no background queue.
- Resume files live on local disk, so several API instances need shared storage.
- There is no migration tool yet; schema changes need a manual step.
- Candidates see the 50 newest open positions; the job list has no paging yet.

## License

[MIT](LICENSE)
