import sys
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services import search_service, storage_factory


def backfill_missing_visual_embeddings(
    db: Session,
    event_id: uuid.UUID | None = None,
    limit: int = 100,
    raise_errors: bool = False,
) -> int:
    storage = storage_factory.get_storage_service()
    processed = 0
    media_items = search_service.list_media_missing_visual_embeddings(
        db,
        event_id=event_id,
        limit=limit,
    )

    for media in media_items:
        temp_path: Path | None = None
        try:
            temp_path = storage.download_to_temp(media.original_object_key)
            search_service.upsert_media_visual_embedding(
                db,
                media,
                temp_path,
                commit=False,
            )
            db.commit()
            processed += 1
        except Exception:
            db.rollback()
            if raise_errors:
                raise
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    return processed


if __name__ == "__main__":
    event_id = uuid.UUID(sys.argv[1]) if len(sys.argv) > 1 else None
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    with SessionLocal() as db:
        count = backfill_missing_visual_embeddings(
            db,
            event_id=event_id,
            limit=limit,
            raise_errors=True,
        )
    print(f"visual_embedding_backfill_complete count={count}")
