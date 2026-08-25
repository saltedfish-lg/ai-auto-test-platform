#!/usr/bin/env python3
"""Run Model Configuration browser acceptance in an isolated MySQL/runtime boundary."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from tools.environment import (  # noqa: E402
    get_env,
    load_project_environment,
    project_environment,
    sanitize_database_error,
)
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

GATE_ID = "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE"
PROVIDER_CODE = "OPENAI"
MODEL_NAME = "browser-runtime-model"


def _isolated_runtime_environment() -> dict[str, str]:
    environment = project_environment(root=ROOT)
    unrelated_e2e_prefixes = (
        "ATP_AUTH_E2E_",
        "ATP_PROJECT_E2E_",
        "ATP_MODEL_E2E_",
    )
    gate_controlled_playwright = {
        "PLAYWRIGHT_BASE_URL",
        "PLAYWRIGHT_TEST_FILE",
        "PLAYWRIGHT_OUTPUT_DIR",
        "PLAYWRIGHT_NO_COPY_PROMPT",
    }
    for name in list(environment):
        if name.startswith(unrelated_e2e_prefixes) or name in gate_controlled_playwright:
            environment.pop(name, None)
    return environment


def _cleanup_step(
    resource: str,
    action: Callable[[], None],
    errors: list[dict[str, str]],
) -> None:
    try:
        action()
    except Exception as exc:
        errors.append({"resource": resource, "error_type": type(exc).__name__})


def _safe_text_diagnostic(text: str) -> str | None:
    sanitized = sanitize_database_error(text)
    sanitized = re.sub(r"[a-z][a-z0-9+.-]*://\S+", "<redacted-url>", sanitized, flags=re.I)
    sanitized = re.sub(
        r"(?i)(password|token|secret|api[_-]?key|key[_-]?material)(\s*[=:]\s*)\S+",
        r"\1\2<redacted>",
        sanitized,
    )
    return sanitized[-1200:] or None


def _safe_log_diagnostic(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[-2000:]
    except OSError:
        return None
    return _safe_text_diagnostic(text)


def _write_model_secret_key_ring(directory: Path) -> Path:
    path = directory / "model-secret-key-ring.json"
    path.write_text(
        json.dumps(
            {
                "active_key_id": "model-browser-active",
                "keys": [
                    {
                        "key_id": "model-browser-active",
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


class _GatewayFixture:
    """Loopback LiteLLM protocol boundary used by the real API adapter.

    The browser, API, encryption store and MySQL path remain real. This fixture only
    replaces the deployment-owned external provider boundary and never records the
    runtime credential it validates.
    """

    def __init__(self, expected_secret: str) -> None:
        self._expected_secret = expected_secret
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                del format, args

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/v1/chat/completions":
                    self.send_error(404)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if size <= 0 or size > 16384:
                        raise ValueError("invalid request size")
                    payload = json.loads(self.rfile.read(size))
                    valid = (
                        payload.get("model") == f"openai/{MODEL_NAME}"
                        and payload.get("api_key") == fixture._expected_secret
                        and payload.get("messages")
                    )
                except (ValueError, json.JSONDecodeError):
                    valid = False
                if not valid:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":{"message":"rejected"}}')
                    return
                body = b'{"id":"runtime-gateway","choices":[{"message":{"content":"OK"}}]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("x-litellm-request-id", "model-browser-runtime")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="model-browser-gateway",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)

    @property
    def stopped(self) -> bool:
        return not self._thread.is_alive()


def _grant_platform_scope(database: str, username: str) -> None:
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT b.binding_id FROM atp_user_role_binding b "
            "JOIN atp_user u ON u.user_id=b.user_id WHERE u.username=%s "
            "AND b.project_id IS NULL",
            (username,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("model browser role binding was not persisted")
        cursor.execute(
            "INSERT INTO atp_data_scope_grant "
            "(grant_id,binding_id,scope_type,scope_id,permission_code,created_at) "
            "VALUES (%s,%s,'PLATFORM_TECHNICAL',NULL,NULL,CURRENT_TIMESTAMP(6))",
            (new_ulid(), str(row[0])),
        )


def _audit_details(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("model activation audit details are unavailable")


def _database_evidence(
    database: str,
    ordinary_code: str,
    super_code: str,
    provider_secret: str,
) -> dict[str, object]:
    evidence: dict[str, object] = {}
    with _connection(database) as connection, connection.cursor() as cursor:
        for label, code in (("ordinary", ordinary_code), ("super_admin", super_code)):
            cursor.execute(
                "SELECT m.model_config_id,m.lifecycle_status,s.encrypted_secret "
                "FROM atp_model_config m JOIN atp_model_config_secret s "
                "ON s.model_config_id=m.model_config_id WHERE m.config_code=%s",
                (code,),
            )
            row = cursor.fetchone()
            if row is None or str(row[1]) != "ACTIVE":
                raise RuntimeError("browser-created model configuration is not ACTIVE")
            ciphertext = bytes(row[2])
            if provider_secret.encode("utf-8") in ciphertext:
                raise RuntimeError("model provider credential was not encrypted")
            cursor.execute(
                "SELECT actor_user_id,details_json FROM atp_model_config_audit "
                "WHERE model_config_id=%s AND action='MODEL_CONFIG_ACTIVATED' "
                "AND result_code='SUCCESS' ORDER BY occurred_at DESC LIMIT 1",
                (str(row[0]),),
            )
            audit = cursor.fetchone()
            if audit is None:
                raise RuntimeError("model activation audit was not persisted")
            actor = str(audit[0])
            details = _audit_details(audit[1])
            if label == "ordinary":
                if details.get("self_approval") is not False:
                    raise RuntimeError("ordinary model review audit lost separation evidence")
                if details.get("submitter_user_id") == details.get("reviewer_user_id"):
                    raise RuntimeError("ordinary model review was not independent")
            else:
                if not (
                    details.get("self_approval") is True
                    and details.get("operator_role") == "SUPER_ADMIN"
                    and details.get("actor_user_id") == actor
                    and details.get("submitter_user_id") == actor
                    and details.get("reviewer_user_id") == actor
                ):
                    raise RuntimeError("SUPER_ADMIN self-approval audit evidence is incomplete")
            cursor.execute(
                "SELECT COUNT(*) FROM atp_model_config_audit "
                "WHERE model_config_id=%s AND action='MODEL_CONFIG_CONNECTION_TESTED' "
                "AND result_code='SUCCESS'",
                (str(row[0]),),
            )
            connection_tests = int(cursor.fetchone()[0])
            if connection_tests < 1:
                raise RuntimeError("model connection test evidence is missing")
            evidence[f"{label}_active"] = True
            evidence[f"{label}_activation_audit"] = True
            evidence[f"{label}_connection_test_count"] = connection_tests
            evidence[f"{label}_secret_encrypted"] = True
        cursor.execute(
            "SELECT COUNT(*) FROM atp_model_capability_default d "
            "JOIN atp_model_config m ON m.model_config_id=d.model_config_id "
            "WHERE d.capability_code='AI_EXPLORATION' AND m.config_code=%s",
            (ordinary_code,),
        )
        if int(cursor.fetchone()[0]) != 1:
            raise RuntimeError("browser model capability default was not persisted")
        evidence["capability_default_persisted"] = True
    return evidence


def main() -> int:
    load_project_environment(root=ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-output", type=Path)
    args = parser.parse_args()
    result = runtime_result_base(
        ROOT,
        gate_id=GATE_ID,
        gate_source=Path(__file__),
        gate_capabilities=[
            "AI_MODEL_CONFIGURATION",
            "SUPER_ADMIN_SELF_APPROVAL",
            "BROWSER_RUNTIME",
            "MYSQL_PERSISTENCE",
            "MODEL_SECRET_ENCRYPTION",
            "LITELLM_PROTOCOL_CONNECTION",
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
    database = _new_database_name("model")
    runtime_directory = RUNTIME_ROOT / f"model-configuration-browser-{secrets.token_hex(6)}"
    runtime_directory.mkdir(parents=True, exist_ok=False)
    api_process: subprocess.Popen[bytes] | None = None
    web_process: subprocess.Popen[bytes] | None = None
    gateway: _GatewayFixture | None = None
    log_handles: list[BinaryIO] = []
    created = False
    removed = False
    runtime_removed = False
    database_ready = False
    browser_exit: int | None = None
    exit_code = 1
    status = "FAIL"
    mysql_version = "UNKNOWN"
    browser_resolution = "NOT_EVALUATED"
    database_evidence: dict[str, object] = {}
    stage = "mysql_connect"
    blocker: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    error_diagnostic: str | None = None
    provider_secret = f"runtime-only-{secrets.token_urlsafe(24)}"
    ordinary_code = f"browser-model-{secrets.token_hex(6)}"
    super_code = f"browser-super-model-{secrets.token_hex(6)}"
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            mysql_version = str(cursor.fetchone()[0])
            if not mysql_version.startswith("8.4."):
                raise GateBlocked(f"MySQL 8.4 is required; detected {mysql_version}")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_0900_ai_ci"
            )
            created = True

        stage = "migrations"
        for migration in _migration_names(authority):
            _execute_script(database, _migration_path(authority, migration))

        stage = "fixtures"
        database_url = _test_database_url(database)
        key_ring = generate_development_key_ring(
            runtime_directory / "keys", kid="model-browser-rs256-v1"
        )
        hmac_key_ring = _write_hmac_key_ring(runtime_directory)
        model_secret_key_ring = _write_model_secret_key_ring(runtime_directory)
        engine = create_database_engine(database_url)
        try:
            factory = create_session_factory(engine)
            passwords = PasswordService()
            manager_username, manager_password = _create_user(
                factory, passwords, lifecycle="ACTIVE", role_code="ROLE-MODEL-ADMIN"
            )
            reviewer_username, reviewer_password = _create_user(
                factory, passwords, lifecycle="ACTIVE", role_code="ROLE-MODEL-REVIEWER"
            )
            super_username, super_password = _create_user(
                factory, passwords, lifecycle="ACTIVE", role_code="ROLE-SUPER-ADMIN"
            )
        finally:
            engine.dispose()
        _grant_platform_scope(database, manager_username)
        _grant_platform_scope(database, reviewer_username)
        database_ready = True

        stage = "gateway_startup"
        gateway = _GatewayFixture(provider_secret)
        gateway.start()

        api_port = _available_loopback_port()
        api_environment = _isolated_runtime_environment()
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
                "ATP_MODEL_SECRET_KEY_RING_FILE": str(model_secret_key_ring),
                "ATP_LITELLM_PROXY_URL": gateway.url,
                "ATP_LITELLM_DYNAMIC_CREDENTIALS_ENABLED": "true",
            }
        )
        api_environment.pop("ATP_LITELLM_PROXY_API_KEY_FILE", None)
        stage = "api_startup"
        api_process, api_log = _start_process(
            [sys.executable, "-m", "platform_api.cli"],
            api_environment,
            runtime_directory / "api.log",
        )
        log_handles.append(api_log)
        _wait_for_port(api_port, api_process, timeout=30)

        node = shutil.which("node")
        if node is None:
            raise GateBlocked("Node.js is required for the Model Configuration browser Gate")
        web_port = _available_loopback_port()
        web_environment = _isolated_runtime_environment()
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
                "PLAYWRIGHT_TEST_FILE": "model-configuration.spec.ts",
                "PLAYWRIGHT_OUTPUT_DIR": str(runtime_directory / "playwright-output"),
                "PLAYWRIGHT_NO_COPY_PROMPT": "1",
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
                "ATP_MODEL_E2E_MANAGER_USERNAME": manager_username,
                "ATP_MODEL_E2E_MANAGER_PASSWORD": manager_password,
                "ATP_MODEL_E2E_REVIEWER_USERNAME": reviewer_username,
                "ATP_MODEL_E2E_REVIEWER_PASSWORD": reviewer_password,
                "ATP_MODEL_E2E_SUPER_ADMIN_USERNAME": super_username,
                "ATP_MODEL_E2E_SUPER_ADMIN_PASSWORD": super_password,
                "ATP_MODEL_E2E_CONFIG_CODE": ordinary_code,
                "ATP_MODEL_E2E_SUPER_CONFIG_CODE": super_code,
                "ATP_MODEL_E2E_PROVIDER": PROVIDER_CODE,
                "ATP_MODEL_E2E_MODEL_NAME": MODEL_NAME,
                "ATP_MODEL_E2E_SECRET": provider_secret,
            }
        )
        browser_resolution = _validate_playwright_browser(node, browser_environment)
        playwright = ROOT / "node_modules" / ".bin" / (
            "playwright.cmd" if sys.platform == "win32" else "playwright"
        )
        if not playwright.is_file():
            raise GateBlocked("Playwright is required for the Model Configuration browser Gate")
        stage = "chromium_test"
        completed = subprocess.run(
            [str(playwright), "test", "--config", "apps/web/playwright.config.ts"],
            cwd=ROOT,
            env=browser_environment,
            check=False,
        )
        browser_exit = completed.returncode
        if browser_exit != 0:
            raise RuntimeError("Model Configuration browser acceptance command failed")

        stage = "database_evidence"
        database_evidence = _database_evidence(
            database, ordinary_code, super_code, provider_secret
        )
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
            for handle in log_handles:
                handle.flush()
            if api_process is not None and api_process.poll() is None:
                error_code = "LOOPBACK_CONNECTIVITY_UNAVAILABLE"
                error_diagnostic = (
                    "The API process remained active, but the host could not connect "
                    "to its bound loopback port."
                )
                status = "BLOCKED"
                blocker = "Windows loopback connectivity is unavailable to the Gate process"
                exit_code = 2
            else:
                error_code = _startup_error_code(runtime_directory / "api.log")
                error_diagnostic = _safe_startup_diagnostic(
                    runtime_directory / "api.log"
                ) or _safe_log_diagnostic(runtime_directory / "api.log")
        elif stage == "web_startup":
            for handle in log_handles:
                handle.flush()
            error_code = _startup_error_code(runtime_directory / "web.log")
            error_diagnostic = _safe_startup_diagnostic(
                runtime_directory / "web.log"
            ) or _safe_log_diagnostic(runtime_directory / "web.log")
        if status != "BLOCKED":
            exit_code = 1
    finally:
        cleanup_errors: list[dict[str, str]] = []
        _cleanup_step("web_process", lambda: _stop_process(web_process), cleanup_errors)
        _cleanup_step("api_process", lambda: _stop_process(api_process), cleanup_errors)
        for index, handle in enumerate(log_handles):
            _cleanup_step(f"log_handle_{index}", handle.close, cleanup_errors)
        if gateway is not None:
            _cleanup_step("gateway_fixture", gateway.stop, cleanup_errors)
        if created:
            def remove_database() -> None:
                nonlocal removed
                _drop_isolated_database(database)
                removed = True

            _cleanup_step("temporary_database", remove_database, cleanup_errors)
        resolved_runtime = runtime_directory.resolve()
        if (
            resolved_runtime.parent == RUNTIME_ROOT.resolve()
            and resolved_runtime.name.startswith("model-configuration-browser-")
            and resolved_runtime.exists()
        ):
            _cleanup_step(
                "runtime_directory",
                lambda: shutil.rmtree(resolved_runtime),
                cleanup_errors,
            )
        runtime_removed = not resolved_runtime.exists()

    processes_terminated = all(
        process is None or process.poll() is not None
        for process in (api_process, web_process)
    )
    gateway_stopped = gateway is None or gateway.stopped
    cleanup_success = (
        not cleanup_errors
        and (removed if created else True)
        and runtime_removed
        and processes_terminated
        and gateway_stopped
    )
    if not cleanup_success:
        status = "FAIL"
        exit_code = 1
        blocker = "isolated Model Configuration runtime cleanup failed"
        error_code = "RUNTIME_CLEANUP_FAILED"
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
                "apps/web/e2e/model-configuration.spec.ts::AI model configuration browser closure",
                "apps/web/e2e/model-configuration.spec.ts::SUPER_ADMIN model configuration self-approval",
            ],
            "gateway_boundary": "LITELLM_CHAT_COMPLETIONS_COMPATIBLE_LOOPBACK",
            "browser_exit_code": browser_exit,
            "checks": {
                "database": "PASS" if database_ready else "NOT_RUN",
                "browser_workflow": (
                    "PASS"
                    if browser_exit == 0
                    else ("NOT_RUN" if browser_exit is None else "FAIL")
                ),
                "database_evidence": "PASS" if database_evidence else "NOT_RUN",
                "secret_encryption": (
                    "PASS"
                    if database_evidence.get("ordinary_secret_encrypted")
                    and database_evidence.get("super_admin_secret_encrypted")
                    else "NOT_RUN"
                ),
                "super_admin_self_approval_audit": (
                    "PASS"
                    if database_evidence.get("super_admin_activation_audit")
                    else "NOT_RUN"
                ),
                "cleanup": "PASS" if cleanup_success else "FAIL",
            },
            "database_evidence": database_evidence,
            "cleanup_status": {
                "temporary_database_removed": removed if created else True,
                "runtime_directory_removed": runtime_removed,
                "processes_terminated": processes_terminated,
                "gateway_fixture_stopped": gateway_stopped,
                "runtime_secrets_removed": runtime_removed,
                "success": cleanup_success,
                "errors": cleanup_errors,
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
