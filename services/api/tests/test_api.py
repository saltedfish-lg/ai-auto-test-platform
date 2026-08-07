import pytest
from fastapi.testclient import TestClient
from platform_api import ApiSettings, create_app
from platform_api.health import process_self_check
from pydantic import ValidationError


def settings() -> ApiSettings:
    return ApiSettings(
        _env_file=None,
        environment="test",
        database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
    )


def test_missing_required_configuration_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLATFORM_ENVIRONMENT", raising=False)
    monkeypatch.delenv("PLATFORM_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        ApiSettings(_env_file=None)


def test_non_mysql_database_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="MySQL PyMySQL"):
        ApiSettings(_env_file=None, environment="test", database_url="sqlite:///local.db")


def test_api_assembles_without_undeclared_public_routes() -> None:
    app = create_app(settings())

    with TestClient(app) as client:
        response = client.get("/not-a-formal-route", headers={"X-Correlation-Id": "request-1"})

    assert response.status_code == 404
    assert response.headers["X-Correlation-Id"] == "request-1"
    assert app.openapi_url is None


def test_process_self_check_is_internal_and_deterministic() -> None:
    assert process_self_check(settings()) == {
        "service": "platform-api",
        "environment": "test",
        "status": "ready",
        "release_id": "PDBR-2026.08.07-R4.2",
    }
