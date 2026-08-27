#!/usr/bin/env python3
"""Run the repository's selected Flyway migration tool against the governed application DB."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402

ROOT = ensure_repo_root_on_path(__file__)

from platform_common.migrations import discover_migrations  # noqa: E402
from tools.database.schema_contract import (  # noqa: E402
    AuthoritySchemaMismatch,
    validate_authority_schema_shape,
)
from tools.environment import (  # noqa: E402
    get_env,
    load_project_environment,
    sanitize_database_error,
)

AUTHORITY_ROOT = ROOT / "docs" / "authority"
APP_ENV = "ATP_DATABASE_URL"
ADMIN_ENV = "ATP_MYSQL_ADMIN_URL"
FLYWAY_COMMAND_ENV = "FLYWAY_COMMAND"
FLYWAY_HISTORY_TABLE = "flyway_schema_history"
SUPPORTED_OPERATIONS = {"info", "validate", "migrate", "baseline-current"}


class FlywayBlocked(RuntimeError):
    """Represent a safe Flyway integration blocker without exposing credentials."""


def _parse_mysql_url(raw: str, *, require_database: bool) -> dict[str, object]:
    parsed = urlsplit(raw)
    if parsed.scheme != "mysql+pymysql" or not parsed.hostname or parsed.username is None:
        raise FlywayBlocked("DATABASE_URL_INVALID")
    database = parsed.path.lstrip("/") or None
    if require_database and not database:
        raise FlywayBlocked("DATABASE_NOT_FOUND")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
        "database": unquote(database) if database else None,
    }


def resolve_flyway_command() -> str:
    """Resolve Flyway from an explicit non-secret executable path or PATH."""
    configured = get_env(FLYWAY_COMMAND_ENV, root=ROOT)
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise FlywayBlocked("FLYWAY_COMMAND_NOT_FOUND")
    for name in ("flyway", "flyway.cmd"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise FlywayBlocked("FLYWAY_NOT_INSTALLED")


def _target_configs(*, target_database: str | None = None) -> tuple[dict[str, object], dict[str, object]]:
    app_url = get_env(APP_ENV, root=ROOT)
    admin_url = get_env(ADMIN_ENV, root=ROOT)
    if not app_url:
        raise FlywayBlocked(f"{APP_ENV}_MISSING")
    if not admin_url:
        raise FlywayBlocked(f"{ADMIN_ENV}_MISSING")
    app = _parse_mysql_url(app_url, require_database=True)
    admin = _parse_mysql_url(admin_url, require_database=False)
    if (app["host"], app["port"]) != (admin["host"], admin["port"]):
        raise FlywayBlocked("DATABASE_HOST_MISMATCH")
    if target_database is not None:
        app["database"] = target_database
    return app, admin


def _flyway_environment(
    *,
    target_database: str | None = None,
    baseline_version: int | None = None,
) -> dict[str, str]:
    app, admin = _target_configs(target_database=target_database)
    ddl_dir = AUTHORITY_ROOT / "编码权威事实" / "DATABASE_DDL"
    env = dict(os.environ)
    env.update(
        {
            "FLYWAY_URL": (
                f"jdbc:mysql://{admin['host']}:{admin['port']}/{app['database']}"
                "?useUnicode=true&characterEncoding=UTF-8&connectionTimeZone=UTC"
            ),
            "FLYWAY_USER": str(admin["user"]),
            "FLYWAY_PASSWORD": str(admin["password"]),
            "FLYWAY_LOCATIONS": f"filesystem:{ddl_dir.resolve().as_posix()}",
            "FLYWAY_TABLE": FLYWAY_HISTORY_TABLE,
            "FLYWAY_CLEAN_DISABLED": "true",
            "FLYWAY_BASELINE_ON_MIGRATE": "false",
            "FLYWAY_VALIDATE_MIGRATION_NAMING": "true",
            "FLYWAY_OUT_OF_ORDER": "false",
            "FLYWAY_FAIL_ON_MISSING_LOCATIONS": "true",
            "FLYWAY_DEFAULT_SCHEMA": str(app["database"]),
            "FLYWAY_CONNECT_RETRIES": "3",
        }
    )
    if baseline_version is not None:
        env["FLYWAY_BASELINE_VERSION"] = str(baseline_version)
        env["FLYWAY_BASELINE_DESCRIPTION"] = "adopt-current-authority-schema"
    return env


def run_flyway(
    operation: str,
    *,
    target_database: str | None = None,
    capture_output: bool = True,
) -> dict[str, object]:
    """Execute Flyway without placing database credentials on the command line."""
    if operation not in {"info", "validate", "migrate"}:
        raise ValueError(f"unsupported Flyway operation: {operation}")
    executable = resolve_flyway_command()
    app, _ = _target_configs(target_database=target_database)
    completed = subprocess.run(
        [executable, operation],
        cwd=ROOT,
        env=_flyway_environment(target_database=target_database),
        text=True,
        capture_output=capture_output,
        check=False,
    )
    app_url = get_env(APP_ENV, root=ROOT)
    diagnostic = sanitize_database_error(
        (completed.stdout or "") + (completed.stderr or ""),
        app_url,
        get_env(ADMIN_ENV, root=ROOT),
    )[-4000:]
    if completed.returncode != 0:
        raise FlywayBlocked(f"FLYWAY_{operation.upper()}_FAILED")
    migrations = discover_migrations(AUTHORITY_ROOT)
    return {
        "status": "PASS",
        "operation": operation,
        "database": str(app["database"]),
        "migration_head": migrations[-1]["name"],
        "migration_count": len(migrations),
        "diagnostic_tail": diagnostic,
    }


def _history_connection(admin: dict[str, object], database: str):
    try:
        import pymysql  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        raise FlywayBlocked("PYMYSQL_NOT_INSTALLED") from exc
    try:
        return pymysql.connect(
            host=str(admin["host"]),
            port=int(admin["port"]),
            user=str(admin["user"]),
            password=str(admin["password"]),
            database=database,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5,
        )
    except pymysql.MySQLError as exc:
        raise FlywayBlocked("DATABASE_CONNECTION_FAILED") from exc


def _history_table_exists(database: str) -> bool:
    _, admin = _target_configs(target_database=database)
    with _history_connection(admin, database) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name=%s",
            (database, FLYWAY_HISTORY_TABLE),
        )
        return int(cursor.fetchone()[0]) == 1


def _assert_current_schema_shape(database: str) -> None:
    """Require both full Authority shape and API ORM shape before legacy-schema adoption."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL
        from platform_api.schema_preflight import validate_mapped_schema_shape
    except ModuleNotFoundError as exc:
        raise FlywayBlocked("API_SCHEMA_PREFLIGHT_DEPENDENCIES_MISSING") from exc
    _, admin = _target_configs(target_database=database)
    try:
        with _history_connection(admin, database) as connection:
            validate_authority_schema_shape(
                connection,
                database=database,
                authority_root=AUTHORITY_ROOT,
                allow_flyway_history=False,
            )
    except AuthoritySchemaMismatch as exc:
        raise FlywayBlocked(exc.code) from exc
    url = URL.create(
        "mysql+pymysql",
        username=str(admin["user"]),
        password=str(admin["password"]),
        host=str(admin["host"]),
        port=int(admin["port"]),
        database=database,
    )
    engine = create_engine(url, pool_pre_ping=True)
    try:
        validate_mapped_schema_shape(engine)
    except Exception as exc:
        raise FlywayBlocked("CURRENT_SCHEMA_SHAPE_MISMATCH") from exc
    finally:
        engine.dispose()


