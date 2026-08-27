#!/usr/bin/env python3
"""Verify that the formal migration chain executes through Flyway on an isolated MySQL 8.4 DB."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))
from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402

ROOT = ensure_repo_root_on_path(__file__)

from platform_api.schema_preflight import (  # noqa: E402
    SchemaPreflightFailure,
    run_schema_preflight,
)
from tools.database.flyway import (  # noqa: E402
    FlywayBlocked,
    resolve_flyway_command,
    run_flyway,
)
from tools.environment import get_env, load_project_environment  # noqa: E402
from tools.governance.runtime_gate_result import (  # noqa: E402
    finalize_runtime_result,
    runtime_result_base,
)

AUTHORITY_ROOT = ROOT / "docs" / "authority"
ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"
DATABASE_PREFIX = "ai_auto_test_platform_gate_flyway_"
GATE_ID = "FLYWAY_MIGRATION_RUNTIME_GATE"
SUPPORTED_MYSQL_SERIES = "8.4"


class GateBlocked(RuntimeError):
    """Represent a non-secret environment blocker."""


def _pymysql():
    try:
        import pymysql  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise GateBlocked("PYMYSQL_NOT_INSTALLED") from exc
    return pymysql


def _admin_url() -> URL:
    raw = get_env(ADMIN_URL_ENV, root=ROOT)
    if not raw:
        raise GateBlocked(f"{ADMIN_URL_ENV}_MISSING")
    try:
        url = make_url(raw)
    except Exception:
        raise GateBlocked(f"{ADMIN_URL_ENV}_INVALID") from None
    if url.drivername != "mysql+pymysql" or url.host is None or url.username is None:
        raise GateBlocked(f"{ADMIN_URL_ENV}_INVALID")
    return url


def _connection(database: str | None = None):
    pymysql = _pymysql()
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
            connect_timeout=5,
        )
    except pymysql.MySQLError as exc:
        raise GateBlocked("DATABASE_CONNECTION_FAILED") from exc


def _database_name() -> str:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4)
    database = f"{DATABASE_PREFIX}{suffix}"
    if len(database) > 64:
        raise RuntimeError("unsafe Flyway Gate database name")
    return database


def _drop_database(database: str) -> None:
    if not database.startswith(DATABASE_PREFIX):
        raise RuntimeError("refusing to drop database outside Flyway Gate namespace")
    with _connection() as connection, connection.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")


def _write(payload: dict[str, Any], output: Path | None) -> None:
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
    payload = runtime_result_base(
        ROOT,
        gate_id=GATE_ID,
        gate_source=Path(__file__),
        gate_capabilities=["FLYWAY_MIGRATION", "MYSQL_RUNTIME", "SCHEMA_PREFLIGHT"],
    )
    payload["checks"] = {
        "flyway_runtime": "NOT_RUN",
        "migration_apply": "NOT_RUN",
        "flyway_validate": "NOT_RUN",
        "schema_preflight": "NOT_RUN",
        "cleanup": "NOT_RUN",
    }
    database = _database_name()
    created = False
    removed = False
    exit_code = 1
    try:
        resolve_flyway_command()
        payload["checks"]["flyway_runtime"] = "PASS"
        with _connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not (version == SUPPORTED_MYSQL_SERIES or version.startswith(SUPPORTED_MYSQL_SERIES + ".")):
                raise GateBlocked("MYSQL_8_4_REQUIRED")
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            created = True
        run_flyway("migrate", target_database=database)
        payload["checks"]["migration_apply"] = "PASS"
        run_flyway("validate", target_database=database)
        payload["checks"]["flyway_validate"] = "PASS"
        admin = _admin_url().set(database=database)
        engine = create_engine(admin, pool_pre_ping=True)
        try:
            preflight = run_schema_preflight(engine, authority_root=AUTHORITY_ROOT)
        finally:
            engine.dispose()
        payload["checks"]["schema_preflight"] = "PASS"
        payload["schema_preflight"] = {
            "migration_head": preflight["migration_head"],
            "migration_version": preflight["migration_version"],
            "mapped_table_count": preflight["mapped_table_count"],
        }
        payload["result"] = "PASS"
        exit_code = 0
    except (GateBlocked, FlywayBlocked, SchemaPreflightFailure) as exc:
        payload["result"] = "BLOCKED" if isinstance(exc, (GateBlocked, FlywayBlocked)) else "FAIL"
        payload["blocker"] = str(exc)
        exit_code = 2 if payload["result"] == "BLOCKED" else 1
    except Exception as exc:
        payload["result"] = "FAIL"
        payload["error_type"] = type(exc).__name__
        exit_code = 1
    finally:
        if created:
            try:
                _drop_database(database)
                removed = True
            except Exception:
                payload["result"] = "FAIL"
                payload["blocker"] = "isolated database cleanup failed"
                exit_code = 1
        payload["checks"]["cleanup"] = "PASS" if removed else ("NOT_APPLICABLE" if not created else "FAIL")
        payload["cleanup_status"] = {
            "temporary_database_removed": removed,
            "success": removed if created else True,
        }
        payload["exit_code"] = exit_code
    _write(payload, args.result_output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
