from dataclasses import dataclass
from importlib.util import find_spec

import httpx
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
        check_vision_provider(),
        check_embedding_provider(),
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


def check_vision_provider() -> ComponentReadiness:
    settings = get_settings()
    provider = settings.vision_provider

    if provider == "mock":
        return ComponentReadiness(
            name="vision_provider",
            status="ok",
            detail="mock provider selected.",
        )

    if provider == "gemini":
        if settings.gemini_api_key:
            return ComponentReadiness(
                name="vision_provider",
                status="ok",
                detail="gemini provider configured.",
            )
        return ComponentReadiness(
            name="vision_provider",
            status="error",
            detail="GEMINI_API_KEY is required when VISION_PROVIDER=gemini.",
        )

    if provider == "ollama":
        if not settings.ollama_base_url or not settings.ollama_vision_model:
            return ComponentReadiness(
                name="vision_provider",
                status="error",
                detail="OLLAMA_BASE_URL and OLLAMA_VISION_MODEL are required.",
            )
        try:
            response = httpx.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=1.5,
            )
            response.raise_for_status()
        except Exception:
            return ComponentReadiness(
                name="vision_provider",
                status="error",
                detail="Ollama is selected but not reachable.",
            )
        return ComponentReadiness(
            name="vision_provider",
            status="ok",
            detail="ollama provider reachable.",
        )

    return ComponentReadiness(
        name="vision_provider",
        status="error",
        detail=f"Unsupported vision provider: {provider}.",
    )


def check_embedding_provider() -> ComponentReadiness:
    settings = get_settings()
    provider = settings.embedding_provider

    if provider == "mock":
        return ComponentReadiness(
            name="embedding_provider",
            status="ok",
            detail="mock provider selected.",
        )

    if provider == "sentence-transformers":
        if not settings.embedding_model:
            return ComponentReadiness(
                name="embedding_provider",
                status="error",
                detail="EMBEDDING_MODEL is required.",
            )
        if settings.embedding_dimension != 384:
            return ComponentReadiness(
                name="embedding_provider",
                status="error",
                detail="EMBEDDING_DIMENSION must be 384 for the current pgvector schema.",
            )
        if find_spec("sentence_transformers") is None:
            return ComponentReadiness(
                name="embedding_provider",
                status="error",
                detail="sentence-transformers package is not installed.",
            )
        return ComponentReadiness(
            name="embedding_provider",
            status="ok",
            detail="sentence-transformers provider configured.",
        )

    return ComponentReadiness(
        name="embedding_provider",
        status="error",
        detail=f"Unsupported embedding provider: {provider}.",
    )
