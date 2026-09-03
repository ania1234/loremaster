import uuid
from datetime import datetime
from pathlib import Path

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
from app.db.session import get_db
from app.ingestion.extract import is_scanned
from app.limiter import limiter
from app.schemas import DocumentCreated, DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Replaced by the real authenticated user in Lesson 33
UPLOAD_DIR = Path("data/uploads")


@router.post("", status_code=status.HTTP_202_ACCEPTED,
             response_model=DocumentCreated)
@limiter.limit("1/minute")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower()
    if not ext.endswith((".pdf", ".md")):
        raise HTTPException(400, "only PDF and md files are supported")

    data = await file.read()

    if ext == ".pdf" and is_scanned(data):
        raise HTTPException(422, "this PDF appears to be a scan with no text layer")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    path = UPLOAD_DIR / f"{doc_id}.{ext}"
    path.write_bytes(data)

    # SEAM: in Lesson 37 this becomes `await redis.enqueue_job("ingest", doc_id)`
    from app.db.store import store_document
    result = store_document(path, str(user_id), doc_type, title)

    if not result:
        path.unlink()  # cleanup
        raise HTTPException(500, "failed to store document")
    return DocumentCreated(id=doc_id, status="pending")


@router.get("", response_model=list[DocumentOut])
@limiter.limit("1/minute")
async def list_documents(
    request: Request,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    return (db.query(Document)
              .filter(Document.user_id == user_id)
              .order_by(Document.created_at.desc())
              .all())


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
):
    doc = (db.query(Document)
             .filter(Document.id == doc_id, Document.user_id == user_id)
             .first())
    if not doc:
        raise HTTPException(404, "document not found")
    Path(doc.storage_path).unlink(missing_ok=True)
    db.delete(doc)          # chunks cascade
    db.commit()