import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db.session import get_db_for_user
from app.limiter import limiter
from app.onboarding import (
    AlreadyOnboarded,
    NoSamples,
    copy_samples,
    get_or_create_profile,
    list_samples,
    skip_onboarding,
)
from app.schemas import DocumentCreated, OnboardingOut

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingOut)
@limiter.limit("10/minute")
async def get_onboarding(
    request: Request,
    db: Session = Depends(get_db_for_user),
    user_id: uuid.UUID = Depends(get_current_user),
):
    profile = get_or_create_profile(db, user_id)
    if profile.onboarded_at is not None:
        return OnboardingOut(onboarded=True, samples=[])
    return OnboardingOut(onboarded=False, samples=list_samples())


@router.post("/samples", status_code=status.HTTP_201_CREATED,
             response_model=list[DocumentCreated])
@limiter.limit("2/minute")
async def add_samples(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user),
):
    # Seconds of blocking DB and storage calls -- keep them off the event loop.
    try:
        doc_ids = await asyncio.to_thread(copy_samples, user_id)
    except AlreadyOnboarded:
        raise HTTPException(status.HTTP_409_CONFLICT, "already onboarded")
    except NoSamples:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "no example documents are available")
    return [DocumentCreated(id=doc_id, status="ready") for doc_id in doc_ids]


@router.post("/skip", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def skip(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user),
):
    await asyncio.to_thread(skip_onboarding, user_id)
