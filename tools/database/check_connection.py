#!/usr/bin/env python3
"""Run the governed database preflight: connectivity, MySQL, Flyway, and schema compatibility."""

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
from tools.database.flyway import FlywayBlocked, resolve_flyway_command, run_flyway  # noqa: E402
from tools.database.schema_contract import (  # noqa: E402
    AuthoritySchemaMismatch,
    validate_authority_schema_shape,
)
from tools.environment import (  # noqa: E402
    get_env,
    load_project_environment,
    redact_database_url,
    sanitize_database_error,
)

APP_ENV = "ATP_DATABASE_URL"
ADMIN_ENV = "ATP_MYSQL_ADMIN_URL"
AUTHORITY_ROOT = ROOT / "docs" / "authority"


def _parse_dsn(raw: str, *, require_database: bool) -> dict[str, object]:
    parsed = urlsplit(raw)
    if parsed.scheme != "mysql+pymysql" or not parsed.hostname or parsed.username is None:
        raise ValueError("DATABASE_URL_INVALID")
    database = parsed.path.lstrip("/") or None
    if require_database and not database:
        raise ValueError("DATABASE_NOT_FOUND")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
        "database": unquote(database) if database else None,
    }


def _classify_mysql_error(exc: BaseException) -> str:
    code = None
    if getattr(exc, "args", None):
        try:
            code = int(exc.args[0])
        except (TypeError, ValueError):
            code = None
    if code == 1045:
        return "DATABASE_AUTHENTICATION_FAILED"
    if code == 1044:
        return "DATABASE_PERMISSION_DENIED"
    if code == 1049:
        return "DATABASE_NOT_FOUND"
    if code in {2002, 2003, 2005, 2006, 2013}:
        return "DATABASE_CONNECTION_REFUSED"
    return "DATABASE_CONNECTION_FAILED"


def _check(raw: str, query: str, *, require_database: bool) -> tuple[str, str | None]:
    try:
        config = _parse_dsn(raw, require_database=require_database)
    except (TypeError, ValueError) as exc:
        return str(exc) if str(exc).startswith("DATABASE_") else "DATABASE_URL_INVALID", None
    try:
        import pymysql  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return "PYMYSQL_NOT_INSTALLED", None
    try:
        connection = pymysql.connect(
            host=str(config["host"]),
            port=int(config["port"]),
            user=str(config["user"]),
            password=str(config["password"]),
            database=str(config["database"]) if config["database"] else None,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5,
        )
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
        return "PASS", str(row[0]) if row else None
    except Exception as exc:  # PyMySQL subclasses are optional at import time.
        return _classify_mysql_error(exc), sanitize_database_error(exc, raw)


def _schema_preflight(app_url: str) -> tuple[str, dict[str, object]]:
    try:
        from platform_api.database import create_database_engine
        from platform_api.schema_preflight import SchemaPreflightFailure, run_schema_preflight

        engine = create_database_engine(app_url)
    except ModuleNotFoundError:
        return "API_SCHEMA_PREFLIGHT_DEPENDENCIES_MISSING", {}
    try:
        return "PASS", run_schema_preflight(engine, authority_root=AUTHORITY_ROOT)
    except SchemaPreflightFailure as exc:
        return exc.code, dict(exc.metadata)
    except Exception as exc:
        return "DATABASE_SCHEMA_PREFLIGHT_FAILED", {"exception_type": type(exc).__name__}
    finally:
        if "engine" in locals():
            engine.dispose()


def _flyway_validate() -> tuple[str, str, dict[str, object]]:
    try:
        executable = resolve_flyway_command()
    except FlywayBlocked as exc:
        return str(exc), "NOT_RUN", {}
    try:
        result = run_flyway("validate")
    except FlywayBlocked as exc:
        return "PASS", str(exc), {"executable": Path(executable).name}
    except Exception as exc:
        return "PASS", "FLYWAY_VALIDATE_FAILED", {
            "executable": Path(executable).name,
            "exception_type": type(exc).__name__,
        }
    return "PASS", "PASS", {
        "executable": Path(executable).name,
        "migration_head": result.get("migration_head"),
    }


