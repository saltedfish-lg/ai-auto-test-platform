#!/usr/bin/env python3
"""Run the authentication MySQL gate with dynamically discovered current migrations."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import URL, make_url

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))
from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402
ROOT = ensure_repo_root_on_path(__file__)
from tools.current_facts import discover_migrations  # noqa: E402
from tools.environment import get_env, load_project_environment, project_environment  # noqa: E402
from tools.governance.migration_registry import migration_for_capability  # noqa: E402
from tools.governance.runtime_gate_result import finalize_runtime_result, runtime_result_base  # noqa: E402

AUTHORITY_ROOT = ROOT / "docs" / "authority"
DATABASE_PREFIX = "ai_auto_test_platform_gate_auth_"
ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"
DATABASE_URL_ENV = "ATP_DATABASE_URL"
GATE_STATUS_NAME = "AUTH_MYSQL_RUNTIME_GATE"
SUPPORTED_MYSQL_SERIES = "8.4"


class GateBlocked(RuntimeError):
    """Represent a safe, non-secret environment blocker for a runtime gate."""


def _pymysql():
    try:
        import pymysql  # type: ignore[import-untyped]
        from pymysql.constants import CLIENT  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise GateBlocked("PYMYSQL_NOT_INSTALLED") from exc
    return pymysql, CLIENT


def _resolve_authority() -> Path:
    if not AUTHORITY_ROOT.is_dir():
        raise RuntimeError("docs/authority is required")
    return AUTHORITY_ROOT


def _migrations(authority: Path) -> list[dict[str, Any]]:
    return discover_migrations(authority)


def _migration_names(authority: Path) -> tuple[str, ...]:
    """Compatibility helper: values are discovered, never coded as a permanent chain."""
    return tuple(item["name"] for item in _migrations(authority))


def _admin_url() -> URL:
    raw_url = get_env(ADMIN_URL_ENV, root=ROOT)
    if not raw_url:
        raise GateBlocked(f"{ADMIN_URL_ENV} is required")
    try:
        url = make_url(raw_url)
    except Exception:
        raise GateBlocked(f"{ADMIN_URL_ENV} is not a valid SQLAlchemy URL") from None
    if url.drivername != "mysql+pymysql" or url.host is None or url.username is None:
        raise GateBlocked(f"{ADMIN_URL_ENV} must use mysql+pymysql with host and username")
    return url


def _connection(database: str | None = None):
    pymysql, client = _pymysql()
    url = _admin_url()
    try:
        return pymysql.connect(
            host=url.host,
            port=url.port or 3306,
            user=url.username,
            password=url.password or "",
            database=database,
            charset="utf8mb4",
            autocommit=True,
            client_flag=client.MULTI_STATEMENTS,
        )
    except pymysql.MySQLError:
        raise GateBlocked(f"cannot connect to MySQL at {url.host}:{url.port or 3306}") from None


def _migration_path(authority: Path, name: str) -> Path:
    matches = [item["path"] for item in _migrations(authority) if item["name"] == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one current-authority migration named {name}, found {len(matches)}")
    return matches[0]


def _execute_script(database: str, path: Path) -> None:
    script = path.read_text(encoding="utf-8")
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(script)
        while cursor.nextset():
            pass


def _seed_legacy_idempotency_record(database: str) -> None:
    """Materialize the canonical pre-boundary row used by the legacy-upgrade probe."""
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO atp_idempotency_record "
            "(idempotency_key, operation_id, request_hash, response_status, response_json, expires_at) "
            "VALUES (%s, %s, %s, 200, NULL, DATE_ADD(NOW(6), INTERVAL 1 DAY))",
            ("AUTH_GATE_LEGACY_V1", "legacy_gate", "0" * 64),
        )


def _test_database_url(database: str) -> str:
    return _admin_url().set(database=database).render_as_string(hide_password=False)


def _new_database_name(scope: str = "mysql") -> str:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4)
    database = f"{DATABASE_PREFIX}{scope}_{suffix}"
    if len(database) > 64 or not database.startswith(DATABASE_PREFIX):
        raise RuntimeError("unsafe authentication Gate database name")
    return database


def _drop_isolated_database(database: str) -> None:
    if not database.startswith(DATABASE_PREFIX):
        raise RuntimeError("refusing to remove a database outside the authentication Gate namespace")
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")


def _write_result(payload: dict[str, Any], output: Path | None) -> None:
    finalize_runtime_result(payload, root=ROOT)
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(raw, encoding="utf-8")
    print(raw)


def main() -> int:
    load_project_environment(root=ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-output", type=Path)
    args = parser.parse_args()
    authority = _resolve_authority()
    migrations = _migrations(authority)
    migration_names = [item["name"] for item in migrations]
    base = runtime_result_base(
        ROOT,
        gate_id=GATE_STATUS_NAME,
        gate_source=Path(__file__),
        gate_capabilities=["MYSQL_RUNTIME", "AUTHENTICATION_RUNTIME", "ISOLATED_DATABASE_CLEANUP"],
    )
    base.update({
        "migration_identity": {"files": migration_names},
        "runtime_versions": {"mysql": "UNKNOWN"},
        "checks": {"migration_apply": "NOT_RUN", "authentication_tests": "NOT_RUN", "cleanup": "NOT_RUN"},
        "cleanup_status": {"temporary_database_removed": False, "success": False},
    })

    if not get_env(ADMIN_URL_ENV, root=ROOT):
        base.update({
            "result": "BLOCKED",
            "exit_code": 2,
            "blocker": f"{ADMIN_URL_ENV} is required",
            "checks": {"migration_apply": "NOT_RUN", "authentication_tests": "NOT_RUN", "cleanup": "NOT_APPLICABLE"},
            "cleanup_status": {"temporary_database_removed": True, "success": True},
        })
        _write_result(base, args.result_output)
        return 2

    database = _new_database_name()
    version = "UNKNOWN"
    test_exit: int | None = None
    created = False
    removed = False
    result = "FAIL"
    blocker: str | None = None
    error_type: str | None = None
    exit_code = 1
    try:
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not version.startswith(SUPPORTED_MYSQL_SERIES + ".") and version != SUPPORTED_MYSQL_SERIES:
                raise GateBlocked(f"MySQL {SUPPORTED_MYSQL_SERIES}.x is required; detected {version}")
            cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            created = True
        legacy_boundary = migration_for_capability(migrations, authority, "LEGACY_UPGRADE_FIXTURE_BOUNDARY")
        for item in migrations:
            if item["name"] == legacy_boundary["name"]:
                _seed_legacy_idempotency_record(database)
            _execute_script(database, item["path"])
        base["checks"]["migration_apply"] = "PASS"
        environment = project_environment(root=ROOT)
        environment[DATABASE_URL_ENV] = _test_database_url(database)
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/integration/test_p1_auth_mysql.py", "-q"],
            cwd=ROOT, env=environment, check=False,
        )
        test_exit = completed.returncode
        base["checks"]["authentication_tests"] = "PASS" if test_exit == 0 else "FAIL"
        result = "PASS" if test_exit == 0 else "FAIL"
        exit_code = test_exit
    except GateBlocked as exc:
        result = "BLOCKED"
        blocker = str(exc)
        exit_code = 2
    except Exception as exc:
        result = "FAIL"
        error_type = type(exc).__name__
        exit_code = 1
    finally:
        if created:
            try:
                _drop_isolated_database(database)
                removed = True
            except Exception:
                result = "FAIL"
                blocker = "isolated database cleanup failed"
                exit_code = 1
        base["checks"]["cleanup"] = "PASS" if removed else ("NOT_APPLICABLE" if not created else "FAIL")
        base["cleanup_status"] = {
            "temporary_database_removed": removed,
            "success": removed if created else True,
        }
        if created and not removed:
            result = "FAIL"

    base.update({
        "result": result,
        "runtime_versions": {"mysql": version},
        "test_runner": "pytest",
        "test_nodeids": ["tests/integration/test_p1_auth_mysql.py"],
        "pytest_exit_code": test_exit,
        "exit_code": exit_code,
    })
    if blocker is not None:
        base["blocker"] = blocker
    if error_type is not None:
        base["error_type"] = error_type
    _write_result(base, args.result_output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
