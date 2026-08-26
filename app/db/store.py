import hashlib
import uuid
import sys
from pathlib import Path

from app.db.models import Chunk as ChunkRow
from app.db.models import Document, SessionLocal
from app.ingestion.chunk import chunk_document
from app.ingestion.embed import embed_chunks
from app.ingestion.extract import extract_pages, is_scanned

"""Store a pdf

    python app/db/store.py "data/Reincarnated as the Unlovable Villainess.pdf"
"""

def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def store_document(path: str, user_id: str, doc_type: str) -> bool:
    file_path = Path(path)
    title = file_path.name
    uid = uuid.UUID(user_id)

    print(f"started document store for {title}")

    if is_scanned(file_path):
        raise ValueError("document appears to be a scan with no text layer")

    pages = extract_pages(file_path)
    chunks = chunk_document(pages)
    if not chunks:
        raise ValueError("no chunks produced from document")

    embeddings = embed_chunks(chunks)
    file_hash = _file_hash(path)

    if len(embeddings) != len(chunks):
        raise ValueError("Embeddings count different than chunks")
    
    with SessionLocal() as session:
        try:
            document = (
                session.query(Document)
                .filter_by(user_id=uid, file_hash=file_hash)
                .first()
            )
            if document is None:
                document = Document(
                    user_id=uid,
                    title=title,
                    doc_type=doc_type,
                    storage_path=str(file_path),
                    page_count=len(pages),
                    status="pending",
                    file_hash=file_hash,
                )
                session.add(document)
                session.flush()  # assigns document.id without committing yet
            else:
                if document.status == "ready":
                    print("Document already stored")
                    return True
                
            session.add_all(
                ChunkRow(
                    document_id=document.id,
                    user_id=document.user_id,
                    ordinal=c.ordinal,
                    content=c.content,
                    heading_path=c.heading_path,
                    page_from=c.page_from,
                    page_to=c.page_to,
                    token_count=c.token_count,
                    embedding=emb,
                )
                for c, emb in zip(chunks, embeddings)
            )
            document.status = "ready"
            session.commit()
            return True

        except Exception as exc:
            session.rollback()
            document.status = "failed"
            document.error_message = str(exc)[:2000]
            session.commit()
            print(f"store_document failed for {file_path}: {exc}")
            return False


if __name__ == "__main__":
    path = Path(sys.argv[1])
    user_id = sys.argv[2] if len(sys.argv) > 2 else "00000000-0000-0000-0000-000000000000"
    doc_type = sys.argv[3] if len(sys.argv) > 3 else "ruleset"
    store_document(path, user_id, doc_type)
