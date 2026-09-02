from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers import documents
from app.routers import chat
from app.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("starting up")
    yield
    print("shutting down")


app = FastAPI(title="Loremaster API", lifespan=lifespan)

app.include_router(documents.router)
app.include_router(chat.router)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # the Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.post("/api/echo")
async def echo(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")
    return {"you_asked": body.question, "length": len(body.question)}