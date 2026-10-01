import datetime

from app.db.models import Chunk as ChunkRow
from app.db.models import Document
from app.db.session import session_for_user
from app.ingestion.chunk import Chunk

"""Store a pdf

    python app/db/store.py "data/Reincarnated as the Unlovable Villainess.pdf" "00000000-0000-0000-0000-000000000000" "ruleset"
    python app/db/store.py "data/sesja.md" "00000000-0000-0000-0000-000000000000" "transcript"
"""




def store_document(path: str, user_id: str, doc_type: str, title: str, pages_no: int, doc_id: str, file_hash: str, session_date: datetime) -> tuple[str, bool]:
    with session_for_user(user_id) as session:
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
                id=doc_id,
                session_date=session_date
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
                    
def store_chunks(chunks: list[Chunk], embeddings: list[list[float]], user_id: str, file_hash: str) -> None:
    """Insert all chunks and mark the document ready, in one transaction.

    Raises on failure (after rolling back) so the caller can record the error.
    Writing "failed" here would not work: the rollback discards the
    transaction-local app.current_user_id, so RLS would block the update.
    """
    with session_for_user(user_id) as session:
        try:
            document = (
                session.query(Document)
                .filter_by(user_id=user_id, file_hash=file_hash)
                .first()
            )
            if document is None:
                raise ValueError("Document not found in database")
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

        except Exception as exc:
            session.rollback()
            print(f"store_chunks failed: {exc}")
            raise
