#!/usr/bin/env python3
"""Run the authentication UI Gate against FastAPI, real Chromium, and isolated MySQL."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import BinaryIO

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))
from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402
ROOT = ensure_repo_root_on_path(__file__)
API_SRC = ROOT / "services" / "api" / "src"
OBSERVABILITY_SRC = ROOT / "packages" / "observability" / "src"
COMMON_SRC = ROOT / "packages" / "platform-common" / "src"
for import_root in (API_SRC, OBSERVABILITY_SRC, COMMON_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))
from tools.environment import get_env, load_project_environment, project_environment  # noqa: E402
from tools.governance.runtime_gate_result import finalize_runtime_result, runtime_result_base  # noqa: E402

from tools.gates.auth_mysql_gate import (
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
from platform_api.bootstrap import AdminBootstrapService
from platform_api.database import create_database_engine, create_session_factory
from platform_api.keygen import generate_development_key_ring
from platform_api.models import PlatformUser, PlatformUserCredential, Role, UserRoleBinding
from platform_api.security import PasswordService, new_ulid, utc_now
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

RUNTIME_ROOT = ROOT / ".runtime"
GATE_STATUS_NAME = "AUTH_BROWSER_RUNTIME_GATE"


def _gate_source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _password(label: str) -> str:
    return f"{label}-{secrets.token_hex(12)}-7"


def _write_hmac_key_ring(directory: Path) -> Path:
    path = directory / "auth-hmac-key-ring.json"
    path.write_text(
        json.dumps(
            {
                "ring_version": "auth-browser-v1",
                "active_key_id": "active",
                "keys": [
                    {
                        "key_id": "active",
                        "key_material": base64.urlsafe_b64encode(secrets.token_bytes(32))
                        .rstrip(b"=")
                        .decode("ascii"),
                        "activated_at": "2025-01-01T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _port_open(port: int) -> bool:
    try:
        with closing(socket.create_connection(("127.0.0.1", port), timeout=0.2)):
            return True
    except OSError:
        return False


def _available_loopback_port() -> int:
    """Ask the OS for an unused loopback port; no stage or current-port assumption is encoded."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen[bytes], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"local process for port {port} exited during startup")
        if _port_open(port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"local process did not listen on port {port} within {timeout} seconds")


def _wait_for_vite(
    port: int,
    process: subprocess.Popen[bytes],
    log_path: Path,
    timeout: float = 30.0,
) -> None:
    """Readiness is network based; logs are diagnostic only."""
    _wait_for_port(port, process, timeout)


def _create_user(
    factory: sessionmaker[Session],
    passwords: PasswordService,
    *,
    lifecycle: str,
    role_code: str | None,
) -> tuple[str, str]:
    now = utc_now()
    user_id = new_ulid()
    credential_id = new_ulid()
    username = f"browser-{lifecycle.lower()}-{new_ulid().lower()}"
    password = _password(lifecycle.title())
    with factory.begin() as db:
        role = (
            None
            if role_code is None
            else db.scalar(select(Role).where(Role.role_code == role_code))
        )
        if role_code is not None and role is None:
            raise RuntimeError(f"frozen role seed is missing: {role_code}")
        db.add_all(
            [
                PlatformUser(
                    user_id=user_id,
                    username=username,
                    role_binding_id=None,
                    lifecycle_status=lifecycle,
                    display_name=f"Browser {lifecycle.title()} User",
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
            ]
        )
        if role is not None:
            db.add(
                UserRoleBinding(
                    binding_id=new_ulid(),
                    user_id=user_id,
                    role_id=role.role_id,
                    project_id=None,
                    valid_from=now,
                    valid_to=None,
                    row_version=0,
                )
            )
    return username, password


def _start_process(
    command: list[str],
    environment: dict[str, str],
    log_path: Path,
    *,
    keep_stdin_open: bool = False,
) -> tuple[subprocess.Popen[bytes], BinaryIO]:
    log_handle = log_path.open("wb")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE if keep_stdin_open else subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )
    return process, log_handle


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _startup_error_code(log_path: Path) -> str:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")[-8192:]
    except OSError:
        return "PROCESS_EXITED_BEFORE_READY"
    known_failures = (
        ("spawn EPERM", "CHILD_PROCESS_SPAWN_DENIED"),
        ("failed to load config", "VITE_CONFIG_LOAD_FAILED"),
        ("is already in use", "PORT_ALREADY_IN_USE"),
        ("EADDRINUSE", "PORT_ALREADY_IN_USE"),
        ("Cannot find module", "NODE_MODULE_MISSING"),
        ("ValidationError", "API_CONFIGURATION_INVALID"),
        ("authentication HMAC", "API_HMAC_KEY_INVALID"),
        ("error when starting dev server", "VITE_START_FAILED"),
        ("ready in", "PORT_PROBE_FAILED"),
        ("Local:", "PORT_PROBE_FAILED"),
    )
    return next(
        (code for marker, code in known_failures if marker in text), "PROCESS_EXITED_BEFORE_READY"
    )


