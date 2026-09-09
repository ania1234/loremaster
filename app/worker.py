import asyncio
import os
import uuid

from arq.connections import RedisSettings
from sqlalchemy import text

from app.db.models import Document, SessionLocal
from app.db.store import store_chunks
from app.ingestion.chunk import chunk_document
from app.ingestion.embed import embed_chunks
from app.ingestion.extract import extract_pages, is_scanned
from app.ingestion.normalise import normalise
from app.storage import download_to_temp

REDIS = RedisSettings.from_dsn(
    os.environ.get("REDIS_URL", "redis://localhost:6379")
)


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


async def ingest_document(ctx, document_id: str, uid: uuid.UUID):
    doc_id = uuid.UUID(document_id)

    with SessionLocal() as db:
        db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(uid)},
        )
        print(f"worker: starting ingestion for {doc_id} (user {uid})")
        doc = db.get(Document, doc_id)
        user_id = doc.user_id
        session_date = doc.session_date
        storage_path = doc.storage_path

    # The API and the worker are separate containers, so the only copy of the
    # file they share is the one in Supabase Storage.
    temp_path = download_to_temp(storage_path)
    print(f"worker: downloaded {storage_path} to {temp_path}")

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

    finally:
        #cleanup: remove the downloaded file (also on the early returns above)
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

