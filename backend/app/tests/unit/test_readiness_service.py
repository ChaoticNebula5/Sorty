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
