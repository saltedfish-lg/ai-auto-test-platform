#!/usr/bin/env python3
"""Recreate the governed local development database and apply every current migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402

ROOT = ensure_repo_root_on_path(__file__)

from platform_common.migrations import discover_migrations  # noqa: E402
from tools.database.flyway import resolve_flyway_command, run_flyway  # noqa: E402
from tools.environment import get_env, load_project_environment, redact_database_url  # noqa: E402

AUTHORITY_ROOT = ROOT / "docs" / "authority"
APP_ENV = "ATP_DATABASE_URL"
ADMIN_ENV = "ATP_MYSQL_ADMIN_URL"
LOCAL_ENV = "PLATFORM_ENVIRONMENT"
EXPECTED_LOCAL_DATABASE = "ai_auto_test_platform_dev"


class RebuildBlocked(RuntimeError):
    """Represent an intentional safety refusal without exposing credentials."""


def _parse_mysql_url(raw: str, *, require_database: bool) -> dict[str, object]:
    parsed = urlsplit(raw)
    if parsed.scheme != "mysql+pymysql" or not parsed.hostname or parsed.username is None:
        raise RebuildBlocked("DATABASE_URL_INVALID")
    database = parsed.path.lstrip("/") or None
    if require_database and not database:
        raise RebuildBlocked("DATABASE_NOT_FOUND")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
        "database": unquote(database) if database else None,
    }


def _pymysql():
    try:
        import pymysql  # type: ignore[import-untyped]
        from pymysql.constants import CLIENT  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise RebuildBlocked("PYMYSQL_NOT_INSTALLED") from exc
    return pymysql, CLIENT


def _connect(config: dict[str, object], *, database: str | None = None):
    pymysql, client = _pymysql()
    try:
        return pymysql.connect(
            host=str(config["host"]),
            port=int(config["port"]),
            user=str(config["user"]),
            password=str(config["password"]),
            database=database,
            charset="utf8mb4",
            autocommit=True,
            client_flag=client.MULTI_STATEMENTS,
            connect_timeout=5,
        )
    except pymysql.MySQLError as exc:
        raise RebuildBlocked("DATABASE_CONNECTION_FAILED") from exc


def _validate_safety(*, platform_environment: str | None, app_url: str, admin_url: str, confirm: str) -> str:
    if platform_environment != "local":
        raise RebuildBlocked("LOCAL_ENVIRONMENT_REQUIRED")

    app = _parse_mysql_url(app_url, require_database=True)
    admin = _parse_mysql_url(admin_url, require_database=False)
    target = str(app["database"])
    if target != EXPECTED_LOCAL_DATABASE:
        raise RebuildBlocked("UNSAFE_DATABASE_TARGET")
    if confirm != target:
        raise RebuildBlocked("EXPLICIT_DATABASE_CONFIRMATION_REQUIRED")
    if (app["host"], app["port"]) != (admin["host"], admin["port"]):
        raise RebuildBlocked("DATABASE_HOST_MISMATCH")
    return target


def _rebuild_database(admin_config: dict[str, object], database: str) -> str:
    with _connect(admin_config) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        mysql_version = str(cursor.fetchone()[0])
        if not mysql_version.startswith("8.4."):
            raise RebuildBlocked("MYSQL_8_4_REQUIRED")
        cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cursor.execute(
            f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        )
    return mysql_version


def run(*, confirm: str, dry_run: bool = False) -> dict[str, object]:
    load_project_environment(root=ROOT)
    app_url = get_env(APP_ENV, root=ROOT)
    admin_url = get_env(ADMIN_ENV, root=ROOT)
    platform_environment = get_env(LOCAL_ENV, root=ROOT)
    if not app_url:
        raise RebuildBlocked(f"{APP_ENV}_MISSING")
    if not admin_url:
        raise RebuildBlocked(f"{ADMIN_ENV}_MISSING")

    target = _validate_safety(
        platform_environment=platform_environment,
        app_url=app_url,
        admin_url=admin_url,
        confirm=confirm,
    )
    migrations = discover_migrations(AUTHORITY_ROOT)
    payload: dict[str, object] = {
        "status": "DRY_RUN" if dry_run else "NOT_RUN",
        "target": redact_database_url(app_url),
        "database": target,
        "migration_count": len(migrations),
        "migration_head": migrations[-1]["name"],
        "migrations": [item["name"] for item in migrations],
    }
    if dry_run:
        return payload

    # Flyway readiness is checked before the destructive DROP/CREATE boundary.
    resolve_flyway_command()
    admin_config = _parse_mysql_url(admin_url, require_database=False)
    mysql_version = _rebuild_database(admin_config, target)
    try:
        migration_result = run_flyway("migrate", target_database=target)
        validation_result = run_flyway("validate", target_database=target)
    except Exception as exc:
        payload.update({"status": "FAIL", "migration_executor": "Flyway"})
        raise RebuildBlocked("FLYWAY_MIGRATION_FAILED") from exc

    with _connect(admin_config, database=target) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s", (target,))
        table_count = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM flyway_schema_history WHERE success = 1")
        flyway_history_rows = int(cursor.fetchone()[0])

    payload.update(
        {
            "status": "PASS",
            "mysql_version": mysql_version,
            "migration_executor": "Flyway",
            "flyway_migrate": migration_result["status"],
            "flyway_validate": validation_result["status"],
            "flyway_history_rows": flyway_history_rows,
            "applied_migrations": [item["name"] for item in migrations],
            "table_count": table_count,
        }
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"must exactly equal {EXPECTED_LOCAL_DATABASE}; destructive local-only safety confirmation",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = run(confirm=args.confirm, dry_run=args.dry_run)
    except RebuildBlocked as exc:
        result = {"status": "BLOCKED", "reason": str(exc)}
        code = 2
    except Exception as exc:
        result = {"status": "FAIL", "reason": type(exc).__name__}
        code = 1
    else:
        code = 0

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"DATABASE_REBUILD={result['status']}")
        if "database" in result:
            print(f"DATABASE={result['database']}")
        if "migration_count" in result:
            print(f"MIGRATION_COUNT={result['migration_count']}")
        if "migration_head" in result:
            print(f"MIGRATION_HEAD={result['migration_head']}")
        if "reason" in result:
            print(f"REASON={result['reason']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
