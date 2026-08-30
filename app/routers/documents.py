import uuid
from pathlib import Path

from fastapi import (APIRouter, Depends, File, Form, HTTPException, UploadFile,
                     status)
from sqlalchemy.orm import Session

from app.db.models import Document
from app.main import get_db
from app.schemas import DocumentCreated, DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Replaced by the real authenticated user in Lesson 33
DEV_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")
UPLOAD_DIR = Path("data/uploads")


@router.post("", status_code=status.HTTP_202_ACCEPTED,
             response_model=DocumentCreated)
async def upload(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lower()
    if not ext.endswith((".pdf", ".md")):
        raise HTTPException(400, "only PDF and md files are supported")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    path = UPLOAD_DIR / f"{doc_id}.{ext}"
    path.write_bytes(await file.read())

    doc = Document(id=doc_id, user_id=DEV_USER, title=title,
                   doc_type=doc_type, storage_path=str(path), status="pending")
    db.add(doc)
    db.commit()

    # SEAM: in Lesson 37 this becomes `await redis.enqueue_job("ingest", doc_id)`
    from app.ingestion.pipeline import ingest_document
    ingest_document(doc_id)

    return DocumentCreated(id=doc_id, status="pending")


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: Session = Depends(get_db)):
    return (db.query(Document)
              .filter(Document.user_id == DEV_USER)
              .order_by(Document.created_at.desc())
              .all())


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = (db.query(Document)
             .filter(Document.id == doc_id, Document.user_id == DEV_USER)
             .first())
    if not doc:
        raise HTTPException(404, "document not found")
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = (db.query(Document)
             .filter(Document.id == doc_id, Document.user_id == DEV_USER)
             .first())
    if not doc:
        raise HTTPException(404, "document not found")
    Path(doc.storage_path).unlink(missing_ok=True)
    db.delete(doc)          # chunks cascade
    db.commit()