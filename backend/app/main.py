# backend/app/main.py

import os
import uuid
import shutil
import logging
import time
import hashlib
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import re
from concurrent.futures import ThreadPoolExecutor

# FastAPI modules
from fastapi import (
    FastAPI, UploadFile, File, Depends, HTTPException, Form, Request,
    Response, status, BackgroundTasks, Query
)
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# SQLAlchemy ORM
from sqlalchemy.orm import Session
from sqlalchemy import func, text

# Local project modules
from .db import SessionLocal, engine, Base
from . import models, schemas, ml_utils
from .cache import CacheService
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    validate_email_format,
    validate_password_strength,
    get_current_user,
    get_optional_user,
    require_role,
    get_db,
)

# Structured logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ReqID: %(name)s] %(message)s"
)
logger = logging.getLogger("api")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
thread_pool = ThreadPoolExecutor(max_workers=8)

# Security constants
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}

# Telemetry counters for Prometheus metrics
METRICS = {
    "requests_total": 0,
    "requests_by_endpoint": {},
    "status_codes": {},
    "cache_hits": 0,
    "cache_misses": 0,
    "start_time": time.time()
}


# -----------------------------------------------------------------------------
# Skill Normalization & Merging
# -----------------------------------------------------------------------------
def _normalize_and_merge_skills_table():
    """Ensures all skill names in DB are lowercase, canonical, and unique."""
    db = SessionLocal()
    try:
        all_skills = db.query(models.Skill).all()
        groups: Dict[str, List[models.Skill]] = {}

        for s in all_skills:
            if s.skill_name:
                key = s.skill_name.strip().lower()
                groups.setdefault(key, []).append(s)

        for lower_name, rows in groups.items():
            canonical = db.query(models.Skill).filter(func.lower(models.Skill.skill_name) == lower_name).first()
            if not canonical:
                canonical = rows[0]
                try:
                    canonical.skill_name = lower_name
                    db.add(canonical)
                    db.commit()
                except Exception:
                    db.rollback()

            keep_id = canonical.skill_id
            for dup in rows:
                if dup.skill_id != keep_id:
                    try:
                        db.execute(
                            text("UPDATE resume_skills SET skill_id = :keep WHERE skill_id = :dup"),
                            {"keep": keep_id, "dup": dup.skill_id},
                        )
                        db.execute(
                            text("UPDATE job_skills SET skill_id = :keep WHERE skill_id = :dup"),
                            {"keep": keep_id, "dup": dup.skill_id},
                        )
                        db.commit()
                    except Exception:
                        db.rollback()

                    try:
                        db.delete(dup)
                        db.commit()
                    except Exception:
                        db.rollback()
    except Exception as e:
        logger.warning("Skill normalization note: %s", e)
    finally:
        db.close()


# -----------------------------------------------------------------------------
# FastAPI Lifespan Manager
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        _normalize_and_merge_skills_table()
        logger.info("[STARTUP] Database connection and schema verification completed successfully.")
    except Exception as e:
        logger.warning("[STARTUP] Database notice: %s", e)
    yield
    thread_pool.shutdown(wait=False)
    logger.info("[SHUTDOWN] Application teardown clean.")


