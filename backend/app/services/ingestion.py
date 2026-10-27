"""Resume ingestion: validate and store uploads, extract features, persist rows.

Single and batch uploads share one code path. Each resume is written inside its
own savepoint, so one bad file never leaves half-written rows or blocks the
rest of the batch; embeddings for the whole batch are computed in one model call.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..auth import ROLE_CANDIDATE, get_owned_job
from ..cache import CacheService, job_summary_key
from ..config import settings
from ..ml_utils import DocumentError, check_file_signature, embed_batch, extract_skills, extract_text, parse_contacts
from ..schemas import ParsedResume, ResumeUploadResult
from .skills import get_or_create_skills, load_skill_index

logger = logging.getLogger("ingestion")
CHUNK_SIZE = 64 * 1024
MIN_TEXT_CHARS = 30
# Characters no common file system accepts in a name (control characters, and the
# ones Windows reserves); they become "_" so a stored name is valid on every OS.
_UNSAFE_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')
# File systems cap a name at 255 bytes; this leaves room for the random prefix.
MAX_NAME_BYTES = 150


class UploadRejected(Exception):
    """A file refused before processing; carries the HTTP status (400 or 413) to return."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        """Create the error with a user-facing ``message`` and an HTTP ``status_code``."""
        super().__init__(message)
        self.status_code = status_code


@dataclass
class StoredUpload:
    """A file saved under ``UPLOAD_DIR`` as ``<12 random hex chars>_<original name>``."""

    original_name: str
    stored_name: str

    @property
    def path(self) -> Path:
        """Absolute location of the stored file."""
        return settings.upload_dir / self.stored_name


def _safe_original_name(filename: Optional[str]) -> str:
    r"""Base name of a client-supplied file name, safe to create on any OS.

    Backslashes count as separators too, so ``..\\..\\x.pdf`` becomes ``x.pdf``.
    Characters invalid in file names become ``_``, and long names are shortened to
    ``MAX_NAME_BYTES`` of UTF-8 (counted in bytes, not characters, because a
    150-character name in a non-Latin script can exceed the 255-byte limit).
    """
    name = Path((filename or "").replace("\\", "/")).name
    name = _UNSAFE_NAME_CHARS.sub("_", name).strip()
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        stem, suffix = Path(name).stem, Path(name).suffix
        room = max(MAX_NAME_BYTES - len(suffix.encode("utf-8")), 0)
        name = stem.encode("utf-8")[:room].decode("utf-8", "ignore").strip() + suffix
    return name or "resume"


def save_upload(upload: UploadFile) -> StoredUpload:
    """Stream an upload to disk, enforcing type, signature and size limits."""
    original = _safe_original_name(upload.filename)
    extension = Path(original).suffix.lower()
    if extension not in settings.allowed_extensions:
        raise UploadRejected(f"Unsupported file type '{extension or 'none'}'. Allowed: {', '.join(settings.allowed_extensions)}")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored = StoredUpload(original, f"{uuid.uuid4().hex[:12]}_{original}")
    written = 0
    try:
        with open(stored.path, "wb") as out:
            while chunk := upload.file.read(CHUNK_SIZE):
                if written == 0:  # the first chunk holds the magic bytes that identify the format
                    check_file_signature(chunk[:8], extension)
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise UploadRejected(
                        f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit.",
                        413,  # Content Too Large
                    )
                out.write(chunk)
        if written == 0:
            raise UploadRejected("Uploaded file is empty.")
    except DocumentError as exc:
        stored.path.unlink(missing_ok=True)
        raise UploadRejected(str(exc)) from exc
    except Exception:
        stored.path.unlink(missing_ok=True)
        raise
    finally:
        upload.file.close()
    return stored


def require_open_job(db: Session, job_id: int, uploader: models.User) -> models.Job:
    """Return the job an upload targets, or raise 404 (unknown job) / 403.

    Candidates may apply to any job. Recruiters upload on applicants' behalf only
    to jobs they created, so one recruiter cannot add applicants to another
    recruiter's pipeline.
    """
    if uploader.role != ROLE_CANDIDATE:
        return get_owned_job(job_id, uploader, db)
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job opening not found.")
    return job


def _upsert_candidate(db: Session, contacts: dict, uploader: models.User) -> models.Candidate:
    """Find or create the applicant this resume belongs to.

    A candidate applying for themselves is identified by their signed-in account,
    never by an email typed inside the document; otherwise anyone could attach
    resumes to (or rename) another applicant's profile. A recruiter uploading on an
    applicant's behalf is trusted to provide that applicant's resume, so the email
    found in the document identifies the applicant. Profiles are shared by every
    job the applicant applied to, so a recruiter's upload only fills in a missing
    name or phone and never renames an existing applicant.
    """
    if uploader.role == ROLE_CANDIDATE:
        email = uploader.email
        name = contacts.get("name") or uploader.name
    else:
        email = contacts.get("email")
        name = contacts.get("name") or "Unnamed candidate"

    candidate = None
    if email:
        candidate = db.query(models.Candidate).filter(func.lower(models.Candidate.email) == email.lower()).first()
    if candidate is None:
        candidate = models.Candidate(full_name=name, email=email.lower() if email else None, phone=contacts.get("phone"))
        db.add(candidate)
        db.flush()
    else:
        if contacts.get("name") and (uploader.role == ROLE_CANDIDATE or not candidate.full_name):
            candidate.full_name = contacts["name"]
        if contacts.get("phone") and not candidate.phone:
            candidate.phone = contacts["phone"]
    return candidate


def process_uploads(db: Session, job: models.Job, uploads: List[StoredUpload], uploader: models.User) -> List[ResumeUploadResult]:
    """Extract, embed and persist a list of stored uploads for ``job``."""
    texts: List[Optional[str]] = []
    results: List[Optional[ResumeUploadResult]] = []
    for item in uploads:
        try:
            text = extract_text(item.path)
            if len(text.strip()) < MIN_TEXT_CHARS:
                raise DocumentError("No readable text found (scanned image PDFs are not supported).")
            texts.append(text)
            results.append(None)
        except DocumentError as exc:
            item.path.unlink(missing_ok=True)
            texts.append(None)
            results.append(ResumeUploadResult(filename=item.original_name, status="failed", error=str(exc)))

    readable = [i for i, t in enumerate(texts) if t is not None]
    embeddings = embed_batch([texts[i] for i in readable])
    embedding_by_index = dict(zip(readable, embeddings, strict=True))
    vocabulary = load_skill_index(db)

    for i in readable:
        item, text = uploads[i], texts[i]
        try:
            # SAVEPOINT: a failure rolls back only this resume, not the whole batch.
            with db.begin_nested():
                contacts = parse_contacts(text)
                candidate = _upsert_candidate(db, contacts, uploader)
                found = extract_skills(text, vocabulary.keys())
                skills = [name for name, _ in found]
                confidence = dict(found)
                resume = models.Resume(
                    candidate=candidate,
                    job_id=job.job_id,
                    filename=item.stored_name,
                    upload_path=item.stored_name,
                    raw_text=text,
                    parsed_json={"parsed": contacts, "skills": skills},
                    embedding=embedding_by_index.get(i),
                )
                db.add(resume)
                for skill in get_or_create_skills(db, skills, vocabulary):
                    db.add(models.ResumeSkill(resume=resume, skill=skill, confidence=confidence.get(skill.skill_name, 0.95)))
                db.flush()
            results[i] = ResumeUploadResult(
                filename=item.original_name,
                status="processed",
                resume_id=resume.resume_id,
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.full_name,
                parsed=ParsedResume(**contacts, skills=skills),
            )
        except Exception:
            logger.exception("Failed to store resume %s", item.original_name)
            item.path.unlink(missing_ok=True)
            results[i] = ResumeUploadResult(filename=item.original_name, status="failed", error="Could not save this resume.")

    try:
        db.commit()
    except Exception:
        # Nothing was saved: remove the files of the resumes that would have been stored.
        db.rollback()
        for i in readable:
            if results[i] is not None and results[i].status == "processed":
                uploads[i].path.unlink(missing_ok=True)
        raise
    CacheService.delete(job_summary_key(job.job_id))
    logger.info("Ingested %s/%s resumes for job %s", sum(r.status == "processed" for r in results), len(results), job.job_id)
    return results
