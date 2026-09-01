from app.db.models import SessionLocal


def get_db():
    """One session per request, always closed. Injected with Depends."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
