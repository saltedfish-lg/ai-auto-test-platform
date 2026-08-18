#!/usr/bin/env python3
"""Formal entrypoint for the current Living Authority MySQL 8.4 Full Schema Gate."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.environment import project_environment  # noqa: E402
from tools.governance.runtime_gate_result import finalize_runtime_result, runtime_result_base  # noqa: E402

AUTHORITY = ROOT / "docs" / "authority"
VALIDATION = AUTHORITY / "validation"
GATE_ID = "FULL_SCHEMA_MYSQL84_RUNTIME_GATE"


def _write(payload: dict, output: Path | None) -> None:
    finalize_runtime_result(payload)
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(raw, encoding="utf-8")
    print(raw, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Run the real MySQL 8.4 Full Schema Gate.")
    parser.add_argument("--result-output", type=Path, help="Write the current task gate result as secret-free JSON.")
    args = parser.parse_args()
    if not args.execute:
        payload = runtime_result_base(
            ROOT,
            gate_id=GATE_ID,
            gate_source=VALIDATION / "run_mysql84_gate.py",
            gate_capabilities=["MYSQL_RUNTIME", "FULL_SCHEMA", "MIGRATION_SET_FRESHNESS"],
        )
        payload.update({
            "result": "NOT_EXECUTED_THIS_RUN",
            "exit_code": 0,
            "authority_model": "SINGLE_LIVING_AUTHORITY",
            "formal_entrypoint": "python tools/mysql84_gate.py --execute",
            "admin_connection_source": "ATP_MYSQL_ADMIN_URL",
            "runtime_versions": {"mysql": "NOT_EXECUTED"},
            "checks": {},
            "cleanup_status": {"success": True, "temporary_database_removed": True, "container_resources_removed": True},
        })
        _write(payload, args.result_output)
        return 0

    command = [
        sys.executable,
        str(VALIDATION / "run_mysql84_gate.py"),
        "--root", str(AUTHORITY),
        "--compose", str(VALIDATION / "mysql84-compose.yml"),
    ]
    if args.result_output:
        command.extend(["--output", str(args.result_output.resolve())])
    completed = subprocess.run(command, cwd=ROOT, env=project_environment(root=ROOT), check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
