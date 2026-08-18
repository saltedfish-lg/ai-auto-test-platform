#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402
REPO_ROOT = ensure_repo_root_on_path(__file__)
from tools.current_facts import derive_current_facts, discover_migrations  # noqa: E402
from tools.environment import get_env, load_project_environment, project_environment, sanitize_database_error  # noqa: E402
from tools.governance.migration_freshness import full_schema_input_identity  # noqa: E402
from tools.governance.migration_registry import migration_for_capability  # noqa: E402
from tools.governance.runtime_gate_result import finalize_runtime_result, runtime_result_base  # noqa: E402

AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
GATE_ID = "FULL_SCHEMA_MYSQL84_RUNTIME_GATE"
ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"


def _parse_admin_url(raw_url: str) -> dict[str, object]:
    """Parse the governed instance-level admin URL without exposing it in gate output."""
    parsed = urlsplit(raw_url)
    if parsed.scheme != "mysql+pymysql":
        raise ValueError(f"{ADMIN_URL_ENV} must use mysql+pymysql")
    if not parsed.hostname or parsed.username is None:
        raise ValueError(f"{ADMIN_URL_ENV} must include host and username")
    try:
        port = parsed.port or 3306
    except ValueError as exc:
        raise ValueError(f"{ADMIN_URL_ENV} contains an invalid port") from exc
    return {
        "host": parsed.hostname,
        "port": str(port),
        "user": unquote(parsed.username),
        "password": unquote(parsed.password or ""),
    }


def _admin_url_from_environment() -> str | None:
    """Read the admin DSN through the repository-root environment loader."""
    return get_env(ADMIN_URL_ENV, root=REPO_ROOT)


def _new_checks() -> dict[str, str]:
    return {
        "mysql_8_4_version": "NOT_RUN",
        "empty_db_migration": "NOT_RUN",
        "seed_replay_idempotency": "NOT_RUN",
        "legacy_upgrade": "NOT_RUN",
        "schema_assertions": "NOT_RUN",
        "temporary_db_cleanup": "NOT_RUN",
    }


