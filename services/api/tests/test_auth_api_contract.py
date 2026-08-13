from __future__ import annotations

import base64
import json
import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from platform_api import ApiSettings, create_app
from platform_api.keygen import generate_development_key_ring


@pytest.fixture
def key_ring_file() -> Iterator[Path]:
    directory = Path.cwd() / ".runtime" / f"auth-api-ring-{secrets.token_hex(8)}"
    generated = generate_development_key_ring(directory, kid="auth-api-test-kid")
    try:
        yield generated.manifest_file
    finally:
        shutil.rmtree(directory)


def _settings(key_ring_file: Path) -> ApiSettings:
    hmac_key_file = key_ring_file.parent / "auth-hmac-master.key"
    _write_hmac_ring(hmac_key_file)
    return ApiSettings(
        _env_file=None,
        environment="test",
        database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
        jwt_key_ring_file=key_ring_file,
        auth_hmac_master_key_file=hmac_key_file,
    )


def test_exact_frozen_auth_operations_are_registered(key_ring_file: Path) -> None:
    app = create_app(_settings(key_ring_file))
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


def test_exact_user_governance_operations_are_registered(key_ring_file: Path) -> None:
    app = create_app(_settings(key_ring_file))
    operations = {
        (method, route.path, route.operation_id)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
        if route.path.startswith(("/api/v1/user", "/api/v1/user-role-binding"))
    }
    assert operations == {
        ("POST", "/api/v1/user", "create_user"),
        ("POST", "/api/v1/user/{id}/credential-reset", "reset_user_credential"),
        ("POST", "/api/v1/user/{id}/enable", "enable_user"),
        ("POST", "/api/v1/user/{id}/disable", "disable_user"),
        ("POST", "/api/v1/user-role-binding", "create_user_role_binding"),
        (
            "POST",
            "/api/v1/user-role-binding/{id}/revoke",
            "revoke_user_role_binding",
        ),
    }


def test_invalid_configured_key_ring_fails_app_creation() -> None:
    directory = Path.cwd() / ".runtime" / f"invalid-ring-{secrets.token_hex(8)}"
    directory.mkdir(parents=True, exist_ok=False)
    try:
        manifest = directory / "invalid-key-ring.json"
        manifest.write_text('{"ring_version":"broken"}', encoding="utf-8")
        hmac_key_file = directory / "auth-hmac-master.key"
        _write_hmac_ring(hmac_key_file)
        settings = ApiSettings(
            _env_file=None,
            environment="test",
            database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
            jwt_key_ring_file=manifest,
            auth_hmac_master_key_file=hmac_key_file,
        )

        with pytest.raises(RuntimeError, match="root schema"):
            create_app(settings)
    finally:
        shutil.rmtree(directory)


def _write_hmac_ring(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ring_version": "test-v1",
                "active_key_id": "active",
                "keys": [
                    {
                        "key_id": "active",
                        "key_material": base64.urlsafe_b64encode(b"x" * 32).rstrip(b"=").decode(),
                        "activated_at": "2025-01-01T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_missing_bearer_returns_frozen_problem_details(key_ring_file: Path) -> None:
    app = create_app(_settings(key_ring_file))
    correlation_id = "11111111111111111111111111111111"
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"X-Correlation-Id": correlation_id},
        )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "about:blank",
        "title": "Authentication required",
        "status": 401,
        "code": "AUTH_REQUIRED",
        "detail": "A Bearer access token is required.",
        "correlation_id": correlation_id,
    }


def test_cookie_operation_requires_same_origin_before_database_access(
    key_ring_file: Path,
) -> None:
    app = create_app(_settings(key_ring_file))
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/refresh", json={})

    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_OPERATION_FORBIDDEN_FOR_STATE"


def test_forwarded_headers_cannot_spoof_refresh_same_origin(key_ring_file: Path) -> None:
    app = create_app(_settings(key_ring_file))
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


def test_login_validation_is_problem_details_and_redacts_password(key_ring_file: Path) -> None:
    secret = "SyntheticLoginSecret-" + ("x" * 160)
    correlation_id = "22222222222222222222222222222222"
    app = create_app(_settings(key_ring_file))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Correlation-Id": correlation_id},
            json={"username": "admin", "password": secret},
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "AUTH_REQUEST_VALIDATION_FAILED"
    assert response.json()["correlation_id"] == correlation_id
    assert response.json()["field_errors"] == [
        {"field": "password", "message": "Field validation failed."}
    ]
    assert secret not in response.text
    assert "input" not in response.text


def test_change_password_validation_is_redacted_problem_details(key_ring_file: Path) -> None:
    secret = "SyntheticChangeSecret-" + ("x" * 160)
    correlation_id = "33333333333333333333333333333333"
    app = create_app(_settings(key_ring_file))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/change-password",
            headers={
                "X-Correlation-Id": correlation_id,
                "Idempotency-Key": "validation-change-password",
            },
            json={"current_password": secret, "new_password": "ValidPassword-7"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "AUTH_REQUEST_VALIDATION_FAILED"
    assert response.json()["correlation_id"] == correlation_id
    assert response.json()["field_errors"] == [
        {"field": "current_password", "message": "Field validation failed."}
    ]
    assert secret not in response.text
    assert "input" not in response.text
