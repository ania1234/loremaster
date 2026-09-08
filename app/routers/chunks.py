import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.models import Chunk
from app.db.session import get_db_for_user
from app.schemas import ChunkOut

router = APIRouter(prefix="/api/chunks", tags=["chunks"])

@router.get("/{chunk_id}", response_model=ChunkOut)
async def get_chunk(
    request: Request,
    chunk_id: uuid.UUID,
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    chunk = db.query(Chunk).filter_by(id=chunk_id, user_id=user_id).first()
    if not chunk:
        raise HTTPException(404, "chunk not found")

    return ChunkOut(id=chunk.id, text=chunk.content)