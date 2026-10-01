import asyncio
import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from litellm import completion
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db.models import Chunk, Conversation, Document, Message, MessageCitation
from app.db.session import get_db_for_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
 
HISTORY_TURNS_FOR_REWRITE = 4
 
 
# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
 
class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
 
 
class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
 
    model_config = {"from_attributes": True}
 
 
class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    role: Literal["user", "bot"]
    model_used: str | None
    citations: list[CitationCreate] = []
 
 
class CitationCreate(BaseModel):
    n: int
    chunk_id: uuid.UUID
    document_title: str
    page_from: int | None
    page_to: int | None
    heading_path: str | None
 
 
class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    model_used: str | None
    created_at: datetime
    citations: list[CitationCreate] = []
 
 
def _owned_conversation(db: Session, conv_id: uuid.UUID) -> Conversation:
    """RLS already scopes the row; 404 (not 403) so we don't leak existence."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    return conv
 
 
def _citations_for(
    db: Session, message_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[CitationCreate]]:
    """Rehydrate stored citations in one query, grouped per message in [n] order.

    Citations of deleted documents are already gone (chunk FK cascades).
    """
    out: dict[uuid.UUID, list[CitationCreate]] = defaultdict(list)
    if not message_ids:
        return out
    rows = (
        db.query(MessageCitation.message_id, MessageCitation.n, Chunk, Document.title)
        .join(Chunk, Chunk.id == MessageCitation.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .filter(MessageCitation.message_id.in_(message_ids))
        .order_by(MessageCitation.n)
        .all()
    )
    for message_id, n, chunk, title in rows:
        out[message_id].append(CitationCreate(
            n=n, chunk_id=chunk.id, document_title=title,
            page_from=chunk.page_from, page_to=chunk.page_to,
            heading_path=chunk.heading_path,
        ))
    return out
 

@router.post("", response_model=ConversationOut,
             status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    conv = Conversation(user_id=user_id, title=body.title)
    db.add(conv)
    db.flush()          # populate the server-side default id before commit
    return conv
 
@router.post("/{conv_id}/message", response_model=MessageOut,
             status_code=status.HTTP_201_CREATED)
async def create_message(
    conv_id: uuid.UUID,
    body: MessageCreate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    _owned_conversation(db, conv_id)

    if body.role == "user" and body.citations:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "user messages cannot carry citations")

    msg = Message(conversation_id=conv_id, role=body.role, content=body.content,
                  model_used=body.model_used)
    db.add(msg)
    db.flush()          # need msg.id for the citation rows

    db.add_all(MessageCitation(message_id=msg.id, chunk_id=c.chunk_id, n=c.n)
               for c in body.citations)
    db.flush()

    return MessageOut(
        id=msg.id, role=msg.role, content=msg.content,
        model_used=msg.model_used, created_at=msg.created_at,
        citations=sorted(body.citations, key=lambda c: c.n),
    )

@router.get("/{conv_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conv_id: uuid.UUID,
    limit: int = Query(default=100, le=200),
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    _owned_conversation(db, conv_id)
 
    q = db.query(Message).filter(Message.conversation_id == conv_id)
    rows = q.order_by(Message.created_at.desc()).limit(limit).all()[::-1]
    citations = _citations_for(db, [m.id for m in rows])

    return [
        MessageOut(
            id=m.id, role=m.role, content=m.content,
            model_used=m.model_used, created_at=m.created_at,
            citations=citations[m.id],
        )
        for m in rows
    ]