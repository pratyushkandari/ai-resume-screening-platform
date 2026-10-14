# REST API Reference & Specification

All API endpoints reside under `/api` and adhere to standard HTTP status codes and JSON semantics.

---

## 1. Authentication & Session

### `POST /api/register`
Creates a new user profile (`hr` or `candidate`) with input sanitization and Bcrypt password hashing.

**Request (JSON or Multipart Form):**
```json
{
  "name": "Jane Recruiter",
  "email": "jane.recruiter@company.com",
  "password": "StrongPassword123!",
  "role": "hr"
}
```

**Password Requirements:**
* Minimum 8 characters, maximum 128 characters
* At least 1 uppercase letter (`A-Z`)
* At least 1 lowercase letter (`a-z`)
* At least 1 numeric digit (`0-9`)
* At least 1 special character (`!@#$%^&*...`)

**Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "msg": "Registered successfully",
  "user_id": 14,
  "role": "hr",
  "name": "Jane Recruiter"
}
```

---

### `POST /api/login`
Authenticates credentials and returns a signed RFC 7519 JWT access token.

**Request:**
```json
{
  "email": "jane.recruiter@company.com",
  "password": "StrongPassword123!"
}
```

**Response (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "role": "hr",
  "name": "Jane Recruiter",
  "user_id": 14
}
```

---

### `GET /api/me`
Retrieves the profile of the currently authenticated bearer token.

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response (`200 OK`):**
```json
{
  "user_id": 14,
  "name": "Jane Recruiter",
  "email": "jane.recruiter@company.com",
  "role": "hr"
}
```

---

## 2. Job Requisition Management

### `GET /api/jobs`
Lists open job requisitions with pagination.

**Query Parameters:**
* `page` *(int, default: 1)*: Page number ($\ge 1$)
* `limit` *(int, default: 50)*: Page size (1 to 100)
* `role` *(string, optional)*: User role filter

**Response (`200 OK`):**
```json
[
  {
    "job_id": 1,
    "title": "Senior AI Infrastructure Engineer",
    "description": "Designing high-throughput vector inference and model serving architectures.",
    "created_by": 14,
    "skills": ["python", "docker", "pytorch", "fastapi", "kubernetes"]
  }
]
```

---

### `POST /api/jobs`
Creates a new requisition and pre-computes semantic embedding. Restricted to users with `role: "hr"`.

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Request (Form Data):**
* `title`: Requisition title (3 to 120 chars)
* `description`: Detailed job responsibilities (20 to 10,000 chars)
* `skills`: Comma-delimited skill list (e.g., `python, docker, pytorch`)

**Response (`200 OK`):**
```json
{
  "job_id": 2,
  "title": "Distributed Systems Architect",
  "description": "Building fault-tolerant event processing pipelines with Kafka and Redis.",
  "created_by": 14,
  "skills": ["python", "kafka", "redis", "kubernetes", "go"]
}
```

---

## 3. Resume Ingestion & Parsing

### `POST /api/resumes/upload`
Uploads and parses a single candidate resume (`.pdf`, `.docx`, `.doc`, `.txt`).

**Request (Multipart Form):**
* `file`: Binary document payload (max 15MB)
* `job_id`: Target requisition ID *(optional)*

**Response (`200 OK`):**
```json
{
  "resume_id": 42,
  "candidate_id": 18,
  "job_id": 1,
  "parsed": {
    "parsed": {
      "name": "Alex Mercer",
      "email": "alex.mercer@example.com",
      "phone": "+1-555-0199"
    },
    "skills": ["python", "pytorch", "docker", "fastapi"]
  }
}
```

---

### `POST /api/resumes/batch-upload`
High-throughput concurrent batch ingestion for multiple candidate resumes.

**Request (Multipart Form):**
* `files`: Array of file binaries
* `job_id`: Target requisition ID

**Response (`200 OK`):**
```json
{
  "total_files": 3,
  "successful": 3,
  "job_id": 1,
  "results": [
    {
      "filename": "Alex_Mercer_AI.pdf",
      "resume_id": 42,
      "candidate_id": 18,
      "candidate_name": "Alex Mercer",
      "status": "processed"
    }
  ]
}
```

---

## 4. Evaluation & Rankings

### `POST /api/jobs/{job_id}/rank`
Executes hardware-vectorized matrix dot-product ranking for all candidate resumes submitted to the specified requisition.

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response (`200 OK`):**
```json
{
  "status": "done",
  "ranked": 48
}
```

---

### `GET /api/jobs/{job_id}/summary`
Retrieves recruitment analytics, skill gap distributions, and sorted candidate rankings for the HR dashboard. Backed by sub-millisecond Redis Cache-Aside.

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response (`200 OK`):**
```json
{
  "job_id": 1,
  "title": "Senior AI Infrastructure Engineer",
  "job_skills": ["python", "docker", "pytorch", "fastapi", "kubernetes"],
  "job_skill_counts": [
    { "skill_name": "python", "matches": 45 },
    { "skill_name": "docker", "matches": 38 },
    { "skill_name": "pytorch", "matches": 29 }
  ],
  "top_skills": [
    { "skill_name": "python", "matches": 82 }
  ],
  "candidates": [
    {
      "candidate_id": 18,
      "candidate_name": "Alex Mercer",
      "resume_id": 42,
      "semantic": 0.8842,
      "skill_score": 0.8000,
      "score": 0.8753,
      "status": "accepted",
      "matched_skills": ["docker", "fastapi", "python", "pytorch"],
      "missing_skills": ["kubernetes"],
      "coverage_vector": [1, 1, 1, 1, 0],
      "coverage_percent": 80
    }
  ]
}
```

---

## 5. Observability & SRE Endpoints

### `GET /healthz`
Liveness probe verifying that the FastAPI server process is active.
```json
{
  "status": "ok",
  "timestamp": "2026-10-14T20:30:00.000Z",
  "service": "resume-screener"
}
```

### `GET /readyz`
Readiness probe verifying active database connection pool and SentenceTransformer embedding model readiness.
```json
{
  "status": "ready",
  "database": "connected",
  "ml_model": "active",
  "timestamp": "2026-10-14T20:30:00.000Z"
}
```

### `GET /metrics`
Prometheus metrics format containing RED method telemetry (`http_requests_total`, `app_uptime_seconds`, `redis_cache_hits_total`, etc.).