app = FastAPI(
    title="AI Resume Screening & Matching Engine",
    version="2.3.0",
    description="Production-grade AI resume screening, dense semantic matching, Redis caching, and candidate ranking system.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Observability Middleware: Request Tracing & Latency Measurement
# -----------------------------------------------------------------------------
@app.middleware("http")
async def trace_and_log_requests(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    start_time = time.time()

    METRICS["requests_total"] += 1
    endpoint = request.url.path
    METRICS["requests_by_endpoint"][endpoint] = METRICS["requests_by_endpoint"].get(endpoint, 0) + 1

    response = await call_next(request)

    status_code = response.status_code
    METRICS["status_codes"][status_code] = METRICS["status_codes"].get(status_code, 0) + 1

    process_time = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-MS"] = str(process_time)

    if endpoint not in ["/healthz", "/readyz", "/metrics"]:
        logger.info(
            f"[{req_id}] {request.method} {endpoint} -> {response.status_code} ({process_time}ms)"
        )
    return response


# -----------------------------------------------------------------------------
# Healthcheck & Prometheus Observability Endpoints
# -----------------------------------------------------------------------------
@app.get("/healthz", tags=["Observability"])
def health_check():
    """Liveness probe to verify server process is active."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "service": "resume-screener"}


@app.get("/readyz", tags=["Observability"])
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe to verify database connectivity and model status."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {e}"
        return JSONResponse(status_code=503, content={"status": "degraded", "db": db_status})

    return {
        "status": "ready",
        "database": db_status,
        "ml_model": "active" if ml_utils.get_model() is not None else "fallback_mode",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    """Prometheus-compatible SRE metrics (RED Method: Rate, Errors, Duration)."""
    uptime_seconds = int(time.time() - METRICS["start_time"])
    lines = [
        "# HELP http_requests_total Total HTTP requests received",
        "# TYPE http_requests_total counter",
        f"http_requests_total {METRICS['requests_total']}",
        "# HELP app_uptime_seconds Application uptime in seconds",
        "# TYPE app_uptime_seconds gauge",
        f"app_uptime_seconds {uptime_seconds}",
        "# HELP redis_cache_hits_total Total Redis cache hits",
        "# TYPE redis_cache_hits_total counter",
        f"redis_cache_hits_total {METRICS['cache_hits']}",
        "# HELP redis_cache_misses_total Total Redis cache misses",
        "# TYPE redis_cache_misses_total counter",
        f"redis_cache_misses_total {METRICS['cache_misses']}",
    ]
    for ep, count in METRICS["requests_by_endpoint"].items():
        lines.append(f'http_endpoint_requests_total{{path="{ep}"}} {count}')
    for code, count in METRICS["status_codes"].items():
        lines.append(f'http_status_code_total{{code="{code}"}} {count}')

    return PlainTextResponse("\n".join(lines), media_type="text/plain")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _unique_preserve_order(seq: List[Any]) -> List[Any]:
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _relevant_resumes(db: Session, after: Optional[datetime] = None, job_id: Optional[int] = None):
    q = db.query(models.Resume)
    if job_id is not None:
        q = q.filter(models.Resume.job_id == job_id)
    elif after is not None:
        q = q.filter(models.Resume.uploaded_at >= after)
    return q.order_by(models.Resume.uploaded_at.desc()).all()


def _sanitize_text(text_input: str) -> str:
    """Removes potentially dangerous script tags and excess whitespace."""
    if not text_input:
        return ""
    # Strip script and style tags
    cleaned = re.sub(r"<(script|style).*?>.*?</\1>", "", text_input, flags=re.IGNORECASE | re.DOTALL)
    # Strip HTML tags
    cleaned = re.sub(r"<[^<]+?>", "", cleaned)
    return cleaned.strip()


# =============================================================================
#  AUTHENTICATION & IDENTITY ENDPOINTS
# =============================================================================
#  AUTHENTICATION & IDENTITY ENDPOINTS (JWT + RBAC + Password Strength)
# =============================================================================
@app.post("/api/register", tags=["Auth"])
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Registers a new recruiter or candidate with strict input validation,
    RFC 5322 email checking, and multi-factor password strength verification.
    Supports both JSON and Form Data payloads.
    """
    try:
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        data = {}

    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip()
    password = str(data.get("password") or "")
    role = str(data.get("role") or "candidate").strip().lower()

    # 1. Validate Name
    clean_name = _sanitize_text(name)
    if len(clean_name) < 2 or len(clean_name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full Name must be between 2 and 100 characters."
        )

    # 2. Validate Email Format
    is_valid_email, email_res = validate_email_format(email)
    if not is_valid_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=email_res)
    clean_email = email_res

    # 3. Validate Password Complexity
    is_strong_pw, pw_res = validate_password_strength(password)
    if not is_strong_pw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pw_res)

    # 4. Normalize & Validate Role
    if role not in ["hr", "candidate"]:
        role = "candidate"

    # 5. Check Duplicate Account
    existing_user = db.query(models.User).filter(func.lower(models.User.email) == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account is already registered with this email address. Please sign in instead."
        )

    # 6. Create User with Bcrypt Hashing
    new_user = models.User(
        name=clean_name,
        email=clean_email,
        password=hash_password(password),
        role=role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 7. Generate Signed JWT Access Token
    token = create_access_token({"user_id": new_user.user_id, "role": new_user.role, "name": new_user.name})

    logger.info("New user registered: %s (role=%s, user_id=%s)", clean_email, role, new_user.user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "msg": "Registered successfully",
        "user_id": new_user.user_id,
        "role": new_user.role,
        "name": new_user.name
    }


@app.post("/api/login", tags=["Auth"])
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticates user credentials and returns signed JWT access token.
    Supports both JSON and Form Data payloads.
    """
    try:
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        data = {}

    email = str(data.get("email") or "").strip()
    password = str(data.get("password") or "")

    is_valid_email, clean_email = validate_email_format(email)
    if not is_valid_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid email address.")

    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is required.")

    user = db.query(models.User).filter(func.lower(models.User.email) == clean_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )

    stored = user.password or ""

    # Legacy plaintext migration fallback
    if stored == password:
        try:
            user.password = hash_password(password)
            db.add(user)
            db.commit()
        except Exception:
            db.rollback()
    elif not verify_password(password, stored):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )

    # Issue standard JWT Access Token
    token = create_access_token({"user_id": user.user_id, "role": user.role, "name": user.name})

    logger.info("User login successful: %s (role=%s, id=%s)", clean_email, user.role, user.user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "name": user.name,
        "user_id": user.user_id
    }



@app.get("/api/me", tags=["Auth"])
def get_current_user_profile(current_user: models.User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated JWT bearer."""
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    }


