from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import SessionLocal
from app.routers import documents


def get_db():
    """One session per request, always closed. Injected with Depends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("starting up")
    yield
    print("shutting down")


app = FastAPI(title="Loremaster API", lifespan=lifespan)

app.include_router(documents.router)

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