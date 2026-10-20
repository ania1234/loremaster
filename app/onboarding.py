"""First-login onboarding: offer the example documents, or let the user skip.

The examples are ordinary documents owned by one "samples" account
(settings.sample_user_id), ingested once through the normal upload flow.
Onboarding copies their rows, chunks (embeddings included) and storage files
into the user's workspace, so nothing is extracted or embedded again.

RLS means the samples can only be read in a session that sets the samples
owner's id, and only written in one that sets the user's. So the copy reads
in one session and writes in another; no policy is loosened for it.
"""
import uuid

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Chunk, Document, UserProfile
from app.db.session import session_for_user
from app.schemas import SampleOut
from app.storage import copy_object, delete_object

# Copied as they are; id, user_id, storage_path and status are set per copy.
DOCUMENT_COLUMNS = ("title", "doc_type", "file_hash", "game_system",
                    "campaign", "session_date", "page_count")
# tsv is computed by Postgres and created_at defaults, so neither is copied.
CHUNK_COLUMNS = ("ordinal", "content", "heading_path", "page_from",
                 "page_to", "token_count", "embedding")


class AlreadyOnboarded(Exception):
    pass


class NoSamples(Exception):
    pass


def get_or_create_profile(db: Session, user_id: uuid.UUID,
                          lock: bool = False) -> UserProfile:
    """The user's profile, created on first sight with onboarding pending."""
    db.execute(pg_insert(UserProfile)
               .values(user_id=user_id)
               .on_conflict_do_nothing(index_elements=["user_id"]))
    query = select(UserProfile).where(UserProfile.user_id == user_id)
    if lock:
        query = query.with_for_update()
    return db.execute(query).scalar_one()


def _sample_documents(db: Session) -> list[Document]:
    return (db.query(Document)
              .filter(Document.user_id == settings.sample_user_id,
                      Document.status == "ready")
              .order_by(Document.doc_type, Document.title)
              .all())


def list_samples() -> list[SampleOut]:
    if settings.sample_user_id is None:
        return []
    with session_for_user(settings.sample_user_id) as db:
        return [SampleOut(title=d.title, doc_type=d.doc_type)
                for d in _sample_documents(db)]


def _read_samples() -> list[tuple[dict, list[dict]]]:
    """Each sample document and its chunks, as plain dicts.

    session_for_user commits on exit, which expires ORM objects -- so copy
    everything out while the session is still open.
    """
    with session_for_user(settings.sample_user_id) as db:
        samples = []
        for doc in _sample_documents(db):
            doc_values = {c: getattr(doc, c) for c in DOCUMENT_COLUMNS}
            doc_values["storage_path"] = doc.storage_path
            rows = db.execute(
                select(*(getattr(Chunk, c) for c in CHUNK_COLUMNS))
                .where(Chunk.document_id == doc.id)
                .order_by(Chunk.ordinal)
            ).mappings().all()
            samples.append((doc_values, [dict(r) for r in rows]))
        return samples


def copy_samples(user_id: uuid.UUID) -> list[uuid.UUID]:
    """Copy every sample into the user's workspace and mark them onboarded.

    The documents, chunks and the onboarded flag are written in one
    transaction. Storage is not transactional, so the files copied before a
    failure are removed again by hand.
    """
    if settings.sample_user_id is None:
        raise NoSamples

    copied_paths: list[str] = []
    try:
        with session_for_user(user_id) as db:
            # Locked so a double click or a second tab can't copy twice.
            profile = get_or_create_profile(db, user_id, lock=True)
            if profile.onboarded_at is not None:
                raise AlreadyOnboarded

            samples = _read_samples()
            if not samples:
                raise NoSamples

            # A sample the user already uploaded themselves is not copied
            # again -- uploads are deduplicated by hash the same way.
            owned_hashes = set(db.scalars(
                select(Document.file_hash).where(Document.user_id == user_id)))

            new_ids = []
            for doc_values, chunk_rows in samples:
                if doc_values["file_hash"] in owned_hashes:
                    continue
                doc_id = uuid.uuid4()
                # The download endpoint expects exactly this path.
                path = copy_object(doc_values["storage_path"],
                                   f"{user_id}/{doc_id}.pdf")
                copied_paths.append(path)

                db.add(Document(
                    id=doc_id,
                    user_id=user_id,
                    storage_path=path,
                    status="ready",
                    **{c: doc_values[c] for c in DOCUMENT_COLUMNS},
                ))
                db.flush()      # the chunks' foreign key needs the row
                if chunk_rows:
                    db.execute(insert(Chunk), [
                        {**row, "document_id": doc_id, "user_id": user_id}
                        for row in chunk_rows
                    ])
                new_ids.append(doc_id)

            profile.onboarded_at = func.now()
        return new_ids

    except Exception:
        for path in copied_paths:
            try:
                delete_object(path)
            except Exception as exc:  # noqa: BLE001 - keep cleaning up the rest
                print(f"onboarding: could not remove {path}: {exc}")
        raise


def skip_onboarding(user_id: uuid.UUID) -> None:
    with session_for_user(user_id) as db:
        profile = get_or_create_profile(db, user_id, lock=True)
        if profile.onboarded_at is None:
            profile.onboarded_at = func.now()
