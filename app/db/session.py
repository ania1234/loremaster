import uuid

from fastapi import Depends
from sqlalchemy import text

from app.auth import get_current_user
from app.db.models import SessionLocal


def get_db():
    """One session per request, always closed. Injected with Depends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_for_user(user_id: uuid.UUID = Depends(get_current_user)):
    """One transaction per request, with the RLS identity set on it."""
    db = SessionLocal()
    try:
        db.execute(
            text("SELECT set_config('app.current_user_id', :uid, true)"),
            {"uid": str(user_id)},
        )
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
