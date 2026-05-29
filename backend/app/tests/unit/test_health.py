from fastapi.testclient import TestClient

from app.api.routes_health import readiness_service
from app.main import app


def test_health_check_returns_ok() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "status": "ok",
            "app": "Sorty AI",
        },
        "error": None,
    }


def test_readiness_check_returns_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "check_readiness",
        lambda: readiness_service.ReadinessReport(
            status="ready",
            components=[
                readiness_service.ComponentReadiness(name="database", status="ok"),
                readiness_service.ComponentReadiness(name="redis", status="ok"),
                readiness_service.ComponentReadiness(name="storage", status="ok"),
            ],
        ),
    )

    response = TestClient(app).get("/api/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["status"] == "ready"
    assert body["data"]["components"][0] == {
        "name": "database",
        "status": "ok",
        "detail": None,
    }


def test_readiness_check_returns_503_when_degraded(monkeypatch) -> None:
    monkeypatch.setattr(
        readiness_service,
        "check_readiness",
        lambda: readiness_service.ReadinessReport(
            status="degraded",
            components=[
                readiness_service.ComponentReadiness(
                    name="database",
                    status="error",
                    detail="Database connection failed.",
                ),
            ],
        ),
    )

    response = TestClient(app).get("/api/ready")

    assert response.status_code == 503
    assert response.json()["data"]["components"][0] == {
        "name": "database",
        "status": "error",
        "detail": "Database connection failed.",
    }
