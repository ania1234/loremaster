"""One ingestion job, run as its own process by app.worker.

    python -m app.ingest_job <document_id> <user_id>
    python -m app.ingest_job --mark-failed <document_id> <user_id> <message>

The process exits when the job ends, which hands all of the pipeline's memory
back to the OS. See app/worker.py for why that matters.
"""
import sys
import time
import traceback
import uuid

from app.db.models import Document
from app.db.session import session_for_user
from app.db.store import store_chunks
from app.ingestion.chunk import chunk_document
from app.ingestion.embed import embed_chunks
from app.ingestion.extract import extract_pages, is_scanned
from app.ingestion.normalise import normalise
from app.storage import download_to_temp
from app.worker import FAILURE_RECORDED


def _set_status(doc_id, status, uid: str, error=None, page_count=None):
    with session_for_user(uid) as db:
        doc = db.get(Document, doc_id)
        doc.status = status
        doc.error_message = error
        if page_count is not None:
            doc.page_count = page_count
    print(f"worker: set status for {doc_id} to {status} (error={error})")


def ingest(document_id: str, uid: str):
    """The whole pipeline, start to finish."""
    doc_id = uuid.UUID(document_id)
    started = time.perf_counter()

    print(f"worker: starting ingestion for {doc_id} (user {uid})")
    # session_for_user commits on exit, which expires `doc` -- copy out
    # everything the pipeline needs while the session is still open.
    with session_for_user(uid) as db:
        doc = db.get(Document, doc_id)
        user_id = doc.user_id
        session_date = doc.session_date
        storage_path = doc.storage_path
        doc_type = doc.doc_type

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

        # Extraction is minutes of CPU on a rulebook, so each stage reports how
        # long it took -- otherwise "processing" is an unexplained black box.
        t0 = time.perf_counter()
        pages = normalise(extract_pages(temp_path, doc_type))
        print(f"worker: {doc_id} extracted {len(pages)} pages "
              f"in {time.perf_counter() - t0:.1f}s")

        chunks = chunk_document(pages, doc_type)
        print(f"worker: {doc_id} chunked into {len(chunks)} chunks")
        if not chunks:
            _set_status(doc_id, "failed", uid=uid, error="No readable text was found in this document.")
            return

        date_str = session_date.isoformat() if session_date else None
        t0 = time.perf_counter()
        vectors = embed_chunks(chunks, session_date=date_str)
        print(f"worker: {doc_id} embedded {len(vectors)} chunks "
              f"in {time.perf_counter() - t0:.1f}s")

        store_chunks(chunks, vectors, str(user_id), doc_id)   # one transaction
        _set_status(doc_id, "ready", uid=uid, page_count=len(pages))
        print(f"ingested {doc_id}: {len(chunks)} chunks from {len(pages)} pages "
              f"in {time.perf_counter() - started:.1f}s total")

    except Exception as exc:
        print(f"worker: {doc_id} failed after {time.perf_counter() - started:.1f}s: {exc}")
        _set_status(doc_id, "failed", uid=uid, error=f"Ingestion failed: {exc}")
        traceback.print_exc()
        # The user already has the specific error, so the parent must not
        # replace it with its generic one.
        sys.exit(FAILURE_RECORDED)

    finally:
        #cleanup: remove the downloaded file (also on the early returns above)
        temp_path.unlink(missing_ok=True)


def main(argv: list[str]):
    if argv[0] == "--mark-failed":
        document_id, uid, message = argv[1:]
        _set_status(uuid.UUID(document_id), "failed", uid, error=message)
    else:
        document_id, uid = argv
        ingest(document_id, uid)


if __name__ == "__main__":
    main(sys.argv[1:])
