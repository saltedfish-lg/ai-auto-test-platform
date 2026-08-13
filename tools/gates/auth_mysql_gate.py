#!/usr/bin/env python3
"""Run the current authentication gate in an isolated MySQL 8.4 database."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pymysql  # type: ignore[import-untyped]
from pymysql.constants import CLIENT  # type: ignore[import-untyped]
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = ROOT / "docs" / "authority"
DATABASE_PREFIX = "ai_auto_test_platform_gate_auth_"
ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"
DATABASE_URL_ENV = "ATP_DATABASE_URL"
GATE_STATUS_NAME = "AUTH_MYSQL_RUNTIME_GATE"
SUPPORTED_MYSQL_PREFIX = "8.4."
MIGRATION_CANDIDATES = (
    "V3__platform_contract_rebuild.sql",
    "V4__rbac_seed_data.sql",
    "V5__platform_authentication_contract.sql",
    "V6__p1_auth_governance_closure.sql",
    "V7__p1_remaining_authentication_closure.sql",
)


class GateBlocked(RuntimeError):
    """Represent a safe, non-secret environment blocker for a runtime Gate."""


def _resolve_authority() -> Path:
    if not AUTHORITY_ROOT.is_dir():
        raise RuntimeError("docs/authority is required")
    return AUTHORITY_ROOT


def _migration_names(authority: Path) -> tuple[str, ...]:
    migrations = tuple(
        name for name in MIGRATION_CANDIDATES if len(list(authority.rglob(name))) == 1
    )
    if migrations != MIGRATION_CANDIDATES:
        raise RuntimeError(
            "current authority must contain the V3/V4/V5/V6/V7 migration chain exactly once"
        )
    return migrations


def _admin_url() -> URL:
    raw_url = os.getenv(ADMIN_URL_ENV)
    if not raw_url:
        raise GateBlocked(f"{ADMIN_URL_ENV} is required")
    try:
        url = make_url(raw_url)
    except Exception:
        raise GateBlocked(f"{ADMIN_URL_ENV} is not a valid SQLAlchemy URL") from None
    if url.drivername != "mysql+pymysql" or url.host is None or url.username is None:
        raise GateBlocked(f"{ADMIN_URL_ENV} must use mysql+pymysql with host and username")
    return url


def _connection(database: str | None = None) -> pymysql.Connection:
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
            client_flag=CLIENT.MULTI_STATEMENTS,
        )
    except pymysql.MySQLError:
        raise GateBlocked(f"cannot connect to MySQL at {url.host}:{url.port or 3306}") from None


def _migration_path(authority: Path, name: str) -> Path:
    matches = list(authority.rglob(name))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one current-authority migration named {name}, found {len(matches)}"
        )
    return matches[0]


def _execute_script(database: str, path: Path) -> None:
    script = path.read_text(encoding="utf-8")
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(script)
        while cursor.nextset():
            pass


def _seed_v6_legacy_idempotency_record(database: str) -> None:
    """Materialize a pre-V7 row so the gate proves additive legacy upgrade semantics."""
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO atp_idempotency_record "
            "(idempotency_key, operation_id, request_hash, response_status, "
            "response_json, expires_at) "
            "VALUES (%s, %s, %s, 200, NULL, DATE_ADD(NOW(6), INTERVAL 1 DAY))",
            ("AUTH_GATE_LEGACY_V1", "legacy_gate", "0" * 64),
        )


def _test_database_url(database: str) -> str:
    url = _admin_url().set(database=database)
    return url.render_as_string(hide_password=False)


def _new_database_name(scope: str = "mysql") -> str:
    """Create a concurrency-safe database name within the governed prefix."""
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4)
    database = f"{DATABASE_PREFIX}{scope}_{suffix}"
    if len(database) > 64 or not database.startswith(DATABASE_PREFIX):
        raise RuntimeError("unsafe authentication Gate database name")
    return database


def _drop_isolated_database(database: str) -> None:
    """Drop only a database created inside the governed authentication Gate namespace."""
    if not database.startswith(DATABASE_PREFIX):
        raise RuntimeError(
            "refusing to remove a database outside the authentication Gate namespace"
        )
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")


def _emit_result(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    authority = _resolve_authority()
    migrations = _migration_names(authority)
    if not os.getenv(ADMIN_URL_ENV):
        _emit_result(
            {
                GATE_STATUS_NAME: "BLOCKED",
                "blocker": f"{ADMIN_URL_ENV} is required",
                "admin_url": "NOT_SET",
                "mysql_version": "UNKNOWN",
                "migration_order": list(migrations),
                "isolated_database_removed": False,
            }
        )
        return 2

    database = _new_database_name()
    version = "UNKNOWN"
    test_exit: int | None = None
    created = False
    removed = False
    status = "FAIL"
    blocker: str | None = None
    error_type: str | None = None
    exit_code = 1
    admin_host = "UNKNOWN"
    admin_port = 3306
    try:
        admin_url = _admin_url()
        admin_host = str(admin_url.host)
        admin_port = admin_url.port or 3306
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not version.startswith(SUPPORTED_MYSQL_PREFIX):
                raise GateBlocked(f"MySQL 8.4 is required; detected {version}")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            created = True
        for migration in migrations:
            if migration == "V7__p1_remaining_authentication_closure.sql":
                _seed_v6_legacy_idempotency_record(database)
            _execute_script(database, _migration_path(authority, migration))
        environment = os.environ.copy()
        environment[DATABASE_URL_ENV] = _test_database_url(database)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/test_p1_auth_mysql.py",
                "-q",
            ],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        test_exit = completed.returncode
        status = "PASS" if test_exit == 0 else "FAIL"
        exit_code = test_exit
    except GateBlocked as exc:
        status = "BLOCKED"
        blocker = str(exc)
        exit_code = 2
    except Exception as exc:
        status = "FAIL"
        error_type = type(exc).__name__
        exit_code = 1
    finally:
        if created:
            try:
                _drop_isolated_database(database)
                removed = True
            except Exception:
                status = "FAIL"
                blocker = f"failed to remove isolated database {database}"
                exit_code = 1

    result: dict[str, object] = {
        GATE_STATUS_NAME: status,
        "admin_url": "SET",
        "admin_host": admin_host,
        "admin_port": admin_port,
        "mysql_version": version,
        "database": database,
        "migration_order": list(migrations),
        "pytest_exit_code": test_exit,
        "isolated_database_removed": removed,
    }
    if blocker is not None:
        result["blocker"] = blocker
    if error_type is not None:
        result["error_type"] = error_type
    _emit_result(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
