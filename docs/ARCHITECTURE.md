# Architecture

## Overview

```
Browser (React SPA)
   │  HTTPS, JSON / multipart, Authorization: Bearer <JWT>
   ▼
Nginx (Docker) or Vite dev proxy  ── serves the SPA, forwards /api to the API
   ▼
FastAPI app (backend/app)
   ├─ middleware: request ID + latency + metrics, security headers, CORS allow-list
   ├─ routers:   auth · jobs · resumes · rankings · ops
   ├─ services:  ingestion · ranking · skills
   ├─ ml_utils:  extraction, parsing, embeddings (MiniLM, in-process), scoring
   ├─ PostgreSQL via SQLAlchemy (SQLite in dev/tests)
   ├─ Redis (optional): summary cache + rate-limit counters
   └─ upload folder (UPLOAD_DIR): original resume files
```

It is a single deployable service. The embedding model runs inside the API
process and loads in a background thread at start-up.

## Main flows

### Resume upload (`POST /api/resumes/upload`, `/batch-upload`)
1. Authenticated user, existing job, at most `MAX_BATCH_FILES` files.
2. Each file: extension allow-list (`.pdf .docx .txt`), content-signature check,
   streamed to disk with a size cap (`MAX_UPLOAD_MB`), stored as
   `<random>_<original name>` inside `UPLOAD_DIR`.
3. Text extraction (pypdf / python-docx / encoding-aware TXT). Unreadable,
   encrypted or image-only files fail with a per-file error and are deleted.
4. All readable texts of the request are embedded in **one** batched model call.
5. Each resume is stored inside its own savepoint: applicant lookup, resume row,
   skill links. One failure never leaves partial rows or blocks the batch. The
   applicant is the signed-in account for candidate uploads, and the email in the
   document for recruiter uploads (see the API reference).
6. One commit (if it fails, the stored files are deleted); the job's cached summary
   is invalidated.

### Dashboard (`GET /api/jobs/{id}/summary`)
1. Recruiter must own the job.
2. Cache-aside: Redis key `job:summary:{id}` (TTL `SUMMARY_CACHE_TTL_SECONDS`).
3. On a miss: the job's skills, all resumes with candidates and skills are loaded
   with a **constant number of queries** (eager `selectinload`, verified by a test).
4. `score_candidates` scores every resume (one matrix-vector product for all cosines).
5. One entry per candidate (their best resume), skill coverage counts, top skills
   among this job's applicants, `last_ranked_at`, and `semantic_available`.

### Evaluate (`POST /api/jobs/{id}/rank`)
Locks the job row (PostgreSQL `SELECT ... FOR UPDATE`, so two simultaneous clicks
run one after the other), computes any embeddings that were missing at upload time
(model unavailable then), re-scores all resumes, replaces the job's `rankings`
snapshot and invalidates the cache. `GET /api/jobs/{id}/rankings` returns the snapshot.

## Scoring

See the formula in the [README](../README.md#how-scoring-works). Constants live at
the top of `ml_utils.py`. A missing embedding contributes a neutral 0.5 rather
than a random vector, and the response flags it (`semantic_available: false`).

## Data model

| Table | Purpose | Key constraints |
|---|---|---|
| users | login identities, `role` = hr / candidate | unique email |
| jobs | requisitions, `created_by` → users, embedding | FK SET NULL |
| skills | shared vocabulary (canonical lowercase) | unique name |
| job_skills | job ↔ skill | unique (job_id, skill_id) |
| candidates | applicant profiles parsed from resumes | unique email |
| resumes | file path (relative), text, parsed JSON, embedding, job | FK candidate CASCADE, job SET NULL |
| resume_skills | resume ↔ skill with match confidence | unique (resume_id, skill_id) |
| rankings | saved evaluation snapshot | unique (job_id, resume_id) |

The schema is created by `Base.metadata.create_all` at start-up (only missing
tables; `app/schema.py`, retried by `/readyz` if the database was down) and by
`sql/seed.sql` for Docker; both define the same columns, constraints and indexes
(including `lower(email)` indexes used by login and applicant lookup). At start-up,
skills that differ only by case/spelling (e.g. `Docker`/`docker`) are merged.

## Security model

* Passwords: bcrypt (cost 12), max 72 bytes, strength rules; no plaintext fallback.
* Tokens: HS256 JWT with `sub`, `role`, `exp`; the role used for authorization is
  always re-read from the database. Default lifetime 60 minutes.
* Authorization: `require_role(["hr"])` plus `get_owned_job` on every recruiter
  endpoint, including file download. Client-supplied role/user ids are ignored.
* Recruiter sign-up requires `HR_SIGNUP_CODE` (constant-time comparison).
* Login and registration are rate limited per client IP (Redis or in-process).
  The client IP comes from `X-Forwarded-For` only when the request arrives from a
  proxy on a private network (`FORWARDED_ALLOW_IPS`), and Nginx overwrites that
  header, so clients cannot spoof their IP to bypass the limit.
* A failed login always runs one bcrypt check (a dummy hash for unknown emails), so
  response time does not reveal which emails have accounts.
* Production (`APP_ENV=production`) refuses to start without a private
  `JWT_SECRET_KEY`.
* CORS allow-list, `nosniff`/`DENY`/`no-referrer` headers on the API and a
  Content-Security-Policy on the SPA (Nginx).
* Uploads: allow-list + signature check + size/count limits; filenames are
  reduced to a base name and prefixed with a random token; downloads are
  attachments and require the owning recruiter.

## Observability

* `X-Request-ID` (propagated or generated) and `X-Response-Time-MS` on every response.
* Middleware order: CORS → security headers → tracing → routes. Unexpected errors are
  logged with the request ID and returned as JSON 500s inside that chain, so they
  still carry CORS headers and the browser can show the message.
* `/metrics`: request counts and latency sums per route template, cache hits/misses,
  model-loaded gauge (per process).
* `/healthz` liveness; `/readyz` checks the database and, when
  `REQUIRE_EMBEDDING_MODEL` is on (default in production), the model.

## Limitations

* Weights (0.7 / 0.3 / 0.05) and threshold (0.6) are not tuned on labelled data;
  there is no evaluation set yet.
* Skill matching is lexical: aliases cover common variants only, and context
  ("no experience with Java") is not understood.
* MiniLM truncates long inputs, so long resumes are embedded mostly from their beginning.
* Ingestion is synchronous; very large batches are bounded by `MAX_BATCH_FILES`
  rather than handled by a background queue.
* Uploaded files live on a filesystem path; multiple replicas need shared
  (ReadWriteMany) storage or a move to object storage.
* No schema migration tool: new columns require a migration step (e.g. Alembic).
* Account emails are not verified, so an account only proves control of the
  password, not of the email address.
