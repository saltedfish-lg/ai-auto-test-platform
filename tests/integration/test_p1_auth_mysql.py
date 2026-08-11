"""Real MySQL 8.4 runtime gate for the current Living Authority P1 auth boundary."""

from __future__ import annotations

import os
import secrets
from collections import defaultdict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from platform_api.app import create_app
from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticationService, AuthorizationContext
from platform_api.bootstrap import BOOTSTRAP_KEY, AdminBootstrapService
from platform_api.config import ApiSettings
from platform_api.errors import PlatformError
from platform_api.keygen import generate_development_key_ring
from platform_api.models import (
    Admin,
    AuthRefreshSession,
    AuthSecurityAudit,
    DataScopeGrant,
    IdempotencyRecord,
    OutboxEvent,
    PermissionCode,
    PlatformUser,
    PlatformUserCredential,
    Project,
    ProjectMember,
    Role,
    RoleBinding,
    RolePermission,
    UserRoleBinding,
)
from platform_api.security import PasswordService, new_refresh_token, new_ulid, utc_now
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker


def _database_url() -> str:
    value = os.getenv("ATP_P1_TEST_DATABASE_URL")
    if value is None:
        pytest.skip("ATP_P1_TEST_DATABASE_URL is required for the real MySQL P1 gate")
    return value


def _password(label: str) -> str:
    return f"{label}-{secrets.token_hex(12)}-7"


def _audit_context(label: str) -> AuditContext:
    return AuditContext(f"{label}-{new_ulid()}", label)


@pytest.fixture
def key_directory() -> Iterator[Path]:
    runtime_root = (Path.cwd() / ".runtime").resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    directory = runtime_root / f"p1-mysql-test-{secrets.token_hex(8)}"
    directory.mkdir(exist_ok=False)
    try:
        yield directory
    finally:
        for child in directory.iterdir():
            if child.is_file():
                child.unlink()
        directory.rmdir()