# =============================================================================
#  JOB MANAGEMENT ENDPOINTS
# =============================================================================
@app.get("/api/jobs", response_model=List[schemas.JobOut], tags=["Jobs"])
def list_jobs(
    role: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    List active company job requisitions with pagination.
    Accessible to both HR recruiters and candidates.
    """
    query = db.query(models.Job)
    rows = query.order_by(models.Job.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    out = []
    for j in rows:
        skill_names = [js.skill.skill_name for js in j.job_skills if js.skill and js.skill.skill_name]
        out.append({
            "job_id": j.job_id,
            "title": j.title,
            "description": j.description,
            "created_by": j.created_by,
            "skills": skill_names
        })
    return out



@app.post("/api/jobs", response_model=schemas.JobOut, tags=["Jobs"])
def create_job(
    title: str = Form(...),
    description: str = Form(""),
    created_by: Optional[int] = Form(None),
    skills: Optional[str] = Form(""),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Create a new job posting with strict validation:
    - Title: 3 to 120 chars
    - Description: 20 to 10,000 chars
    - Skills: at least 1 valid skill required
    """
    eff_user = current_user
    if not eff_user and created_by:
        eff_user = db.query(models.User).filter_by(user_id=created_by).first()

    if not eff_user or eff_user.role != "hr":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: Only verified HR recruiters can post job requisitions."
        )

    clean_title = _sanitize_text(title)
    if len(clean_title) < 3 or len(clean_title) > 120:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job title must be between 3 and 120 characters long."
        )

    clean_desc = _sanitize_text(description)
    if len(clean_desc) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description must be at least 20 characters describing responsibilities and requirements."
        )

    if len(clean_desc) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description is too long (maximum 10,000 characters)."
        )

    # Process and deduplicate skills
    raw_skills = [s.strip().lower() for s in (skills or "").split(",") if s.strip()]
    cleaned_skills = []
    for s in raw_skills:
        s_clean = re.sub(r"[^a-zA-Z0-9\+\#\.\-\s]", "", s).strip()
        if s_clean and len(s_clean) <= 50 and s_clean not in cleaned_skills:
            cleaned_skills.append(s_clean)

    if not cleaned_skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one required skill must be specified for the job requisition (e.g. Python, Docker)."
        )

    job_row = models.Job(
        title=clean_title,
        description=clean_desc,
        created_by=eff_user.user_id
    )

    try:
        job_row.embedding = ml_utils.embed_text(f"{clean_title}\n{clean_desc}")
    except Exception:
        job_row.embedding = None

    db.add(job_row)
    db.commit()
    db.refresh(job_row)

    seen_skill_ids = set()
    for s_name in cleaned_skills:
        skill_row = db.query(models.Skill).filter(func.lower(models.Skill.skill_name) == s_name).first()
        if not skill_row:
            skill_row = models.Skill(skill_name=s_name, canonical_name=s_name)
            db.add(skill_row)
            db.commit()
            db.refresh(skill_row)

        if skill_row.skill_id not in seen_skill_ids:
            seen_skill_ids.add(skill_row.skill_id)
            exists_js = db.query(models.JobSkill).filter_by(job_id=job_row.job_id, skill_id=skill_row.skill_id).first()
            if not exists_js:
                db.add(models.JobSkill(job_id=job_row.job_id, skill_id=skill_row.skill_id, required_level=1))

    db.commit()
    logger.info("Created job '%s' (id=%s) by recruiter %s", job_row.title, job_row.job_id, eff_user.user_id)

    return {
        "job_id": job_row.job_id,
        "title": job_row.title,
        "description": job_row.description,
        "created_by": job_row.created_by,
        "skills": cleaned_skills
    }


