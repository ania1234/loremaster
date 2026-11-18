import hashlib
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.models import Document
from app.db.session import get_db_for_user
from app.db.store import store_document
from app.ingestion.extract import is_scanned
from app.limiter import limiter
from app.schemas import DocumentCreated, DocumentOut, DownloadLinkOut
from app.storage import delete_object, signed_url, upload_pdf

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Scratch space for the page count only -- the file the worker reads comes
# from Supabase Storage, since it runs in a different container.
UPLOAD_DIR = Path("data/uploads")

# Matches Supabase Storage's default per-file limit.
MAX_UPLOAD_BYTES = 50_000_000

SESSION_DATE_RE =re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_session_date(filename: str | None) -> date | None:
    """Pull the session date out of a filename like "session-2025-03-14.md".

    Returns None when the name holds no date, or holds one that is not real
    (e.g. 2025-02-30).
    """
    if not filename:
        return None
    match = SESSION_DATE_RE.search(Path(filename).stem)
    if match is None:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


@router.post("", status_code=status.HTTP_202_ACCEPTED,
             response_model=DocumentCreated)
@limiter.limit("2/minute")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: Literal["ruleset", "transcript"] = Form(...),
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if not ext.endswith((".pdf", ".md")):
        raise HTTPException(400, "only PDF and md files are supported")

    # Starlette has spooled the upload to disk by now; read() would put all of
    # it in memory, so a huge file could take the API down for everyone.
    if file.size is None or file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"files are limited to {MAX_UPLOAD_BYTES // 1_000_000} MB")

    data = await file.read()

    if ext == ".pdf" and is_scanned(data):
        raise HTTPException(422, "this PDF appears to be a scan with no text layer")

    #send the document to cloud storage (Supabase) instead of local storage

    file_hash = hashlib.sha256(data).hexdigest()
    redis = request.app.state.redis

    # Checked before the storage upload, so a repeat upload leaves no orphan file.
    existing = (db.query(Document)
                  .filter(Document.user_id == user_id, Document.file_hash == file_hash)
                  .first())
    if existing is not None:
        if existing.status == "ready":
            return DocumentCreated(id=existing.id, status="ready")
        # pending, processing or failed: queue it again. If a job for it is
        # still queued or running, enqueue_ingest is a no-op.
        await enqueue_ingest(redis, existing.id, user_id)
        return DocumentCreated(id=existing.id, status="pending")

    doc_id = uuid.uuid4()
    cloud_path = upload_pdf(user_id, doc_id, data)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOAD_DIR / f"{doc_id}{ext}"
    temp_path.write_bytes(data)
    try:
        doc = pymupdf.open(temp_path)
        pages_no = doc.page_count
        doc.close()
    finally:
        temp_path.unlink(missing_ok=True)

    session_date = parse_session_date(file.filename)

    doc_id, pending = store_document(cloud_path, str(user_id), doc_type, title, pages_no, str(doc_id), file_hash, session_date)
    if not pending:
        return DocumentCreated(id=doc_id, status="ready")
    await enqueue_ingest(redis, doc_id, user_id)
    return DocumentCreated(id=doc_id, status="pending")


async def enqueue_ingest(redis, doc_id, user_id) -> None:
    """Queue ingestion, at most one job per document at a time.

    arq refuses a job whose id is already queued or running, so a repeat
    upload can't start a second job that stores every chunk twice.
    WorkerSettings.keep_result = 0 lets the id be reused once the job ends,
    so a failed document can still be retried.
    """
    await redis.enqueue_job("ingest_document", str(doc_id), str(user_id),
                            _job_id=f"ingest:{doc_id}")

@router.get("/download/{doc_id}", response_model=DownloadLinkOut)
@limiter.limit("10/minute")
async def get_download_link(
    request: Request,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    # Implementation for generating download link
    storage_path = f"{user_id}/{doc_id}.pdf"
    link, err = signed_url(storage_path)
    if err is not None:
        status_code = int(getattr(err, "status", 502) or 502)
        detail = getattr(err, "message", None) or "could not generate download link"
        raise HTTPException(status_code, detail)
    return DownloadLinkOut(id=doc_id, link=link)

@router.get("", response_model=list[DocumentOut])
@limiter.limit("10/minute")
async def list_documents(
    request: Request,
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    return (db.query(Document)
              .filter(Document.user_id == user_id)
              .order_by(Document.created_at.desc())
              .all())


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    doc = (db.query(Document)
             .filter(Document.id == doc_id, Document.user_id == user_id)
             .first())
    if not doc:
        raise HTTPException(404, "document not found")
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    doc = (db.query(Document)
             .filter(Document.id == doc_id, Document.user_id == user_id)
             .first())
    if not doc:
        raise HTTPException(404, "document not found")
    delete_object(doc.storage_path)
    db.delete(doc)          # chunks cascade
    db.commit()