from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    import backend.main

    return importlib.reload(backend.main)


def test_fastapi_import_and_health(application) -> None:
    client = TestClient(application.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health(application) -> None:
    class FakeResult:
        def scalar_one(self):
            return 1

    class FakeSession:
        def execute(self, statement):
            assert "SELECT 1" in str(statement)
            return FakeResult()

    def override_get_db():
        yield FakeSession()

    application.app.dependency_overrides[application.get_db] = override_get_db
    try:
        response = TestClient(application.app).get("/health/db")
    finally:
        application.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_cors_is_environment_driven(application) -> None:
    response = TestClient(application.app).get(
        "/health",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://example.com"


def test_configuration_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import backend.core.config as config

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        importlib.reload(config)


def test_habitation_routes_validate_input_and_unknown_resources(application) -> None:
    class FakeScalars:
        def all(self):
            return []

    class FakeSession:
        def scalar(self, statement):
            return None

        def scalars(self, statement):
            return FakeScalars()

    def override_get_db():
        yield FakeSession()

    application.app.dependency_overrides[application.get_db] = override_get_db
    try:
        client = TestClient(application.app)
        assert client.get("/api/v1/habitations?limit=0").status_code == 422
        assert client.get("/api/v1/habitations/999999").status_code == 404
        assert client.get("/api/v1/habitations").status_code == 200
    finally:
        application.app.dependency_overrides.clear()


def test_approval_requires_authentication(application) -> None:
    response = TestClient(application.app).post(
        "/api/v1/recommendations/1/approval",
        json={"action": "APPROVE"},
    )
    assert response.status_code == 401
