from types import SimpleNamespace

from app.services import readiness_service


def test_check_readiness_reports_ready_when_all_components_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "check_database",
        lambda: readiness_service.ComponentReadiness(name="database", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_redis",
        lambda: readiness_service.ComponentReadiness(name="redis", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_storage",
        lambda: readiness_service.ComponentReadiness(name="storage", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_vision_provider",
        lambda: readiness_service.ComponentReadiness(name="vision_provider", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_embedding_provider",
        lambda: readiness_service.ComponentReadiness(name="embedding_provider", status="ok"),
    )

    report = readiness_service.check_readiness()

    assert report.status == "ready"


def test_check_readiness_reports_degraded_when_any_component_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "check_database",
        lambda: readiness_service.ComponentReadiness(name="database", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_redis",
        lambda: readiness_service.ComponentReadiness(name="redis", status="error"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_storage",
        lambda: readiness_service.ComponentReadiness(name="storage", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_vision_provider",
        lambda: readiness_service.ComponentReadiness(name="vision_provider", status="ok"),
    )
    monkeypatch.setattr(
        readiness_service,
        "check_embedding_provider",
        lambda: readiness_service.ComponentReadiness(name="embedding_provider", status="ok"),
    )

    report = readiness_service.check_readiness()

    assert report.status == "degraded"


def test_check_database_hides_exception_details(monkeypatch) -> None:
    class FailingSession:
        def __enter__(self):
            raise RuntimeError("postgres://secret")

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

    monkeypatch.setattr(readiness_service, "SessionLocal", lambda: FailingSession())

    result = readiness_service.check_database()

    assert result.name == "database"
    assert result.status == "error"
    assert result.detail == "Database connection failed."


def test_check_redis_hides_exception_details(monkeypatch) -> None:
    class FailingRedis:
        def ping(self) -> None:
            raise RuntimeError("redis://secret")

    monkeypatch.setattr(
        readiness_service.redis,
        "from_url",
        lambda url: FailingRedis(),
    )

    result = readiness_service.check_redis()

    assert result.name == "redis"
    assert result.status == "error"
    assert result.detail == "Redis connection failed."


def test_check_storage_hides_exception_details(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service.storage_factory,
        "get_storage_service",
        lambda: (_ for _ in ()).throw(RuntimeError("minio-secret")),
    )

    result = readiness_service.check_storage()

    assert result.name == "storage"
    assert result.status == "error"
    assert result.detail == "Storage service unavailable."


def test_check_vision_provider_reports_mock_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "get_settings",
        lambda: SimpleNamespace(vision_provider="mock"),
    )

    result = readiness_service.check_vision_provider()

    assert result.name == "vision_provider"
    assert result.status == "ok"


def test_check_vision_provider_reports_gemini_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "get_settings",
        lambda: SimpleNamespace(vision_provider="gemini", gemini_api_key=""),
    )

    result = readiness_service.check_vision_provider()

    assert result.name == "vision_provider"
    assert result.status == "error"
    assert "GEMINI_API_KEY" in result.detail


def test_check_vision_provider_reports_ollama_reachable(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        readiness_service,
        "get_settings",
        lambda: SimpleNamespace(
            vision_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_vision_model="llava",
        ),
    )
    monkeypatch.setattr(readiness_service.httpx, "get", lambda *args, **kwargs: FakeResponse())

    result = readiness_service.check_vision_provider()

    assert result.name == "vision_provider"
    assert result.status == "ok"


def test_check_vision_provider_reports_ollama_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "get_settings",
        lambda: SimpleNamespace(
            vision_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_vision_model="llava",
        ),
    )
    monkeypatch.setattr(
        readiness_service.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    result = readiness_service.check_vision_provider()

    assert result.name == "vision_provider"
    assert result.status == "error"
    assert result.detail == "Ollama is selected but not reachable."


def test_check_embedding_provider_reports_sentence_transformers_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="sentence-transformers",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dimension=384,
        ),
    )
    monkeypatch.setattr(readiness_service, "find_spec", lambda package: object())

    result = readiness_service.check_embedding_provider()

    assert result.name == "embedding_provider"
    assert result.status == "ok"


def test_check_embedding_provider_reports_dimension_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="sentence-transformers",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dimension=768,
        ),
    )

    result = readiness_service.check_embedding_provider()

    assert result.name == "embedding_provider"
    assert result.status == "error"
    assert result.detail == "EMBEDDING_DIMENSION must be 384 for the current pgvector schema."
