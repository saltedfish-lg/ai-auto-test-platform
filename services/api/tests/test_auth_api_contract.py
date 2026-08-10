from __future__ import annotations

from fastapi.testclient import TestClient
from platform_api import ApiSettings, create_app


def _settings() -> ApiSettings:
    return ApiSettings(
        _env_file=None,
        environment="test",
        database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
    )


def test_exact_frozen_auth_operations_are_registered() -> None:
    app = create_app(_settings())
    operations = {
        (method, route.path, route.operation_id)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
        if route.path.startswith("/api/v1/auth")
    }
    assert operations == {
        ("POST", "/api/v1/auth/login", "login_platform_user"),
        ("POST", "/api/v1/auth/refresh", "refresh_platform_session"),
        ("POST", "/api/v1/auth/logout", "logout_platform_user"),
        ("GET", "/api/v1/auth/me", "get_current_user"),
        ("POST", "/api/v1/auth/change-password", "change_current_user_password"),
    }


def test_missing_bearer_returns_frozen_problem_details() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"X-Correlation-Id": "auth-test"})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "about:blank",
        "title": "Authentication required",
        "status": 401,
        "code": "AUTH_REQUIRED",
        "detail": "A Bearer access token is required.",
        "correlation_id": "auth-test",
    }


def test_cookie_operation_requires_same_origin_before_database_access() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/refresh", json={})

    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_OPERATION_FORBIDDEN_FOR_STATE"


def test_forwarded_headers_cannot_spoof_refresh_same_origin() -> None:
    app = create_app(_settings())
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/auth/refresh",
            headers={
                "Origin": "https://attacker.example",
                "X-Forwarded-Host": "attacker.example",
                "X-Forwarded-Proto": "https",
            },
            json={},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_OPERATION_FORBIDDEN_FOR_STATE"


def test_login_validation_is_problem_details_and_redacts_password() -> None:
    secret = "SyntheticLoginSecret-" + ("x" * 160)
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Correlation-Id": "validation-login"},
            json={"username": "admin", "password": secret},
        )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"
    assert response.json()["correlation_id"] == "validation-login"
    assert response.json()["field_errors"] == [
        {"field": "password", "message": "Field validation failed."}
    ]
    assert secret not in response.text
    assert "input" not in response.text


def test_change_password_validation_is_redacted_problem_details() -> None:
    secret = "SyntheticChangeSecret-" + ("x" * 160)
    app = create_app(_settings())
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/change-password",
            headers={
                "X-Correlation-Id": "validation-change",
                "Idempotency-Key": "validation-change-password",
            },
            json={"current_password": secret, "new_password": "ValidPassword-7"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "AUTH_OPERATION_FORBIDDEN_FOR_STATE"
    assert response.json()["correlation_id"] == "validation-change"
    assert response.json()["field_errors"] == [
        {"field": "current_password", "message": "Field validation failed."}
    ]
    assert secret not in response.text
    assert "input" not in response.text
