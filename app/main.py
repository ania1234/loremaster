import os
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.limiter import limiter
from app.routers import chat, chunks, documents
from app.worker import REDIS


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("starting up")
    app.state.redis = await create_pool(REDIS)
    yield
    await app.state.redis.close()
    print("shutting down")


app = FastAPI(title="Loremaster API", lifespan=lifespan)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(chunks.router)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Comma-separated list; defaults to the Next.js dev server.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
async def health():
    """Liveness only -- the platform healthcheck must not fail on a DB blip."""
    return {"status": "ok"}


@app.get("/health/deep")
async def health_deep(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.post("/api/echo")
async def echo(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    return {"you_asked": body.question, "length": len(body.question)}