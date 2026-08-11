#!/usr/bin/env python3
"""Run the current living-authority P1 auth/RBAC gate in an isolated MySQL database."""

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
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = ROOT / "docs" / "authority"
DATABASE_PREFIX = "ai_auto_test_platform_p1_codex_"
ADMIN_URL_ENV = "ATP_P1_MYSQL_ADMIN_URL"
MIGRATION_CANDIDATES = (
    "V3__platform_contract_rebuild.sql",
    "V4__rbac_seed_data.sql",
    "V5__platform_authentication_contract.sql",
    "V6__p1_auth_governance_closure.sql",
)


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
            "current authority must contain the V3/V4/V5/V6 migration chain exactly once"
        )
    return migrations

def _connection(database: str | None = None) -> pymysql.Connection:
    raw_url = os.getenv(ADMIN_URL_ENV)
    if raw_url is None:
        raise RuntimeError(f"{ADMIN_URL_ENV} must contain a local mysql+pymysql admin URL")
    url = make_url(raw_url)
    if url.drivername != "mysql+pymysql" or url.host is None or url.username is None:
        raise RuntimeError(f"{ADMIN_URL_ENV} must use mysql+pymysql with host and username")
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


def _migration_path(authority: Path, name: str) -> Path:
    matches = list(authority.rglob(name))
    if len(matches) != 1:
        raise RuntimeError(f"expected one current-authority migration named {name}, found {len(matches)}")
    return matches[0]


def _execute_script(database: str, path: Path) -> None:
    script = path.read_text(encoding="utf-8")
    with _connection(database) as connection, connection.cursor() as cursor:
        cursor.execute(script)
        while cursor.nextset():
            pass


def _test_database_url(database: str) -> str:
    url = make_url(os.environ[ADMIN_URL_ENV]).set(database=database)
    return url.render_as_string(hide_password=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    authority = _resolve_authority()
    migrations = _migration_names(authority)
    database = DATABASE_PREFIX + datetime.now(UTC).strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)
    if not database.startswith(DATABASE_PREFIX):
        raise RuntimeError("unsafe P1 gate database name")
    version = "UNKNOWN"
    test_exit = 1
    created = False
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
        environment = os.environ.copy()
        environment["ATP_P1_TEST_DATABASE_URL"] = _test_database_url(database)
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
        return test_exit
    finally:
        if created and database.startswith(DATABASE_PREFIX):
            with _connection() as connection, connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        print(
            json.dumps(
                {
                    "mysql_version": version,
                    "authority_model": "SINGLE_LIVING_AUTHORITY",
                    "authority_root": "docs/authority",
                    "migration_order": list(migrations),
                    "isolated_database_removed": created,
                    "pytest_exit_code": test_exit,
                    "gate": "PASS" if test_exit == 0 else "FAIL",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
