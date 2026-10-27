# API reference

Interactive docs: `http://127.0.0.1:8000/docs` (Swagger UI) when running locally.

* Authentication: `Authorization: Bearer <access_token>` from `/api/register` or `/api/login`.
* Errors: `{"detail": "message"}` (validation errors from typed parameters: 422 with a list).
  Unexpected server errors return `500 {"detail": "Internal server error.", "request_id": "..."}`;
  the request ID is also in the `X-Request-ID` header and in the server log.
* Every response carries `X-Request-ID` and `X-Response-Time-MS`.

| Method | Path | Access | Success |
|---|---|---|---|
| POST | `/api/register` | public, rate limited | 201 token |
| POST | `/api/login` | public, rate limited | 200 token |
| GET | `/api/me` | any signed-in user | 200 |
| GET | `/api/jobs` | public | 200 list |
| GET | `/api/jobs/mine` | recruiter | 200 list |
| POST | `/api/jobs` | recruiter | 201 |
| POST | `/api/resumes/upload` | candidate (any job) or recruiter (own jobs), rate limited | 201 |
| POST | `/api/resumes/batch-upload` | candidate (any job) or recruiter (own jobs), rate limited | 200 |
| GET | `/api/resumes/{resume_id}/download` | recruiter who owns the job | 200 file |
| GET | `/api/jobs/{job_id}/summary` | recruiter who owns the job | 200 |
| POST | `/api/jobs/{job_id}/rank` | recruiter who owns the job | 200 |
| GET | `/api/jobs/{job_id}/rankings` | recruiter who owns the job | 200 list |
| GET | `/healthz`, `/readyz`, `/metrics` | public (operations) | 200 / 503 |

Status codes used: 400 invalid input or rejected file · 401 missing/invalid/expired
token · 403 wrong role or not your job · 404 unknown job/resume · 409 email already
registered · 413 file too large · 422 unreadable document or invalid parameter ·
429 too many login/registration attempts per IP or uploads per account (`Retry-After`
header) · 503 not ready.

---

## Auth

### `POST /api/register`
JSON or form data.

```json
{ "name": "Jane Recruiter", "email": "jane@acme.com", "password": "Str0ng!Passw0rd",
  "role": "hr", "access_code": "<HR_SIGNUP_CODE>" }
```
`role` is `candidate` (default) or `hr`. `access_code` is required for `hr` and must
equal the server's `HR_SIGNUP_CODE`; if that variable is empty, recruiter sign-up is
disabled (403). Password: 8–128 characters (≤ 72 bytes), upper, lower, digit, special.

Response `201`:
```json
{ "access_token": "eyJ...", "token_type": "bearer", "user_id": 14, "name": "Jane Recruiter",
  "role": "hr", "expires_in": 3600 }
```

### `POST /api/login`
`{"email": "...", "password": "..."}` → `200` same shape as registration.
Wrong email and wrong password both return `401 "Invalid email or password."`.

### `GET /api/me`
`{"user_id": 14, "name": "Jane Recruiter", "email": "jane@acme.com", "role": "hr"}`.
Useful to check whether a stored token is still valid (the web app relies on any
`401` instead).

## Jobs

### `GET /api/jobs?page=1&limit=50`
Open positions, newest first. `limit` 1–100. The web app requests the first page only,
so candidates see the newest 50 positions.
```json
[{ "job_id": 3, "title": "ML Engineer", "description": "...", "created_by": 14,
   "skills": ["python", "pytorch", "docker"] }]
```

### `GET /api/jobs/mine`
The signed-in recruiter's own jobs (same shape).

### `POST /api/jobs` (form data)
| Field | Rules |
|---|---|
| `title` | 3–120 characters |
| `description` | 20–10,000 characters (used for the job embedding) |
| `skills` | comma-separated, 1–30 skills, normalized to lowercase (`Machine-Learning` → `machine learning`) |

`201` → the created job. The owner is always the signed-in recruiter.

## Resumes

### `POST /api/resumes/upload` (multipart)
Fields: `file` (`.pdf`, `.docx`, `.txt`; ≤ `MAX_UPLOAD_MB`, default 15 MB) and `job_id`.

