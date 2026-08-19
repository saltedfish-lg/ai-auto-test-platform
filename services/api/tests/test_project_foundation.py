from __future__ import annotations

import base64
import json
import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from platform_api import ApiSettings, create_app
from platform_api.auth_service import (
    GENERIC_RBAC_CONDITION,
    AuthenticationService,
)
from platform_api.errors import PlatformError
from platform_api.keygen import generate_development_key_ring
from platform_api.models import ProjectAudit
from platform_api.project_schemas import (
    CreateProjectRequest,
    ProjectStateCommandRequest,
    UpdateProjectRequest,
)
from platform_api.project_service import ProjectService, _project_integrity_error
from pydantic import ValidationError
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def key_ring_file() -> Iterator[Path]:
    directory = Path.cwd() / ".runtime" / f"project-api-ring-{secrets.token_hex(8)}"
    generated = generate_development_key_ring(directory, kid="project-api-test-kid")
    hmac_file = directory / "auth-hmac-master.key"
    hmac_file.write_text(
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
    try:
        yield generated.manifest_file
    finally:
        shutil.rmtree(directory)


def _settings(key_ring_file: Path) -> ApiSettings:
    return ApiSettings(
        _env_file=None,
        environment="test",
        database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
        jwt_key_ring_file=key_ring_file,
        auth_hmac_master_key_file=key_ring_file.parent / "auth-hmac-master.key",
    )


def test_exact_project_foundation_operations_are_registered(key_ring_file: Path) -> None:
    app = create_app(_settings(key_ring_file))
    operations = {
        (method, route.path, route.operation_id)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
        if route.path.startswith("/api/v1/project")
    }
    assert operations == {
        ("GET", "/api/v1/project", "list_project"),
        ("POST", "/api/v1/project", "create_project"),
        ("GET", "/api/v1/project/{id}", "get_project"),
        ("PATCH", "/api/v1/project/{id}", "update_project"),
        ("POST", "/api/v1/project/{id}/disable", "disable_project"),
        ("POST", "/api/v1/project/{id}/recover", "recover_project"),
        ("POST", "/api/v1/project/{id}/archive", "archive_project"),
    }


def test_project_commands_enforce_immutable_code_and_state_reason() -> None:
    body = CreateProjectRequest(project_code="ATP-PROJECT", owner_user_id=None)
    assert body.owner_user_id is None
    assert body.display_name is None

    with pytest.raises(ValidationError):
        CreateProjectRequest(project_code=" ATP-PROJECT")
    with pytest.raises(ValidationError):
        UpdateProjectRequest.model_validate(
            {"expected_version": 0, "project_code": "MUTATION-FORBIDDEN"}
        )
    with pytest.raises(ValidationError):
        ProjectStateCommandRequest(expected_version=0, reason="")


class _OwnerPermissionSession:
    def execute(self, statement: object) -> list[tuple[str, str | None, str]]:
        compiled = str(statement)
        if "atp_project_member" in compiled:
            return [("ALLOWED", GENERIC_RBAC_CONDITION, "ROLE-PROJECT-OWNER-DUTY")]
        return []


def test_active_owner_derives_project_permission_without_data_scope_grant() -> None:
    service = AuthenticationService.__new__(AuthenticationService)
    identity = SimpleNamespace(user=SimpleNamespace(user_id="owner-user-id"))
    context = SimpleNamespace(correlation_id="correlation-id", source_context="source-context")

    decision = service.require_project_permissions_in_transaction(
        _OwnerPermissionSession(),  # type: ignore[arg-type]
        identity,  # type: ignore[arg-type]
        "update_project",
        ("PROJECT_EDIT",),
        "project-id",
        context,  # type: ignore[arg-type]
    )
    assert decision == "DYNAMIC_PROJECT_OWNER_ALL"


class _PermissionProbe(AuthenticationService):
    def __init__(self) -> None:
        pass

    def _raise_permission_denied(  # type: ignore[override]
        self,
        identity: object,
        operation_id: str,
        audit_context: object,
        *,
        db: object | None = None,
    ) -> None:
        del identity, operation_id, audit_context, db
        raise PlatformError(
            title="Permission denied",
            detail="denied",
            status=403,
            code="AUTH_PERMISSION_DENIED",
        )


def _literal_sql(statement: object) -> str:
    return str(
        statement.compile(  # type: ignore[attr-defined]
            dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


class _PlatformProjectPermissionSession:
    def __init__(self, *, exact_project_grant: bool) -> None:
        self.exact_project_grant = exact_project_grant
        self.scalar_sql: list[str] = []

    def execute(self, statement: object) -> list[tuple[object, ...]]:
        sql = _literal_sql(statement)
        if "FROM atp_project_member" in sql:
            return []
        return [
            (
                "platform-binding",
                None,
                "platform-role",
                "ROLE-PLATFORM-ADMIN",
                "ALLOWED",
                GENERIC_RBAC_CONDITION,
            )
        ]

    def scalar(self, statement: object) -> str | None:
        sql = _literal_sql(statement)
        self.scalar_sql.append(sql)
        if (
            self.exact_project_grant
            and "AUTHORIZED_PROJECT_ACTIVE" in sql
            and "project-target" in sql
        ):
            return "grant-id"
        return None


def test_platform_technical_scope_never_grants_arbitrary_project_access() -> None:
    service = _PermissionProbe()
    session = _PlatformProjectPermissionSession(exact_project_grant=False)
    identity = SimpleNamespace(user=SimpleNamespace(user_id="platform-admin"))
    context = SimpleNamespace(correlation_id="correlation", source_context="source")

    with pytest.raises(PlatformError, match="denied") as caught:
        service.require_project_permissions_in_transaction(
            session,  # type: ignore[arg-type]
            identity,  # type: ignore[arg-type]
            "get_project",
            ("PROJECT_VIEW",),
            "project-target",
            context,  # type: ignore[arg-type]
        )

    assert caught.value.code == "AUTH_PERMISSION_DENIED"
    assert all("PLATFORM_TECHNICAL" not in sql for sql in session.scalar_sql)
    assert all("PLATFORM_ALL" not in sql for sql in session.scalar_sql)


def test_platform_admin_exact_project_grant_does_not_require_project_member() -> None:
    service = _PermissionProbe()
    session = _PlatformProjectPermissionSession(exact_project_grant=True)
    identity = SimpleNamespace(user=SimpleNamespace(user_id="platform-admin"))
    context = SimpleNamespace(correlation_id="correlation", source_context="source")

    decision = service.require_project_permissions_in_transaction(
        session,  # type: ignore[arg-type]
        identity,  # type: ignore[arg-type]
        "get_project",
        ("PROJECT_VIEW",),
        "project-target",
        context,  # type: ignore[arg-type]
    )

    assert decision == "ALLOWED"
    assert any("AUTHORIZED_PROJECT_ACTIVE" in sql for sql in session.scalar_sql)


class _RealtimeOwnerSession:
    def __init__(self, *, owner_duty_current: bool) -> None:
        self.owner_duty_current = owner_duty_current
        self.business_writes: list[object] = []

    def execute(self, statement: object) -> list[tuple[object, ...]]:
        sql = _literal_sql(statement)
        if "FROM atp_project_member" in sql and self.owner_duty_current:
            return [("ALLOWED", GENERIC_RBAC_CONDITION, "ROLE-PROJECT-OWNER-DUTY")]
        return []

    def add(self, value: object) -> None:
        self.business_writes.append(value)


@pytest.mark.parametrize("revoked_fact", ["membership_inactive", "owner_duty_removed"])
def test_same_identity_is_immediately_denied_after_owner_fact_revocation(
    revoked_fact: str,
) -> None:
    del revoked_fact
    service = _PermissionProbe()
    identity = SimpleNamespace(user=SimpleNamespace(user_id="owner-user"))
    context = SimpleNamespace(correlation_id="correlation", source_context="source")
    active = _RealtimeOwnerSession(owner_duty_current=True)
    revoked = _RealtimeOwnerSession(owner_duty_current=False)

    assert (
        service.require_project_permissions_in_transaction(
            active,  # type: ignore[arg-type]
            identity,  # type: ignore[arg-type]
            "update_project",
            ("PROJECT_EDIT",),
            "project-target",
            context,  # type: ignore[arg-type]
        )
        == "DYNAMIC_PROJECT_OWNER_ALL"
    )
    with pytest.raises(PlatformError) as caught:
        service.require_project_permissions_in_transaction(
            revoked,  # type: ignore[arg-type]
            identity,  # type: ignore[arg-type]
            "update_project",
            ("PROJECT_EDIT",),
            "project-target",
            context,  # type: ignore[arg-type]
        )

    assert caught.value.code == "AUTH_PERMISSION_DENIED"
    assert revoked.business_writes == []


class _Transaction:
    def __init__(self, session: _RealtimeOwnerSession) -> None:
        self.session = session

    def __enter__(self) -> _RealtimeOwnerSession:
        return self.session

    def __exit__(self, *args: object) -> None:
        del args


class _RevokedOwnerFactory:
    def __init__(self) -> None:
        self.session = _RealtimeOwnerSession(owner_duty_current=False)

    def begin(self) -> _Transaction:
        return _Transaction(self.session)


class _RevokedOwnerAuthentication:
    def __init__(self) -> None:
        self.probe = _PermissionProbe()
        self.identity = SimpleNamespace(user=SimpleNamespace(user_id="owner-user"))

    def authenticate_access_in_transaction(self, *args: object) -> object:
        del args
        return self.identity

    def require_project_permissions_in_transaction(
        self,
        db: object,
        identity: object,
        operation_id: str,
        permission_codes: tuple[str, ...],
        project_id: str,
        audit_context: object,
    ) -> str:
        return self.probe.require_project_permissions_in_transaction(
            db,  # type: ignore[arg-type]
            identity,  # type: ignore[arg-type]
            operation_id,
            permission_codes,
            project_id,
            audit_context,  # type: ignore[arg-type]
        )


class _IdempotencySpy:
    def __init__(self) -> None:
        self.claim_calls = 0

    def claim(self, *args: object) -> object:
        del args
        self.claim_calls += 1
        raise AssertionError("idempotency must not be claimed after authorization denial")


@pytest.mark.parametrize("revoked_fact", ["membership_inactive", "owner_duty_removed"])
def test_revoked_owner_same_token_api_request_has_no_business_side_effects(
    key_ring_file: Path,
    revoked_fact: str,
) -> None:
    del revoked_fact
    app = create_app(_settings(key_ring_file))
    factory = _RevokedOwnerFactory()
    idempotency = _IdempotencySpy()
    app.state.project_service = ProjectService(
        factory,  # type: ignore[arg-type]
        _RevokedOwnerAuthentication(),  # type: ignore[arg-type]
        idempotency,  # type: ignore[arg-type]
    )

    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/project/{'P' * 26}",
            headers={
                "Authorization": "Bearer same-valid-token",
                "Idempotency-Key": "revoked-owner-request",
            },
            json={"expected_version": 0, "display_name": "must-not-write"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_PERMISSION_DENIED"
    assert idempotency.claim_calls == 0
    assert factory.session.business_writes == []


class _QualificationSession:
    def __init__(self, decision: str) -> None:
        self.decision = decision

    def execute(self, statement: object) -> list[tuple[str, str]]:
        del statement
        return [(self.decision, GENERIC_RBAC_CONDITION)]


def test_owner_qualification_uses_deny_precedence() -> None:
    service = AuthenticationService.__new__(AuthenticationService)
    assert service.user_has_permission_qualification_in_transaction(
        _QualificationSession("ALLOWED"),  # type: ignore[arg-type]
        "user-id",
        "PROJECT_OWNER_ELIGIBLE",
    )
    assert not service.user_has_permission_qualification_in_transaction(
        _QualificationSession("DENIED"),  # type: ignore[arg-type]
        "user-id",
        "PROJECT_OWNER_ELIGIBLE",
    )


class _AuditCaptureSession:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, value: object) -> None:
        self.rows.append(value)


@pytest.mark.parametrize(
    "scope_decision",
    ["NOT_APPLICABLE", "DYNAMIC_PROJECT_OWNER_ALL", "ALLOWED"],
)
def test_project_audit_persists_actual_authorization_path(scope_decision: str) -> None:
    db = _AuditCaptureSession()
    project = SimpleNamespace(project_id="P" * 26, project_code="PROJECT-CODE")
    context = SimpleNamespace(correlation_id="correlation", source_context="source")

    ProjectService._append_audit(
        db,  # type: ignore[arg-type]
        project,  # type: ignore[arg-type]
        context,  # type: ignore[arg-type]
        action="PROJECT_UPDATED",
        operation_id="update_project",
        actor_user_id="U" * 26,
        participant_user_id=None,
        required_permission="PROJECT_EDIT",
        scope_decision=scope_decision,
        previous_status="ACTIVE",
        new_status="ACTIVE",
        reason=None,
    )

    assert len(db.rows) == 1
    row = db.rows[0]
    assert isinstance(row, ProjectAudit)
    assert row.scope_decision == scope_decision


def test_only_project_code_unique_integrity_error_maps_to_domain_conflict() -> None:
    duplicate = IntegrityError(
        "INSERT",
        {},
        Exception(
            1062,
            "Duplicate entry 'PROJECT-CODE' for key 'uq_atp_project_business'",
        ),
    )
    unrelated = IntegrityError(
        "INSERT",
        {},
        Exception(1452, "sentinel-sensitive-foreign-key-detail"),
    )

    assert _project_integrity_error(duplicate).code == "PROJECT_CODE_CONFLICT"
    failure = _project_integrity_error(unrelated)
    assert failure.code == "INTERNAL_ERROR"
    assert failure.status == 500
    assert "sentinel-sensitive" not in failure.detail


def test_project_validation_is_secret_free_problem_details(key_ring_file: Path) -> None:
    app = create_app(_settings(key_ring_file))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/project",
            headers={"Idempotency-Key": "project-validation"},
            json={"project_code": ""},
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "AUTH_REQUEST_VALIDATION_FAILED"
    assert response.json()["field_errors"] == [
        {"field": "project_code", "message": "Field validation failed."}
    ]