def _safe_startup_diagnostic(log_path: Path) -> str | None:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if "Error:" not in line and "error when starting" not in line.lower():
            continue
        sanitized = re.sub(r"[a-z][a-z0-9+.-]*://\S+", "<redacted-url>", line, flags=re.I)
        sanitized = re.sub(
            r"(?i)(password|token|secret|key(?:_material)?)(\s*[=:]\s*)\S+",
            r"\1\2<redacted>",
            sanitized,
        )
        return sanitized[:300]
    return None


def _validate_playwright_browser(node: str, environment: dict[str, str]) -> str:
    """Require the Chromium revision matched to this project's @playwright/test.

    An explicit PLAYWRIGHT_CHROMIUM_EXECUTABLE remains an opt-in override. Otherwise the Gate
    asks the current project dependency for chromium.executablePath() and only checks that exact
    file exists; Playwright itself still launches the browser without an executable override.
    This prevents a different Python/Node Playwright installation's cached revision from being
    silently selected just because it sorts later under %LOCALAPPDATA%/ms-playwright.
    """
    override = environment.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise GateBlocked("PLAYWRIGHT_CHROMIUM_EXECUTABLE does not exist")
        return "EXPLICIT_OVERRIDE"

    probe = subprocess.run(
        [
            node,
            "-e",
            "const { chromium } = require('@playwright/test'); process.stdout.write(chromium.executablePath());",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        raise GateBlocked("CURRENT_PLAYWRIGHT_BROWSER_RESOLUTION_FAILED")
    value = probe.stdout.strip()
    if not value or not Path(value).is_file():
        raise GateBlocked(
            "CURRENT_PLAYWRIGHT_BROWSER_NOT_INSTALLED; run `npx playwright install chromium` in this project"
        )
    return "PROJECT_PLAYWRIGHT_MATCHED"


def main() -> int:
    load_project_environment(root=ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-output", type=Path)
    args = parser.parse_args()
    authority = _resolve_authority()
    migrations = _migration_names(authority)
    result_payload = runtime_result_base(
        ROOT,
        gate_id=GATE_STATUS_NAME,
        gate_source=Path(__file__),
        gate_capabilities=["BROWSER_RUNTIME", "AUTHENTICATION_RUNTIME", "PLAYWRIGHT_PROJECT_BROWSER", "ISOLATED_RUNTIME_CLEANUP"],
    )

    def emit() -> None:
        finalize_runtime_result(result_payload, root=ROOT)
        raw = json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n"
        if args.result_output:
            args.result_output.parent.mkdir(parents=True, exist_ok=True)
            args.result_output.write_text(raw, encoding="utf-8")
        print(raw)

    if not get_env(ADMIN_URL_ENV, root=ROOT):
        result_payload.update({
            "result": "BLOCKED",
            "exit_code": 2,
            "blocker": f"{ADMIN_URL_ENV} is required",
            "runtime_versions": {"mysql": "UNKNOWN", "browser": "UNKNOWN"},
            "checks": {"database": "NOT_RUN", "api_readiness": "NOT_RUN", "web_readiness": "NOT_RUN", "browser_test": "NOT_RUN", "cleanup": "NOT_RUN"},
            "cleanup_status": {"success": True, "temporary_database_removed": True, "runtime_directory_removed": True, "processes_terminated": True},
        })
        emit()
        return 2

    database = _new_database_name("browser")
    runtime_directory = RUNTIME_ROOT / f"auth-browser-{secrets.token_hex(6)}"
    runtime_directory.mkdir(parents=True, exist_ok=False)
    api_process: subprocess.Popen[bytes] | None = None
    web_process: subprocess.Popen[bytes] | None = None
    log_handles: list[BinaryIO] = []
    created = False
    removed = False
    browser_exit = 1
    version = "UNKNOWN"
    status = "FAIL"
    blocker: str | None = None
    error_type: str | None = None
    error_stage: str | None = None
    error_code: str | None = None
    error_diagnostic: str | None = None
    api_port: int | None = None
    web_port: int | None = None
    browser_resolution = "NOT_EVALUATED"
    runtime_removed = False
    exit_code = 1
    stage = "mysql_connect"
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not version.startswith("8.4."):
                raise GateBlocked(f"MySQL 8.4 is required; detected {version}")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            created = True
        stage = "migrations"
        for migration in migrations:
            _execute_script(database, _migration_path(authority, migration))

        stage = "fixtures"
        database_url = _test_database_url(database)
        key_ring = generate_development_key_ring(
            runtime_directory / "keys", kid="auth-browser-rs256-v1"
        )
        hmac_key_ring_file = _write_hmac_key_ring(runtime_directory)
        engine = create_database_engine(database_url)
        factory = create_session_factory(engine)
        passwords = PasswordService()
        initial_password = _password("Initial")
        changed_password = _password("Changed")
        AdminBootstrapService(factory, passwords).bootstrap(
            initial_password, f"browser-{new_ulid()}"
        )
        normal_username, normal_password = _create_user(
            factory,
            passwords,
            lifecycle="ACTIVE",
            role_code="ROLE-REPORT-VIEWER",
        )
        disabled_username, disabled_password = _create_user(
            factory,
            passwords,
            lifecycle="DISABLED",
            role_code=None,
        )
        engine.dispose()

        api_port = _available_loopback_port()
        api_environment = project_environment(root=ROOT)
        api_environment.pop(ADMIN_URL_ENV, None)
        api_environment.update(
            {
                "PLATFORM_ENVIRONMENT": "test",
                DATABASE_URL_ENV: database_url,
                "API_HOST": "127.0.0.1",
                "API_PORT": str(api_port),
                "ATP_JWT_KEY_RING_FILE": str(key_ring.manifest_file),
                "ATP_AUTH_HMAC_MASTER_KEY_FILE": str(hmac_key_ring_file),
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
            raise GateBlocked("Node.js is required for the authentication browser Gate")
        stage = "web_startup"
        web_port = _available_loopback_port()
        web_environment = project_environment(root=ROOT)
        # The frontend process never needs database credentials. Keep project .env
        # loading centralized without propagating DB secrets to an unrelated child.
        web_environment.pop(ADMIN_URL_ENV, None)
        web_environment.pop(DATABASE_URL_ENV, None)
        web_environment["ATP_VITE_PROXY_TARGET"] = f"http://127.0.0.1:{api_port}"
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
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
                "ATP_AUTH_E2E_ADMIN_INITIAL_PASSWORD": initial_password,
                "ATP_AUTH_E2E_ADMIN_CHANGED_PASSWORD": changed_password,
                "ATP_AUTH_E2E_NORMAL_USERNAME": normal_username,
                "ATP_AUTH_E2E_NORMAL_PASSWORD": normal_password,
                "ATP_AUTH_E2E_DISABLED_USERNAME": disabled_username,
                "ATP_AUTH_E2E_DISABLED_PASSWORD": disabled_password,
                "PLAYWRIGHT_NO_COPY_PROMPT": "1",
                "PLAYWRIGHT_OUTPUT_DIR": str(runtime_directory / "playwright-output"),
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
            raise GateBlocked("Playwright is required for the authentication browser Gate")
        stage = "chromium_test"
        completed = subprocess.run(
            [
                str(playwright),
                "test",
                "--config",
                "apps/web/playwright.config.ts",
            ],
            cwd=ROOT,
            env=browser_environment,
            check=False,
        )
        browser_exit = completed.returncode
        status = "PASS" if browser_exit == 0 else "FAIL"
        exit_code = browser_exit
    except GateBlocked as exc:
        status = "BLOCKED"
        blocker = str(exc)
        exit_code = 2
    except Exception as exc:
        status = "FAIL"
        error_type = type(exc).__name__
        error_stage = stage
        if stage == "api_startup":
            error_code = _startup_error_code(runtime_directory / "api.log")
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
                blocker = f"failed to remove isolated database {database}"
                exit_code = 1
        resolved_runtime = runtime_directory.resolve()
        if (
            resolved_runtime.parent == RUNTIME_ROOT.resolve()
            and resolved_runtime.name.startswith("auth-browser-")
            and resolved_runtime.exists()
        ):
            try:
                shutil.rmtree(resolved_runtime)
            except OSError:
                status = "FAIL"
                blocker = f"failed to remove runtime directory {resolved_runtime.name}"
                exit_code = 1
        runtime_removed = not resolved_runtime.exists()

    process_cleanup_ok = all(proc is None or proc.poll() is not None for proc in (api_process, web_process))
    cleanup_success = (removed if created else True) and runtime_removed and process_cleanup_ok
    if not cleanup_success:
        status = "FAIL"
        exit_code = 1
    result_payload.update({
        "result": status,
        "runtime_versions": {"mysql": version, "browser": "chromium", "browser_resolution": browser_resolution},
        "runtime_allocation": {"api_port": api_port, "web_port": web_port},
        "test_runner": "playwright",
        "test_cases": ["apps/web/playwright.config.ts"],
        "checks": {
            "database": "PASS" if created else "NOT_RUN",
            "api_readiness": "PASS" if api_port is not None and error_stage not in {"api_startup"} else "FAIL",
            "web_readiness": "PASS" if web_port is not None and error_stage not in {"web_startup"} else "FAIL",
            "browser_test": "PASS" if browser_exit == 0 else ("NOT_RUN" if stage != "chromium_test" else "FAIL"),
            "cleanup": "PASS" if cleanup_success else "FAIL",
        },
        "cleanup_status": {
            "temporary_database_removed": removed if created else True,
            "runtime_directory_removed": runtime_removed,
            "processes_terminated": process_cleanup_ok,
            "success": cleanup_success,
            "transient_artifacts_persisted": not runtime_removed,
        },
        "browser_exit_code": browser_exit,
        "exit_code": exit_code,
    })
    if blocker is not None:
        result_payload["blocker"] = blocker
    if error_type is not None:
        result_payload["error_type"] = error_type
    if error_stage is not None:
        result_payload["error_stage"] = error_stage
    if error_code is not None:
        result_payload["error_code"] = error_code
    if error_diagnostic is not None:
        result_payload["error_diagnostic"] = error_diagnostic
    emit()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
