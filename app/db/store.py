import hashlib
import uuid
import sys
from pathlib import Path

from sqlalchemy import text

from app.db.models import Chunk as ChunkRow
from app.db.models import Document, SessionLocal
from app.ingestion.chunk import Chunk, chunk_document
from app.ingestion.embed import embed_chunks
from app.ingestion.extract import extract_pages, is_scanned
from app.ingestion.normalise import normalise

"""Store a pdf

    python app/db/store.py "data/Reincarnated as the Unlovable Villainess.pdf" "00000000-0000-0000-0000-000000000000" "ruleset"
    python app/db/store.py "data/sesja.md" "00000000-0000-0000-0000-000000000000" "transcript"
"""




def store_document(path: str, user_id: str, doc_type: str, title: str, pages_no: int, doc_id: str, file_hash: str) -> tuple[str, bool]:
    with SessionLocal() as session:
        session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id)},
        )
        document = (
            session.query(Document)
            .filter_by(user_id=user_id, file_hash=file_hash)
            .first()
        )
        if document is None:
            document = Document(
                user_id=user_id,
                title=title,
                doc_type=doc_type,
                storage_path=str(path),
                page_count=pages_no,
                status="pending",
                file_hash=file_hash,
                id=doc_id
            )
            session.add(document)
            session.commit()
            return doc_id, True
        else:
            if document.status == "ready":
                print("Document already stored")
                return document.id, False
            else:
                return document.id, True
                    
def store_chunks(chunks: list[Chunk], embeddings: list[list[float]], user_id: str, file_hash: str) -> bool:
     with SessionLocal() as session:
            session.execute(
            text("SELECT set_config('app.current_user_id', :uid, true)"),
            {"uid": str(user_id)},
            )
            try:
                document = (
                    session.query(Document)
                    .filter_by(user_id=user_id, file_hash=file_hash)
                    .first()
                )
                if document is None:
                    raise ValueError("Document not found in database")
                else:
                    if document.status == "ready":
                        raise ValueError("Document already stored")
                    
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
                if(document is not None):
                    document.status = "failed"
                    document.error_message = str(exc)[:2000]
                session.commit()
                print(f"store_chunks failed: {exc}")
                return False


