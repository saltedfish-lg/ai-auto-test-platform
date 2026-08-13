#!/usr/bin/env python3
"""Formal entrypoint for the current Living Authority MySQL 8.4 Full Schema Gate."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "docs" / "authority"
VALIDATION = AUTHORITY / "validation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Run the real MySQL 8.4 Full Schema Gate.")
    parser.add_argument(
        "--evidence-output",
        type=Path,
        help="Write the same structured, secret-free JSON evidence emitted on stdout to this path.",
    )
    args = parser.parse_args()
    if not args.execute:
        payload = {
            "evidence_schema_version": 1,
            "gate_id": "FULL_SCHEMA_MYSQL84_RUNTIME_GATE",
            "result": "NOT_EXECUTED_THIS_RUN",
            "authority_model": "SINGLE_LIVING_AUTHORITY",
            "formal_entrypoint": "python tools/mysql84_gate.py --execute",
            "admin_connection_source": "ATP_MYSQL_ADMIN_URL",
        }
        raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.evidence_output:
            args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_output.write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 0

    command = [
        sys.executable,
        str(VALIDATION / "run_mysql84_gate.py"),
        "--root",
        str(AUTHORITY),
        "--compose",
        str(VALIDATION / "mysql84-compose.yml"),
    ]
    if args.evidence_output:
        command.extend(["--output", str(args.evidence_output.resolve())])
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
