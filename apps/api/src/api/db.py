from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings
from api.models.base import Base

__all__ = ["Base", "get_db", "engine", "SessionLocal"]


_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True) if _settings.database_url else None
SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, expire_on_commit=False) if engine else None
)


def get_db() -> Iterator[Session]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
