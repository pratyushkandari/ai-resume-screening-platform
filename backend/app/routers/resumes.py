"""Resume upload (single and batch) and recruiter-only download."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user, get_owned_job, require_hr
from ..config import settings
from ..db import get_db
from ..schemas import BatchUploadOut, ResumeUploadResult
from ..services.ingestion import StoredUpload, UploadRejected, process_uploads, require_open_job, save_upload

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


@router.post("/upload", response_model=ResumeUploadResult, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    job_id: int = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeUploadResult:
    """Upload one resume (.pdf, .docx, .txt) as an application to ``job_id``."""
    job = require_open_job(db, job_id)
    try:
        stored = save_upload(file)
    except UploadRejected as exc:
        raise HTTPException(exc.status_code, detail=str(exc)) from exc
    result = process_uploads(db, job, [stored], current_user)[0]
    if result.status != "processed":
        raise HTTPException(422, detail=result.error)  # unreadable content; the file was already deleted
    return result


@router.post("/batch-upload", response_model=BatchUploadOut)
def batch_upload_resumes(
    files: List[UploadFile] = File(...),
    job_id: int = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchUploadOut:
    """Upload several resumes; each file gets its own ``processed``/``failed`` result."""
    if len(files) > settings.max_batch_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"At most {settings.max_batch_files} files per batch.")
    job = require_open_job(db, job_id)

    stored: List[StoredUpload] = []
    order: List[object] = []  # StoredUpload or a failed ResumeUploadResult, in request order
    for upload in files:
        try:
            item = save_upload(upload)
            stored.append(item)
            order.append(item)
        except UploadRejected as exc:
            order.append(ResumeUploadResult(filename=upload.filename or "resume", status="failed", error=str(exc)))

    processed = iter(process_uploads(db, job, stored, current_user) if stored else [])
    results = [next(processed) if isinstance(entry, StoredUpload) else entry for entry in order]
    successful = sum(r.status == "processed" for r in results)
    return BatchUploadOut(job_id=job.job_id, total_files=len(results), successful=successful, failed=len(results) - successful, results=results)


def _resolve_stored_path(resume: models.Resume) -> Path:
    """Absolute path of a stored resume, refusing anything outside ``UPLOAD_DIR``.

    Rows written by version 2 stored absolute paths; those are trusted as-is
    because they came from the server itself, not from a client.
    """
    stored = Path(resume.upload_path)
    if stored.is_absolute():  # rows written by older versions stored absolute paths
        return stored
    path = (settings.upload_dir / stored).resolve()
    if settings.upload_dir.resolve() not in path.parents:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume file not found.")
    return path


@router.get("/{resume_id}/download")
def download_resume(
    resume_id: int,
    current_user: models.User = Depends(require_hr),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the original file. Only the recruiter who owns the job may access it."""
    resume = db.get(models.Resume, resume_id)
    if resume is None or resume.job_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    get_owned_job(resume.job_id, current_user, db)
    path = _resolve_stored_path(resume)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resume file not found on server storage.")
    download_name = (resume.filename or path.name).split("_", 1)[-1]
    media_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
    return FileResponse(path, filename=download_name, media_type=media_type)