def main() -> int:
    load_project_environment(root=REPO_ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--compose", type=Path, default=Path(__file__).resolve().parent / "mysql84-compose.yml")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.compose = args.compose.resolve()
    repo_root = args.root.parents[1]
    facts = derive_current_facts(repo_root)
    migrations = discover_migrations(args.root)
    ddl_dir = (args.root / "编码权威事实/DATABASE_DDL").resolve()
    migration_head = facts["migration"]["head"]
    migration_chain = facts["migration"]["chain"]
    seed_migration = migration_for_capability(migrations, args.root, "RBAC_SEED_REPLAY")
    legacy_boundary = migration_for_capability(migrations, args.root, "LEGACY_UPGRADE_FIXTURE_BOUNDARY")
    assertion_source = Path(__file__).resolve().parent / "mysql84_assertions.sql"
    input_identity = full_schema_input_identity(migrations, args.root, Path(__file__).resolve(), assertion_source)

    docker = shutil.which("docker")
    podman = shutil.which("podman")
    mysql = get_env("ATP_MYSQL_CLIENT", root=REPO_ROOT) or shutil.which("mysql")
    if not mysql and os.name == "nt":
        candidate = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")
        if candidate.is_file():
            mysql = str(candidate)
    report: dict[str, object] = runtime_result_base(
        repo_root,
        gate_id=GATE_ID,
        gate_source=Path(__file__).resolve(),
        gate_capabilities=["MYSQL_RUNTIME", "FULL_SCHEMA", "MIGRATION_SET_FRESHNESS", "ISOLATED_DATABASE_CLEANUP"],
    )
    report.update({
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
        "formal_entrypoint": "python tools/mysql84_gate.py --execute",
        "blocking_scope": "DATABASE_MODULE_FORMAL_MERGE",
        "current_migration_head": migration_head,
        "current_migration_chain": migration_chain,
        "migration_set_digest": input_identity["migration_set_digest"],
        "migration_set": input_identity["migrations"],
        "gate_source_digest": input_identity["gate_source_digest"],
        "schema_assertion_source_digest": input_identity["schema_assertion_source_digest"],
        "current_facts_source": "tools/current_facts.py",
        "admin_connection_source": ADMIN_URL_ENV,
        "runtime_versions": {"mysql": "UNKNOWN"},
        "details": {"docker": docker, "podman": podman, "mysql_client": bool(mysql)},
        "checks": _new_checks(),
        "cleanup_status": {"success": False, "temporary_database_removed": False, "container_resources_removed": False},
        "required_step_capabilities": [
            "APPLY_DISCOVERED_MIGRATION_CHAIN",
            "REPLAY_SEED_CAPABILITY",
            "LEGACY_UPGRADE_FIXTURE_BOUNDARY",
            "SCHEMA_ASSERTIONS",
            "TEMPORARY_RESOURCE_CLEANUP",
        ],
        "contains_secrets": False,
    })

    admin_url = _admin_url_from_environment()
    if mysql and admin_url:
        try:
            connection = _parse_admin_url(admin_url)
        except ValueError as exc:
            report["checks"]["temporary_db_cleanup"] = "NOT_APPLICABLE"
            report.update({
                "status": "BLOCKED",
                "result": "BLOCKED",
                "error": str(exc),
                "cleanup_status": {
                    "success": True,
                    "temporary_database_removed": True,
                    "container_resources_removed": True,
                },
            })
            rc = 2
        else:
            rc = run_local_mysql(args.root, Path(mysql), connection, report, migrations, seed_migration, legacy_boundary)
    else:
        engine = docker or podman
        if not engine:
            report["checks"]["temporary_db_cleanup"] = "NOT_APPLICABLE"
            if admin_url:
                environment_note = (
                    f"{ADMIN_URL_ENV} was loaded, but no MySQL client or Docker/Podman runtime is available. "
                    "No secret is written to gate output."
                )
            else:
                environment_note = (
                    f"{ADMIN_URL_ENV} is not configured and no Docker/Podman runtime is available. "
                    "No secret is written to gate output."
                )
            report.update({
                "status": "NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE",
                "result": "NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE",
                "note": environment_note,
                "cleanup_status": {
                    "success": True,
                    "temporary_database_removed": True,
                    "container_resources_removed": True,
                },
            })
            rc = 2
        else:
            command = [engine, "compose", "-f", str(args.compose), "up", "--abort-on-container-exit", "--exit-code-from", "validator"]
            compose_env = project_environment(root=REPO_ROOT)
            # Container fallback provisions its own isolated MySQL instance and does
            # not need the user's local application/admin database credentials.
            compose_env.pop(ADMIN_URL_ENV, None)
            compose_env.pop("ATP_DATABASE_URL", None)
            compose_env["ATP_AUTHORITY_DDL_DIR"] = str(ddl_dir)
            compose_env["ATP_MIGRATION_HEAD"] = str(migration_head)
            compose_env["ATP_SEED_MIGRATION_NAME"] = str(seed_migration["name"])
            compose_env["ATP_LEGACY_BOUNDARY_MIGRATION_NAME"] = str(legacy_boundary["name"])
            process = subprocess.run(command, cwd=args.compose.parent, env=compose_env, text=True, capture_output=True)
            cleanup = subprocess.run([engine, "compose", "-f", str(args.compose), "down", "-v"], cwd=args.compose.parent, env=compose_env, text=True, capture_output=True)
            checks = report["checks"]
            assert isinstance(checks, dict)
            process_ok = process.returncode == 0
            cleanup_ok = cleanup.returncode == 0
            for key in ("mysql_8_4_version", "empty_db_migration", "seed_replay_idempotency", "legacy_upgrade", "schema_assertions"):
                checks[key] = "PASS" if process_ok else "FAIL"
            checks["temporary_db_cleanup"] = "PASS" if cleanup_ok else "FAIL"
            overall_ok = process_ok and cleanup_ok
            report.update({
                "execution_mode": "CONTAINER",
                "admin_connection_source": "ISOLATED_CONTAINER_MYSQL",
                "validated_migration_head": migration_head if overall_ok else None,
                "validated_migration_chain": migration_chain if overall_ok else None,
                "validated_paths": {"empty": "DYNAMIC_DISCOVERED_CHAIN_PLUS_SEED_REPLAY", "upgrade": "CAPABILITY_BOUNDARY_PLUS_LEGACY_FIXTURE_PLUS_REMAINDER"},
                "ddl_source": str(ddl_dir),
                "status": "PASS" if overall_ok else "FAIL",
                "result": "PASS" if overall_ok else "FAIL",
                "runtime_versions": {"mysql": "MYSQL_8_4_SERIES_CONTAINER"},
                "cleanup_status": {"success": cleanup_ok, "temporary_database_removed": cleanup_ok, "container_resources_removed": cleanup_ok},
                "command": command,
                "returncode": 0 if overall_ok else 1,
                "validator_returncode": process.returncode,
                "cleanup_returncode": cleanup.returncode,
                "stdout": sanitize_database_error(process.stdout[-20000:]),
                "stderr": sanitize_database_error(process.stderr[-20000:]),
            })
            rc = 0 if overall_ok else 1
    report["exit_code"] = rc
    finalize_runtime_result(report, root=repo_root)
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return rc


def run_local_mysql(root: Path, mysql: Path, connection: dict[str, object], report: dict[str, object], migrations: list[dict], seed_migration: dict, legacy_boundary: dict) -> int:
    environment = project_environment(root=REPO_ROOT)
    environment["MYSQL_PWD"] = str(connection["password"])
    base = [
        str(mysql), "--protocol=TCP", "--host", str(connection["host"]), "--port", str(connection["port"]),
        "--user", str(connection["user"]), "--batch", "--skip-column-names",
    ]
    suffix = f"{int(time.time())}_{os.getpid()}"
    databases = [f"atp_authority_empty_{suffix}", f"atp_authority_upgrade_{suffix}"]
    if any(not re.fullmatch(r"[a-z0-9_]+", name) for name in databases):
        raise RuntimeError("unsafe generated database name")
    steps: list[dict[str, object]] = []
    checks = report["checks"]
    assert isinstance(checks, dict)
    created: set[str] = set()
    main_error: Exception | None = None

    def execute(name: str, sql: str, database: str | None = None) -> subprocess.CompletedProcess[str]:
        command = base + ([database] if database else [])
        process = subprocess.run(command, input=sql, text=True, capture_output=True, env=environment)
        steps.append({"name": name, "database": database, "returncode": process.returncode, "stdout_tail": sanitize_database_error(process.stdout[-4000:]), "stderr_tail": sanitize_database_error(process.stderr[-4000:])})
        if process.returncode:
            raise RuntimeError(f"{name} failed with {process.returncode}: {sanitize_database_error(process.stderr[-1000:])}")
        return process

    validation = root / "validation"
    assertions = (validation / "mysql84_assertions.sql").read_text(encoding="utf-8")
    legacy_fixture = (validation / "mysql84_upgrade_legacy_fixture.sql").read_text(encoding="utf-8")
    payloads = [(item["version"], item["name"], item["path"].read_text(encoding="utf-8")) for item in migrations]
    seed = next((sql for _version, name, sql in payloads if name == seed_migration["name"]), None)
    if seed is None:
        raise RuntimeError("required RBAC_SEED_REPLAY migration capability did not resolve")
    legacy_boundary_version = int(legacy_boundary["version"])

    try:
        version = execute("MYSQL_VERSION", "SELECT VERSION();").stdout.strip()
        if not re.match(r"^8\.4(?:\.|$)", version):
            raise RuntimeError(f"MySQL 8.4 required, got {version}")
        checks["mysql_8_4_version"] = "PASS"
        report["server_version"] = version
        for database in databases:
            execute(f"CREATE_{database}", f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;")
            created.add(database)
        for migration_version, _name, sql in payloads:
            execute(f"EMPTY_V{migration_version}", sql, databases[0])
        checks["empty_db_migration"] = "PASS"
        execute("EMPTY_SEED_REPLAY", seed, databases[0])
        checks["seed_replay_idempotency"] = "PASS"
        empty_assert = execute("EMPTY_ASSERTIONS", assertions, databases[0]).stdout

        fixture_inserted = False
        for migration_version, _name, sql in payloads:
            if not fixture_inserted and migration_version >= legacy_boundary_version:
                execute("UPGRADE_LEGACY_FIXTURE", legacy_fixture, databases[1])
                fixture_inserted = True
            execute(f"UPGRADE_V{migration_version}", sql, databases[1])
        if not fixture_inserted:
            raise RuntimeError("LEGACY_UPGRADE_FIXTURE_BOUNDARY migration capability not found in discovered chain")
        checks["legacy_upgrade"] = "PASS"
        upgrade_assert = execute("UPGRADE_ASSERTIONS", assertions, databases[1]).stdout
        if "CURRENT_AUTHORITY_MYSQL84_GATE_PASS" not in empty_assert or "CURRENT_AUTHORITY_MYSQL84_GATE_PASS" not in upgrade_assert:
            raise RuntimeError("formal assertion PASS marker missing")
        checks["schema_assertions"] = "PASS"
    except Exception as error:
        main_error = error
    finally:
        cleanup_ok = True
        for database in databases:
            process = subprocess.run(base, input=f"DROP DATABASE IF EXISTS `{database}`;", text=True, capture_output=True, env=environment)
            steps.append({"name": f"DROP_{database}", "returncode": process.returncode, "stderr_tail": sanitize_database_error(process.stderr[-1000:])})
            cleanup_ok = cleanup_ok and process.returncode == 0
        checks["temporary_db_cleanup"] = "PASS" if cleanup_ok else "FAIL"
        environment.pop("MYSQL_PWD", None)

    overall_ok = main_error is None and checks["temporary_db_cleanup"] == "PASS"
    if overall_ok:
        report.update({
            "execution_mode": "LOCAL_MYSQL",
            "status": "PASS",
            "result": "PASS",
            "returncode": 0,
            "runtime_versions": {"mysql": report.get("server_version", "UNKNOWN")},
            "cleanup_status": {"success": True, "temporary_database_removed": True, "container_resources_removed": True},
            "validated_migration_head": migrations[-1]["version"],
            "validated_migration_chain": " → ".join(f"V{item['version']}" for item in migrations),
            "databases": {"empty": "TEMPORARY_CREATED_AND_REMOVED", "upgrade": "TEMPORARY_CREATED_AND_REMOVED"},
            "steps": steps,
        })
        return 0

    report.update({
        "execution_mode": "LOCAL_MYSQL",
        "status": "FAIL",
        "result": "FAIL",
        "returncode": 1,
        "runtime_versions": {"mysql": report.get("server_version", "UNKNOWN")},
        "cleanup_status": {"success": checks["temporary_db_cleanup"] == "PASS", "temporary_database_removed": checks["temporary_db_cleanup"] == "PASS", "container_resources_removed": True},
        "error": sanitize_database_error(main_error) if main_error else "temporary database cleanup failed",
        "steps": steps,
    })
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
