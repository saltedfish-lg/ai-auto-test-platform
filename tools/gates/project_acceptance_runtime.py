#!/usr/bin/env python3
"""Run REAL_ACCEPTANCE_GATE for Project management in an isolated MySQL/browser runtime."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import BinaryIO

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from tools.environment import get_env, load_project_environment, project_environment  # noqa: E402
from tools.gates.auth_browser_gate import (  # noqa: E402
    _available_loopback_port,
    _create_user,
    _safe_startup_diagnostic,
    _start_process,
    _startup_error_code,
    _stop_process,
    _validate_playwright_browser,
    _wait_for_port,
    _wait_for_vite,
    _write_hmac_key_ring,
)
from tools.gates.auth_mysql_gate import (  # noqa: E402
    ADMIN_URL_ENV,
    DATABASE_URL_ENV,
    GateBlocked,
    _connection,
    _drop_isolated_database,
    _execute_script,
    _migration_names,
    _migration_path,
    _new_database_name,
    _resolve_authority,
    _test_database_url,
)
from tools.governance.runtime_gate_result import (  # noqa: E402
    finalize_runtime_result,
    runtime_result_base,
)

ROOT = _BOOTSTRAP_ROOT
RUNTIME_ROOT = ROOT / ".runtime"
API_SRC = ROOT / "services" / "api" / "src"
COMMON_SRC = ROOT / "packages" / "platform-common" / "src"
OBSERVABILITY_SRC = ROOT / "packages" / "observability" / "src"
for import_root in (API_SRC, COMMON_SRC, OBSERVABILITY_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from platform_api.database import create_database_engine, create_session_factory  # noqa: E402
from platform_api.keygen import generate_development_key_ring  # noqa: E402
from platform_api.security import PasswordService, new_ulid  # noqa: E402

GATE_ID = "REAL_ACCEPTANCE_GATE"


def _database_evidence(database: str, project_code: str) -> dict[str, object]:
    retry_code = f"RETRY-{project_code}"
    denied_code = f"DENIED-{project_code}"
    service_account_code = f"SERVICE-{project_code}"
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT project_id, display_name, lifecycle_status, row_version "
            "FROM atp_project WHERE project_code=%s",
            (project_code,),
        )
        project = cursor.fetchone()
        if project is None:
            raise RuntimeError("browser-created project was not persisted")
        project_id, display_name, lifecycle_status, row_version = project
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project_member pm "
            "JOIN atp_role r ON r.role_id=pm.role_id "
            "WHERE pm.project_id=%s AND pm.lifecycle_status='ACTIVE' "
            "AND r.role_code='ROLE-PROJECT-OWNER-DUTY'",
            (project_id,),
        )
        owner_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT pm.user_id FROM atp_project_member pm "
            "JOIN atp_role r ON r.role_id=pm.role_id "
            "WHERE pm.project_id=%s AND pm.lifecycle_status='ACTIVE' "
            "AND r.role_code='ROLE-PROJECT-OWNER-DUTY'",
            (project_id,),
        )
        owner_user_id = str(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_data_scope_grant g "
            "JOIN atp_user_role_binding b ON b.binding_id=g.binding_id "
            "JOIN atp_role r ON r.role_id=b.role_id "
            "WHERE r.role_code='ROLE-PROJECT-OWNER-DUTY'"
        )
        scope_grant_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project WHERE lifecycle_status IN "
            "('CREATED','CONFIGURING','VALIDATING')"
        )
        intermediate_project_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project WHERE project_code=%s", (retry_code,)
        )
        corrected_retry_project_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project WHERE project_code=%s", (denied_code,)
        )
        denied_project_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project WHERE project_code=%s", (service_account_code,)
        )
        service_account_owner_project_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT action, COUNT(*) FROM atp_project_audit "
            "WHERE project_id=%s AND result_code='SUCCESS' GROUP BY action",
            (project_id,),
        )
        audit_actions = {str(action): int(count) for action, count in cursor.fetchall()}
        cursor.execute(
            "SELECT action,actor_user_id,participant_user_id,required_permission,"
            "scope_decision,previous_status,new_status,result_code,correlation_id,"
            "OCTET_LENGTH(source_context_hash),occurred_at "
            "FROM atp_project_audit WHERE project_id=%s AND result_code='SUCCESS'",
            (project_id,),
        )
        successful_audit_rows = list(cursor.fetchall())
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project_audit WHERE project_code IN (%s,%s,%s) "
            "AND result_code IN ('PROJECT_OWNER_NOT_ELIGIBLE','PROJECT_CODE_CONFLICT') "
            "AND actor_user_id IS NOT NULL AND required_permission='PROJECT_CREATE' "
            "AND scope_decision='NOT_APPLICABLE' "
            "AND previous_status IS NULL AND new_status IS NULL "
            "AND correlation_id <> '' AND OCTET_LENGTH(source_context_hash)=32",
            (project_code, retry_code, service_account_code),
        )
        failed_audit_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT a.actor_user_id,a.participant_user_id,a.required_permission,"
            "a.scope_decision,a.previous_status,a.new_status,a.result_code,"
            "a.correlation_id,OCTET_LENGTH(a.source_context_hash),a.occurred_at,pm.user_id "
            "FROM atp_project_audit a JOIN atp_project p ON p.project_id=a.project_id "
            "JOIN atp_project_member pm ON pm.project_id=p.project_id "
            "JOIN atp_role r ON r.role_id=pm.role_id "
            "WHERE p.project_code=%s AND a.action='PROJECT_CREATED' "
            "AND r.role_code='ROLE-PROJECT-OWNER-DUTY'",
            (f"DELEGATED-{project_code}",),
        )
        delegated_audit_rows = list(cursor.fetchall())
        cursor.execute(
            "SELECT event_type, COUNT(*) FROM atp_outbox_event "
            "WHERE aggregate_id=%s GROUP BY event_type",
            (project_id,),
        )
        event_types = {str(event_type): int(count) for event_type, count in cursor.fetchall()}
        cursor.execute(
            "SELECT COUNT(*) FROM atp_idempotency_record WHERE "
            "(operation_id LIKE '%project' OR operation_id LIKE '%_project') "
            "AND response_status IS NOT NULL AND completed_at IS NOT NULL"
        )
        terminal_commands = int(cursor.fetchone()[0])

    required_audits = {
        "PROJECT_CREATED",
        "PROJECT_UPDATED",
        "PROJECT_DISABLED",
        "PROJECT_RECOVERED",
        "PROJECT_ARCHIVED",
    }
    required_events = {
        "project.created",
        "project.active",
        "project.updated",
        "project.disabled",
        "project.recovering",
        "project.archived",
    }
    expected_audit_fields = {
        "PROJECT_CREATED": ("PROJECT_CREATE", "NOT_APPLICABLE", "CREATED", "ACTIVE"),
        "PROJECT_UPDATED": (
            "PROJECT_EDIT",
            "ALLOWED",
            "ACTIVE",
            "ACTIVE",
        ),
        "PROJECT_DISABLED": (
            "PROJECT_EDIT",
            "ALLOWED",
            "ACTIVE",
            "DISABLED",
        ),
        "PROJECT_RECOVERED": (
            "PROJECT_EDIT",
            "ALLOWED",
            "DISABLED",
            "ACTIVE",
        ),
        "PROJECT_ARCHIVED": (
            "PROJECT_ARCHIVE",
            "ALLOWED",
            "DISABLED",
            "ARCHIVED",
        ),
    }
    for row in successful_audit_rows:
        (
            action,
            actor_user_id,
            participant_user_id,
            required_permission,
            scope_decision,
            previous_status,
            new_status,
            result_code,
            correlation_id,
            source_hash_length,
            occurred_at,
        ) = row
        expected = expected_audit_fields.get(str(action))
        if expected is None or (
            required_permission,
            scope_decision,
            previous_status,
            new_status,
        ) != expected:
            raise RuntimeError("successful ProjectAudit authorization fields are inaccurate")
        expected_participant = owner_user_id if action == "PROJECT_CREATED" else None
        if (
            actor_user_id != owner_user_id
            or participant_user_id != expected_participant
            or result_code != "SUCCESS"
            or not correlation_id
            or int(source_hash_length or 0) != 32
            or occurred_at is None
        ):
            raise RuntimeError("successful ProjectAudit evidence fields are incomplete")
    expected_successful_audit_count = sum(audit_actions.values())
    if len(successful_audit_rows) != expected_successful_audit_count:
        raise RuntimeError("successful ProjectAudit field coverage is incomplete")
    if len(delegated_audit_rows) != 1:
        raise RuntimeError("delegated ProjectAudit evidence is incomplete")
    (
        delegated_actor,
        delegated_participant,
        delegated_permission,
        delegated_scope,
        delegated_previous,
        delegated_new,
        delegated_result,
        delegated_correlation,
        delegated_hash_length,
        delegated_occurred_at,
        delegated_owner,
    ) = delegated_audit_rows[0]
    if (
        not delegated_actor
        or delegated_actor == delegated_owner
        or delegated_participant != delegated_owner
        or delegated_permission != "PROJECT_CREATE"
        or delegated_scope != "NOT_APPLICABLE"
        or delegated_previous != "CREATED"
        or delegated_new != "ACTIVE"
        or delegated_result != "SUCCESS"
        or not delegated_correlation
        or int(delegated_hash_length or 0) != 32
        or delegated_occurred_at is None
    ):
        raise RuntimeError("delegated ProjectAudit fields do not describe the real decision")
    if lifecycle_status != "ARCHIVED" or display_name != "浏览器验收项目（已更新）":  # noqa: RUF001
        raise RuntimeError("project persistence did not match the browser workflow")
    if owner_count != 1 or scope_grant_count != 0:
        raise RuntimeError("dynamic owner scope persistence invariant failed")
    if intermediate_project_count != 0 or corrected_retry_project_count != 1:
        raise RuntimeError("project rollback/retry persistence invariant failed")
    if (
        denied_project_count != 0
        or service_account_owner_project_count != 0
        or failed_audit_count < 3
    ):
        raise RuntimeError("project rejection evidence is incomplete")
    if not required_audits.issubset(audit_actions) or not required_events.issubset(event_types):
        raise RuntimeError("project audit/outbox evidence is incomplete")
    if terminal_commands < 7:
        raise RuntimeError("project idempotency terminal evidence is incomplete")
    return {
        "project_status": lifecycle_status,
        "project_row_version": int(row_version),
        "active_owner_count": owner_count,
        "physical_owner_scope_grant_count": scope_grant_count,
        "intermediate_project_count": intermediate_project_count,
        "corrected_retry_project_count": corrected_retry_project_count,
        "denied_project_count": denied_project_count,
        "service_account_owner_project_count": service_account_owner_project_count,
        "failed_audit_count": failed_audit_count,
        "successful_audit_field_count": len(successful_audit_rows),
        "delegated_audit_field_count": len(delegated_audit_rows),
        "audit_actions": audit_actions,
        "outbox_event_types": event_types,
        "terminal_command_count": terminal_commands,
    }


def _post_json(
    url: str, payload: dict[str, object], *, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, object]]:
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return int(error.code), json.loads(error.read().decode("utf-8"))


def _get_json(url: str, *, headers: dict[str, str]) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return int(error.code), json.loads(error.read().decode("utf-8"))


def _patch_json(
    url: str, payload: dict[str, object], *, headers: dict[str, str]
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return int(error.code), json.loads(error.read().decode("utf-8"))


def _dynamic_owner_revocation_probe(
    database: str,
    api_port: int,
    username: str,
    password: str,
    project_code: str,
) -> dict[str, object]:
    status, login = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/auth/login",
        {"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError("dynamic Owner probe login failed")
    token = str(dict(login["data"])["access_token"])
    headers = {"Authorization": f"Bearer {token}"}
    delegated_code = f"DELEGATED-{project_code}"
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.project_id,p.lifecycle_status,p.row_version,pm.project_member_id,"
            "pm.lifecycle_status,pm.role_id,r.lifecycle_status "
            "FROM atp_project p JOIN atp_project_member pm ON pm.project_id=p.project_id "
            "JOIN atp_role r ON r.role_id=pm.role_id "
            "JOIN atp_user u ON u.user_id=pm.user_id "
            "WHERE p.project_code=%s AND u.username=%s "
            "AND r.role_code='ROLE-PROJECT-OWNER-DUTY'",
            (delegated_code, username),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("delegated dynamic Owner fixture was not persisted")
        (
            project_id,
            project_status,
            project_version,
            member_id,
            member_status,
            role_id,
            role_status,
        ) = row
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project_audit WHERE project_id=%s",
            (project_id,),
        )
        business_audit_count = int(cursor.fetchone()[0])

    url = f"http://127.0.0.1:{api_port}/api/v1/project/{project_id}"
    before_status, _ = _get_json(url, headers=headers)
    owner_update_status, owner_update = _patch_json(
        url,
        {
            "expected_version": int(project_version),
            "display_name": "动态 Owner 范围验证项目",
            "reason": "验证纯 Owner 授权路径的真实审计判定",
        },
        headers={**headers, "Idempotency-Key": f"owner-scope-{project_code}"},
    )
    if owner_update_status != 200:
        raise RuntimeError("dynamic Owner command did not succeed")
    project_version = int(dict(owner_update["data"])["row_version"])
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project_audit WHERE project_id=%s "
            "AND action='PROJECT_UPDATED' AND actor_user_id=("
            "SELECT user_id FROM atp_user WHERE username=%s) "
            "AND required_permission='PROJECT_EDIT' "
            "AND scope_decision='DYNAMIC_PROJECT_OWNER_ALL' "
            "AND previous_status='ACTIVE' AND new_status='ACTIVE' "
            "AND result_code='SUCCESS' AND correlation_id<>'' "
            "AND OCTET_LENGTH(source_context_hash)=32",
            (project_id, username),
        )
        dynamic_owner_audit_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project_audit WHERE project_id=%s",
            (project_id,),
        )
        business_audit_count = int(cursor.fetchone()[0])
    if dynamic_owner_audit_count != 1:
        raise RuntimeError("dynamic Owner command audit did not record the real scope decision")
    membership_denied_status = 0
    role_denied_status = 0
    after_restore_status = 0
    try:
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE atp_project_member SET lifecycle_status='DISABLED' "
                "WHERE project_member_id=%s AND lifecycle_status='ACTIVE'",
                (member_id,),
            )
        membership_denied_status, membership_problem = _get_json(url, headers=headers)
        if (
            membership_denied_status != 403
            or membership_problem.get("code") != "AUTH_PERMISSION_DENIED"
        ):
            raise RuntimeError("inactive ProjectMember did not revoke dynamic Owner scope")

        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE atp_project_member SET lifecycle_status=%s WHERE project_member_id=%s",
                (member_status, member_id),
            )
            cursor.execute(
                "UPDATE atp_role SET lifecycle_status='DISABLED' "
                "WHERE role_id=%s AND lifecycle_status='ACTIVE'",
                (role_id,),
            )
        role_denied_status, role_problem = _get_json(url, headers=headers)
        if role_denied_status != 403 or role_problem.get("code") != "AUTH_PERMISSION_DENIED":
            raise RuntimeError("inactive Owner duty role did not revoke dynamic Owner scope")
    finally:
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE atp_project_member SET lifecycle_status=%s WHERE project_member_id=%s",
                (member_status, member_id),
            )
            cursor.execute(
                "UPDATE atp_role SET lifecycle_status=%s WHERE role_id=%s",
                (role_status, role_id),
            )

    after_restore_status, _ = _get_json(url, headers=headers)
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT lifecycle_status,row_version FROM atp_project WHERE project_id=%s",
            (project_id,),
        )
        final_status, final_version = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) FROM atp_project_audit WHERE project_id=%s",
            (project_id,),
        )
        final_business_audit_count = int(cursor.fetchone()[0])
    if before_status != 200 or after_restore_status != 200:
        raise RuntimeError("dynamic Owner scope was not restored after fixture rollback")
    if (
        final_status != project_status
        or int(final_version) != int(project_version)
        or final_business_audit_count != business_audit_count
    ):
        raise RuntimeError("dynamic Owner denial changed Project business state")
    return {
        "before_status": before_status,
        "owner_update_status": owner_update_status,
        "dynamic_owner_audit_count": dynamic_owner_audit_count,
        "membership_inactive_status": membership_denied_status,
        "owner_role_inactive_status": role_denied_status,
        "after_restore_status": after_restore_status,
        "project_state_unchanged": True,
        "business_audit_count_unchanged": True,
    }


def _audit_unavailable_probe(
    database: str,
    api_port: int,
    username: str,
    password: str,
    project_code: str,
) -> dict[str, object]:
    status, login = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/auth/login",
        {"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError("audit-unavailable probe login failed")
    token = str(dict(login["data"])["access_token"])
    probe_code = f"AUDIT-UNAVAILABLE-{project_code}"
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "RENAME TABLE atp_project_audit TO atp_project_audit_unavailable_probe"
        )
    try:
        status, problem = _post_json(
            f"http://127.0.0.1:{api_port}/api/v1/project",
            {"project_code": probe_code},
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"audit-unavailable-{project_code}",
            },
        )
    finally:
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "RENAME TABLE atp_project_audit_unavailable_probe TO atp_project_audit"
            )
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM atp_project WHERE project_code=%s", (probe_code,))
        project_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_idempotency_record WHERE idempotency_key=%s",
            (f"audit-unavailable-{project_code}",),
        )
        idempotency_count = int(cursor.fetchone()[0])
    if status != 500 or problem.get("code") != "INTERNAL_ERROR":
        raise RuntimeError("audit unavailability did not fail closed")
    if project_count != 0 or idempotency_count != 0:
        raise RuntimeError("audit unavailability left a partial project command")
    return {
        "http_status": status,
        "problem_code": problem.get("code"),
        "partial_project_count": project_count,
        "partial_idempotency_count": idempotency_count,
    }


def main() -> int:
    load_project_environment(root=ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-output", type=Path)
    parser.add_argument(
        "--task-id",
        help="Run the current Task's full required Gate set while this isolated runtime is active.",
    )
    args = parser.parse_args()
    result = runtime_result_base(
        ROOT,
        gate_id=GATE_ID,
        gate_source=Path(__file__),
        gate_capabilities=[
            "PROJECT_MANAGEMENT_FOUNDATION",
            "BROWSER_RUNTIME",
            "RBAC_RUNTIME",
            "MYSQL_PERSISTENCE",
            "ISOLATED_RUNTIME_CLEANUP",
        ],
    )

    def emit() -> None:
        finalize_runtime_result(result, root=ROOT)
        raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.result_output:
            args.result_output.parent.mkdir(parents=True, exist_ok=True)
            args.result_output.write_text(raw, encoding="utf-8")
        print(raw, end="")

    if not get_env(ADMIN_URL_ENV, root=ROOT):
        result.update(
            {
                "result": "BLOCKED",
                "exit_code": 2,
                "blocker": f"{ADMIN_URL_ENV} is required",
                "cleanup_status": {"success": True, "temporary_database_removed": True},
            }
        )
        emit()
        return 2

    authority = _resolve_authority()
    database = _new_database_name("project")
    runtime_directory = RUNTIME_ROOT / f"project-browser-{secrets.token_hex(6)}"
    runtime_directory.mkdir(parents=True, exist_ok=False)
    api_process: subprocess.Popen[bytes] | None = None
    web_process: subprocess.Popen[bytes] | None = None
    log_handles: list[BinaryIO] = []
    created = False
    removed = False
    runtime_removed = False
    browser_exit = 1
    exit_code = 1
    status = "FAIL"
    mysql_version = "UNKNOWN"
    browser_resolution = "NOT_EVALUATED"
    database_evidence: dict[str, object] = {}
    audit_unavailable_evidence: dict[str, object] = {}
    dynamic_owner_evidence: dict[str, object] = {}
    stage = "mysql_connect"
    error_type: str | None = None
    error_code: str | None = None
    error_diagnostic: str | None = None
    blocker: str | None = None
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            mysql_version = str(cursor.fetchone()[0])
            if not mysql_version.startswith("8.4."):
                raise GateBlocked(f"MySQL 8.4 is required; detected {mysql_version}")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            created = True
        stage = "migrations"
        for migration in _migration_names(authority):
            _execute_script(database, _migration_path(authority, migration))

        stage = "fixtures"
        database_url = _test_database_url(database)
        key_ring = generate_development_key_ring(
            runtime_directory / "keys", kid="project-browser-rs256-v1"
        )
        hmac_key_ring = _write_hmac_key_ring(runtime_directory)
        engine = create_database_engine(database_url)
        factory = create_session_factory(engine)
        passwords = PasswordService()
        authorized_username, authorized_password = _create_user(
            factory, passwords, lifecycle="ACTIVE", role_code="ROLE-SUPER-ADMIN"
        )
        unauthorized_username, unauthorized_password = _create_user(
            factory, passwords, lifecycle="ACTIVE", role_code="ROLE-REPORT-VIEWER"
        )
        platform_admin_username, platform_admin_password = _create_user(
            factory, passwords, lifecycle="ACTIVE", role_code="ROLE-PLATFORM-ADMIN"
        )
        owner_username, owner_password = _create_user(
            factory, passwords, lifecycle="ACTIVE", role_code="ROLE-PROJECT-OWNER-DUTY"
        )
        engine.dispose()
        project_code = f"browser-project-{secrets.token_hex(6)}"
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id FROM atp_user WHERE username=%s", (unauthorized_username,)
            )
            ineligible_owner_id = str(cursor.fetchone()[0])
            cursor.execute("SELECT user_id FROM atp_user WHERE username=%s", (owner_username,))
            eligible_owner_id = str(cursor.fetchone()[0])
            cursor.execute(
                "SELECT b.binding_id FROM atp_user_role_binding b "
                "JOIN atp_user u ON u.user_id=b.user_id WHERE u.username=%s",
                (platform_admin_username,),
            )
            platform_admin_binding_id = str(cursor.fetchone()[0])
            cursor.execute(
                "INSERT INTO atp_data_scope_grant "
                "(grant_id,binding_id,scope_type,scope_id,permission_code,created_at) "
                "VALUES (%s,%s,'PLATFORM_ALL',NULL,NULL,CURRENT_TIMESTAMP(6))",
                (new_ulid(), platform_admin_binding_id),
            )

        api_port = _available_loopback_port()
        api_environment = project_environment(root=ROOT)
        api_environment.pop(ADMIN_URL_ENV, None)
        python_paths = [str(API_SRC), str(COMMON_SRC), str(OBSERVABILITY_SRC)]
        if api_environment.get("PYTHONPATH"):
            python_paths.append(api_environment["PYTHONPATH"])
        api_environment["PYTHONPATH"] = os.pathsep.join(python_paths)
        api_environment.update(
            {
                "PLATFORM_ENVIRONMENT": "test",
                DATABASE_URL_ENV: database_url,
                "API_HOST": "127.0.0.1",
                "API_PORT": str(api_port),
                "ATP_JWT_KEY_RING_FILE": str(key_ring.manifest_file),
                "ATP_AUTH_HMAC_MASTER_KEY_FILE": str(hmac_key_ring),
            }
        )
        stage = "api_startup"
        api_process, api_log = _start_process(
            [sys.executable, "-m", "platform_api.cli"],
            api_environment,
            runtime_directory / "api.log",
        )
        log_handles.append(api_log)
        _wait_for_port(api_port, api_process)

        node = shutil.which("node")
        if node is None:
            raise GateBlocked("Node.js is required for REAL_ACCEPTANCE_GATE")
        web_port = _available_loopback_port()
        web_environment = project_environment(root=ROOT)
        web_environment.pop(ADMIN_URL_ENV, None)
        web_environment.pop(DATABASE_URL_ENV, None)
        web_environment["ATP_VITE_PROXY_TARGET"] = f"http://127.0.0.1:{api_port}"
        stage = "web_startup"
        web_log_path = runtime_directory / "web.log"
        web_process, web_log = _start_process(
            [
                node,
                str(ROOT / "node_modules" / "vite" / "bin" / "vite.js"),
                str(ROOT / "apps" / "web"),
                "--host",
                "127.0.0.1",
                "--port",
                str(web_port),
                "--strictPort",
            ],
            web_environment,
            web_log_path,
            keep_stdin_open=True,
        )
        log_handles.append(web_log)
        _wait_for_vite(web_port, web_process, web_log_path)

        browser_environment = web_environment.copy()
        for proxy_name in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            browser_environment.pop(proxy_name, None)
        browser_environment.update(
            {
                "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{web_port}",
                "PLAYWRIGHT_TEST_FILE": "project-management.spec.ts",
                "PLAYWRIGHT_OUTPUT_DIR": str(runtime_directory / "playwright-output"),
                "PLAYWRIGHT_NO_COPY_PROMPT": "1",
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
                "ATP_PROJECT_E2E_AUTHORIZED_USERNAME": authorized_username,
                "ATP_PROJECT_E2E_AUTHORIZED_PASSWORD": authorized_password,
                "ATP_PROJECT_E2E_UNAUTHORIZED_USERNAME": unauthorized_username,
                "ATP_PROJECT_E2E_UNAUTHORIZED_PASSWORD": unauthorized_password,
                "ATP_PROJECT_E2E_PLATFORM_ADMIN_USERNAME": platform_admin_username,
                "ATP_PROJECT_E2E_PLATFORM_ADMIN_PASSWORD": platform_admin_password,
                "ATP_PROJECT_E2E_ELIGIBLE_OWNER_ID": eligible_owner_id,
                "ATP_PROJECT_E2E_INELIGIBLE_OWNER_ID": ineligible_owner_id,
                "ATP_PROJECT_E2E_CODE": project_code,
            }
        )
        browser_resolution = _validate_playwright_browser(node, browser_environment)
        stage = "required_gates" if args.task_id else "chromium_test"
        if args.task_id:
            command = [
                sys.executable,
                "tools/governance/task_governance.py",
                "gate",
                "--root",
                ".",
                "--task-id",
                args.task_id,
            ]
        else:
            playwright = ROOT / "node_modules" / ".bin" / (
                "playwright.cmd" if sys.platform == "win32" else "playwright"
            )
            if not playwright.is_file():
                raise GateBlocked("Playwright is required for REAL_ACCEPTANCE_GATE")
            command = [
                str(playwright),
                "test",
                "--config",
                "apps/web/playwright.config.ts",
            ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=browser_environment,
            check=False,
        )
        browser_exit = completed.returncode
        if browser_exit != 0:
            raise RuntimeError("project browser acceptance command failed")
        stage = "dynamic_owner_revocation_probe"
        dynamic_owner_evidence = _dynamic_owner_revocation_probe(
            database,
            api_port,
            owner_username,
            owner_password,
            project_code,
        )
        stage = "audit_unavailable_probe"
        audit_unavailable_evidence = _audit_unavailable_probe(
            database,
            api_port,
            authorized_username,
            authorized_password,
            project_code,
        )
        stage = "database_evidence"
        database_evidence = _database_evidence(database, project_code)
        status = "PASS"
        exit_code = 0
    except GateBlocked as exc:
        status = "BLOCKED"
        blocker = str(exc)
        exit_code = 2
    except Exception as exc:
        status = "FAIL"
        error_type = type(exc).__name__
        if stage == "api_startup":
            error_code = _startup_error_code(runtime_directory / "api.log")
            error_diagnostic = _safe_startup_diagnostic(runtime_directory / "api.log")
        elif stage == "web_startup":
            error_code = _startup_error_code(runtime_directory / "web.log")
            error_diagnostic = _safe_startup_diagnostic(runtime_directory / "web.log")
        exit_code = 1
    finally:
        _stop_process(web_process)
        _stop_process(api_process)
        for handle in log_handles:
            handle.close()
        if created:
            try:
                _drop_isolated_database(database)
                removed = True
            except Exception:
                status = "FAIL"
                blocker = "failed to remove the isolated project acceptance database"
                exit_code = 1
        resolved_runtime = runtime_directory.resolve()
        if (
            resolved_runtime.parent == RUNTIME_ROOT.resolve()
            and resolved_runtime.name.startswith("project-browser-")
            and resolved_runtime.exists()
        ):
            try:
                shutil.rmtree(resolved_runtime)
            except OSError:
                status = "FAIL"
                blocker = "failed to remove the isolated project acceptance runtime directory"
                exit_code = 1
        runtime_removed = not resolved_runtime.exists()

    processes_terminated = all(
        process is None or process.poll() is not None for process in (api_process, web_process)
    )
    cleanup_success = (removed if created else True) and runtime_removed and processes_terminated
    if not cleanup_success:
        status = "FAIL"
        exit_code = 1
    result.update(
        {
            "result": status,
            "exit_code": exit_code,
            "runtime_versions": {
                "mysql": mysql_version,
                "browser": "chromium",
                "browser_resolution": browser_resolution,
            },
            "test_runner": "playwright",
            "test_cases": [
                "apps/web/e2e/project-management.spec.ts::project management browser closure"
            ],
            "browser_exit_code": browser_exit,
            "checks": {
                "database": "PASS" if created else "NOT_RUN",
                "browser_workflow": "PASS" if browser_exit == 0 else "FAIL",
                "database_evidence": "PASS" if database_evidence else "NOT_RUN",
                "audit_unavailable_fail_closed": (
                    "PASS" if audit_unavailable_evidence else "NOT_RUN"
                ),
                "dynamic_owner_revocation": (
                    "PASS" if dynamic_owner_evidence else "NOT_RUN"
                ),
                "cleanup": "PASS" if cleanup_success else "FAIL",
            },
            "database_evidence": database_evidence,
            "audit_unavailable_evidence": audit_unavailable_evidence,
            "dynamic_owner_evidence": dynamic_owner_evidence,
            "cleanup_status": {
                "temporary_database_removed": removed if created else True,
                "runtime_directory_removed": runtime_removed,
                "processes_terminated": processes_terminated,
                "runtime_secrets_removed": runtime_removed,
                "success": cleanup_success,
            },
        }
    )
    if blocker:
        result["blocker"] = blocker
    if error_type:
        result["error_type"] = error_type
        result["error_stage"] = stage
    if error_code:
        result["error_code"] = error_code
    if error_diagnostic:
        result["error_diagnostic"] = error_diagnostic
    emit()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
