from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

__all__ = ["get_db", "require_api_key"]
