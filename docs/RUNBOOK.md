# Production Operations & Reliability Runbook

**Service:** `resume-screener-backend`  
**Tier:** Tier-1 Enterprise Recruitment Pipeline  
**Target SLA:** 99.95% Availability  
**P99 Latency Objective:** $< 100\text{ ms}$ for candidate ranking  

---

## 1. Architecture Checklist & Topology

```
Ingress (Nginx / Cloud Load Balancer)
   │
   ├── /api/* ───────────────> FastAPI Deployment (k8s / Docker / Render)
   │                               │
   │                               ├── Connection Pool (SQLAlchemy) ──> PostgreSQL 15
   │                               └── TCP 6379 Cache-Aside ─────────> Redis 7
   │
   └── /* (Static Assets) ───> React 18 SPA (Vite Production Build)
```

---

## 2. Standard Operational Procedures (SOP)

### 2.1 Starting the Environment Locally
```powershell
# Using automated orchestration script (Windows)
.\deploy.ps1

# Or via Docker Compose multi-container stack
docker compose up --build -d
```

### 2.2 Running Automated Testing & Benchmarking
```powershell
# Run the complete test suite (29 tests)
backend\venv\Scripts\python.exe -m pytest backend/tests -v

# Run the 1,000-candidate concurrency benchmark
backend\venv\Scripts\python.exe backend/benchmark_concurrency.py
```

### 2.3 Performing Database Schema Migrations & Seeding
```bash
# Seed test database manually via psql
psql -h localhost -U resume_user1 -d resume_db1 -f sql/seed.sql
```

---

## 3. Incident Triage & Troubleshooting Matrix

### Alert: `PodCrashLoopBackOff` or `ReadinessProbeFailed`
* **Symptoms:** Kubernetes pod fails readiness probe on `/readyz`.
* **Root Cause 1:** PostgreSQL host unreachable or max connections reached.
  * **Remediation:** Check DB host connectivity:
    ```bash
    pg_isready -h db -p 5432 -U resume_user1
    ```
    Verify PostgreSQL max connections: `SHOW max_connections;`.
* **Root Cause 2:** SentenceTransformer download blocked by container network proxy.
  * **Remediation:** Verify that `/tmp/hf_cache` has read/write permissions for `appuser` (UID 1000) and that outbound HTTPS access to Hugging Face Hub is permitted or pre-cached in Docker build.

### Alert: `RedisConnectionRefused`
* **Symptoms:** Log shows `[CACHE] Redis not connected. Running in local passthrough mode.`
* **Impact:** Non-critical. System automatically degrades to local passthrough mode with zero service interruption.
* **Remediation:** Check Redis service status:
  ```bash
  docker compose ps redis
  redis-cli ping
  ```

### Alert: High P99 Ranking Latency (> 200ms)
* **Symptoms:** Candidate evaluation endpoint `POST /api/jobs/{id}/rank` slow.
* **Root Cause:** Large requisition applicant pool evaluated sequentially instead of via BLAS vectorized matrix multiplication.
* **Remediation:** Verify that NumPy is utilizing OpenBLAS or MKL:
  ```python
  import numpy as np
  np.show_config()
  ```

---

## 4. Disaster Recovery & Backup

### 4.1 Automated Daily PostgreSQL Dump
```bash
pg_dump -h localhost -U resume_user1 -F c -b -v -f "resume_db_$(date +%Y%m%d).dump" resume_db1
```

### 4.2 Restoring from Backup
```bash
pg_restore -h localhost -U resume_user1 -d resume_db1 -v "resume_db_20261015.dump"
```