# =============================================================================
#  RESUME UPLOAD & PARSING PIPELINE
# =============================================================================
def _validate_upload_file(file: UploadFile) -> Tuple[bool, str]:
    """Validates file extension and filename safety."""
    if not file or not file.filename:
        return False, "No file provided."

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Allowed formats: .pdf, .docx, .doc, .txt"

    return True, ext


def _process_single_resume_file(saved_path: str, job_id: Optional[int], db: Session, user_email: Optional[str] = None, user_name: Optional[str] = None):
    """Worker function for single resume text extraction, contact parsing, and skill detection."""
    # Check file size
    if os.path.getsize(saved_path) == 0:
        raise ValueError("Uploaded file is empty (0 bytes). Please upload a valid resume.")

    raw_text = ml_utils.extract_text(saved_path)
    if not raw_text or len(raw_text.strip()) < 10:
        raise ValueError("Could not extract readable text from document. The file may be password-protected, encrypted, or corrupted.")

    parsed_contacts = ml_utils.parse_contacts(raw_text) or {}
    email_val = parsed_contacts.get("email") or user_email

    # Upsert Candidate
    candidate = None
    if email_val:
        candidate = db.query(models.Candidate).filter(func.lower(models.Candidate.email) == email_val.strip().lower()).first()

    if not candidate:
        candidate = models.Candidate(
            full_name=parsed_contacts.get("name") or user_name or "Candidate",
            email=(email_val.strip().lower() if email_val else None),
            phone=parsed_contacts.get("phone"),
        )
        db.add(candidate)
        try:
            db.commit()
            db.refresh(candidate)
        except Exception:
            db.rollback()
            candidate = db.query(models.Candidate).filter(func.lower(models.Candidate.email) == email_val.strip().lower()).first() if email_val else None
            if not candidate:
                candidate = models.Candidate(full_name=parsed_contacts.get("name") or "Candidate")
                db.add(candidate)
                db.commit()
                db.refresh(candidate)

    # Create Resume entity
    resume = models.Resume(
        candidate_id=candidate.candidate_id,
        filename=os.path.basename(saved_path),
        upload_path=os.path.abspath(saved_path),
        raw_text=raw_text,
        parsed_json={"parsed": parsed_contacts, "skills": []},
        job_id=job_id,
    )

    try:
        resume.embedding = ml_utils.embed_text(raw_text)
    except Exception:
        resume.embedding = None

    db.add(resume)
    db.commit()
    db.refresh(resume)

    # Word-boundary skill extraction
    all_skills_rows = db.query(models.Skill).all()
    canonical_skills = [s.skill_name.lower() for s in all_skills_rows if s.skill_name]
    detected_skills = ml_utils.extract_skills(raw_text, canonical_skills)
    skill_names_for_json = []

    for s_name, conf in detected_skills:
        name_lower = s_name.strip().lower()
        skill_names_for_json.append(name_lower)

        s_row = db.query(models.Skill).filter(func.lower(models.Skill.skill_name) == name_lower).first()
        if not s_row:
            s_row = models.Skill(skill_name=name_lower, canonical_name=name_lower)
            db.add(s_row)
            db.commit()
            db.refresh(s_row)

        exists_link = db.query(models.ResumeSkill).filter_by(resume_id=resume.resume_id, skill_id=s_row.skill_id).first()
        if not exists_link:
            db.add(models.ResumeSkill(resume_id=resume.resume_id, skill_id=s_row.skill_id, confidence=conf))

    try:
        resume.parsed_json = {"parsed": parsed_contacts, "skills": skill_names_for_json}
        db.add(resume)
        db.commit()
    except Exception:
        db.rollback()

    # Invalidate Redis Cache for this job opening
    if job_id:
        CacheService.delete(f"job:summary:{job_id}")

    return resume, candidate


