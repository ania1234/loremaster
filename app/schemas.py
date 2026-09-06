import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

class DownloadLinkOut(BaseModel):
    id: uuid.UUID
    link: str

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    doc_type: Literal["ruleset", "transcript"]
    status: Literal["pending", "processing", "ready", "failed"]
    error_message: str | None = None
    game_system: str | None = None
    campaign: str | None = None
    session_date: date | None = None
    page_count: int | None = None
    created_at: datetime
    # note: no embedding, no storage_path, no user_id


class DocumentCreated(BaseModel):
    id: uuid.UUID
    status: str


class Citation(BaseModel):
    n: int
    chunk_id: uuid.UUID
    document_title: str
    page_from: int | None
    page_to: int | None
    heading_path: str | None


class AnswerOut(BaseModel):
    answer: str
    citations: list[Citation]
    verified: bool