def _create_normal_user(
    factory: sessionmaker[Session], passwords: PasswordService
) -> tuple[str, str, str, str, str]:
    username = f"gate-{new_ulid().lower()}"
    password = _password("Normal")
    now = utc_now()
    decisions: dict[str, dict[str, str]] = defaultdict(dict)
    with factory() as db:
        rows = db.execute(
            select(
                Role.role_id,
                Role.role_code,
                PermissionCode.permission_code,
                RolePermission.decision,
            )
            .join(RolePermission, RolePermission.role_id == Role.role_id)
            .join(PermissionCode, PermissionCode.permission_code_id == RolePermission.permission_id)
            .where(Role.lifecycle_status == "ACTIVE", Role.role_code != "ROLE-SUPER-ADMIN")
        )
        role_ids: dict[str, str] = {}
        for role_id, role_code, permission_code, decision in rows:
            if role_code is not None:
                role_ids[role_code] = role_id
                decisions[role_code][permission_code] = decision
        selected = "ROLE-PLATFORM-ADMIN"
        assert "ALLOWED" in decisions[selected].values()
        assert "DENIED" in decisions[selected].values()
        allowed = next(
            code for code, decision in decisions[selected].items() if decision == "ALLOWED"
        )
        denied = next(
            code for code, decision in decisions[selected].items() if decision == "DENIED"
        )
        allowing_role = next(
            role_code
            for role_code, mapping in decisions.items()
            if role_code != selected and mapping.get(denied) == "ALLOWED"
        )
        user_id = new_ulid()
        credential_id = new_ulid()
        project_id = new_ulid()
        db.add(
            Project(
                project_id=project_id,
                project_code=f"P1-{project_id}",
                lifecycle_status="ACTIVE",
                display_name="P1 Runtime Gate Project",
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=user_id,
                updated_by=user_id,
                extension_json=None,
            )
        )
        db.flush()
        binding_id = new_ulid()
        allowing_binding_id = new_ulid()
        db.add_all(
            [
                PlatformUser(
                    user_id=user_id,
                    username=username,
                    role_binding_id=None,
                    lifecycle_status="ACTIVE",
                    display_name="P1 Runtime Gate User",
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=user_id,
                    updated_by=user_id,
                    extension_json=None,
                ),
                PlatformUserCredential(
                    credential_id=credential_id,
                    user_id=user_id,
                    credential_type="PASSWORD",
                    password_hash=passwords.hash(password),
                    password_algorithm="ARGON2ID_V19",
                    credential_version=1,
                    force_password_change=False,
                    failed_login_count=0,
                    failure_window_started_at=None,
                    locked_until=None,
                    last_failed_at=None,
                    last_successful_login_at=None,
                    password_changed_at=now,
                    lifecycle_status="ACTIVE",
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=user_id,
                    updated_by=user_id,
                ),
                UserRoleBinding(
                    binding_id=binding_id,
                    user_id=user_id,
                    role_id=role_ids[selected],
                    project_id=None,
                    valid_from=now,
                    valid_to=None,
                    row_version=0,
                ),
                UserRoleBinding(
                    binding_id=allowing_binding_id,
                    user_id=user_id,
                    role_id=role_ids[allowing_role],
                    project_id=project_id,
                    valid_from=now,
                    valid_to=None,
                    row_version=0,
                ),
                ProjectMember(
                    project_member_id=new_ulid(),
                    project_id=project_id,
                    user_id=user_id,
                    role_id=role_ids[selected],
                    lifecycle_status="ACTIVE",
                    display_name="P1 Runtime Gate Member",
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=user_id,
                    updated_by=user_id,
                    extension_json=None,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                DataScopeGrant(
                    grant_id=new_ulid(),
                    binding_id=binding_id,
                    scope_type="AUTHORIZED_PROJECT_ACTIVE",
                    scope_id=project_id,
                    permission_code=allowed,
                    created_at=now,
                ),
                DataScopeGrant(
                    grant_id=new_ulid(),
                    binding_id=allowing_binding_id,
                    scope_type="AUTHORIZED_PROJECT_ACTIVE",
                    scope_id=project_id,
                    permission_code=denied,
                    created_at=now,
                ),
                DataScopeGrant(
                    grant_id=new_ulid(),
                    binding_id=binding_id,
                    scope_type="AUTHORIZED_PROJECT_ACTIVE",
                    scope_id=project_id,
                    permission_code=denied,
                    created_at=now,
                ),
            ]
        )
        db.commit()
    return username, password, allowed, denied, project_id


def test_p1_auth_rbac_real_mysql_runtime_gate(key_directory: Path) -> None:
    key_ring = generate_development_key_ring(key_directory, kid="p1-mysql-rs256-v1")
    settings = ApiSettings(
        environment="test",
        database_url=_database_url(),
        jwt_key_ring_file=key_ring.manifest_file,
    )
    app = create_app(settings)
    factory: sessionmaker[Session] = app.state.session_factory
    passwords = PasswordService()
    initial_password = _password("Initial")
    changed_password = _password("Changed")

    bootstrap = AdminBootstrapService(factory, passwords)
    bootstrap_failure_correlation = str(uuid4())
    with factory.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER trg_test_auth_audit_no_insert "
                "BEFORE INSERT ON atp_auth_security_audit FOR EACH ROW "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'test audit insert failure'"
            )
        )
    try:
        with pytest.raises(DBAPIError):
            bootstrap.bootstrap(initial_password, bootstrap_failure_correlation)
    finally:
        with factory.begin() as db:
            db.execute(text("DROP TRIGGER trg_test_auth_audit_no_insert"))
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Admin)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlatformUser)
                .where(PlatformUser.username == "admin")
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlatformUserCredential)
                .join(PlatformUser, PlatformUser.user_id == PlatformUserCredential.user_id)
                .where(PlatformUser.username == "admin")
            )
            == 0
        )
        assert db.get(IdempotencyRecord, BOOTSTRAP_KEY) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(RoleBinding)
                .where(RoleBinding.display_name == "Default admin super-admin binding")
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(
                    OutboxEvent.event_type.in_(
                        ["user.active", "admin.active", "role_binding.active"]
                    )
                )
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthSecurityAudit)
                .where(AuthSecurityAudit.correlation_id == bootstrap_failure_correlation)
            )
            == 0
        )

    bootstrap_inputs = (f"gate-{new_ulid()}", f"gate-{new_ulid()}")
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent_results = list(
            executor.map(
                lambda correlation_id: bootstrap.bootstrap(initial_password, correlation_id),
                bootstrap_inputs,
            )
        )
    second = bootstrap.bootstrap(_password("Ignored"), f"gate-{new_ulid()}")
    assert sorted(result.status for result in concurrent_results) == [
        "ALREADY_INITIALIZED",
        "INITIALIZED",
    ]
    assert second.status == "ALREADY_INITIALIZED"

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PermissionCode)) == 50
        assert db.scalar(select(func.count()).select_from(Role)) == 12
        assert db.scalar(select(func.count()).select_from(RolePermission)) == 600
        assert db.scalar(select(func.count()).select_from(Admin)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlatformUser)
                .where(PlatformUser.username == "admin")
            )
            == 1
        )
        credential = db.scalar(
            select(PlatformUserCredential)
            .join(PlatformUser, PlatformUser.user_id == PlatformUserCredential.user_id)
            .where(PlatformUser.username == "admin")
        )
        assert credential is not None
        assert credential.password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=1$")
        assert credential.force_password_change is True
        role_assigned_audits = list(
            db.scalars(select(AuthSecurityAudit).where(AuthSecurityAudit.action == "ROLE_ASSIGNED"))
        )
        assert len(role_assigned_audits) == 1
        assert role_assigned_audits[0].operation_id == "bootstrap_admin"
        assert role_assigned_audits[0].result_code == "ROLE-SUPER-ADMIN"
        assert role_assigned_audits[0].actor_id == credential.user_id
        assert role_assigned_audits[0].target_user_id == credential.user_id
        bootstrap_events = list(
            db.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.event_type.in_(
                        ["user.active", "admin.active", "role_binding.active"]
                    )
                )
            )
        )
        assert len(bootstrap_events) == 3
        bootstrap_correlations = {
            event.payload_json["correlation_id"] for event in bootstrap_events
        }
        bootstrap_correlations.add(role_assigned_audits[0].correlation_id)
        assert len(bootstrap_correlations) == 1
        stored_bootstrap_correlation = bootstrap_correlations.pop()
        assert stored_bootstrap_correlation not in bootstrap_inputs

    auth = app.state.auth_service
    assert isinstance(auth, AuthenticationService)
    normal_username, normal_password, allowed, denied, project_id = _create_normal_user(
        factory, passwords
    )
    atomicity_correlation = str(uuid4())
    with factory.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER trg_test_auth_audit_no_insert "
                "BEFORE INSERT ON atp_auth_security_audit FOR EACH ROW "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'test audit insert failure'"
            )
        )
    try:
        with pytest.raises(DBAPIError):
            auth.login(
                normal_username,
                normal_password,
                AuditContext(atomicity_correlation, "atomicity-source"),
            )
    finally:
        with factory.begin() as db:
            db.execute(text("DROP TRIGGER trg_test_auth_audit_no_insert"))
    with factory() as db:
        untouched_credential = db.scalar(
            select(PlatformUserCredential)
            .join(PlatformUser, PlatformUser.user_id == PlatformUserCredential.user_id)
            .where(PlatformUser.username == normal_username)
        )
        assert untouched_credential is not None
        assert untouched_credential.row_version == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthRefreshSession)
                .where(AuthRefreshSession.credential_id == untouched_credential.credential_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthSecurityAudit)
                .where(AuthSecurityAudit.correlation_id == atomicity_correlation)
            )
            == 0
        )

    normal = auth.login(normal_username, normal_password, _audit_context("mysql-gate"))
    assert denied not in normal.current_user.permissions
    authorization_context = AuthorizationContext(
        project_id=project_id,
        scope_type="AUTHORIZED_PROJECT_ACTIVE",
        scope_id=project_id,
        object_state_allowed=True,
    )
    auth.authorize_access(
        normal.access_token,
        "runtime_gate_allow",
        allowed,
        authorization_context,
        _audit_context("runtime-gate-allow"),
    )
    with factory() as db:
        ungranted_allowed = db.scalar(
            select(PermissionCode.permission_code)
            .join(
                RolePermission,
                RolePermission.permission_id == PermissionCode.permission_code_id,
            )
            .join(Role, Role.role_id == RolePermission.role_id)
            .where(
                Role.role_code == "ROLE-PLATFORM-ADMIN",
                RolePermission.decision == "ALLOWED",
                PermissionCode.permission_code != allowed,
            )
            .limit(1)
        )
    assert ungranted_allowed is not None
    with pytest.raises(PlatformError) as missing_grant_denial:
        auth.authorize_access(
            normal.access_token,
            "runtime_gate_missing_scope_grant",
            ungranted_allowed,
            authorization_context,
            _audit_context("runtime-gate-missing-grant"),
        )
    assert missing_grant_denial.value.code == "AUTH_PERMISSION_DENIED"
    with factory.begin() as db:
        normal_user_id = db.scalar(
            select(PlatformUser.user_id).where(PlatformUser.username == normal_username)
        )
        platform_binding_id = db.scalar(
            select(UserRoleBinding.binding_id)
            .join(Role, Role.role_id == UserRoleBinding.role_id)
            .where(
                UserRoleBinding.user_id == normal_user_id,
                UserRoleBinding.project_id.is_(None),
                Role.role_code == "ROLE-PLATFORM-ADMIN",
            )
        )
        assert platform_binding_id is not None
        db.add(
            DataScopeGrant(
                grant_id=new_ulid(),
                binding_id=platform_binding_id,
                scope_type="AUTHORIZED_PROJECT_ACTIVE",
                scope_id=None,
                permission_code=ungranted_allowed,
                created_at=utc_now(),
            )
        )
    with pytest.raises(PlatformError) as null_scope_denial:
        auth.authorize_access(
            normal.access_token,
            "runtime_gate_null_project_scope_grant",
            ungranted_allowed,
            authorization_context,
            _audit_context("runtime-gate-null-scope"),
        )
    assert null_scope_denial.value.code == "AUTH_PERMISSION_DENIED"
    with pytest.raises(PlatformError) as denial:
        auth.authorize_access(
            normal.access_token,
            "runtime_gate_deny",
            denied,
            authorization_context,
            _audit_context("runtime-gate-deny"),
        )
    assert getattr(denial.value, "status", None) == 403
    assert getattr(denial.value, "code", None) == "AUTH_PERMISSION_DENIED"
    for denied_context in (
        AuthorizationContext(project_id, "REPORT_ACTIVE_HISTORY", project_id, True),
        AuthorizationContext(project_id, "AUTHORIZED_PROJECT_ACTIVE", project_id, False),
        AuthorizationContext(new_ulid(), "AUTHORIZED_PROJECT_ACTIVE", project_id, True),
        AuthorizationContext(project_id, "AUTHORIZED_PROJECT_ACTIVE", new_ulid(), True),
        AuthorizationContext(None, "AUTHORIZED_PROJECT_ACTIVE", project_id, True),
        AuthorizationContext(project_id, "UNKNOWN_SCOPE", project_id, True),
    ):
        with pytest.raises(PlatformError) as scoped_denial:
            auth.authorize_access(
                normal.access_token,
                "runtime_gate_scope_deny",
                allowed,
                denied_context,
                _audit_context("runtime-gate-scope-deny"),
            )
        assert scoped_denial.value.code == "AUTH_PERMISSION_DENIED"
    with factory.begin() as db:
        normal_user = db.scalar(
            select(PlatformUser).where(PlatformUser.username == normal_username)
        )
        assert normal_user is not None
        normal_credential = db.scalar(
            select(PlatformUserCredential).where(
                PlatformUserCredential.user_id == normal_user.user_id
            )
        )
        assert normal_credential is not None
        assert normal_credential.row_version == 1
        db.execute(
            update(UserRoleBinding)
            .where(UserRoleBinding.user_id == normal_user.user_id)
            .values(valid_to=utc_now(), row_version=UserRoleBinding.row_version + 1)
        )
    with pytest.raises(PlatformError) as realtime_denial:
        auth.authorize_access(
            normal.access_token,
            "runtime_gate_realtime_deny",
            allowed,
            authorization_context,
            _audit_context("runtime-gate-realtime-deny"),
        )
    assert realtime_denial.value.code == "AUTH_PERMISSION_DENIED"

    newest_normal = normal
    for _ in range(5):
        newest_normal = auth.login(
            normal_username,
            normal_password,
            _audit_context("mysql-gate-session-limit"),
        )
    with factory() as db:
        assert normal_credential is not None
        active_sessions = db.scalar(
            select(func.count())
            .select_from(AuthRefreshSession)
            .where(
                AuthRefreshSession.credential_id == normal_credential.credential_id,
                AuthRefreshSession.lifecycle_status == "ACTIVE",
            )
        )
        assert active_sessions == 5
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthRefreshSession)
                .where(
                    AuthRefreshSession.credential_id == normal_credential.credential_id,
                    AuthRefreshSession.revoke_reason == "SESSION_LIMIT",
                )
            )
            >= 1
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        refresh_future = pool.submit(
            auth.refresh,
            newest_normal.refresh_token,
            _audit_context("mysql-gate-concurrent-refresh"),
        )
        login_future = pool.submit(
            auth.login,
            normal_username,
            normal_password,
            _audit_context("mysql-gate-concurrent-login"),
        )
        newest_normal = refresh_future.result(timeout=20)
        assert login_future.result(timeout=20).current_user.username == normal_username
    newest_session_id = auth._jwt.decode(newest_normal.access_token).session_id
    with factory.begin() as db:
        session = db.get(AuthRefreshSession, newest_session_id)
        assert session is not None
        session.expires_at = utc_now()
    with pytest.raises(PlatformError):
        auth.authenticate_access(
            newest_normal.access_token,
            "runtime_gate_expired",
            _audit_context("runtime-gate-expired"),
        )
    with factory() as db:
        session = db.get(AuthRefreshSession, newest_session_id)
        assert session is not None
        assert session.lifecycle_status == "EXPIRED"

    with TestClient(app, base_url="http://localhost") as client:
        with factory() as db:
            unresolved_logout_count = db.scalar(
                select(func.count())
                .select_from(AuthSecurityAudit)
                .where(AuthSecurityAudit.action == "LOGOUT")
            )
        client.cookies.set("atp_refresh", "not-base64url", path="/api/v1/auth")
        invalid_refresh = client.post(
            "/api/v1/auth/refresh", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert invalid_refresh.status_code == 401
        assert invalid_refresh.json()["code"] == "AUTH_SESSION_REVOKED"
        invalid_logout = client.post(
            "/api/v1/auth/logout", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert invalid_logout.status_code == 204
        client.cookies.clear()
        missing_logout = client.post(
            "/api/v1/auth/logout", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert missing_logout.status_code == 204
        client.cookies.set("atp_refresh", new_refresh_token(), path="/api/v1/auth")
        unresolved_logout = client.post(
            "/api/v1/auth/logout", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert unresolved_logout.status_code == 204
        client.cookies.clear()
        with factory() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AuthSecurityAudit)
                    .where(AuthSecurityAudit.action == "LOGOUT")
                )
                == unresolved_logout_count
            )

        login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": initial_password},
        )
        assert login.status_code == 200
        login_data = login.json()["data"]
        assert login_data["expires_in"] == 900
        assert login_data["current_user"]["force_password_change"] is True
        assert len(login_data["current_user"]["permissions"]) == 50
        cookie_header = login.headers["set-cookie"].lower()
        assert "httponly" in cookie_header
        assert "samesite=strict" in cookie_header
        assert "path=/api/v1/auth" in cookie_header
        assert "secure" not in cookie_header
        access_before_change = login_data["access_token"]

        me = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_before_change}"}
        )
        assert me.status_code == 200
        refresh_before_change = client.post(
            "/api/v1/auth/refresh", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert refresh_before_change.status_code == 403
        assert refresh_before_change.json()["code"] == "AUTH_PASSWORD_CHANGE_REQUIRED"

        changed = client.post(
            "/api/v1/auth/change-password",
            headers={
                "Authorization": f"Bearer {access_before_change}",
                "Idempotency-Key": new_ulid(),
            },
            json={"current_password": initial_password, "new_password": changed_password},
        )
        assert changed.status_code == 200
        changed_data = changed.json()["data"]
        assert changed_data["current_user"]["force_password_change"] is False
        assert (
            client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_before_change}"},
            ).status_code
            == 401
        )

        rotated_raw = client.cookies.get("atp_refresh")
        assert rotated_raw is not None
        refreshed = client.post(
            "/api/v1/auth/refresh", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert refreshed.status_code == 200
        replacement_raw = client.cookies.get("atp_refresh")
        assert replacement_raw is not None
        assert replacement_raw != rotated_raw
        with pytest.raises(PlatformError) as replay:
            auth.refresh(rotated_raw, _audit_context("mysql-gate-replay"))
        assert getattr(replay.value, "code", None) == "AUTH_SESSION_REVOKED"
        with pytest.raises(PlatformError):
            auth.refresh(replacement_raw, _audit_context("mysql-gate-compromised"))

        fresh_login = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": changed_password}
        )
        assert fresh_login.status_code == 200
        fresh_access = fresh_login.json()["data"]["access_token"]
        super_context = AuthorizationContext(
            project_id=project_id,
            scope_type="AUTHORIZED_PROJECT_ACTIVE",
            scope_id=project_id,
            object_state_allowed=True,
        )
        auth.authorize_access(
            fresh_access,
            "runtime_gate_super_generic",
            "PROJECT_VIEW",
            super_context,
            _audit_context("runtime-gate-super-generic"),
        )
        for special_permission in (
            "VERSION_REVIEW_APPROVE",
            "CROSS_PROJECT_AUTHORIZATION_GRANT_ALL",
        ):
            with pytest.raises(PlatformError) as special_denial:
                auth.authorize_access(
                    fresh_access,
                    "runtime_gate_special_fail_closed",
                    special_permission,
                    super_context,
                    _audit_context("runtime-gate-special-deny"),
                )
            assert special_denial.value.code == "AUTH_PERMISSION_DENIED"
        logout = client.post(
            "/api/v1/auth/logout", headers={"Sec-Fetch-Site": "same-origin"}, json={}
        )
        assert logout.status_code == 204
        assert (
            client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh_access}"}
            ).status_code
            == 401
        )

        for _ in range(5):
            failed = client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": _password("Wrong")},
            )
            assert failed.status_code == 401
            assert failed.json()["code"] == "AUTH_INVALID_CREDENTIALS"
        locked = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": changed_password}
        )
        assert locked.status_code == 403
        assert locked.json()["code"] == "AUTH_ACCOUNT_TEMPORARILY_LOCKED"
        nonexistent = client.post(
            "/api/v1/auth/login",
            json={"username": f"missing-{new_ulid()}", "password": _password("Missing")},
        )
        assert nonexistent.status_code == 401
        assert nonexistent.json()["code"] == "AUTH_INVALID_CREDENTIALS"

    with factory() as db:
        hashes = list(db.scalars(select(AuthRefreshSession.token_hash)))
        assert hashes
        assert all(isinstance(value, bytes) and len(value) == 32 for value in hashes)
        family_sessions = list(
            db.scalars(
                select(AuthRefreshSession).where(
                    AuthRefreshSession.family_id
                    == auth._jwt.decode(changed_data["access_token"]).session_id
                )
            )
        )
        assert all(session.lifecycle_status != "ACTIVE" for session in family_sessions)
        assert len({session.expires_at for session in family_sessions}) == 1

        audits = list(db.scalars(select(AuthSecurityAudit)))
        actions = {row.action for row in audits}
        assert {
            "LOGIN_SUCCEEDED",
            "LOGIN_FAILED",
            "REFRESH_SUCCEEDED",
            "REFRESH_FAILED",
            "LOGOUT",
            "PASSWORD_CHANGED",
            "SESSION_REVOKED",
            "USER_DISABLED_OR_LOCKED",
            "PERMISSION_DENIED",
        }.issubset(actions)
        assert all(row.operation_id and row.result_code for row in audits)
        assert all(1 <= len(row.correlation_id) <= 128 for row in audits)
        assert all(len(row.source_context_hash) == 32 for row in audits)
        visible_audit = "\n".join(
            "|".join(
                filter(
                    None,
                    (
                        row.action,
                        row.operation_id,
                        row.actor_id,
                        row.target_user_id,
                        row.session_id,
                        row.result_code,
                        row.correlation_id,
                        row.source_context_hash.hex(),
                    ),
                )
            )
            for row in audits
        )
        for forbidden_secret in (
            initial_password,
            changed_password,
            normal_password,
            normal.access_token,
            normal.refresh_token,
            rotated_raw,
            replacement_raw,
        ):
            assert forbidden_secret not in visible_audit
        immutable_audit_id = audits[0].audit_id
        logout_audits = [row for row in audits if row.action == "LOGOUT"]
        assert len(logout_audits) == 1
        assert logout_audits[0].result_code == "SUCCESS"
        assert logout_audits[0].session_id is not None

    with pytest.raises(DBAPIError), factory.begin() as db:
        db.execute(
            text(
                "UPDATE atp_auth_security_audit SET result_code = 'TAMPERED' "
                "WHERE audit_id = :audit_id"
            ),
            {"audit_id": immutable_audit_id},
        )
    with pytest.raises(DBAPIError), factory.begin() as db:
        db.execute(
            text("DELETE FROM atp_auth_security_audit WHERE audit_id = :audit_id"),
            {"audit_id": immutable_audit_id},
        )
    with factory() as db:
        immutable_audit = db.get(AuthSecurityAudit, immutable_audit_id)
        assert immutable_audit is not None
        assert immutable_audit.result_code != "TAMPERED"

    with pytest.raises(IntegrityError), factory.begin() as db:
        assert credential is not None
        db.add(
            PlatformUserCredential(
                credential_id=new_ulid(),
                user_id=credential.user_id,
                credential_type="PASSWORD",
                password_hash=passwords.hash(_password("Duplicate")),
                password_algorithm="ARGON2ID_V19",
                credential_version=1,
                force_password_change=True,
                failed_login_count=0,
                failure_window_started_at=None,
                locked_until=None,
                last_failed_at=None,
                last_successful_login_at=None,
                password_changed_at=utc_now(),
                lifecycle_status="ACTIVE",
                row_version=0,
                created_at=utc_now(),
                updated_at=utc_now(),
                created_by=credential.user_id,
                updated_by=credential.user_id,
            )
        )
        db.flush()
