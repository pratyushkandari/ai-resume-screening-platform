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
- "Evaluate" re-scores a job, fills in embeddings and semantic scores that were missing
  at upload time and saves a snapshot of the ranking
- A graded evaluation set for the ranking and a k6 load test of the dashboard
- Candidate and recruiter roles with JWT authentication; recruiters need an access code to sign up
- Rate limits on login, registration and uploads, a Redis cache for dashboards,
  Prometheus metrics and health checks

## How ranking works

```text
skill_score = required skills found in the resume / required skills
semantic    = (cosine(job_embedding, resume_embedding) + 1) / 2      # 0.5 if an embedding is missing
final       = 0.1 * skill_score + 0.9 * semantic
```

An applicant with a final score of 0.74 or more is shortlisted, and the dashboard calls
0.80 and above a strong fit. Skills are matched against a shared vocabulary (the seed
list plus every skill a recruiter has used) with word-boundary rules, so `java` does not
match `javascript`, and "Go beyond targets" is not the Go language. The job embedding
comes from its title and description, the resume embedding from the extracted text, and
the semantic score is computed once, at upload (or by "Evaluate"), and stored.

The weights and the cut-off were tuned on a graded evaluation set (see
[Ranking evaluation](#ranking-evaluation)). Meaning gets most of the weight because a
skill list is easy to game: a resume that lists every keyword without the experience
scores 1.0 on skills. Without the embedding model every semantic score is a neutral 0.5,
so nobody reaches the cut-off until the model is loaded and "Evaluate" runs.

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
   in one model call, and each resume's semantic score is stored. Every resume is saved
   in its own savepoint, so one bad file never affects the others. The job's cached
   dashboard is invalidated.
2. **Dashboard** (`routers/rankings.py`, `services/ranking.py`): three queries load the
   resumes' stored scores and skills (not their text or embeddings), they are scored
   with `ml_utils.score_candidates` and reduced to each applicant's best resume. The
   response lists the best 100 with totals over every applicant and is cached in Redis.
3. **Evaluate:** fills in missing embeddings and scores, re-scores every resume and
   replaces the job's snapshot in the `rankings` table.

The embedding model runs inside the API process and loads in a background thread at
start-up. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) covers the data model and the
security model in more detail.

## Ranking evaluation

`backend/evaluation/` holds a small graded dataset and a script that measures how well
the ranking agrees with it.

**Dataset.** 5 jobs (`jobs.json`: backend, frontend, machine learning, DevOps, data
analyst) and 50 plain-text resumes of 88 to 170 words (`resumes/`). For every job there
are strong, partial and irrelevant fits. The set also has people who combine two
disciplines, aliases (`k8s`, `Postgres`, `ReactJS`), skills described in prose without
the keyword, three keyword-stuffed resumes with no real experience, two with explicit
negations ("no experience with X"), two juniors and five people from unrelated
professions.

**Labels.** `labels.csv` grades all 250 (job, resume) pairs:

| Grade | Meaning |
|---|---|
| 3 | Strong fit: hands-on experience with most of what the job needs, at roughly the right level. Would interview. |
| 2 | Good fit: relevant experience but missing some requirements, or an adjacent role who could ramp up quickly. Would probably interview. |
| 1 | Weak fit: some transferable skills, but would not normally be shortlisted. |
| 0 | Not relevant. |

Demonstrated experience counts and a bare keyword list counts for very little; explicit
negations are respected; equivalent wording (`Postgres`, `k8s`) counts when the
experience behind it is real. The resumes are synthetic, written for this evaluation,
and each pair was graded once against this rubric before any scores were computed.
There is one set of labels (no second grader, so no agreement figure), and the same
project wrote the dataset and the scoring code. Treat the results as a sanity and
regression check, not a benchmark.

**Method.** Every resume goes through the production code once per job (text
extraction, skill matching, MiniLM embeddings, `score_candidates`), which gives each pair
a skill score and a semantic score; the setups below only recombine those two numbers.
The main metric is NDCG@10 (gain `2^grade - 1`); Precision@5 counts grades 2 and 3 as
relevant; both are averaged over the five jobs. Shortlist F1 checks the cut-off. The
tuned setup comes from a grid search (skill weight 0 to 1 in steps of 0.05, bonus 0 or
0.05, cut-off 0.30 to 0.90) inside 5-fold cross-validation over resumes (seed 42), so
every resume is scored with values chosen on the other 40.

```bash
make eval          # or: cd backend && python -m evaluation.evaluate (needs the model)
```

| Setup | Skill / semantic weight | Shortlist cut-off | NDCG@10 | Precision@5 | Shortlist F1 |
|---|---|---|---|---|---|
| Skills only | 1.00 / 0.00 | - | 0.890 | 0.800 | - |
| Semantic only | 0.00 / 1.00 | - | 0.906 | 0.960 | - |
| Previous weights | 0.70 / 0.30, +0.05 bonus | 0.60 | 0.890 | 0.880 | 0.744 |
| **Tuned, held out (5-fold CV)** | chosen per fold (skill 0.05 to 0.30) | chosen per fold (0.72 to 0.75) | **0.894** | **0.960** | **0.817** |
| Tuned on all 50 resumes (production) | 0.10 / 0.90 | 0.74 | 0.930 | 0.960 | 0.880 |

The held-out row is the estimate to quote. The last row is scored on the resumes it was
tuned on, so it is optimistic; it is there to show where the production values come from.

What the results show:

- The tuned weights fix the top of the list. With the previous weights, keyword-stuffed
  resumes ranked #3 for backend and #5 for machine learning, and a weak fit #4 for
  DevOps. With the production weights only that DevOps weak fit remains in a top 5 (#3).
  On held-out resumes Precision@5 rose from 0.88 to 0.96 and shortlist F1 from 0.74 to 0.82.
- NDCG@10 barely moved (0.890 to 0.894), and per job it is mixed: backend (0.835 to
  0.938) and DevOps (0.869 to 0.880) improved, machine learning (0.893 to 0.856) and data
  analyst (0.859 to 0.795) got worse. With 50 resumes these differences are within noise.
- Semantic-only ranks as well as the tuned mix on this set. Skills keep 10% because every
  training fold chose a small non-zero weight and because matched and missing skills are
  what the dashboard explains to recruiters, not because they measurably improve ranking here.

## Load test

`loadtest/dashboard.js` is a k6 test of `GET /api/jobs/{id}/summary`, the dashboard
endpoint, against the Docker Compose stack through Nginx.

```bash
docker compose up -d --build
# Register a recruiter (UI, or POST /api/register with HR_SIGNUP_CODE), then:
docker compose exec backend python manage.py seed-load-test --email recruiter@example.com --resumes 10000
```

`seed-load-test` creates a job and adds generated resumes through the same ingestion
code as the API (text extraction, skill matching, embeddings, stored scores), 250 at a
time. 10,000 took about 14 minutes on the machine below.

```bash
docker run --rm -i --add-host=host.docker.internal:host-gateway \
  -e BASE_URL=http://host.docker.internal -e EMAIL=recruiter@example.com -e PASSWORD='...' \
  -e JOB_ID=1 -e VUS=10 -e DURATION=30s \
  grafana/k6:0.57.0 run - < loadtest/dashboard.js
```

Cached runs use the stack as it is: every request after the first is a Redis hit. For
uncached runs, stop Redis (`docker compose stop redis`; the API keeps serving without a
cache), use `-e VUS=2 -e DURATION=90s`, and start it again afterwards.

Measured on a laptop (Intel i5-12500H, Docker Desktop on Windows 11) with one Uvicorn
worker, the real model and 10,000 applicants in one job. "Before" is commit `a626e22`.
Latency is k6's `http_req_duration`, which also includes the one login request.
Response size is the uncompressed JSON; Nginx gzips it.

| Run | p50 | p95 | Requests/s | Response size |
|---|---|---|---|---|
| Uncached, 2 users, before | 13.2 s | 19.8 s | 0.14 | 3.27 MB |
| Uncached, 2 users, after | 1.10 s | 1.44 s | 1.39 | 33.7 KB |
| Cached, 10 users, before | 4.87 s | 8.99 s | 1.8 | 3.27 MB |
| Cached, 10 users, after | 132 ms | 265 ms | 64.9 | 33.7 KB |
| Uncached, 10 users, after | 4.97 s | 20.4 s | 0.83 | 33.7 KB |

**The bottleneck.** Profiling one uncached request showed the time going into loading
data, not scoring. Every request read all 10,000 embeddings (384 numbers each, stored
as JSON) from PostgreSQL: about 4.2 s to fetch, 2.1 s to decode and 1.6 s to build ORM
objects. The response then listed all 10,000 candidates. At 3.3 MB, even cache hits took
seconds under load, and the browser stopped responding while it rendered all 10,000
candidates.

**The fix.**

1. Each resume's semantic score is stored when it is uploaded or evaluated. Neither
   embedding changes afterwards, so recomputing the cosine on every request was wasted
   work. The summary now reads a few small columns, and embeddings only for resumes that
   have no stored score yet.
2. The summary returns the best 100 candidates plus counts over every applicant (total,
   shortlisted, strong fits, average score), which is what the dashboard shows.
   `/rankings` still returns every resume.
3. The coverage chart draws the top 10 candidates, and the doughnut chart uses the totals.

An uncached request now spends about 0.4 s in Python (240 ms loading rows, 90 ms
scoring). With 10,000 applicants the dashboard renders 100 cards and all four charts
without blocking the page.

The remaining limit is the last row of the table. Scoring is CPU-bound and the API runs
one Uvicorn worker, so 10 concurrent uncached requests queue (p95 20 s). The cache
absorbs repeated loads; more workers would be the next step.

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
pytest -q                                                    # 227 tests, in-memory SQLite, no network
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db pytest -q
ruff check .

cd frontend
npm run lint && npm run build
```

The backend suite covers input validation, password hashing and JWTs (expired, tampered
and malformed tokens), an authorization matrix for every recruiter endpoint, applicant
identity rules, upload limits and file handling, document parsing edge cases, the
scoring formula (including a check of the optimized implementation against a plain
reference version), query counts, the Redis cache and rate limiter (against fakeredis),
the health endpoints, the `manage.py` commands and the evaluation script. CI runs it on
SQLite and PostgreSQL with warnings treated as errors and keeps the JUnit and coverage
reports as artifacts.

Two end-to-end suites run against the Docker Compose stack with the real model: API
tests over HTTP (`make e2e`) and browser tests with Playwright (`make e2e-browser`).
[docs/TESTING.md](docs/TESTING.md) describes every suite, how to run it and the latest
results.

## Deployment

Production runs on a single AWS EC2 instance with Docker Compose. A timer on the server
deploys every commit on `main` that passed CI (`infra/auto-update/`).
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
  manage.py            create-user, reset-password and seed-load-test commands
  benchmark_scoring.py scoring micro-benchmark
  evaluation/          graded jobs and resumes, ranking metrics, make eval
  tests/               unit and integration tests (pytest)
  e2e/                 API end-to-end tests against a running stack
frontend/src/          React app: components/, hooks/useUpload.js, api.js, session.js
frontend/e2e/          browser tests (Playwright)
loadtest/dashboard.js  k6 load test of the dashboard endpoint
sql/seed.sql           PostgreSQL schema and starter skills (safe to re-run)
infra/auto-update/     server timer that deploys passing commits from main
k8s/, render.yaml      alternative deployment manifests
docs/                  architecture, API reference, deployment guide, runbook, testing
```

## Limitations

- The weights and the cut-off were tuned on 50 synthetic resumes with one set of labels,
  so the evaluation is a sanity check, not proof that the ranking generalizes.
- Skill matching is lexical: aliases cover common variants, and context such as
  "no experience with Java" is not understood.
- One Uvicorn worker serves the API, so uncached dashboards of very large jobs queue
  under concurrent load (see [Load test](#load-test)).
- MiniLM truncates long inputs, so long resumes are embedded mostly from their beginning.
- Uploads are processed while the request waits; there is no background queue.
- Resume files live on local disk, so several API instances need shared storage.
- There is no migration tool yet. Start-up adds `resumes.semantic_score`; other schema
  changes need a manual step.
- Candidates see the 50 newest open positions; the job list has no paging yet.

## License

[MIT](LICENSE)