def baseline_current() -> dict[str, object]:
    """Adopt an already-current direct-SQL schema into Flyway without reapplying migrations."""
    executable = resolve_flyway_command()
    del executable  # readiness is checked before any database adoption work
    app, _ = _target_configs()
    database = str(app["database"])
    if _history_table_exists(database):
        raise FlywayBlocked("FLYWAY_HISTORY_ALREADY_EXISTS")
    _assert_current_schema_shape(database)
    migrations = discover_migrations(AUTHORITY_ROOT)
    head = migrations[-1]
    completed = subprocess.run(
        [resolve_flyway_command(), "baseline"],
        cwd=ROOT,
        env=_flyway_environment(baseline_version=int(head["version"])),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FlywayBlocked("FLYWAY_BASELINE_FAILED")
    validate = run_flyway("validate")
    return {
        "status": "PASS",
        "operation": "baseline-current",
        "database": database,
        "baseline_version": int(head["version"]),
        "migration_head": head["name"],
        "validation": validate["status"],
    }


def main() -> int:
    load_project_environment(root=ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=sorted(SUPPORTED_OPERATIONS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = baseline_current() if args.operation == "baseline-current" else run_flyway(args.operation)
    except FlywayBlocked as exc:
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
        print(f"FLYWAY={result['status']}")
        if "operation" in result:
            print(f"OPERATION={result['operation']}")
        if "migration_head" in result:
            print(f"MIGRATION_HEAD={result['migration_head']}")
        if "reason" in result:
            print(f"REASON={result['reason']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
