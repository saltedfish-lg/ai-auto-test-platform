#!/usr/bin/env python3
"""Check application/admin MySQL connectivity from the repository-root local environment."""

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
from tools.environment import get_env, load_project_environment, redact_database_url, sanitize_database_error  # noqa: E402

APP_ENV = "ATP_DATABASE_URL"
ADMIN_ENV = "ATP_MYSQL_ADMIN_URL"


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


def run() -> dict[str, object]:
    load_project_environment(root=ROOT)
    app_url = get_env(APP_ENV, root=ROOT)
    admin_url = get_env(ADMIN_ENV, root=ROOT)
    result: dict[str, object] = {
        "app_database": "DATABASE_ENV_MISSING" if not app_url else "NOT_RUN",
        "mysql_admin": "DATABASE_ENV_MISSING" if not admin_url else "NOT_RUN",
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
    result["status"] = "PASS" if result["app_database"] == result["mysql_admin"] == "PASS" else "FAIL"
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
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