`201`:
```json
{ "filename": "alice.pdf", "status": "processed", "resume_id": 42, "candidate_id": 18,
  "candidate_name": "Alice Kumar",
  "parsed": { "name": "Alice Kumar", "email": "alice@example.com", "phone": "+91 98765 43210",
              "skills": ["docker", "fastapi", "python"] } }
```
Rejections: 400 (type, signature mismatch, empty), 403 (a recruiter uploading to a job
they did not create), 404 (unknown job), 413 (too large), 422 (no readable text),
429 (more than `UPLOAD_RATE_LIMIT_PER_MINUTE` upload requests from this account in the
current minute, default 10). Characters that are invalid in file names become `_`.

Who the resume belongs to:
* uploaded by a **candidate** → that signed-in account (its email), whatever email the
  document contains, so nobody can attach resumes to another applicant's profile;
* uploaded by a **recruiter** on someone's behalf → the email found in the resume
  (a new applicant profile if none is found). A recruiter's upload only fills in a
  missing name or phone; it never renames an existing applicant.

### `POST /api/resumes/batch-upload` (multipart)
Fields: `files` (repeat, ≤ `MAX_BATCH_FILES`, default 25) and `job_id`. Same access
rules and rate limit as a single upload (a batch counts as one request). `200` with a
result per file, in request order (400 if there are too many files):
```json
{ "job_id": 3, "total_files": 3, "successful": 2, "failed": 1,
  "results": [ { "filename": "a.pdf", "status": "processed", "resume_id": 43, "...": "..." },
               { "filename": "b.exe", "status": "failed", "error": "Unsupported file type '.exe'..." } ] }
```

### `GET /api/resumes/{resume_id}/download`
The original file as an attachment. Only the recruiter who owns the resume's job.

## Rankings

### `GET /api/jobs/{job_id}/summary`
Live scores, one entry per candidate (their best resume), highest first. Header
`X-Cache: HIT|MISS` when Redis is configured.
```json
{
  "job_id": 3, "title": "ML Engineer",
  "job_skills": ["python", "pytorch", "docker"],
  "job_skill_counts": [{ "skill_name": "python", "matches": 12 }],
  "top_skills": [{ "skill_name": "python", "matches": 12 }],
  "candidates": [{
    "candidate_id": 18, "candidate_name": "Alice Kumar", "resume_id": 42, "filename": "alice.pdf",
    "semantic": 0.81, "skill_score": 0.6667, "score": 0.7097, "status": "accepted",
    "matched_skills": ["docker", "python"], "missing_skills": ["pytorch"],
    "coverage_vector": [1, 0, 1], "coverage_percent": 67 }],
  "semantic_available": true,
  "last_ranked_at": "2026-10-22T07:30:00+00:00"
}
```
`top_skills` counts skills among this job's applicants. `semantic_available` is false
when any score used the neutral 0.5 semantic value.

### `POST /api/jobs/{job_id}/rank`
Fills missing embeddings (if the model is loaded), re-scores every resume and replaces
the saved snapshot: `{"status": "done", "ranked": 12, "ranked_at": "..."}`.

### `GET /api/jobs/{job_id}/rankings`
The saved snapshot, one row per resume:
`[{"ranking_id": 7, "resume_id": 42, "candidate_id": 18, "candidate_name": "Alice Kumar", "score": 0.7097, "status": "accepted"}]`

## Operations

* `GET /healthz` → `{"status": "ok", ...}` (liveness)
* `GET /readyz` → `{"status": "ready", "database": "connected", "ml_model": "active|unavailable", "cache": "redis|disabled"}`;
  503 if the database is down, its tables could not be created yet (`"database": "schema not ready"`,
  retried on every check), or the model is not loaded while `REQUIRE_EMBEDDING_MODEL` is on.
* `GET /metrics` → Prometheus text (`http_requests_total{method,path,status}`,
  `http_request_duration_seconds_sum/count`, `summary_cache_hits_total`, `embedding_model_loaded`, …)
