#!/usr/bin/env python3
"""Run REAL_ACCEPTANCE_GATE for Project management in an isolated MySQL/browser runtime."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from tools.database.flyway import FlywayBlocked, run_flyway  # noqa: E402
from tools.environment import get_env, load_project_environment, project_environment  # noqa: E402
from tools.gates import model_configuration_browser_gate as model_gate  # noqa: E402
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
    _new_database_name,
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
RUNNER_SRC = ROOT / "runner" / "agent" / "src"
for import_root in (API_SRC, COMMON_SRC, OBSERVABILITY_SRC, RUNNER_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from platform_api.database import create_database_engine, create_session_factory  # noqa: E402
from platform_api.keygen import generate_development_key_ring  # noqa: E402
from platform_api.models import Project, Runner  # noqa: E402
from platform_api.runner_resource_reconciler import reconcile_formal_execution_slot  # noqa: E402
from platform_api.secret_store import AesGcmSecretProtector  # noqa: E402
from platform_api.security import PasswordService, new_ulid  # noqa: E402
from platform_runner.credentials import AgentCredentialStore, StoredAgentIdentity  # noqa: E402

GATE_ID = "REAL_ACCEPTANCE_GATE"
AI_EXPLORATION_MODEL_NAME = model_gate.MODEL_NAME
AI_EXPLORATION_PROVIDER_CODE = model_gate.PROVIDER_CODE


class _ExplorationTargetFixture:
    """Deterministic browser target; no platform component is mocked."""

    def __init__(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                del format, args

            def do_GET(self) -> None:
                if self.path == "/dashboard":
                    body = (
                        b"<!doctype html><html><head><title>Exploration Dashboard</title></head>"
                        b"<body><main><h1>Exploration complete</h1>"
                        b"<p>The deterministic dashboard is visible.</p></main></body></html>"
                    )
                elif self.path == "/":
                    body = (
                        b"<!doctype html><html><head><title>Exploration Start</title></head>"
                        b"<body><main><h1>Exploration start</h1>"
                        b'<form id="login"><label>Account<input name="username" '
                        b'autocomplete="username"></label><label>Password<input name="password" '
                        b'type="password"></label><button type="submit">Sign in</button></form>'
                        b'<p id="credential-echo"></p><script>document.getElementById("login")'
                        b'.addEventListener("submit",e=>{e.preventDefault();document.getElementById('
                        b'"credential-echo").textContent=e.target.password.value;});</script>'
                        b'<a data-testid="advance" href="/dashboard">Open dashboard</a>'
                        b"</main></body></html>"
                    )
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="ai-exploration-target",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _write_test_account_secret_key_ring(directory: Path) -> Path:
    path = directory / "test-account-secret-key-ring.json"
    path.write_text(
        json.dumps(
            {
                "active_key_id": "project-browser-test-account-active",
                "keys": [
                    {
                        "key_id": "project-browser-test-account-active",
                        "key_material": base64.urlsafe_b64encode(secrets.token_bytes(32))
                        .rstrip(b"=")
                        .decode("ascii"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _database_evidence(
    database: str, project_code: str, runner_project_id: str
) -> dict[str, object]:
    retry_code = f"RETRY-{project_code}"
    denied_code = f"DENIED-{project_code}"
    service_account_code = f"SERVICE-{project_code}"
    environment_code = f"ENV-{project_code}"
    terminal_code = f"ADMIN-{project_code}"
    account_identifier = f"qa-{project_code}"
    initial_account_secret = f"initial-test-account-{project_code}".encode()
    rotated_account_secret = f"rotated-test-account-{project_code}".encode()
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
        cursor.execute("SELECT COUNT(*) FROM atp_project WHERE project_code=%s", (retry_code,))
        corrected_retry_project_count = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM atp_project WHERE project_code=%s", (denied_code,))
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
        cursor.execute(
            "SELECT environment_id,display_name,lifecycle_status,row_version "
            "FROM atp_environment "
            "WHERE project_id=%s AND environment_code=%s",
            (project_id, environment_code),
        )
        environment = cursor.fetchone()
        if environment is None:
            raise RuntimeError("browser-created environment was not persisted")
        (
            environment_id,
            environment_display_name,
            environment_status,
            environment_row_version,
        ) = environment
        cursor.execute(
            "SELECT action,COUNT(*) FROM atp_environment_audit "
            "WHERE project_id=%s AND environment_code=%s AND result_code='SUCCESS' "
            "GROUP BY action",
            (project_id, environment_code),
        )
        environment_audit_actions = {str(action): int(count) for action, count in cursor.fetchall()}
        cursor.execute(
            "SELECT COUNT(*) FROM atp_environment_audit "
            "WHERE project_id=%s AND environment_code=%s "
            "AND result_code IN ('ENVIRONMENT_CONCURRENCY_CONFLICT',"
            "'ENVIRONMENT_CODE_CONFLICT') AND correlation_id<>'' "
            "AND OCTET_LENGTH(source_context_hash)=32",
            (project_id, environment_code),
        )
        environment_failed_audits = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT operation_id,result_code,COUNT(*) FROM atp_environment_audit "
            "WHERE environment_id=%s AND operation_id='validate_environment' "
            "AND result_code IN ('ENVIRONMENT_CONCURRENCY_CONFLICT',"
            "'ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE') "
            "GROUP BY operation_id,result_code",
            (environment_id,),
        )
        environment_lifecycle_failure_results = {
            f"{operation_id}:{result_code}": int(count)
            for operation_id, result_code, count in cursor.fetchall()
        }
        cursor.execute(
            "SELECT operation_id,COUNT(*) FROM atp_idempotency_record "
            "WHERE operation_id IN ('validate_environment','reconfigure_environment',"
            "'activate_environment') AND response_status=200 AND completed_at IS NOT NULL "
            "GROUP BY operation_id"
        )
        environment_lifecycle_idempotency = {
            str(operation_id): int(count) for operation_id, count in cursor.fetchall()
        }
        cursor.execute(
            "SELECT event_type,COUNT(*) FROM atp_outbox_event "
            "WHERE aggregate_id=%s GROUP BY event_type",
            (environment_id,),
        )
        environment_event_types = {
            str(event_type): int(count) for event_type, count in cursor.fetchall()
        }
        cursor.execute(
            "SELECT COUNT(*) FROM atp_environment WHERE environment_code=%s",
            (environment_code,),
        )
        cross_project_environment_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT business_terminal_id,current_published_revision_id,"
            "lifecycle_status,row_version "
            "FROM atp_business_terminal WHERE project_id=%s AND terminal_code=%s",
            (project_id, terminal_code),
        )
        terminal = cursor.fetchone()
        if terminal is None:
            raise RuntimeError("browser-created BusinessTerminal was not persisted")
        terminal_id, current_revision_id, terminal_status, terminal_row_version = terminal
        cursor.execute(
            "SELECT r.revision_no,r.lifecycle_status,r.login_strategy_id,s.lifecycle_status,"
            "s.automation_asset_id,a.project_id "
            "FROM atp_environment_terminal_access_revision r "
            "LEFT JOIN atp_login_strategy s ON s.login_strategy_id=r.login_strategy_id "
            "LEFT JOIN atp_automation_asset a ON a.automation_asset_id=s.automation_asset_id "
            "WHERE r.environment_terminal_access_revision_id=%s "
            "AND r.business_terminal_id=%s",
            (current_revision_id, terminal_id),
        )
        revision = cursor.fetchone()
        if revision is None:
            raise RuntimeError("published Terminal Access Revision was not persisted")
        (
            revision_no,
            revision_status,
            login_strategy_id,
            login_strategy_status,
            automation_asset_id,
            automation_asset_project_id,
        ) = revision
        cursor.execute(
            "SELECT action,COUNT(*) FROM atp_business_terminal_audit "
            "WHERE business_terminal_id=%s AND result_code='SUCCESS' GROUP BY action",
            (terminal_id,),
        )
        terminal_audit_actions = {str(action): int(count) for action, count in cursor.fetchall()}
        cursor.execute(
            "SELECT event_type,COUNT(*) FROM atp_outbox_event "
            "WHERE aggregate_id=%s GROUP BY event_type",
            (terminal_id,),
        )
        terminal_event_types = {
            str(event_type): int(count) for event_type, count in cursor.fetchall()
        }
        cursor.execute(
            "SELECT event_type,COUNT(*),COUNT(CASE WHEN "
            "JSON_UNQUOTE(JSON_EXTRACT(payload_json,'$.payload."
            "environment_terminal_access_revision_id'))=%s THEN 1 END) "
            "FROM atp_outbox_event WHERE aggregate_id=%s GROUP BY event_type",
            (current_revision_id, current_revision_id),
        )
        revision_event_rows = cursor.fetchall()
        revision_event_types = {
            str(event_type): int(count) for event_type, count, _ in revision_event_rows
        }
        revision_event_identity_count = sum(
            int(identity_count) for _, _, identity_count in revision_event_rows
        )
        cursor.execute(
            "SELECT action,COUNT(*) FROM atp_login_strategy_audit "
            "WHERE login_strategy_id=%s AND result_code='SUCCESS' GROUP BY action",
            (login_strategy_id,),
        )
        login_strategy_audit_actions = {
            str(action): int(count) for action, count in cursor.fetchall()
        }
        cursor.execute(
            "SELECT event_type,COUNT(*) FROM atp_outbox_event "
            "WHERE aggregate_id=%s GROUP BY event_type",
            (login_strategy_id,),
        )
        login_strategy_event_types = {
            str(event_type): int(count) for event_type, count in cursor.fetchall()
        }
        cursor.execute(
            "SELECT test_account_id,display_name,lifecycle_status,credential_state,row_version "
            "FROM atp_test_account WHERE project_id=%s AND environment_id=%s "
            "AND account_identifier=%s",
            (project_id, environment_id, account_identifier),
        )
        account = cursor.fetchone()
        if account is None:
            raise RuntimeError("browser-created TestAccount was not persisted")
        (
            test_account_id,
            test_account_display_name,
            test_account_status,
            credential_state,
            test_account_row_version,
        ) = account
        cursor.execute(
            "SELECT c.revision_no,c.lifecycle_status,c.secret_ref,s.encrypted_secret,s.key_id "
            "FROM atp_credential_revision c JOIN atp_test_account_secret s "
            "ON s.credential_revision_id=c.credential_revision_id "
            "WHERE c.test_account_id=%s ORDER BY c.revision_no",
            (test_account_id,),
        )
        credential_rows = list(cursor.fetchall())
        cursor.execute(
            "SELECT business_terminal_id,lifecycle_status "
            "FROM atp_account_mapping_revision WHERE test_account_id=%s",
            (test_account_id,),
        )
        mapping_rows = list(cursor.fetchall())
        cursor.execute(
            "SELECT action,business_terminal_ids,before_json,after_json,credential_changed,"
            "correlation_id,OCTET_LENGTH(source_context_hash) "
            "FROM atp_test_account_audit WHERE test_account_id=%s ORDER BY occurred_at",
            (test_account_id,),
        )
        test_account_audit_rows = list(cursor.fetchall())
        test_account_audit_actions = {str(row[0]) for row in test_account_audit_rows}
        cursor.execute(
            "SELECT event_type,payload_json FROM atp_outbox_event "
            "WHERE aggregate_id=%s ORDER BY sequence",
            (test_account_id,),
        )
        test_account_event_rows = list(cursor.fetchall())
        test_account_event_types = {str(row[0]) for row in test_account_event_rows}
        runner_code = f"RUNNER-{project_code}"
        cursor.execute(
            "SELECT runner_id,lifecycle_status,registration_status,connection_status,"
            "health_status,enable_status,project_binding_status,scheduling_status,row_version "
            "FROM atp_runner WHERE project_id=%s AND runner_code=%s",
            (runner_project_id, runner_code),
        )
        runner = cursor.fetchone()
        if runner is None:
            raise RuntimeError("browser-created Runner was not persisted")
        (
            runner_id,
            runner_lifecycle_status,
            runner_registration_status,
            runner_connection_status,
            runner_health_status,
            runner_enable_status,
            runner_binding_status,
            runner_scheduling_status,
            runner_row_version,
        ) = runner
        cursor.execute(
            "SELECT enrollment_id,enrollment_status,consumed_runner_id,"
            "OCTET_LENGTH(credential_hash) FROM atp_runner_enrollment "
            "WHERE project_id=%s AND runner_code=%s",
            (runner_project_id, runner_code),
        )
        enrollment = cursor.fetchone()
        if enrollment is None:
            raise RuntimeError("Runner enrollment evidence is missing")
        enrollment_id, enrollment_status, consumed_runner_id, enrollment_hash_length = enrollment
        cursor.execute(
            "SELECT token_status,token_version,OCTET_LENGTH(token_hash),"
            "OCTET_LENGTH(machine_fingerprint_hash),lifecycle_status "
            "FROM atp_runner_agent WHERE runner_id=%s",
            (runner_id,),
        )
        runner_agent = cursor.fetchone()
        if runner_agent is None:
            raise RuntimeError("Runner Agent identity evidence is missing")
        (
            agent_token_status,
            agent_token_version,
            agent_token_hash_length,
            machine_fingerprint_hash_length,
            agent_lifecycle_status,
        ) = runner_agent
        cursor.execute(
            "SELECT capability_code FROM atp_runner_capability "
            "WHERE runner_id=%s AND availability_status='CONFIGURED' "
            "AND lifecycle_status='ACTIVE'",
            (runner_id,),
        )
        runner_capabilities = {str(row[0]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT action,actor_type,required_permission,credential_changed "
            "FROM atp_runner_audit WHERE runner_id=%s OR enrollment_id=%s",
            (runner_id, enrollment_id),
        )
        runner_audit_rows = list(cursor.fetchall())
        runner_audit_actions = {str(row[0]) for row in runner_audit_rows}
        cursor.execute(
            "SELECT event_type FROM atp_outbox_event WHERE aggregate_id IN (%s,%s)",
            (runner_id, enrollment_id),
        )
        runner_event_types = {str(row[0]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=DATABASE() "
            "AND table_name IN ('atp_runner_enrollment','atp_runner_agent') "
            "AND column_name IN ('enrollment_credential','agent_token')"
        )
        runner_plaintext_secret_column_count = int(cursor.fetchone()[0])

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
        if (
            expected is None
            or (
                required_permission,
                scope_decision,
                previous_status,
                new_status,
            )
            != expected
        ):
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
    if (
        environment_display_name != "真实事务更新环境"
        or environment_status != "ACTIVE"
        or int(environment_row_version) != 6
    ):
        raise RuntimeError("Environment persistence does not match the browser/API workflow")
    if not {
        "ENVIRONMENT_CREATED",
        "ENVIRONMENT_UPDATED",
        "ENVIRONMENT_VALIDATING",
        "ENVIRONMENT_CONFIGURING",
        "ENVIRONMENT_ACTIVE",
    }.issubset(environment_audit_actions):
        raise RuntimeError("Environment success audit evidence is incomplete")
    if environment_failed_audits < 2:
        raise RuntimeError("Environment failure audit evidence is incomplete")
    if environment_lifecycle_failure_results != {
        "validate_environment:ENVIRONMENT_CONCURRENCY_CONFLICT": 1,
        "validate_environment:ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE": 1,
    }:
        raise RuntimeError("Environment lifecycle failure audit evidence is incomplete")
    if environment_lifecycle_idempotency != {
        "validate_environment": 2,
        "reconfigure_environment": 1,
        "activate_environment": 1,
    }:
        raise RuntimeError("Environment lifecycle idempotency evidence is incomplete")
    if (
        environment_event_types.get("environment.configuring") != 2
        or environment_event_types.get("environment.validating") != 2
        or environment_event_types.get("environment.active") != 1
    ):
        raise RuntimeError("Environment outbox evidence is incomplete")
    if cross_project_environment_count != 2:
        raise RuntimeError("Environment project-scoped uniqueness evidence is incomplete")
    if (
        current_revision_id is None
        or terminal_status != "ACTIVE"
        or int(terminal_row_version) != 4
        or int(revision_no) != 1
        or revision_status != "PUBLISHED"
        or login_strategy_id is None
        or login_strategy_status != "ACTIVE"
        or automation_asset_id is None
        or automation_asset_project_id != project_id
    ):
        raise RuntimeError("BusinessTerminal published Revision ownership is inconsistent")
    if not {
        "BUSINESS_TERMINAL_CREATED",
        "TERMINAL_ACCESS_REVISION_CREATED",
        "TERMINAL_ACCESS_REVISION_VALIDATING",
        "TERMINAL_ACCESS_REVISION_PUBLISHED",
        "BUSINESS_TERMINAL_VALIDATING",
        "BUSINESS_TERMINAL_ACTIVE",
    }.issubset(terminal_audit_actions):
        raise RuntimeError("BusinessTerminal audit evidence is incomplete")
    if (
        terminal_event_types.get("business_terminal.configuring") != 1
        or terminal_event_types.get("business_terminal.validating") != 1
        or terminal_event_types.get("business_terminal.active") != 1
    ):
        raise RuntimeError("BusinessTerminal aggregate outbox evidence is incomplete")
    if (
        not {
            "environment_terminal_access_revision.draft",
            "environment_terminal_access_revision.validating",
            "environment_terminal_access_revision.published",
        }.issubset(revision_event_types)
        or revision_event_identity_count != 3
    ):
        raise RuntimeError("Terminal Access Revision outbox identity evidence is incomplete")
    if not {
        "LOGIN_STRATEGY_CREATED",
        "LOGIN_STRATEGY_UPDATED",
        "LOGIN_STRATEGY_DRAFT",
        "LOGIN_STRATEGY_ACTIVE",
    }.issubset(login_strategy_audit_actions):
        raise RuntimeError("LoginStrategy audit evidence is incomplete")
    if not {"login_strategy.draft", "login_strategy.active"}.issubset(login_strategy_event_types):
        raise RuntimeError("LoginStrategy lifecycle outbox evidence is incomplete")
    if (
        test_account_display_name != "浏览器验收测试账号（已更新）"  # noqa: RUF001
        or test_account_status != "ACTIVE"
        or credential_state != "VALID"
        or int(test_account_row_version) != 5
    ):
        raise RuntimeError("TestAccount persistence does not match the browser workflow")
    if len(mapping_rows) != 1 or (
        str(mapping_rows[0][0]) != str(terminal_id) or str(mapping_rows[0][1]) != "PUBLISHED"
    ):
        raise RuntimeError("TestAccount terminal mapping scope is inconsistent")
    if len(credential_rows) != 2:
        raise RuntimeError("TestAccount credential rotation did not retain two revisions")
    for index, row in enumerate(credential_rows, start=1):
        revision_number, revision_status_value, secret_ref, encrypted_secret, key_id = row
        expected_status = "SUPERSEDED" if index == 1 else "PUBLISHED"
        ciphertext = bytes(encrypted_secret)
        if (
            int(revision_number) != index
            or str(revision_status_value) != expected_status
            or not str(secret_ref).startswith("test-account-secret:")
            or not str(key_id)
            or len(ciphertext) <= 28
            or initial_account_secret in ciphertext
            or rotated_account_secret in ciphertext
        ):
            raise RuntimeError("TestAccount credential encryption evidence is invalid")
    required_test_account_audits = {
        "TEST_ACCOUNT_CREATED",
        "TEST_ACCOUNT_UPDATED",
        "TEST_ACCOUNT_CREDENTIAL_ROTATED",
        "TEST_ACCOUNT_VALIDATING",
        "TEST_ACCOUNT_ACTIVE",
    }
    if not required_test_account_audits.issubset(test_account_audit_actions):
        raise RuntimeError("TestAccount append-only audit evidence is incomplete")
    if sum(bool(row[4]) for row in test_account_audit_rows) != 2 or any(
        not row[5] or int(row[6] or 0) != 32 for row in test_account_audit_rows
    ):
        raise RuntimeError("TestAccount audit security fields are incomplete")
    required_test_account_events = {
        "test_account.configuring",
        "test_account.updated",
        "test_account.credential_rotated",
        "test_account.validating",
        "test_account.active",
    }
    if not required_test_account_events.issubset(test_account_event_types):
        raise RuntimeError("TestAccount outbox evidence is incomplete")
    if (
        runner_lifecycle_status != "REGISTERED"
        or runner_registration_status != "REGISTERED"
        or runner_connection_status != "OFFLINE"
        or runner_health_status != "HEALTHY"
        or runner_enable_status != "DISABLED"
        or runner_binding_status != "BOUND"
        or runner_scheduling_status != "UNSCHEDULABLE"
        or int(runner_row_version) != 4
    ):
        raise RuntimeError("Runner separated state persistence is inconsistent")
    if (
        enrollment_status != "CONSUMED"
        or consumed_runner_id != runner_id
        or int(enrollment_hash_length or 0) != 32
        or agent_token_status != "REVOKED"
        or int(agent_token_version) != 2
        or int(agent_token_hash_length or 0) != 32
        or int(machine_fingerprint_hash_length or 0) != 32
        or agent_lifecycle_status != "REVOKED"
        or runner_plaintext_secret_column_count != 0
    ):
        raise RuntimeError("Runner one-time credential or Agent token hash evidence is invalid")
    if runner_capabilities != {"AGENT_VERSION", "BROWSER_CHROMIUM", "CONTEXT_ISOLATION"}:
        raise RuntimeError("Runner capability snapshot evidence is incomplete")
    if not {
        "CREATE_ENROLLMENT",
        "REGISTER",
        "REPORT_CAPABILITIES",
        "ROTATE_AGENT_TOKEN",
        "REVOKE_AGENT_TOKEN",
    }.issubset(runner_audit_actions):
        raise RuntimeError("Runner append-only audit evidence is incomplete")
    runner_audit_by_action = {str(row[0]): row for row in runner_audit_rows}
    if (
        runner_audit_by_action["CREATE_ENROLLMENT"][1:3] != ("HUMAN", "RUNNER_BIND")
        or runner_audit_by_action["REPORT_CAPABILITIES"][1:3] != ("AGENT", None)
        or runner_audit_by_action["ROTATE_AGENT_TOKEN"][1:3] != ("HUMAN", "RUNNER_REGISTER")
        or runner_audit_by_action["REVOKE_AGENT_TOKEN"][1:3] != ("HUMAN", "RUNNER_REGISTER")
        or sum(bool(row[3]) for row in runner_audit_rows) < 4
    ):
        raise RuntimeError("Runner human and machine audit semantics are not separated")
    if not {
        "runner.enrollment_created",
        "runner.registered",
        "runner.agent_token_rotated",
        "runner.agent_token_revoked",
    }.issubset(runner_event_types):
        raise RuntimeError("Runner outbox evidence is incomplete")
    sensitive_evidence = json.dumps(
        {
            "audit": test_account_audit_rows,
            "events": test_account_event_rows,
        },
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    if initial_account_secret in sensitive_evidence or rotated_account_secret in sensitive_evidence:
        raise RuntimeError("TestAccount secret leaked into audit or outbox evidence")
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
        "environment_status": environment_status,
        "environment_row_version": int(environment_row_version),
        "environment_audit_actions": environment_audit_actions,
        "environment_failed_audit_count": environment_failed_audits,
        "environment_lifecycle_failure_results": environment_lifecycle_failure_results,
        "environment_lifecycle_idempotency": environment_lifecycle_idempotency,
        "environment_outbox_event_types": environment_event_types,
        "cross_project_environment_count": cross_project_environment_count,
        "business_terminal_status": terminal_status,
        "business_terminal_row_version": int(terminal_row_version),
        "current_published_revision_id": str(current_revision_id),
        "published_revision_no": int(revision_no),
        "login_strategy_status": login_strategy_status,
        "login_strategy_audit_actions": login_strategy_audit_actions,
        "login_strategy_outbox_event_types": login_strategy_event_types,
        "business_terminal_audit_actions": terminal_audit_actions,
        "business_terminal_outbox_event_types": terminal_event_types,
        "terminal_access_revision_outbox_event_types": revision_event_types,
        "test_account_status": test_account_status,
        "test_account_row_version": int(test_account_row_version),
        "test_account_mapping_count": len(mapping_rows),
        "test_account_credential_revision_count": len(credential_rows),
        "test_account_secret_encrypted": True,
        "test_account_audit_actions": sorted(test_account_audit_actions),
        "test_account_outbox_event_types": sorted(test_account_event_types),
        "test_account_secret_absent_from_audit_and_outbox": True,
        "runner_lifecycle_status": runner_lifecycle_status,
        "runner_registration_status": runner_registration_status,
        "runner_connection_status": runner_connection_status,
        "runner_health_status": runner_health_status,
        "runner_enable_status": runner_enable_status,
        "runner_binding_status": runner_binding_status,
        "runner_scheduling_status": runner_scheduling_status,
        "runner_row_version": int(runner_row_version),
        "runner_enrollment_status": enrollment_status,
        "runner_agent_token_status": agent_token_status,
        "runner_agent_token_version": int(agent_token_version),
        "runner_hash_only_credentials": True,
        "runner_capabilities": sorted(runner_capabilities),
        "runner_audit_actions": sorted(runner_audit_actions),
        "runner_outbox_event_types": sorted(runner_event_types),
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


def _prepare_execution_binding_acceptance(
    database: str, project_code: str, username: str
) -> dict[str, object]:
    """Stage an isolated ExecutionBinding relationship fixture, not Runner readiness proof.

    This controlled SQL fixture deliberately prebuilds schedulable Runner state so the
    gate can exercise binding relationships that still lack public provisioning commands.
    Formal Register -> capability validation -> compatibility/scheduling evidence belongs
    to AI_EXPLORATION_REAL_RUNNER_ACCEPTANCE and must never be inferred from this fixture.
    """

    runner_id = new_ulid()
    runner_agent_token = "rat_" + secrets.token_urlsafe(32)
    policy_id = new_ulid()
    run_task_id = new_ulid()
    attempt_ids = [new_ulid() for _ in range(5)]
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT project_id,lifecycle_status FROM atp_project WHERE project_code=%s",
            (project_code,),
        )
        project_id, previous_project_status = cursor.fetchone()
        cursor.execute(
            "SELECT environment_id FROM atp_environment WHERE project_id=%s "
            "AND environment_code=%s AND lifecycle_status='ACTIVE'",
            (project_id, f"ENV-{project_code}"),
        )
        environment_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT business_terminal_id,current_published_revision_id "
            "FROM atp_business_terminal WHERE project_id=%s AND terminal_code=%s "
            "AND lifecycle_status='ACTIVE'",
            (project_id, f"ADMIN-{project_code}"),
        )
        terminal_id, terminal_revision_id = cursor.fetchone()
        cursor.execute(
            "SELECT test_account_id FROM atp_test_account WHERE project_id=%s "
            "AND environment_id=%s AND account_identifier=%s AND lifecycle_status='ACTIVE'",
            (project_id, environment_id, f"qa-{project_code}"),
        )
        account_id = cursor.fetchone()[0]
        cursor.execute("SELECT user_id FROM atp_user WHERE username=%s", (username,))
        actor_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT credential_revision_id FROM atp_credential_revision "
            "WHERE test_account_id=%s AND lifecycle_status='PUBLISHED' "
            "ORDER BY revision_no DESC LIMIT 1",
            (account_id,),
        )
        credential_revision_id = cursor.fetchone()[0]

        cursor.execute(
            "UPDATE atp_project SET lifecycle_status='ACTIVE' WHERE project_id=%s",
            (project_id,),
        )
        cursor.execute(
            "INSERT INTO atp_runner "
            "(runner_id,project_id,runner_code,registration_status,connection_status,"
            "health_status,enable_status,project_binding_status,scheduling_status,"
            "resource_status,version_compatibility,last_heartbeat_at,registered_at,"
            "runtime_metadata_json,lifecycle_status,display_name,row_version,"
            "created_by,updated_by) "
            "VALUES (%s,%s,%s,'REGISTERED','ONLINE','HEALTHY','ENABLED','BOUND','IDLE',"
            "'AVAILABLE','COMPATIBLE',CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),"
            "JSON_OBJECT('acceptance_fixture',TRUE),'ACTIVE',%s,1,%s,%s)",
            (
                runner_id,
                project_id,
                f"BINDING-{project_code}",
                "Execution Binding Acceptance Runner",
                actor_id,
                actor_id,
            ),
        )
        cursor.execute(
            "INSERT INTO atp_runner_agent "
            "(runner_agent_id,project_id,runner_id,token_hash,token_status,token_version,"
            "machine_fingerprint_hash,agent_version,last_authenticated_at,credential_rotated_at,"
            "revoked_at,lifecycle_status,display_name,row_version,created_at,updated_at,"
            "created_by,updated_by,extension_json) VALUES (%s,%s,%s,%s,'ACTIVE',1,%s,"
            "'acceptance-agent',NULL,CURRENT_TIMESTAMP(6),NULL,'ACTIVE',%s,1,"
            "CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),%s,%s,NULL)",
            (
                new_ulid(),
                project_id,
                runner_id,
                hashlib.sha256(runner_agent_token.encode("utf-8")).digest(),
                hashlib.sha256(b"acceptance-machine").digest(),
                "Execution Binding Acceptance Agent",
                actor_id,
                actor_id,
            ),
        )
        capabilities = {
            "FORMAL_EXECUTION": "FLOW",
            "TERMINAL_ADMIN_WEB": "TERMINAL",
            "BROWSER_CHROMIUM": "BROWSER",
            "CAPTURE_SCREENSHOT": "ARTIFACT",
            "INTRANET_ACCESS": "NETWORK",
        }
        for code, capability_type in capabilities.items():
            cursor.execute(
                "INSERT INTO atp_runner_capability "
                "(runner_capability_id,project_id,runner_id,capability_code,capability_type,"
                "availability_status,validation_status,observed_version,reported_at,"
                "lifecycle_status,display_name,row_version,created_by,updated_by) "
                "VALUES (%s,%s,%s,%s,%s,'CONFIGURED','VALID','acceptance',"
                "CURRENT_TIMESTAMP(6),'ACTIVE',%s,1,%s,%s)",
                (
                    new_ulid(),
                    project_id,
                    runner_id,
                    code,
                    capability_type,
                    code,
                    actor_id,
                    actor_id,
                ),
            )
        cursor.execute(
            "INSERT INTO atp_project_runtime_policy_revision "
            "(runtime_policy_revision_id,project_id,revision_no,browser_runtime,"
            "artifact_policy,timeout_seconds,max_steps,total_exploration_timeout_seconds,"
            "model_transient_retry_per_step,allowed_origins,authentication_redirect_origins,"
            "retry_mode,network_requirement,"
            "serial_execution_policy,lifecycle_status,row_version,created_by,updated_by) "
            "VALUES (%s,%s,1,'CHROMIUM','SCREENSHOT',300,50,1800,2,JSON_ARRAY(),"
            "JSON_ARRAY(),'UNIFIED','INTRANET',"
            "'SINGLE_PROCESS_UNIFIED_RETRY','PUBLISHED',1,%s,%s)",
            (policy_id, project_id, actor_id, actor_id),
        )
        standard_case_id = new_ulid()
        case_version_id = new_ulid()
        case_suite_id = new_ulid()
        cursor.execute(
            "INSERT INTO atp_standard_case "
            "(standard_case_id,project_id,case_code,lifecycle_status,display_name,row_version,"
            "created_by,updated_by) VALUES (%s,%s,%s,'READY',%s,1,%s,%s)",
            (
                standard_case_id,
                project_id,
                f"BINDING-{project_code}",
                "Binding acceptance case",
                actor_id,
                actor_id,
            ),
        )
        cursor.execute(
            "INSERT INTO atp_case_version "
            "(case_version_id,project_id,case_id,version_no,standard_case_id,lifecycle_status,"
            "display_name,row_version,created_by,updated_by) "
            "VALUES (%s,%s,%s,'1',%s,'PUBLISHED',%s,1,%s,%s)",
            (
                case_version_id,
                project_id,
                standard_case_id,
                standard_case_id,
                "Binding acceptance case revision",
                actor_id,
                actor_id,
            ),
        )
        cursor.execute(
            "INSERT INTO atp_case_suite "
            "(case_suite_id,project_id,suite_code,case_version_id,lifecycle_status,display_name,"
            "row_version,created_by,updated_by) VALUES (%s,%s,%s,%s,'ACTIVE',%s,1,%s,%s)",
            (
                case_suite_id,
                project_id,
                f"BINDING-{project_code}",
                case_version_id,
                "Binding acceptance suite",
                actor_id,
                actor_id,
            ),
        )
        cursor.execute(
            "INSERT INTO atp_run_task "
            "(run_task_id,project_id,idempotency_key,case_suite_id,environment_id,"
            "lifecycle_status,task_state,final_result,display_name,row_version,"
            "created_by,updated_by) "
            "VALUES (%s,%s,%s,%s,%s,'WAITING_RESOURCE','WAITING_RESOURCE','UNKNOWN',%s,1,%s,%s)",
            (
                run_task_id,
                project_id,
                f"binding-{project_code}",
                case_suite_id,
                environment_id,
                "Binding acceptance root task",
                actor_id,
                actor_id,
            ),
        )
        for attempt_id in attempt_ids:
            configuration_id = new_ulid()
            batch_id = new_ulid()
            case_attempt_id = new_ulid()
            cursor.execute(
                "INSERT INTO atp_configuration_snapshot "
                "(configuration_snapshot_id,project_id,lifecycle_status,display_name,row_version,"
                "created_by,updated_by) VALUES (%s,%s,'SEALED',%s,1,%s,%s)",
                (configuration_id, project_id, "Binding acceptance config", actor_id, actor_id),
            )
            cursor.execute(
                "INSERT INTO atp_execution_batch "
                "(execution_batch_id,project_id,batch_no,lifecycle_status,display_name,row_version,"
                "created_by,updated_by) VALUES (%s,%s,%s,'CREATED',%s,1,%s,%s)",
                (batch_id, project_id, attempt_id, "Binding acceptance batch", actor_id, actor_id),
            )
            # V3 models the CaseAttempt/ExecutionAttempt pair with mutual mandatory FKs.
            # The isolated fixture inserts the complete pair before restoring enforcement.
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            try:
                cursor.execute(
                    "INSERT INTO atp_case_attempt "
                    "(case_attempt_id,project_id,execution_attempt_id,result_status,"
                    "lifecycle_status,display_name,row_version,created_by,updated_by) "
                    "VALUES (%s,%s,%s,'BROKEN','CREATED',%s,1,%s,%s)",
                    (
                        case_attempt_id,
                        project_id,
                        attempt_id,
                        "Binding acceptance case",
                        actor_id,
                        actor_id,
                    ),
                )
                cursor.execute(
                    "INSERT INTO atp_execution_attempt "
                    "(execution_attempt_id,project_id,run_task_id,attempt_no,case_attempt_id,runner_id,"
                    "configuration_snapshot_id,execution_batch_id,execution_status,"
                    "finalization_status,lifecycle_status,display_name,row_version,"
                    "created_by,updated_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'READY','INITIAL','CREATED',%s,1,%s,%s)",
                    (
                        attempt_id,
                        project_id,
                        run_task_id,
                        attempt_id,
                        case_attempt_id,
                        runner_id,
                        configuration_id,
                        batch_id,
                        "Binding acceptance attempt",
                        actor_id,
                        actor_id,
                    ),
                )
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS=1")

        cursor.execute(
            "SELECT COUNT(*) FROM atp_execution_attempt ea "
            "JOIN atp_case_attempt ca ON ca.case_attempt_id=ea.case_attempt_id "
            "AND ca.execution_attempt_id=ea.execution_attempt_id "
            "WHERE ea.execution_attempt_id IN (%s,%s,%s,%s,%s) AND ea.run_task_id=%s",
            (*attempt_ids, run_task_id),
        )
        if int(cursor.fetchone()[0]) != 5:
            raise RuntimeError("execution binding acceptance owner fixture is inconsistent")

    # The controlled relationship fixture still seeds its surrounding objects, but the
    # formal slot itself must be formed by the same system-owned reconciliation used by
    # a real Runner.  This prevents the acceptance gate from masking Slot provisioning.
    engine = create_database_engine(_test_database_url(database))
    try:
        factory = create_session_factory(engine)
        with factory() as db:
            runner = db.get(Runner, runner_id)
            project = db.get(Project, str(project_id))
            if runner is None or project is None:
                raise RuntimeError("execution binding runner/project fixture is unavailable")
            execution_slot = reconcile_formal_execution_slot(db, runner, project)
            if execution_slot is None or execution_slot.lifecycle_status != "ACTIVE":
                raise RuntimeError("formal ExecutionSlot was not reconciled from Runner facts")
            execution_slot_id = execution_slot.execution_slot_id
            db.commit()
    finally:
        engine.dispose()

    return {
        "project_id": str(project_id),
        "previous_project_status": str(previous_project_status),
        "environment_id": str(environment_id),
        "terminal_id": str(terminal_id),
        "terminal_revision_id": str(terminal_revision_id),
        "account_id": str(account_id),
        "credential_revision_id": str(credential_revision_id),
        "runner_id": runner_id,
        "runner_agent_token": runner_agent_token,
        "policy_id": policy_id,
        "attempt_ids": attempt_ids,
        "runner_resource_identity": execution_slot_id,
        "owner_execution_identity": run_task_id,
    }


def _wait_for_runner_agent(database: str, runner_id: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("bound Runner Agent stopped during startup")
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT last_authenticated_at FROM atp_runner_agent WHERE runner_id=%s",
                (runner_id,),
            )
            row = cursor.fetchone()
        if row is not None and row[0] is not None:
            return
        time.sleep(0.1)
    raise RuntimeError("bound Runner Agent did not establish a machine-authenticated session")


def _restore_execution_binding_project(database: str, fixture: dict[str, object]) -> None:
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE atp_project SET lifecycle_status=%s WHERE project_id=%s",
            (fixture["previous_project_status"], fixture["project_id"]),
        )


def _execution_binding_recovery_evidence(
    database: str,
    api_port: int,
    username: str,
    password: str,
    fixture: dict[str, object],
) -> dict[str, object]:
    status, login = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/auth/login",
        {"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError("execution binding recovery probe login failed")
    token = str(dict(login["data"])["access_token"])
    headers = {"Authorization": f"Bearer {token}"}
    attempt_ids = tuple(fixture["attempt_ids"])[:4]
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT b.execution_binding_snapshot_id,b.execution_attempt_id,b.row_version,"
            "b.owner_execution_identity,b.identity_lease_generation,b.runner_lease_generation,"
            "b.identity_lease_id,b.runner_lease_id "
            "FROM atp_execution_binding_snapshot b "
            "WHERE b.execution_attempt_id IN (%s,%s,%s,%s) AND b.status='READY'",
            attempt_ids,
        )
        active_rows = list(cursor.fetchall())
        if len(active_rows) != 1:
            raise RuntimeError("contention must leave exactly one active binding")
        (
            binding_id,
            winner_attempt_id,
            row_version,
            owner_identity,
            identity_generation,
            runner_generation,
            identity_lease_id,
            runner_lease_id,
        ) = active_rows[0]
        cursor.execute(
            "UPDATE atp_resource_lease SET "
            "expires_at=DATE_SUB(UTC_TIMESTAMP(6),INTERVAL 1 SECOND) "
            "WHERE resource_lease_id IN (%s,%s) AND status='ACTIVE'",
            (identity_lease_id, runner_lease_id),
        )

    recover_status, recover_payload = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/execution-binding-snapshots/{binding_id}/recover",
        {
            "owner_execution_identity": owner_identity,
            "expected_version": int(row_version),
            "identity_lease_generation": int(identity_generation),
            "runner_lease_generation": int(runner_generation),
            "reason": "real stale recovery acceptance",
            "recovery_evidence": "both server-time lease expiries were forced stale in isolated DB",
        },
        headers={**headers, "Idempotency-Key": f"recover-{binding_id}"},
    )
    recovered = dict(recover_payload.get("data") or {})
    if (
        recover_status != 200
        or recovered.get("status") != "EXPIRED"
        or dict(recovered.get("identity_lease") or {}).get("status") != "EXPIRED"
        or dict(recovered.get("runner_lease") or {}).get("status") != "EXPIRED"
    ):
        raise RuntimeError(
            "server-time stale recovery did not expire binding and leases: "
            f"http={recover_status}, code={recover_payload.get('code')}, "
            f"binding_status={recovered.get('status')}, "
            f"identity_status={dict(recovered.get('identity_lease') or {}).get('status')}, "
            f"runner_status={dict(recovered.get('runner_lease') or {}).get('status')}"
        )

    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*),COUNT(DISTINCT execution_attempt_id) "
            "FROM atp_execution_binding_snapshot WHERE execution_attempt_id IN (%s,%s,%s,%s)",
            attempt_ids,
        )
        binding_count, bound_attempt_count = cursor.fetchone()
        cursor.execute(
            "SELECT l.resource_type,GROUP_CONCAT("
            "l.fencing_generation ORDER BY l.fencing_generation) "
            "FROM atp_resource_lease l JOIN atp_execution_binding_snapshot b "
            "ON l.resource_lease_id IN (b.identity_lease_id,b.runner_lease_id) "
            "WHERE b.execution_attempt_id IN (%s,%s,%s,%s) GROUP BY l.resource_type",
            attempt_ids,
        )
        generations = {str(kind): str(values) for kind, values in cursor.fetchall()}
        cursor.execute(
            "SELECT action,COUNT(*) FROM atp_execution_binding_audit "
            "WHERE execution_attempt_id IN (%s,%s,%s,%s) GROUP BY action",
            attempt_ids,
        )
        audit_actions = {str(action): int(count) for action, count in cursor.fetchall()}
        cursor.execute(
            "SELECT event_type,COUNT(*) FROM atp_outbox_event WHERE aggregate_id IN ("
            "SELECT execution_binding_snapshot_id FROM atp_execution_binding_snapshot "
            "WHERE execution_attempt_id IN (%s,%s,%s,%s)) GROUP BY event_type",
            attempt_ids,
        )
        outbox_events = {str(event_type): int(count) for event_type, count in cursor.fetchall()}
        cursor.execute(
            "SELECT COUNT(*) FROM atp_execution_binding_snapshot b "
            "JOIN atp_resource_lease i ON i.resource_lease_id=b.identity_lease_id "
            "JOIN atp_resource_lease r ON r.resource_lease_id=b.runner_lease_id "
            "WHERE b.execution_attempt_id IN (%s,%s,%s,%s)",
            attempt_ids,
        )
        atomically_complete_count = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
            "AND table_name IN ('atp_execution_binding_snapshot','atp_resource_lease',"
            "'atp_execution_binding_audit') AND column_name LIKE '%%secret%%'"
        )
        secret_column_count = int(cursor.fetchone()[0])

    if int(binding_count) != 3 or int(bound_attempt_count) != 3:
        raise RuntimeError("lease contention did not yield exactly one committed winner")
    if generations != {"IDENTITY": "1,2,3", "RUNNER": "1,2,3"}:
        raise RuntimeError("release/reacquire fencing generations are not monotonic")
    if audit_actions != {"CREATE": 3, "RECOVER": 1, "RELEASE": 2, "RENEW": 1}:
        raise RuntimeError("execution binding append-only audit evidence is incomplete")
    required_events = {
        "execution_binding_snapshot.ready": 3,
        "execution_binding_snapshot.leases_renewed": 1,
        "execution_binding_snapshot.released": 2,
        "execution_binding_snapshot.expired": 1,
    }
    if outbox_events != required_events:
        raise RuntimeError("execution binding outbox evidence is incomplete")
    if atomically_complete_count != 3 or secret_column_count != 0:
        raise RuntimeError("binding/lease atomicity or secret minimization evidence failed")
    return {
        "binding_count": int(binding_count),
        "contention_winner_attempt_id": str(winner_attempt_id),
        "generation_sequences": generations,
        "audit_actions": audit_actions,
        "outbox_events": outbox_events,
        "stale_recovery_status": recover_status,
        "atomic_binding_lease_count": atomically_complete_count,
        "secret_column_count": secret_column_count,
    }


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
        cursor.execute("RENAME TABLE atp_project_audit TO atp_project_audit_unavailable_probe")
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
            cursor.execute("RENAME TABLE atp_project_audit_unavailable_probe TO atp_project_audit")
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


def _prepare_ai_exploration_runtime(
    database: str,
    fixture: dict[str, object],
    username: str,
    target_url: str,
    key_ring_file: Path,
    provider_secret: str,
) -> str:
    """Project the isolated target and frozen model through their formal DB owners."""

    parsed = urlsplit(target_url)
    origin = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    model_config_id = new_ulid()
    encrypted = AesGcmSecretProtector.load(key_ring_file).encrypt(model_config_id, provider_secret)
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM atp_user WHERE username=%s", (username,))
        actor_id = str(cursor.fetchone()[0])
        cursor.execute(
            "UPDATE atp_environment_terminal_access_revision "
            "SET entry_url=%s,login_url=NULL,row_version=row_version+1,updated_at=UTC_TIMESTAMP(6) "
            "WHERE environment_terminal_access_revision_id=%s",
            (target_url, fixture["terminal_revision_id"]),
        )
        cursor.execute(
            "UPDATE atp_project_runtime_policy_revision "
            "SET allowed_origins=JSON_ARRAY(%s),authentication_redirect_origins=JSON_ARRAY(),"
            "timeout_seconds=10,row_version=row_version+1,updated_at=UTC_TIMESTAMP(6) "
            "WHERE runtime_policy_revision_id=%s",
            (origin, fixture["policy_id"]),
        )
        cursor.execute(
            "INSERT INTO atp_model_config "
            "(model_config_id,config_code,provider_code,model_name,request_timeout_seconds,"
            "lifecycle_status,display_name,row_version,created_at,updated_at,"
            "created_by,updated_by) "
            "VALUES (%s,%s,%s,%s,30,'ACTIVE',%s,1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6),%s,%s)",
            (
                model_config_id,
                f"ai-exploration-{model_config_id}",
                AI_EXPLORATION_PROVIDER_CODE,
                AI_EXPLORATION_MODEL_NAME,
                "AI exploration deterministic model",
                actor_id,
                actor_id,
            ),
        )
        cursor.execute(
            "INSERT INTO atp_model_config_secret "
            "(model_config_id,encrypted_secret,key_id,created_at,updated_at) "
            "VALUES (%s,%s,%s,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))",
            (model_config_id, encrypted.ciphertext, encrypted.key_id),
        )
        cursor.execute(
            "INSERT INTO atp_model_capability_default "
            "(capability_code,model_config_id,row_version,created_at,updated_at,"
            "created_by,updated_by) "
            "VALUES ('AI_EXPLORATION',%s,1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6),%s,%s)",
            (model_config_id, actor_id, actor_id),
        )
    return model_config_id


def _create_ai_execution_binding(
    database: str,
    api_port: int,
    username: str,
    password: str,
    fixture: dict[str, object],
    *,
    execution_attempt_id: str | None = None,
    owner_execution_identity: str | None = None,
    bearer_token: str | None = None,
) -> str:
    token = bearer_token
    if token is None:
        status, login = _post_json(
            f"http://127.0.0.1:{api_port}/api/v1/auth/login",
            {"username": username, "password": password},
        )
        if status != 200:
            raise RuntimeError("AI exploration binding login failed")
        token = str(dict(login["data"])["access_token"])
    attempt_id = execution_attempt_id
    if attempt_id is None:
        attempt_ids = tuple(fixture["attempt_ids"])
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT ea.execution_attempt_id FROM atp_execution_attempt ea "
                "LEFT JOIN atp_execution_binding_snapshot b "
                "ON b.execution_attempt_id=ea.execution_attempt_id "
                "WHERE ea.execution_attempt_id IN (%s,%s,%s,%s,%s) "
                "AND b.execution_binding_snapshot_id IS NULL "
                "ORDER BY ea.execution_attempt_id LIMIT 1",
                attempt_ids,
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("AI exploration has no unbound ExecutionAttempt fixture")
        attempt_id = str(row[0])
    owner_identity = owner_execution_identity or str(fixture["owner_execution_identity"])
    create_status, payload = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/execution-binding-snapshots",
        {
            "execution_attempt_id": attempt_id,
            "project_id": fixture["project_id"],
            "environment_id": fixture["environment_id"],
            "business_terminal_id": fixture["terminal_id"],
            "test_account_id": fixture["account_id"],
            "runner_id": fixture["runner_id"],
            "runtime_policy_revision_id": fixture["policy_id"],
            "runner_resource_type": "FORMAL_EXECUTION_SLOT",
            "runner_resource_identity": fixture["runner_resource_identity"],
            "owner_execution_identity": owner_identity,
            "required_capabilities": [],
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"ai-exploration-binding-{attempt_id}",
        },
    )
    binding = dict(payload.get("data") or {})
    if create_status != 201 or binding.get("status") != "READY":
        raise RuntimeError(
            "AI exploration binding creation failed: "
            f"http={create_status}, code={payload.get('code')}, "
            f"detail={payload.get('detail')}"
        )
    return attempt_id


def _provision_ai_cancellation_owner(
    api_port: int,
    token: str,
    fixture: dict[str, object],
) -> tuple[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    project_id = str(fixture["project_id"])

    run_key = f"ai-exploration-cancel-run-task-{project_id}"
    run_status, run_payload = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/run-task",
        {
            "display_name": "AI exploration cancellation acceptance task",
            "project_id": project_id,
            "environment_id": fixture["environment_id"],
            "task_type": "AI_EXPLORATION",
            "reason": "isolated cancellation acceptance owner",
        },
        headers={**headers, "Idempotency-Key": run_key},
    )

    run_task = dict(run_payload.get("data") or {})
    run_task_id = str(run_task.get("run_task_id") or "")

    if run_status != 202 or len(run_task_id) != 26:
        raise RuntimeError(
            "AI exploration cancellation RunTask provisioning failed: "
            f"http={run_status}, code={run_payload.get('code')}, "
            f"detail={run_payload.get('detail')}"
        )

    attempt_key = f"ai-exploration-cancel-attempt-{run_task_id}"
    attempt_status, attempt_payload = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/execution-attempt",
        {
            "display_name": "AI exploration cancellation acceptance attempt",
            "run_task_id": run_task_id,
            "runner_id": fixture["runner_id"],
            "reason": "isolated cancellation acceptance owner",
        },
        headers={**headers, "Idempotency-Key": attempt_key},
    )

    attempt = dict(attempt_payload.get("data") or {})
    attempt_id = str(attempt.get("execution_attempt_id") or "")

    if attempt_status != 201 or len(attempt_id) != 26:
        raise RuntimeError(
            "AI exploration cancellation ExecutionAttempt provisioning failed: "
            f"http={attempt_status}, code={attempt_payload.get('code')}, "
            f"detail={attempt_payload.get('detail')}"
        )

    return run_task_id, attempt_id


def _ai_exploration_cancel_probe(
    database: str,
    api_port: int,
    username: str,
    password: str,
    fixture: dict[str, object],
    target_url: str,
) -> dict[str, object]:
    login_status, login = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/auth/login",
        {"username": username, "password": password},
    )
    if login_status != 200:
        raise RuntimeError("AI exploration cancellation probe login failed")

    token = str(dict(login["data"])["access_token"])
    headers = {"Authorization": f"Bearer {token}"}

    run_task_id, attempt_id = _provision_ai_cancellation_owner(
        api_port,
        token,
        fixture,
    )

    _create_ai_execution_binding(
        database,
        api_port,
        username,
        password,
        fixture,
        execution_attempt_id=attempt_id,
        owner_execution_identity=run_task_id,
        bearer_token=token,
    )
    create_status, created = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/ai-exploration-sessions",
        {
            "project_id": fixture["project_id"],
            "objective": "CANCEL_PROBE keep the terminal fence authoritative",
            "target_url": target_url,
        },
        headers={**headers, "Idempotency-Key": f"cancel-create-{attempt_id}"},
    )
    resource = dict(created.get("data") or {})
    if create_status != 201 or resource.get("lifecycle_status") != "READY":
        raise RuntimeError("AI exploration cancellation probe planning failed")
    session_id = str(resource["session_id"])
    start_status, started = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/ai-exploration-sessions/{session_id}/start",
        {
            "execution_attempt_id": attempt_id,
            "expected_row_version": int(resource["row_version"]),
        },
        headers={**headers, "Idempotency-Key": f"cancel-start-{attempt_id}"},
    )
    if start_status != 202 or dict(started.get("data") or {}).get("lifecycle_status") != "RUNNING":
        raise RuntimeError("AI exploration cancellation probe did not start")
    running: dict[str, object] = {}
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        get_status, current = _get_json(
            f"http://127.0.0.1:{api_port}/api/v1/ai-exploration-sessions/{session_id}",
            headers=headers,
        )
        running = dict(current.get("data") or {})
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM atp_ai_exploration_step WHERE session_id=%s "
                "ORDER BY sequence DESC LIMIT 1",
                (session_id,),
            )
            step_row = cursor.fetchone()
        step_status = str(step_row[0]) if step_row else ""
        if (
            get_status == 200
            and running.get("lifecycle_status") == "RUNNING"
            and running.get("browser_session_id")
            and int(running.get("current_step_sequence") or 0) >= 1
            and step_status == "EXECUTING"
        ):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("AI exploration cancellation probe missed the in-flight Browser action")
    cancel_status, cancelled = _post_json(
        f"http://127.0.0.1:{api_port}/api/v1/ai-exploration-sessions/{session_id}/cancel",
        {"expected_row_version": int(running["row_version"])},
        headers={**headers, "Idempotency-Key": f"cancel-command-{attempt_id}"},
    )
    cancelled_resource = dict(cancelled.get("data") or {})
    if cancel_status != 200 or cancelled_resource.get("lifecycle_status") != "CANCELLED":
        raise RuntimeError("AI exploration cancellation command failed")
    time.sleep(3.2)
    final_status, final = _get_json(
        f"http://127.0.0.1:{api_port}/api/v1/ai-exploration-sessions/{session_id}",
        headers=headers,
    )
    if final_status != 200 or dict(final.get("data") or {}).get("lifecycle_status") != "CANCELLED":
        raise RuntimeError("late Provider response overwrote the cancellation terminal fence")
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT b.status,ea.execution_status,il.status,rl.status "
            "FROM atp_ai_exploration_session s "
            "JOIN atp_execution_binding_snapshot b "
            "ON b.execution_binding_snapshot_id=s.execution_binding_snapshot_id "
            "JOIN atp_execution_attempt ea ON ea.execution_attempt_id=s.execution_attempt_id "
            "JOIN atp_resource_lease il ON il.resource_lease_id=b.identity_lease_id "
            "JOIN atp_resource_lease rl ON rl.resource_lease_id=b.runner_lease_id "
            "WHERE s.session_id=%s",
            (session_id,),
        )
        released = tuple(map(str, cursor.fetchone() or ()))
        cursor.execute(
            "SELECT action,COUNT(*) FROM atp_ai_exploration_audit "
            "WHERE session_id=%s GROUP BY action",
            (session_id,),
        )
        audits = {str(action): int(count) for action, count in cursor.fetchall()}
        cursor.execute(
            "SELECT COUNT(*) FROM atp_outbox_event WHERE aggregate_id=%s "
            "AND event_type='ai_exploration.cancelled'",
            (session_id,),
        )
        cancelled_events = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM atp_ai_exploration_step WHERE session_id=%s "
            "AND status='DISCARDED' AND failure_code='CANCELLED'",
            (session_id,),
        )
        discarded_steps = int(cursor.fetchone()[0])
    if (
        released != ("RELEASED", "CANCELLED", "RELEASED", "RELEASED")
        or audits.get("CANCEL_REQUESTED") != 1
        or audits.get("BROWSER_CANCELLED") != 1
        or cancelled_events != 1
        or discarded_steps < 1
    ):
        raise RuntimeError("AI exploration cancellation evidence is inconsistent")
    return {
        "session_status": "CANCELLED",
        "in_flight_browser_action_interrupted": True,
        "late_browser_response_discarded": True,
        "binding_and_leases_released": True,
        "discarded_step_count": discarded_steps,
        "audit_actions": audits,
        "cancelled_outbox_count": cancelled_events,
    }


def _ai_exploration_database_evidence(
    database: str,
    project_id: str,
    model_config_id: str,
    provider_secret: str,
    runtime_secret: str,
) -> dict[str, object]:
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT session_id,lifecycle_status,current_step_sequence,execution_attempt_id,"
            "execution_binding_snapshot_id,resolved_model_config_id "
            "FROM atp_ai_exploration_session WHERE project_id=%s "
            "AND lifecycle_status='SUCCEEDED' AND resolved_model_config_id=%s "
            "ORDER BY created_at DESC LIMIT 1",
            (project_id, model_config_id),
        )
        session = cursor.fetchone()
        if session is None:
            raise RuntimeError("AI exploration Session evidence is missing")
        session_id, status, sequence, attempt_id, binding_id, resolved_model_id = session
        cursor.execute(
            "SELECT COUNT(*),COUNT(DISTINCT ai_call_id),"
            "SUM(status='SUCCEEDED'),SUM(status='COMPLETION_PROPOSED') "
            "FROM atp_ai_exploration_step WHERE session_id=%s",
            (session_id,),
        )
        step_count, step_call_count, succeeded_steps, completion_steps = cursor.fetchone()
        cursor.execute(
            "SELECT action,COUNT(*) FROM atp_ai_exploration_audit "
            "WHERE session_id=%s GROUP BY action",
            (session_id,),
        )
        audits = {str(action): int(count) for action, count in cursor.fetchall()}
        cursor.execute(
            "SELECT event_type,COUNT(*) FROM atp_outbox_event "
            "WHERE aggregate_id=%s GROUP BY event_type",
            (session_id,),
        )
        events = {str(event): int(count) for event, count in cursor.fetchall()}
        cursor.execute(
            "SELECT b.status,ea.execution_status,ea.lifecycle_status,il.status,rl.status "
            "FROM atp_execution_binding_snapshot b "
            "JOIN atp_execution_attempt ea ON ea.execution_attempt_id=b.execution_attempt_id "
            "JOIN atp_resource_lease il ON il.resource_lease_id=b.identity_lease_id "
            "JOIN atp_resource_lease rl ON rl.resource_lease_id=b.runner_lease_id "
            "WHERE b.execution_binding_snapshot_id=%s",
            (binding_id,),
        )
        released = cursor.fetchone()
        cursor.execute(
            "SELECT ra.last_authenticated_at FROM atp_runner_agent ra "
            "JOIN atp_execution_binding_snapshot b ON b.runner_id=ra.runner_id "
            "WHERE b.execution_binding_snapshot_id=%s AND ra.token_status='ACTIVE'",
            (binding_id,),
        )
        runner_authentication = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) FROM atp_ai_exploration_step "
            "WHERE session_id=%s AND (CAST(observation_json AS CHAR) LIKE %s "
            "OR CAST(action_json AS CHAR) LIKE %s OR CAST(action_result_json AS CHAR) LIKE %s "
            "OR CAST(observation_json AS CHAR) LIKE %s OR CAST(action_json AS CHAR) LIKE %s "
            "OR CAST(action_result_json AS CHAR) LIKE %s)",
            (
                session_id,
                f"%{provider_secret}%",
                f"%{provider_secret}%",
                f"%{provider_secret}%",
                f"%{runtime_secret}%",
                f"%{runtime_secret}%",
                f"%{runtime_secret}%",
            ),
        )
        secret_rows = int(cursor.fetchone()[0])
    if not (
        str(status) == "SUCCEEDED"
        and int(sequence) >= 2
        and str(resolved_model_id) == model_config_id
        and int(step_count) >= 2
        and int(step_call_count) == int(step_count)
        and int(succeeded_steps or 0) >= 1
        and int(completion_steps or 0) == 1
        and audits.get("BROWSER_STARTED") == 1
        and audits.get("BROWSER_SUCCEEDED") == 1
        and events.get("ai_exploration.browser_started") == 1
        and events.get("ai_exploration.succeeded") == 1
        and tuple(map(str, released or ()))
        == ("RELEASED", "SUCCEEDED", "PASSED", "RELEASED", "RELEASED")
        and runner_authentication is not None
        and runner_authentication[0] is not None
        and secret_rows == 0
    ):
        raise RuntimeError("AI exploration Browser Loop database evidence is inconsistent")
    return {
        "session_status": str(status),
        "execution_attempt_id": str(attempt_id),
        "ordered_step_count": int(step_count),
        "step_ai_call_count": int(step_call_count),
        "binding_and_leases_released": True,
        "audit_actions": audits,
        "outbox_events": events,
        "secret_boundary": "PASS",
        "bound_runner_machine_auth": "PASS",
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
            "TEST_ACCOUNT_FOUNDATION",
            "BROWSER_RUNTIME",
            "RBAC_RUNTIME",
            "MYSQL_PERSISTENCE",
            "TEST_ACCOUNT_SECRET_ENCRYPTION",
            "EXECUTION_BINDING_FENCING",
            "RESOURCE_LEASE_CONTENTION",
            "AI_EXPLORATION_BROWSER_LOOP",
            "LITELLM_COMPATIBLE_MODEL_GATEWAY",
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

    database = _new_database_name("project")
    runtime_directory = RUNTIME_ROOT / f"project-browser-{secrets.token_hex(6)}"
    runtime_directory.mkdir(parents=True, exist_ok=False)
    api_process: subprocess.Popen[bytes] | None = None
    runner_process: subprocess.Popen[bytes] | None = None
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
    execution_binding_fixture: dict[str, object] = {}
    execution_binding_evidence: dict[str, object] = {}
    ai_exploration_evidence: dict[str, object] = {}
    ai_exploration_cancellation_evidence: dict[str, object] = {}
    gateway: model_gate._GatewayFixture | None = None
    target: _ExplorationTargetFixture | None = None
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
        stage = "flyway_migrations"
        run_flyway("migrate", target_database=database)

        stage = "fixtures"
        database_url = _test_database_url(database)
        key_ring = generate_development_key_ring(
            runtime_directory / "keys", kid="project-browser-rs256-v1"
        )
        hmac_key_ring = _write_hmac_key_ring(runtime_directory)
        test_account_secret_key_ring = _write_test_account_secret_key_ring(runtime_directory)
        provider_secret = secrets.token_urlsafe(24)
        gateway = model_gate._GatewayFixture(provider_secret)
        gateway.start()
        target = _ExplorationTargetFixture()
        target.start()
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
        runner_admin_username, runner_admin_password = _create_user(
            factory, passwords, lifecycle="ACTIVE", role_code="ROLE-RUNNER-ADMIN"
        )
        runner_owner_username, _runner_owner_password = _create_user(
            factory, passwords, lifecycle="ACTIVE", role_code="ROLE-PROJECT-OWNER-DUTY"
        )
        engine.dispose()
        project_code = f"browser-project-{secrets.token_hex(6)}"
        runner_project_id = new_ulid()
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
            cursor.execute(
                "SELECT u.user_id,b.binding_id,b.role_id FROM atp_user u "
                "JOIN atp_user_role_binding b ON b.user_id=u.user_id "
                "JOIN atp_role r ON r.role_id=b.role_id "
                "WHERE u.username=%s AND r.role_code='ROLE-RUNNER-ADMIN'",
                (runner_admin_username,),
            )
            runner_admin_user_id, runner_admin_binding_id, runner_admin_role_id = cursor.fetchone()
            cursor.execute(
                "SELECT u.user_id,b.role_id FROM atp_user u "
                "JOIN atp_user_role_binding b ON b.user_id=u.user_id "
                "JOIN atp_role r ON r.role_id=b.role_id "
                "WHERE u.username=%s AND r.role_code='ROLE-PROJECT-OWNER-DUTY'",
                (runner_owner_username,),
            )
            runner_owner_user_id, runner_owner_role_id = cursor.fetchone()
            cursor.execute(
                "INSERT INTO atp_project "
                "(project_id,project_code,lifecycle_status,display_name,row_version,"
                "created_by,updated_by) VALUES (%s,%s,'ACTIVE',%s,1,%s,%s)",
                (
                    runner_project_id,
                    f"runner-scope-{project_code}",
                    "Runner Admin Browser Scope",
                    runner_owner_user_id,
                    runner_owner_user_id,
                ),
            )
            cursor.execute(
                "INSERT INTO atp_project_member "
                "(project_member_id,project_id,user_id,role_id,lifecycle_status,display_name,"
                "row_version,created_by,updated_by) VALUES (%s,%s,%s,%s,'ACTIVE',%s,1,%s,%s)",
                (
                    new_ulid(),
                    runner_project_id,
                    runner_owner_user_id,
                    runner_owner_role_id,
                    "Runner Browser Scope Owner",
                    runner_owner_user_id,
                    runner_owner_user_id,
                ),
            )
            cursor.execute(
                "INSERT INTO atp_project_member "
                "(project_member_id,project_id,user_id,role_id,lifecycle_status,display_name,"
                "row_version,created_by,updated_by) VALUES (%s,%s,%s,%s,'ACTIVE',%s,1,%s,%s)",
                (
                    new_ulid(),
                    runner_project_id,
                    runner_admin_user_id,
                    runner_admin_role_id,
                    "Runner Admin Browser Member",
                    runner_admin_user_id,
                    runner_admin_user_id,
                ),
            )
            cursor.execute(
                "INSERT INTO atp_data_scope_grant "
                "(grant_id,binding_id,scope_type,scope_id,permission_code,created_at) "
                "VALUES (%s,%s,'AUTHORIZED_PROJECT_ACTIVE',%s,NULL,CURRENT_TIMESTAMP(6))",
                (new_ulid(), runner_admin_binding_id, runner_project_id),
            )

        api_port = _available_loopback_port()
        api_environment = project_environment(root=ROOT)
        api_environment.pop(ADMIN_URL_ENV, None)
        python_paths = [
            str(ROOT),
            str(API_SRC),
            str(COMMON_SRC),
            str(OBSERVABILITY_SRC),
            str(RUNNER_SRC),
        ]
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
                "ATP_MODEL_SECRET_KEY_RING_FILE": str(test_account_secret_key_ring),
                "ATP_LITELLM_PROXY_URL": gateway.url,
                "ATP_LITELLM_DYNAMIC_CREDENTIALS_ENABLED": "true",
            }
        )
        api_environment.pop("ATP_LITELLM_PROXY_API_KEY_FILE", None)
        stage = "api_startup"
        api_process, api_log = _start_process(
            [sys.executable, "-m", "tools.gates.ai_exploration_runtime_api"],
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
                "ATP_PROJECT_E2E_RUNNER_ADMIN_USERNAME": runner_admin_username,
                "ATP_PROJECT_E2E_RUNNER_ADMIN_PASSWORD": runner_admin_password,
                "ATP_PROJECT_E2E_RUNNER_PROJECT_ID": runner_project_id,
                "ATP_PROJECT_E2E_ELIGIBLE_OWNER_ID": eligible_owner_id,
                "ATP_PROJECT_E2E_INELIGIBLE_OWNER_ID": ineligible_owner_id,
                "ATP_PROJECT_E2E_CODE": project_code,
            }
        )
        browser_resolution = _validate_playwright_browser(node, browser_environment)
        playwright = (
            ROOT
            / "node_modules"
            / ".bin"
            / ("playwright.cmd" if sys.platform == "win32" else "playwright")
        )
        if not playwright.is_file():
            raise GateBlocked("Playwright is required for REAL_ACCEPTANCE_GATE")
        playwright_command = [
            str(playwright),
            "test",
            "--config",
            "apps/web/playwright.config.ts",
        ]
        stage = "chromium_test"
        completed = subprocess.run(
            playwright_command,
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
        stage = "execution_binding_fixtures"
        execution_binding_fixture = _prepare_execution_binding_acceptance(
            database, project_code, authorized_username
        )
        runner_work_dir = runtime_directory / "runner-agent"
        AgentCredentialStore(runner_work_dir / "agent-identity.json").save(
            StoredAgentIdentity(
                runner_id=str(execution_binding_fixture["runner_id"]),
                agent_token=str(execution_binding_fixture.pop("runner_agent_token")),
                token_version=1,
            )
        )
        runner_environment = api_environment.copy()
        runner_environment.update(
            {
                "RUNNER_PLATFORM_URL": f"http://127.0.0.1:{api_port}",
                "RUNNER_WORK_DIR": str(runner_work_dir),
                "RUNNER_HEARTBEAT_INTERVAL_SECONDS": "2",
                "RUNNER_DECLARED_CAPABILITIES": json.dumps(
                    [
                        "BROWSER_CHROMIUM",
                        "CAPTURE_SCREENSHOT",
                        "FORMAL_EXECUTION",
                        "INTRANET_ACCESS",
                        "TERMINAL_ADMIN_WEB",
                    ]
                ),
            }
        )
        stage = "runner_agent_startup"
        runner_process, runner_log = _start_process(
            [sys.executable, "-m", "platform_runner.cli"],
            runner_environment,
            runtime_directory / "runner.log",
        )
        log_handles.append(runner_log)
        _wait_for_runner_agent(
            database, str(execution_binding_fixture["runner_id"]), runner_process
        )
        with _connection(database) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE atp_runner_capability SET validation_status='VALID',"
                "updated_at=UTC_TIMESTAMP(6),row_version=row_version+1 "
                "WHERE runner_id=%s AND availability_status='CONFIGURED' "
                "AND lifecycle_status='ACTIVE'",
                (execution_binding_fixture["runner_id"],),
            )
        browser_environment.update(
            {
                "PLAYWRIGHT_TEST_FILE": "execution-binding.spec.ts",
                "ATP_BINDING_E2E_USERNAME": authorized_username,
                "ATP_BINDING_E2E_PASSWORD": authorized_password,
                "ATP_BINDING_E2E_PROJECT_ID": str(execution_binding_fixture["project_id"]),
                "ATP_BINDING_E2E_ENVIRONMENT_ID": str(execution_binding_fixture["environment_id"]),
                "ATP_BINDING_E2E_TERMINAL_ID": str(execution_binding_fixture["terminal_id"]),
                "ATP_BINDING_E2E_TERMINAL_REVISION_ID": str(
                    execution_binding_fixture["terminal_revision_id"]
                ),
                "ATP_BINDING_E2E_ACCOUNT_ID": str(execution_binding_fixture["account_id"]),
                "ATP_BINDING_E2E_CREDENTIAL_REVISION_ID": str(
                    execution_binding_fixture["credential_revision_id"]
                ),
                "ATP_BINDING_E2E_RUNNER_ID": str(execution_binding_fixture["runner_id"]),
                "ATP_BINDING_E2E_POLICY_ID": str(execution_binding_fixture["policy_id"]),
                "ATP_BINDING_E2E_ATTEMPT_IDS": ",".join(
                    str(value) for value in execution_binding_fixture["attempt_ids"][:4]
                ),
                "ATP_BINDING_E2E_RESOURCE_IDENTITY": str(
                    execution_binding_fixture["runner_resource_identity"]
                ),
                "ATP_BINDING_E2E_OWNER_IDENTITY": str(
                    execution_binding_fixture["owner_execution_identity"]
                ),
            }
        )
        stage = "execution_binding_chromium_test"
        binding_completed = subprocess.run(
            playwright_command,
            cwd=ROOT,
            env=browser_environment,
            check=False,
        )
        if binding_completed.returncode != 0:
            browser_exit = binding_completed.returncode
            raise RuntimeError("execution binding browser acceptance command failed")
        stage = "execution_binding_recovery_evidence"
        execution_binding_evidence = _execution_binding_recovery_evidence(
            database,
            api_port,
            authorized_username,
            authorized_password,
            execution_binding_fixture,
        )
        if args.task_id:
            stage = "required_gates"
            required_gates_command = [
                sys.executable,
                "tools/governance/task_governance.py",
                "gate",
                "--root",
                ".",
                "--task-id",
                args.task_id,
                "--timeout",
                "1200",
            ]
            browser_environment["PYTHONIOENCODING"] = "utf-8"
            required_gates_completed = subprocess.run(
                required_gates_command,
                cwd=ROOT,
                env=browser_environment,
                check=False,
            )
            if required_gates_completed.returncode != 0:
                browser_exit = required_gates_completed.returncode
                raise RuntimeError("required gates failed")
        if target is None:
            raise RuntimeError("AI exploration target fixture is unavailable")
        stage = "ai_exploration_fixtures"
        model_config_id = _prepare_ai_exploration_runtime(
            database,
            execution_binding_fixture,
            authorized_username,
            target.url,
            test_account_secret_key_ring,
            provider_secret,
        )
        ai_attempt_id = _create_ai_execution_binding(
            database,
            api_port,
            authorized_username,
            authorized_password,
            execution_binding_fixture,
        )
        browser_environment.update(
            {
                "PLAYWRIGHT_TEST_FILE": "ai-exploration-browser-loop.spec.ts",
                "ATP_AI_EXPLORATION_E2E_USERNAME": authorized_username,
                "ATP_AI_EXPLORATION_E2E_PASSWORD": authorized_password,
                "ATP_AI_EXPLORATION_E2E_PROJECT_ID": str(execution_binding_fixture["project_id"]),
                "ATP_AI_EXPLORATION_E2E_ATTEMPT_ID": ai_attempt_id,
                "ATP_AI_EXPLORATION_E2E_TARGET_URL": target.url,
            }
        )
        stage = "ai_exploration_chromium_test"
        ai_completed = subprocess.run(
            playwright_command,
            cwd=ROOT,
            env=browser_environment,
            check=False,
        )
        browser_exit = ai_completed.returncode
        if browser_exit != 0:
            raise RuntimeError("AI exploration Browser Loop acceptance command failed")
        stage = "ai_exploration_cancellation_probe"
        ai_exploration_cancellation_evidence = _ai_exploration_cancel_probe(
            database,
            api_port,
            authorized_username,
            authorized_password,
            execution_binding_fixture,
            target.url,
        )
        stage = "database_evidence"
        _restore_execution_binding_project(database, execution_binding_fixture)
        database_evidence = _database_evidence(database, project_code, runner_project_id)
        ai_exploration_evidence = _ai_exploration_database_evidence(
            database,
            str(execution_binding_fixture["project_id"]),
            model_config_id,
            provider_secret,
            f"rotated-test-account-{project_code}",
        )
        status = "PASS"
        exit_code = 0
    except (GateBlocked, FlywayBlocked) as exc:
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
        elif stage in {
            "database_evidence",
            "execution_binding_fixtures",
            "execution_binding_recovery_evidence",
            "ai_exploration_cancellation_probe",
        } and isinstance(exc, RuntimeError):
            error_code = "DATABASE_EVIDENCE_INVARIANT_FAILED"
            error_diagnostic = str(exc)
        elif stage in {"ai_exploration_chromium_test", "required_gates"}:
            for handle in log_handles:
                handle.flush()
            error_code = "AI_EXPLORATION_BROWSER_ACCEPTANCE_FAILED"
            error_diagnostic = _safe_startup_diagnostic(
                runtime_directory / "api.log"
            ) or model_gate._safe_exception_diagnostic(runtime_directory / "api.log")
            if execution_binding_fixture:
                with _connection(database) as connection, connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT lifecycle_status,failure_code,current_step_sequence "
                        "FROM atp_ai_exploration_session WHERE project_id=%s "
                        "ORDER BY created_at DESC LIMIT 1",
                        (execution_binding_fixture["project_id"],),
                    )
                    diagnostic_row = cursor.fetchone()
                if diagnostic_row is not None:
                    error_diagnostic = json.dumps(
                        {
                            "session_status": str(diagnostic_row[0]),
                            "failure_code": (
                                None if diagnostic_row[1] is None else str(diagnostic_row[1])
                            ),
                            "current_step_sequence": int(diagnostic_row[2]),
                        },
                        separators=(",", ":"),
                    )
        exit_code = 1
    finally:
        _stop_process(web_process)
        _stop_process(runner_process)
        _stop_process(api_process)
        if target is not None:
            target.stop()
        if gateway is not None:
            gateway.stop()
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
        process is None or process.poll() is not None
        for process in (api_process, runner_process, web_process)
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
                "apps/web/e2e/project-management.spec.ts::project and Test Account browser closure",
                "apps/web/e2e/execution-binding.spec.ts::binding and fenced lease browser closure",
                "apps/web/e2e/ai-exploration-browser-loop.spec.ts::bound Browser Loop closure",
                (
                    "tools/gates/project_acceptance_runtime.py::cancel fencing "
                    "and late response closure"
                ),
            ],
            "browser_exit_code": browser_exit,
            "checks": {
                "database": "PASS" if created else "NOT_RUN",
                "browser_workflow": "PASS" if browser_exit == 0 else "FAIL",
                "database_evidence": "PASS" if database_evidence else "NOT_RUN",
                "audit_unavailable_fail_closed": (
                    "PASS" if audit_unavailable_evidence else "NOT_RUN"
                ),
                "dynamic_owner_revocation": ("PASS" if dynamic_owner_evidence else "NOT_RUN"),
                "execution_binding_fencing": ("PASS" if execution_binding_evidence else "NOT_RUN"),
                "ai_exploration_browser_loop": ("PASS" if ai_exploration_evidence else "NOT_RUN"),
                "ai_exploration_cancellation": (
                    "PASS" if ai_exploration_cancellation_evidence else "NOT_RUN"
                ),
                "cleanup": "PASS" if cleanup_success else "FAIL",
            },
            "database_evidence": database_evidence,
            "audit_unavailable_evidence": audit_unavailable_evidence,
            "dynamic_owner_evidence": dynamic_owner_evidence,
            "execution_binding_evidence": execution_binding_evidence,
            "ai_exploration_evidence": ai_exploration_evidence,
            "ai_exploration_cancellation_evidence": ai_exploration_cancellation_evidence,
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
