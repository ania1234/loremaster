import asyncio
import uuid
from pathlib import Path

from arq.connections import RedisSettings
from sqlalchemy import text

from app.db.models import Document, SessionLocal
from app.db.store import store_chunks
from app.ingestion.chunk import chunk_document
from app.ingestion.embed import embed_chunks
from app.ingestion.extract import extract_pages, is_scanned
from app.ingestion.normalise import normalise

REDIS = RedisSettings(host="localhost", port=6379)


def _set_status(doc_id, status, uid: uuid.UUID, error=None, page_count=None):
    with SessionLocal() as db:
        db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(uid)},
        )
        doc = db.get(Document, doc_id)
        doc.status = status
        doc.error_message = error
        if page_count is not None:
            doc.page_count = page_count
        db.commit()
        print(f"worker: set status for {doc_id} to {status} (error={error})")   


async def ingest_document(ctx, document_id: str, uid: uuid.UUID, temp_path: Path):
    doc_id = uuid.UUID(document_id)

    print(f"worker ingesting doc with temp path {temp_path}")
    with SessionLocal() as db:
        db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(uid)},
        )
        print(f"worker: starting ingestion for {doc_id} (user {uid})")
        doc = db.get(Document, doc_id)
        user_id = doc.user_id
        session_date = doc.session_date

    try:
        _set_status(doc_id, "processing", uid)

        # Design doc section 6, step 0 -- reject scans with a clear message
        if  is_scanned(temp_path):
            _set_status(
                doc_id, "failed",
                uid=uid,
                error="This PDF contains images rather than selectable text "
                      "(it looks like a scan). Re-export it from the original "
                      "source, or run OCR before uploading.",
            )
            return

        pages = normalise(extract_pages(temp_path, doc.doc_type))
        chunks = chunk_document(pages, doc.doc_type)
        if not chunks:
            _set_status(doc_id, "failed", uid=uid, error="No readable text was found in this document.")
            return

        date_str = session_date.isoformat() if session_date else None
        vectors = embed_chunks(chunks, session_date=date_str)

        store_chunks(chunks, vectors, str(user_id), doc.file_hash)   # one transaction
        _set_status(doc_id, "ready", uid=uid, page_count=len(pages))
        print(f"ingested {doc_id}: {len(chunks)} chunks from {len(pages)} pages")

    except Exception as exc:
        _set_status(doc_id, "failed", uid=uid, error=f"Ingestion failed: {exc}")
        raise            # re-raise so ARQ logs it and retry policy applies

    #cleanup: remove the temporary file
    temp_path.unlink(missing_ok=True)


async def hello(ctx, name: str):
    print(f"worker: starting job for {name}")
    await asyncio.sleep(5)
    print(f"worker: done with {name}")
    return f"hello {name}"

class WorkerSettings:
    functions = [ingest_document, hello]
    redis_settings = REDIS
    max_jobs = 2
    job_timeout = 900

