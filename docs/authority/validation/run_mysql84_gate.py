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
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
from current_facts import derive_current_facts, discover_migrations  # noqa: E402

AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
GATE_ID = "FULL_SCHEMA_MYSQL84_RUNTIME_GATE"
EVIDENCE_SCHEMA_VERSION = 1
ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"
LEGACY_FIXTURE_BEFORE_VERSION = 7  # semantic compatibility boundary, not the current migration head
SEED_VERSION = 4


def _parse_admin_url(raw_url: str) -> dict[str, object]:
    """Parse the governed instance-level admin URL without exposing it in evidence."""
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


def _new_checks() -> dict[str, str]:
    return {
        "mysql_8_4_version": "NOT_RUN",
        "empty_db_migration": "NOT_RUN",
        "v4_seed_idempotency": "NOT_RUN",
        "legacy_upgrade": "NOT_RUN",
        "schema_assertions": "NOT_RUN",
        "temporary_db_cleanup": "NOT_RUN",
    }


def main() -> int:
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

    docker = shutil.which("docker")
    podman = shutil.which("podman")
    mysql = os.environ.get("ATP_MYSQL_CLIENT") or shutil.which("mysql")
    if not mysql and os.name == "nt":
        candidate = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")
        if candidate.is_file():
            mysql = str(candidate)
    executed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report: dict[str, object] = {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
        "gate_id": GATE_ID,
        "gate": "MYSQL84_EMPTY_DATABASE_AND_CURRENT_SCHEMA_UPGRADE",
        "formal_entrypoint": "python tools/mysql84_gate.py --execute",
        "blocking_scope": "DATABASE_MODULE_FORMAL_MERGE",
        "executed_at": executed_at,
        "current_migration_head": migration_head,
        "current_migration_chain": migration_chain,
        "current_facts_source": "tools/current_facts.py",
        "admin_connection_source": ADMIN_URL_ENV,
        "details": {"docker": docker, "podman": podman, "mysql_client": mysql},
        "checks": _new_checks(),
        "required_steps": [
            "empty database: apply every mechanically discovered formal migration in numeric order, then re-run the seed migration",
            f"upgrade path: apply migrations before V{LEGACY_FIXTURE_BEFORE_VERSION}, inject the canonical legacy fixture, then apply V{LEGACY_FIXTURE_BEFORE_VERSION} and every later discovered migration",
            "RBAC row counts must equal the current permission/role/mapping definitions",
            "credential user FK rejection",
            "username and credential uniqueness rejection",
            "refresh token hash uniqueness rejection",
            "credential version and refresh lifecycle CHECK rejection",
            "temporary databases/containers must be cleaned before PASS is emitted",
        ],
        "secrets_in_evidence": False,
    }

    admin_url = os.environ.get(ADMIN_URL_ENV)
    if mysql and admin_url:
        try:
            connection = _parse_admin_url(admin_url)
        except ValueError as exc:
            report.update({"status": "BLOCKED", "result": "BLOCKED", "error": str(exc)})
            rc = 2
        else:
            rc = run_local_mysql(args.root, Path(mysql), connection, report, migrations)
    else:
        engine = docker or podman
        if not engine:
            report.update({
                "status": "NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE",
                "result": "NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE",
                "note": f"Provide {ADMIN_URL_ENV} with a MySQL 8.4 client, or Docker/Podman. No secret is written to evidence.",
            })
            rc = 2
        else:
            command = [engine, "compose", "-f", str(args.compose), "up", "--abort-on-container-exit", "--exit-code-from", "validator"]
            compose_env = dict(os.environ)
            compose_env["ATP_AUTHORITY_DDL_DIR"] = str(ddl_dir)
            compose_env["ATP_MIGRATION_HEAD"] = str(migration_head)
            process = subprocess.run(command, cwd=args.compose.parent, env=compose_env, text=True, capture_output=True)
            cleanup = subprocess.run([engine, "compose", "-f", str(args.compose), "down", "-v"], cwd=args.compose.parent, env=compose_env, text=True, capture_output=True)
            checks = report["checks"]
            assert isinstance(checks, dict)
            process_ok = process.returncode == 0
            cleanup_ok = cleanup.returncode == 0
            for key in ("mysql_8_4_version", "empty_db_migration", "v4_seed_idempotency", "legacy_upgrade", "schema_assertions"):
                checks[key] = "PASS" if process_ok else "FAIL"
            checks["temporary_db_cleanup"] = "PASS" if cleanup_ok else "FAIL"
            overall_ok = process_ok and cleanup_ok
            report.update({
                "execution_mode": "CONTAINER",
                "admin_connection_source": "ISOLATED_CONTAINER_MYSQL",
                "validated_migration_head": migration_head if overall_ok else None,
                "validated_migration_chain": migration_chain if overall_ok else None,
                "validated_paths": {"empty": "DYNAMIC_DISCOVERED_CHAIN_PLUS_SEED_REPLAY", "upgrade": f"DYNAMIC_PRE_V{LEGACY_FIXTURE_BEFORE_VERSION}_PLUS_LEGACY_FIXTURE_PLUS_REMAINDER"},
                "ddl_source": str(ddl_dir),
                "status": "PASS" if overall_ok else "FAIL",
                "result": "PASS" if overall_ok else "FAIL",
                "command": command,
                "returncode": 0 if overall_ok else 1,
                "validator_returncode": process.returncode,
                "cleanup_returncode": cleanup.returncode,
                "stdout": process.stdout[-20000:],
                "stderr": process.stderr[-20000:],
            })
            rc = 0 if overall_ok else 1
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return rc


def run_local_mysql(root: Path, mysql: Path, connection: dict[str, object], report: dict[str, object], migrations: list[dict]) -> int:
    environment = os.environ.copy()
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
        steps.append({"name": name, "database": database, "returncode": process.returncode, "stdout_tail": process.stdout[-4000:], "stderr_tail": process.stderr[-4000:]})
        if process.returncode:
            raise RuntimeError(f"{name} failed with {process.returncode}: {process.stderr[-1000:]}")
        return process

    validation = root / "validation"
    assertions = (validation / "mysql84_assertions.sql").read_text(encoding="utf-8")
    legacy_fixture = (validation / "mysql84_upgrade_legacy_fixture.sql").read_text(encoding="utf-8")
    payloads = [(item["version"], item["name"], item["path"].read_text(encoding="utf-8")) for item in migrations]
    seed = next((sql for version, _name, sql in payloads if version == SEED_VERSION), None)
    if seed is None:
        raise RuntimeError(f"required seed migration V{SEED_VERSION} not found")

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
        execute(f"EMPTY_V{SEED_VERSION}_SEED_REPLAY", seed, databases[0])
        checks["v4_seed_idempotency"] = "PASS"
        empty_assert = execute("EMPTY_ASSERTIONS", assertions, databases[0]).stdout

        fixture_inserted = False
        for migration_version, _name, sql in payloads:
            if not fixture_inserted and migration_version >= LEGACY_FIXTURE_BEFORE_VERSION:
                execute("UPGRADE_LEGACY_FIXTURE", legacy_fixture, databases[1])
                fixture_inserted = True
            execute(f"UPGRADE_V{migration_version}", sql, databases[1])
        if not fixture_inserted:
            raise RuntimeError(f"migration V{LEGACY_FIXTURE_BEFORE_VERSION} compatibility boundary not found")
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
            steps.append({"name": f"DROP_{database}", "returncode": process.returncode, "stderr_tail": process.stderr[-1000:]})
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
        "error": str(main_error) if main_error else "temporary database cleanup failed",
        "steps": steps,
    })
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
