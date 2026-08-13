import base64
import json
import logging
import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from platform_api import ApiSettings, create_app
from platform_api.audit import AuditContext, AuthenticationAuditService
from platform_api.health import process_self_check
from platform_api.keygen import generate_development_key_ring
from platform_api.middleware import CorrelationIdMiddleware, canonicalize_correlation_id
from platform_api.security import new_refresh_token
from platform_observability import configure_logging
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


@pytest.fixture
def key_ring_file() -> Iterator[Path]:
    directory = Path.cwd() / ".runtime" / f"api-test-ring-{secrets.token_hex(8)}"
    generated = generate_development_key_ring(directory, kid="api-test-kid")
    try:
        yield generated.manifest_file
    finally:
        shutil.rmtree(directory)


def settings(key_ring_file: Path) -> ApiSettings:
    hmac_key_file = key_ring_file.parent / "auth-hmac-master.key"
    hmac_key_file.write_text(
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
    return ApiSettings(
        _env_file=None,
        environment="test",
        database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
        jwt_key_ring_file=key_ring_file,
        auth_hmac_master_key_file=hmac_key_file,
    )


def test_missing_required_configuration_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLATFORM_ENVIRONMENT", raising=False)
    monkeypatch.delenv("ATP_DATABASE_URL", raising=False)
    monkeypatch.delenv("ATP_JWT_KEY_RING_FILE", raising=False)
    monkeypatch.delenv("ATP_AUTH_HMAC_MASTER_KEY_FILE", raising=False)

    with pytest.raises(ValidationError):
        ApiSettings(_env_file=None)


def test_application_database_uses_the_governed_environment_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governed_url = "mysql+pymysql://platform:local@127.0.0.1/ai_auto_test_platform_dev"
    monkeypatch.setenv("ATP_DATABASE_URL", governed_url)
    monkeypatch.setenv("PLATFORM_DATABASE_URL", "sqlite:///legacy-must-not-win.db")

    configured = ApiSettings(
        _env_file=None,
        environment="test",
        jwt_key_ring_file=Path("runtime-jwt-ring.json"),
        auth_hmac_master_key_file=Path("runtime-auth-hmac-ring.json"),
    )

    assert configured.database_url == governed_url


def test_invalid_database_environment_value_hides_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = "environment-database-secret"
    monkeypatch.setenv("ATP_DATABASE_URL", f"postgresql://platform:{marker}@127.0.0.1/platform")

    with pytest.raises(ValidationError) as captured:
        ApiSettings(
            _env_file=None,
            environment="test",
            jwt_key_ring_file=Path("runtime-jwt-ring.json"),
            auth_hmac_master_key_file=Path("runtime-auth-hmac-ring.json"),
        )

    assert marker not in str(captured.value)


def test_missing_key_ring_configuration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATP_JWT_KEY_RING_FILE", raising=False)

    with pytest.raises(ValidationError, match="ATP_JWT_KEY_RING_FILE"):
        ApiSettings(
            _env_file=None,
            environment="test",
            database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
        )


def test_non_mysql_database_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="MySQL PyMySQL"):
        ApiSettings(_env_file=None, environment="test", database_url="sqlite:///local.db")


def test_invalid_database_configuration_hides_secret_input() -> None:
    marker = "synthetic-database-secret"
    with pytest.raises(ValidationError) as captured:
        ApiSettings(
            _env_file=None,
            environment="test",
            database_url=f"postgresql://platform:{marker}@127.0.0.1/platform",
        )

    assert marker not in str(captured.value)


def test_api_assembles_without_undeclared_public_routes(key_ring_file: Path) -> None:
    app = create_app(settings(key_ring_file))
    correlation_id = "0123456789abcdef0123456789abcdef"

    with TestClient(app) as client:
        response = client.get(
            "/not-a-formal-route",
            headers={"X-Correlation-Id": correlation_id},
        )

    assert response.status_code == 404
    assert response.headers["X-Correlation-Id"] == correlation_id
    assert app.openapi_url is None


@pytest.mark.parametrize(
    "correlation_id",
    [
        "01J5M7Y6Q4Z8W3R2T1V0X9C8B7",
        "550e8400-e29b-41d4-a716-446655440000",
        "0123456789abcdef0123456789abcdef",
    ],
)
def test_correlation_policy_preserves_canonical_ids(correlation_id: str) -> None:
    assert canonicalize_correlation_id(correlation_id) == correlation_id


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "request-1",
        "auth:login:attempt-42",
        "short-password",
        "release_candidate_validation_2026_08_11",
        "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.signature",
        "0" * 32,
    ],
)
def test_correlation_policy_replaces_every_noncanonical_value(unsafe_value: str) -> None:
    canonical = canonicalize_correlation_id(unsafe_value)

    assert canonical != unsafe_value
    assert str(UUID(canonical)) == canonical


def test_refresh_token_correlation_header_never_reaches_response_log_or_audit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_refresh_token = new_refresh_token()

    async def endpoint(request: Request) -> JSONResponse:
        logging.getLogger("correlation-security-test").warning("request handled")
        return JSONResponse({"correlation_id": request.state.correlation_id})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationIdMiddleware)
    configure_logging("INFO")
    try:
        with TestClient(app) as client:
            response = client.get("/", headers={"X-Correlation-Id": raw_refresh_token})
        log_output = capsys.readouterr().err
    finally:
        logging.getLogger().handlers.clear()

    canonical = response.headers["X-Correlation-Id"]
    assert canonical != raw_refresh_token
    assert response.json()["correlation_id"] == canonical
    assert raw_refresh_token not in response.text
    assert raw_refresh_token not in log_output
    assert canonical in log_output
    assert AuditContext(raw_refresh_token, "test-source").correlation_id != raw_refresh_token

    class CapturingSession:
        row: object | None = None

        def add(self, row: object) -> None:
            self.row = row

    capturing_session = CapturingSession()
    audit_row = AuthenticationAuditService().append(
        cast(Session, capturing_session),
        AuditContext(canonical, "test-source"),
        action="REFRESH_FAILED",
        operation_id="refresh_platform_session",
        result_code="AUTH_SESSION_REVOKED",
    )
    assert audit_row.correlation_id == canonical
    assert raw_refresh_token not in repr(audit_row)


def test_process_self_check_is_internal_and_deterministic(key_ring_file: Path) -> None:
    assert process_self_check(settings(key_ring_file)) == {
        "service": "platform-api",
        "environment": "test",
        "status": "ready",
        "authority_model": "SINGLE_LIVING_AUTHORITY",
    }