def _authority_schema_preflight(app_url: str, admin_url: str) -> tuple[str, dict[str, object]]:
    try:
        import pymysql  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return "PYMYSQL_NOT_INSTALLED", {}
    try:
        app = _parse_dsn(app_url, require_database=True)
        admin = _parse_dsn(admin_url, require_database=False)
        database = str(app["database"])
        with pymysql.connect(
            host=str(admin["host"]),
            port=int(admin["port"]),
            user=str(admin["user"]),
            password=str(admin["password"]),
            database=database,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=5,
        ) as connection:
            details = validate_authority_schema_shape(
                connection,
                database=database,
                authority_root=AUTHORITY_ROOT,
                allow_flyway_history=True,
            )
    except AuthoritySchemaMismatch as exc:
        return exc.code, dict(exc.metadata)
    except Exception as exc:
        return "DATABASE_AUTHORITY_SCHEMA_PREFLIGHT_FAILED", {
            "exception_type": type(exc).__name__
        }
    return "PASS", details


def run() -> dict[str, object]:
    load_project_environment(root=ROOT)
    app_url = get_env(APP_ENV, root=ROOT)
    admin_url = get_env(ADMIN_ENV, root=ROOT)
    migrations = discover_migrations(AUTHORITY_ROOT)
    result: dict[str, object] = {
        "app_database": "DATABASE_ENV_MISSING" if not app_url else "NOT_RUN",
        "mysql_admin": "DATABASE_ENV_MISSING" if not admin_url else "NOT_RUN",
        "mysql_series": "NOT_RUN",
        "flyway_runtime": "NOT_RUN",
        "flyway_validate": "NOT_RUN",
        "schema_preflight": "NOT_RUN",
        "authority_schema": "NOT_RUN",
        "migration_head": migrations[-1]["name"],
        "migration_version": migrations[-1]["version"],
        "contains_secrets": False,
    }
    if app_url:
        status, diagnostic = _check(app_url, "SELECT 1", require_database=True)
        result["app_database"] = status
        result["app_database_target"] = redact_database_url(app_url)
        if diagnostic and status != "PASS":
            result["app_database_error"] = diagnostic
    if admin_url:
        status, diagnostic = _check(admin_url, "SELECT VERSION()", require_database=False)
        result["mysql_admin"] = status
        result["mysql_admin_target"] = redact_database_url(admin_url)
        if diagnostic and status != "PASS":
            result["mysql_admin_error"] = diagnostic
        elif diagnostic and status == "PASS":
            result["mysql_version"] = diagnostic
            result["mysql_series"] = "PASS" if diagnostic.startswith("8.4.") else "MYSQL_8_4_REQUIRED"

    if result["app_database"] == "PASS" and result["mysql_admin"] == "PASS":
        runtime_status, validate_status, flyway_details = _flyway_validate()
        result["flyway_runtime"] = runtime_status
        result["flyway_validate"] = validate_status
        if flyway_details:
            result["flyway"] = flyway_details
        schema_status, schema_details = _schema_preflight(str(app_url))
        result["schema_preflight"] = schema_status
        if schema_details:
            result["schema"] = schema_details
        authority_status, authority_details = _authority_schema_preflight(
            str(app_url), str(admin_url)
        )
        result["authority_schema"] = authority_status
        if authority_details:
            result["authority_schema_details"] = authority_details

    checks = (
        result["app_database"],
        result["mysql_admin"],
        result["mysql_series"],
        result["flyway_runtime"],
        result["flyway_validate"],
        result["schema_preflight"],
        result["authority_schema"],
    )
    result["status"] = "PASS" if all(value == "PASS" for value in checks) else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"APP_DATABASE_CONNECTION={result['app_database']}")
        print(f"MYSQL_ADMIN_CONNECTION={result['mysql_admin']}")
        print(f"MYSQL_SERIES={result['mysql_series']}")
        print(f"FLYWAY_VALIDATE={result['flyway_validate']}")
        print(f"DATABASE_SCHEMA_PREFLIGHT={result['schema_preflight']}")
        print(f"DATABASE_AUTHORITY_SCHEMA={result['authority_schema']}")
        print(f"MIGRATION_HEAD={result['migration_head']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
