import hashlib
import uuid
from pathlib import Path

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

@router.post("", status_code=status.HTTP_202_ACCEPTED,
             response_model=DocumentCreated)
@limiter.limit("2/minute")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if not ext.endswith((".pdf", ".md")):
        raise HTTPException(400, "only PDF and md files are supported")

    data = await file.read()

    if ext == ".pdf" and is_scanned(data):
        raise HTTPException(422, "this PDF appears to be a scan with no text layer")

    #send the document to cloud storage (Supabase) instead of local storage

    doc_id = uuid.uuid4()
    file_hash = hashlib.sha256(data).hexdigest()

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

    doc_id, pending = store_document(cloud_path, str(user_id), doc_type, title, pages_no, str(doc_id), file_hash)
    redis = request.app.state.redis
    if pending:
        job = await redis.enqueue_job("ingest_document", str(doc_id), str(user_id))
    else:
        return DocumentCreated(id=doc_id, status="ready")
    return DocumentCreated(id=doc_id, status="pending")

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