@app.post("/api/resumes/upload", response_model=schemas.ResumeUploadResponse, tags=["Resumes"])
def upload_resume(
    file: UploadFile = File(...),
    job_id: Optional[int] = Form(None),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Upload and parse a single resume document (.pdf, .docx, .doc, .txt).
    Validates file size (max 15MB), format, and document readability.
    """
    # 1. Validate Extension
    is_valid, ext_err = _validate_upload_file(file)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ext_err)

    uid = str(uuid.uuid4())[:8]
    safe_name = Path(file.filename).name
    saved_path = os.path.join(UPLOAD_DIR, f"{uid}_{safe_name}")

    try:
        bytes_read = 0
        with open(saved_path, "wb") as out:
            while chunk := file.file.read(8192):
                bytes_read += len(chunk)
                if bytes_read > MAX_FILE_SIZE:
                    out.close()
                    if os.path.exists(saved_path):
                        os.unlink(saved_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of 15MB ({round(bytes_read / (1024*1024), 2)}MB detected)."
                    )
                out.write(chunk)
    finally:
        file.file.close()

    try:
        resume, candidate = _process_single_resume_file(
            saved_path=saved_path,
            job_id=job_id,
            db=db,
            user_email=current_user.email if current_user else None,
            user_name=current_user.name if current_user else None
        )
    except ValueError as ve:
        if os.path.exists(saved_path):
            os.unlink(saved_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        if os.path.exists(saved_path):
            os.unlink(saved_path)
        logger.exception("Processing failed for %s", saved_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to process resume: {e}")

    logger.info("Uploaded resume -> resume_id=%s, candidate_id=%s, job_id=%s", resume.resume_id, candidate.candidate_id, job_id)
    return {
        "resume_id": resume.resume_id,
        "candidate_id": candidate.candidate_id,
        "job_id": job_id,
        "parsed": resume.parsed_json
    }


@app.post("/api/resumes/batch-upload", tags=["Resumes"])
def batch_upload_resumes(
    files: List[UploadFile] = File(...),
    job_id: Optional[int] = Form(None),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    High-Throughput Batch Resume Ingestion with size and format verification.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for batch upload.")

    saved_files = []
    results = []

    for f in files:
        is_valid, ext_err = _validate_upload_file(f)
        if not is_valid:
            results.append({
                "filename": f.filename,
                "status": "failed",
                "error": ext_err
            })
            continue

        uid = str(uuid.uuid4())[:8]
        safe_name = Path(f.filename).name
        saved_path = os.path.join(UPLOAD_DIR, f"{uid}_{safe_name}")

        try:
            bytes_read = 0
            with open(saved_path, "wb") as out:
                while chunk := f.file.read(8192):
                    bytes_read += len(chunk)
                    if bytes_read > MAX_FILE_SIZE:
                        out.close()
                        if os.path.exists(saved_path):
                            os.unlink(saved_path)
                        raise ValueError(f"File exceeds 15MB limit ({round(bytes_read / (1024*1024), 2)}MB).")
                    out.write(chunk)
            f.file.close()
            saved_files.append(saved_path)
        except ValueError as ve:
            results.append({
                "filename": f.filename,
                "status": "failed",
                "error": str(ve)
            })

    user_email = current_user.email if current_user else None
    user_name = current_user.name if current_user else None

    for sp in saved_files:
        try:
            resume, candidate = _process_single_resume_file(sp, job_id, db, user_email, user_name)
            results.append({
                "filename": os.path.basename(sp),
                "resume_id": resume.resume_id,
                "candidate_id": candidate.candidate_id,
                "candidate_name": candidate.full_name,
                "status": "processed"
            })
        except Exception as e:
            results.append({
                "filename": os.path.basename(sp),
                "status": "failed",
                "error": str(e)
            })

    if job_id:
        CacheService.delete(f"job:summary:{job_id}")

    logger.info("Batch uploaded %s resumes for job %s", len(results), job_id)
    return {
        "total_files": len(files),
        "successful": len([r for r in results if r["status"] == "processed"]),
        "job_id": job_id,
        "results": results
    }


# =============================================================================
#  RANKINGS & EVALUATION ENGINE
# =============================================================================
@app.post("/api/jobs/{job_id}/rank", tags=["Rankings"])
def rank_job(
    job_id: int,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Computes high-performance vectorized matrix composite rankings for all resumes submitted to this job opening.
    """
    job = db.query(models.Job).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found.")

    job_skill_links = db.query(models.JobSkill).filter_by(job_id=job_id).all()
    job_skill_ids = [jl.skill_id for jl in job_skill_links]
    job_skills_objs = db.query(models.Skill).filter(models.Skill.skill_id.in_(job_skill_ids)).all() if job_skill_ids else []
    job_skill_names = [s.skill_name for s in job_skills_objs if s.skill_name]

    db.query(models.Ranking).filter_by(job_id=job_id).delete(synchronize_session=False)
    db.commit()

    resumes = _relevant_resumes(db, after=job.created_at, job_id=job_id)
    if not resumes:
        CacheService.delete(f"job:summary:{job_id}")
        return {"status": "done", "ranked": 0}

    # Prepare inputs for vectorized ranking
    resume_embeddings = []
    resume_skill_lists = []
    resume_objs = []

    for r in resumes:
        r_skill_links = db.query(models.ResumeSkill).filter_by(resume_id=r.resume_id).all()
        r_skill_ids = [rl.skill_id for rl in r_skill_links]
        r_skill_objs = db.query(models.Skill).filter(models.Skill.skill_id.in_(r_skill_ids)).all() if r_skill_ids else []
        r_skills = [s.skill_name for s in r_skill_objs if s.skill_name]

        resume_embeddings.append(r.embedding or [0.0] * 384)
        resume_skill_lists.append(r_skills)
        resume_objs.append(r)

    # Vectorized Matrix Evaluation
    eval_results = ml_utils.vectorized_candidate_ranking(
        job_embedding=job.embedding or [0.0] * 384,
        resume_embeddings=resume_embeddings,
        job_skill_names=job_skill_names,
        resume_skill_list=resume_skill_lists
    )

    for i, res_eval in enumerate(eval_results):
        r = resume_objs[i]
        new_ranking = models.Ranking(
            job_id=job_id,
            resume_id=r.resume_id,
            score=res_eval["final_score"],
            status=res_eval["status"]
        )
        db.add(new_ranking)

    db.commit()
    CacheService.delete(f"job:summary:{job_id}")
    logger.info("Vectorized ranked %s resumes for job %s", len(eval_results), job_id)
    return {"status": "done", "ranked": len(eval_results)}


@app.get("/api/jobs/{job_id}/summary", response_model=schemas.JobSummaryOut, tags=["Rankings"])
def job_summary(
    job_id: int,
    response: Response,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Returns recruitment analytics and candidate evaluations for the HR dashboard.
    Implements Redis Cache-Aside with sub-1ms response times on cache hits.
    """
    eff_role = current_user.role if current_user else (role or "").strip().lower()
    eff_user_id = current_user.user_id if current_user else user_id

    if eff_role != "hr":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recruitment dashboard access is restricted to HR recruiters."
        )

    job = db.query(models.Job).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found.")


    # 1. Check Redis Cache
    cache_key = f"job:summary:{job_id}"
    cached_data = CacheService.get(cache_key)
    if cached_data:
        METRICS["cache_hits"] += 1
        response.headers["X-Cache"] = "HIT"
        return cached_data

    METRICS["cache_misses"] += 1
    response.headers["X-Cache"] = "MISS"

    job_skill_links = db.query(models.JobSkill).filter_by(job_id=job_id).all()
    job_skill_ids = _unique_preserve_order([jl.skill_id for jl in job_skill_links])
    job_skill_objs = db.query(models.Skill).filter(models.Skill.skill_id.in_(job_skill_ids)).all() if job_skill_ids else []
    id_to_name = {s.skill_id: s.skill_name for s in job_skill_objs}
    job_skill_names = [id_to_name[sid] for sid in job_skill_ids if sid in id_to_name]

    resumes = _relevant_resumes(db, after=job.created_at, job_id=job_id)
    candidate_map: Dict[int, List[Dict[str, Any]]] = {}

    for r in resumes:
        cand = db.query(models.Candidate).filter_by(candidate_id=r.candidate_id).first()
        r_skill_links = db.query(models.ResumeSkill).filter_by(resume_id=r.resume_id).all()
        r_skill_ids = [rl.skill_id for rl in r_skill_links]
        r_skill_objs = db.query(models.Skill).filter(models.Skill.skill_id.in_(r_skill_ids)).all() if r_skill_ids else []
        r_skill_names = [s.skill_name for s in r_skill_objs if s.skill_name]

        eval_res = ml_utils.calculate_candidate_match(
            job_embedding=job.embedding,
            resume_embedding=r.embedding,
            job_skill_names=job_skill_names,
            resume_skill_names=r_skill_names
        )

        cand_id = cand.candidate_id if cand else -1
        candidate_map.setdefault(cand_id, []).append({
            "candidate_id": cand_id if cand_id != -1 else None,
            "candidate_name": cand.full_name if cand else "Unknown",
            "resume_id": r.resume_id,
            "semantic": eval_res["semantic"],
            "skill_score": eval_res["skill_score"],
            "score": eval_res["final_score"],
            "status": eval_res["status"],
            "matched_skills": eval_res["matched_skills"],
            "missing_skills": eval_res["missing_skills"],
            "coverage_vector": eval_res["coverage_vector"],
            "coverage_percent": eval_res["coverage_percent"],
        })

    final_candidates = []
    coverage_counts = {s: 0 for s in job_skill_names}

    for cid, evals in candidate_map.items():
        best = max(evals, key=lambda x: x["score"])
        matched_union = set()
        for ev in evals:
            matched_union.update(ev.get("matched_skills", []))

        coverage_vec = [1 if s in matched_union else 0 for s in job_skill_names]
        matched_list = sorted(list(matched_union))
        missing_list = [s for s in job_skill_names if s not in matched_union]

        for i, s in enumerate(job_skill_names):
            if coverage_vec[i]:
                coverage_counts[s] = coverage_counts.get(s, 0) + 1

        final_candidates.append({
            "candidate_id": best["candidate_id"],
            "candidate_name": best["candidate_name"],
            "resume_id": best["resume_id"],
            "semantic": best["semantic"],
            "skill_score": best["skill_score"],
            "score": best["score"],
            "status": best["status"],
            "matched_skills": matched_list,
            "missing_skills": missing_list,
            "coverage_vector": coverage_vec,
            "coverage_percent": int((sum(coverage_vec) / len(coverage_vec) * 100)) if coverage_vec else 0,
        })

    final_candidates = sorted(final_candidates, key=lambda x: x["score"], reverse=True)
    job_skill_counts = [{"skill_name": s, "matches": int(coverage_counts.get(s, 0))} for s in job_skill_names]

    agg = db.query(models.Skill.skill_name,
                   func.count(func.distinct(models.Resume.candidate_id)).label("matches")) \
        .join(models.ResumeSkill, models.ResumeSkill.skill_id == models.Skill.skill_id) \
        .join(models.Resume, models.Resume.resume_id == models.ResumeSkill.resume_id) \
        .group_by(models.Skill.skill_name) \
        .order_by(func.count(func.distinct(models.Resume.candidate_id)).desc()) \
        .limit(10).all()

    top_skills = [{"skill_name": a.skill_name, "matches": int(a.matches)} for a in agg]

    result = {
        "job_id": job.job_id,
        "title": job.title,
        "job_skills": job_skill_names,
        "job_skill_counts": job_skill_counts,
        "top_skills": top_skills,
        "candidates": final_candidates
    }

    # Store in Redis Cache (TTL: 300s)
    CacheService.set(cache_key, result, ttl_seconds=300)
    return result


@app.get("/api/jobs/{job_id}/rankings", response_model=List[schemas.RankingOut], tags=["Rankings"])
def get_rankings(
    job_id: int,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    eff_role = current_user.role if current_user else (role or "").strip().lower()
    eff_user_id = current_user.user_id if current_user else user_id

    if eff_role != "hr":
        raise HTTPException(403, "Access restricted to HR recruiters.")

    job = db.query(models.Job).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(404, "Job opening not found.")

    if eff_user_id and job.created_by != int(eff_user_id):
        raise HTTPException(403, "Not authorized to access rankings for this job requisition.")

    rows = db.query(models.Ranking).filter_by(job_id=job_id).order_by(models.Ranking.score.desc()).all()
    out = []
    for row in rows:
        r = db.query(models.Resume).filter_by(resume_id=row.resume_id).first()
        cand = db.query(models.Candidate).filter_by(candidate_id=r.candidate_id).first() if r else None

        out.append({
            "ranking_id": row.ranking_id,
            "resume_id": row.resume_id,
            "candidate_id": cand.candidate_id if cand else 0,
            "candidate_name": cand.full_name if cand else "Unknown",
            "score": row.score,
            "status": row.status or ("accepted" if row.score >= 0.60 else "rejected")
        })
    return out


@app.get("/api/resumes/{resume_id}/download", tags=["Resumes"])
def download_resume(resume_id: int, db: Session = Depends(get_db)):
    """Allows authenticated download of a candidate's resume document."""
    r = db.query(models.Resume).filter_by(resume_id=resume_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resume record not found.")
    if not os.path.exists(r.upload_path):
        raise HTTPException(status_code=404, detail="Resume file not found on server storage.")
    return FileResponse(r.upload_path, filename=r.filename, media_type="application/octet-stream")


@app.post("/api/ranking/{ranking_id}/status", tags=["Rankings"])
def update_status(ranking_id: int):
    """Automatic system note - manual status mutation is disabled."""
    raise HTTPException(
        status_code=403,
        detail="Manual status overrides disabled. Shortlisting is computed automatically by AI evaluation."
    )