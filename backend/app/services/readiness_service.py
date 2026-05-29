from dataclasses import dataclass

import redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import storage_factory


@dataclass(frozen=True)
class ComponentReadiness:
    name: str
    status: str
    detail: str | None = None


@dataclass(frozen=True)
class ReadinessReport:
    status: str
    components: list[ComponentReadiness]


def check_readiness() -> ReadinessReport:
    components = [
        check_database(),
        check_redis(),
        check_storage(),
    ]
    status = "ready" if all(item.status == "ok" for item in components) else "degraded"
    return ReadinessReport(status=status, components=components)


def check_database() -> ComponentReadiness:
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
    except Exception:
        return ComponentReadiness(
            name="database",
            status="error",
            detail="Database connection failed.",
        )

    return ComponentReadiness(name="database", status="ok")


def check_redis() -> ComponentReadiness:
    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url)
        client.ping()
    except Exception:
        return ComponentReadiness(
            name="redis",
            status="error",
            detail="Redis connection failed.",
        )

    return ComponentReadiness(name="redis", status="ok")


def check_storage() -> ComponentReadiness:
    try:
        storage_factory.get_storage_service()
    except Exception:
        return ComponentReadiness(
            name="storage",
            status="error",
            detail="Storage service unavailable.",
        )

    return ComponentReadiness(name="storage", status="ok")
