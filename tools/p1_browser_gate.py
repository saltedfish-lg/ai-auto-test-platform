#!/usr/bin/env python3
"""Run the current living-authority P1 auth UI gate against FastAPI, Chromium and MySQL."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from p1_auth_mysql_gate import (
    ADMIN_URL_ENV,
    DATABASE_PREFIX,
    _connection,
    _execute_script,
    _migration_names,
    _migration_path,
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

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / ".runtime"


def _password(label: str) -> str:
    return f"{label}-{secrets.token_hex(12)}-7"


def _port_open(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, process: subprocess.Popen[bytes], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"local process for port {port} exited during startup")
        if _port_open(port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"local process did not listen on port {port} within {timeout} seconds")


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
    command: list[str], environment: dict[str, str], log_path: Path
) -> tuple[subprocess.Popen[bytes], BinaryIO]:
    log_handle = log_path.open("wb")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
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


def _browser_executable() -> Path | None:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        cached = sorted(
            Path(local_app_data).glob("ms-playwright/chromium-*/chrome-win64/chrome.exe"),
            reverse=True,
        )
        if cached:
            return cached[0]
    for candidate in (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    authority = _resolve_authority()
    migrations = _migration_names(authority)
    if ADMIN_URL_ENV not in os.environ:
        raise RuntimeError(f"{ADMIN_URL_ENV} is required")
    if _port_open(8000) or _port_open(5173):
        raise RuntimeError("ports 8000 and 5173 must be free before the isolated browser gate")

    database = DATABASE_PREFIX + "browser_" + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    runtime_directory = RUNTIME_ROOT / f"p1-browser-{secrets.token_hex(6)}"
    runtime_directory.mkdir(parents=True, exist_ok=False)
    api_process: subprocess.Popen[bytes] | None = None
    web_process: subprocess.Popen[bytes] | None = None
    log_handles: list[BinaryIO] = []
    created = False
    browser_exit = 1
    version = "UNKNOWN"
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not version.startswith("8.4."):
                raise RuntimeError(f"MySQL 8.4 is required; detected {version}")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            created = True
        for migration in migrations:
            _execute_script(database, _migration_path(authority, migration))

        database_url = _test_database_url(database)
        key_ring = generate_development_key_ring(
            runtime_directory / "keys", kid="p1-browser-rs256-v1"
        )
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

        api_environment = os.environ.copy()
        api_environment.pop(ADMIN_URL_ENV, None)
        api_environment.update(
            {
                "PLATFORM_ENVIRONMENT": "test",
                "PLATFORM_DATABASE_URL": database_url,
                "API_HOST": "127.0.0.1",
                "API_PORT": "8000",
                "ATP_JWT_KEY_RING_FILE": str(key_ring.manifest_file),
            }
        )
        api_process, api_log = _start_process(
            [sys.executable, "-m", "platform_api.cli"],
            api_environment,
            runtime_directory / "api.log",
        )
        log_handles.append(api_log)
        _wait_for_port(8000, api_process)

        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Node.js is required for the P1 browser gate")
        web_environment = os.environ.copy()
        web_environment.pop(ADMIN_URL_ENV, None)
        web_process, web_log = _start_process(
            [
                node,
                str(ROOT / "node_modules" / "vite" / "bin" / "vite.js"),
                str(ROOT / "apps" / "web"),
                "--host",
                "127.0.0.1",
            ],
            web_environment,
            runtime_directory / "web.log",
        )
        log_handles.append(web_log)
        _wait_for_port(5173, web_process)

        browser_environment = web_environment.copy()
        browser_environment.update(
            {
                "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:5173",
                "P1_E2E_ADMIN_INITIAL_PASSWORD": initial_password,
                "P1_E2E_ADMIN_CHANGED_PASSWORD": changed_password,
                "P1_E2E_NORMAL_USERNAME": normal_username,
                "P1_E2E_NORMAL_PASSWORD": normal_password,
                "P1_E2E_DISABLED_USERNAME": disabled_username,
                "P1_E2E_DISABLED_PASSWORD": disabled_password,
                "PLAYWRIGHT_NO_COPY_PROMPT": "1",
                "PLAYWRIGHT_OUTPUT_DIR": str(runtime_directory / "playwright-output"),
            }
        )
        browser_executable = _browser_executable()
        if browser_executable is not None:
            browser_environment["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = str(browser_executable)
        playwright = (
            ROOT
            / "node_modules"
            / ".bin"
            / ("playwright.cmd" if sys.platform == "win32" else "playwright")
        )
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
        return browser_exit
    finally:
        _stop_process(web_process)
        _stop_process(api_process)
        for handle in log_handles:
            handle.close()
        if created and database.startswith(DATABASE_PREFIX + "browser_"):
            with _connection() as connection, connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        resolved_runtime = runtime_directory.resolve()
        if (
            resolved_runtime.parent == RUNTIME_ROOT.resolve()
            and resolved_runtime.name.startswith("p1-browser-")
            and resolved_runtime.exists()
        ):
            shutil.rmtree(resolved_runtime)
        print(
            json.dumps(
                {
                    "mysql_version": version,
                    "browser": "chromium",
                    "browser_exit_code": browser_exit,
                    "isolated_database_removed": created,
                    "runtime_secrets_removed": not resolved_runtime.exists(),
                    "screenshot": "test-results/p1-auth-workspace.png",
                    "gate": "PASS" if browser_exit == 0 else "FAIL",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
