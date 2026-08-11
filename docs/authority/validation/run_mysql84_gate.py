#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--compose", type=Path, default=Path(__file__).resolve().parent / "mysql84-compose.yml")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    docker = shutil.which("docker")
    podman = shutil.which("podman")
    mysql = os.environ.get("ATP_MYSQL_CLIENT") or shutil.which("mysql")
    if not mysql and os.name == "nt":
        candidate = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")
        if candidate.is_file():
            mysql = str(candidate)
    executed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report = {
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
        "gate": "MYSQL84_EMPTY_DATABASE_AND_CURRENT_SCHEMA_UPGRADE",
        "blocking_scope": "DATABASE_MODULE_FORMAL_MERGE",
        "executed_at": executed_at,
        "details": {"docker": docker, "podman": podman, "mysql_client": mysql},
        "required_steps": [
            "empty database: V3 -> V4 -> V5 -> V6 -> V4 again",
            "upgrade path: V3 -> V4 -> V5 -> V6",
            "permission/role/mapping counts remain 50/12/600",
            "credential user FK rejection",
            "username and credential uniqueness rejection",
            "refresh token hash uniqueness rejection",
            "credential version and refresh lifecycle CHECK rejection",
        ],
    }
    host = os.environ.get("ATP_MYSQL_HOST")
    port = os.environ.get("ATP_MYSQL_PORT", "3306")
    user = os.environ.get("ATP_MYSQL_USER")
    password = os.environ.get("ATP_MYSQL_PASSWORD")
    if mysql and host and user and password is not None:
        rc = run_local_mysql(args.root, Path(mysql), host, port, user, password, report)
    else:
        engine = docker or podman
        if not engine:
            report.update(
                {
                    "status": "NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE",
                    "note": "Provide ATP_MYSQL_HOST/PORT/USER/PASSWORD with a MySQL 8.4 client, or Docker/Podman. No secret is written to evidence.",
                }
            )
            rc = 2
        else:
            command = [engine, "compose", "-f", str(args.compose), "up", "--abort-on-container-exit", "--exit-code-from", "validator"]
            process = subprocess.run(command, cwd=args.compose.parent, text=True, capture_output=True)
            cleanup = subprocess.run(
                [engine, "compose", "-f", str(args.compose), "down", "-v"],
                cwd=args.compose.parent,
                text=True,
                capture_output=True,
            )
            report.update(
                {
                    "execution_mode": "CONTAINER",
                    "status": "PASS" if process.returncode == 0 else "FAIL",
                    "command": command,
                    "returncode": process.returncode,
                    "stdout": process.stdout[-20000:],
                    "stderr": process.stderr[-20000:],
                    "cleanup_returncode": cleanup.returncode,
                }
            )
            rc = 0 if process.returncode == 0 else 1
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return rc


def run_local_mysql(root: Path, mysql: Path, host: str, port: str, user: str, password: str, report: dict) -> int:
    environment = os.environ.copy()
    environment.pop("ATP_MYSQL_PASSWORD", None)
    environment["MYSQL_PWD"] = password
    base = [str(mysql), "--protocol=TCP", "--host", host, "--port", port, "--user", user, "--batch", "--skip-column-names"]
    suffix = f"{int(time.time())}_{os.getpid()}"
    databases = [f"atp_authority_empty_{suffix}", f"atp_authority_upgrade_{suffix}"]
    if any(not re.fullmatch(r"[a-z0-9_]+", name) for name in databases):
        raise RuntimeError("unsafe generated database name")
    steps = []

    def execute(name: str, sql: str, database: str | None = None) -> subprocess.CompletedProcess[str]:
        command = base + ([database] if database else [])
        process = subprocess.run(command, input=sql, text=True, capture_output=True, env=environment)
        steps.append(
            {
                "name": name,
                "database": database,
                "returncode": process.returncode,
                "stdout_tail": process.stdout[-4000:],
                "stderr_tail": process.stderr[-4000:],
            }
        )
        if process.returncode:
            raise RuntimeError(f"{name} failed with {process.returncode}: {process.stderr[-1000:]}")
        return process

    ddl = root / "编码权威事实/DATABASE_DDL"
    validation = root / "validation"
    v3 = (ddl / "V3__platform_contract_rebuild.sql").read_text(encoding="utf-8")
    v4 = (ddl / "V4__rbac_seed_data.sql").read_text(encoding="utf-8")
    v5 = (ddl / "V5__platform_authentication_contract.sql").read_text(encoding="utf-8")
    v6 = (ddl / "V6__p1_auth_governance_closure.sql").read_text(encoding="utf-8")
    assertions = (validation / "mysql84_assertions.sql").read_text(encoding="utf-8")
    try:
        version = execute("MYSQL_VERSION", "SELECT VERSION();").stdout.strip()
        if not re.match(r"^8\.4(?:\.|$)", version):
            raise RuntimeError(f"MySQL 8.4 required, got {version}")
        for database in databases:
            execute(f"CREATE_{database}", f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;")
        execute("EMPTY_V3", v3, databases[0])
        execute("EMPTY_V4_FIRST", v4, databases[0])
        execute("EMPTY_V5", v5, databases[0])
        execute("EMPTY_V6", v6, databases[0])
        execute("EMPTY_V4_SECOND", v4, databases[0])
        empty_assert = execute("EMPTY_ASSERTIONS", assertions, databases[0]).stdout
        execute("UPGRADE_V3", v3, databases[1])
        execute("UPGRADE_V4", v4, databases[1])
        execute("UPGRADE_V5", v5, databases[1])
        execute("UPGRADE_V6", v6, databases[1])
        upgrade_assert = execute("UPGRADE_ASSERTIONS", assertions, databases[1]).stdout
        if "CURRENT_AUTHORITY_MYSQL84_GATE_PASS" not in empty_assert or "CURRENT_AUTHORITY_MYSQL84_GATE_PASS" not in upgrade_assert:
            raise RuntimeError("formal assertion PASS marker missing")
        report.update(
            {
                "execution_mode": "LOCAL_MYSQL",
                "server_version": version,
                "status": "PASS",
                "returncode": 0,
                "databases": {"empty": "TEMPORARY_CREATED_AND_REMOVED", "upgrade": "TEMPORARY_CREATED_AND_REMOVED"},
                "steps": steps,
                "secrets_in_evidence": False,
            }
        )
        rc = 0
    except Exception as error:
        report.update({"execution_mode": "LOCAL_MYSQL", "status": "FAIL", "returncode": 1, "error": str(error), "steps": steps})
        rc = 1
    finally:
        for database in databases:
            process = subprocess.run(base, input=f"DROP DATABASE IF EXISTS `{database}`;", text=True, capture_output=True, env=environment)
            steps.append({"name": f"DROP_{database}", "returncode": process.returncode})
        environment.pop("MYSQL_PWD", None)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
