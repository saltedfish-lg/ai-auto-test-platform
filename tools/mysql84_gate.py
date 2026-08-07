#!/usr/bin/env python3
"""Explicit entrypoint for the CURRENT baseline MySQL 8.4 runtime gate."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_BASELINE = (ROOT / "docs" / "baseline" / "CURRENT").read_text(encoding="utf-8").strip()
BASELINE = ROOT / "docs" / "baseline" / CURRENT_BASELINE
VALIDATION = BASELINE / "编码冻结基线" / "RELEASE" / "validation"
RELEASE = BASELINE / "编码冻结基线" / "RELEASE" / "platform_design_baseline_release.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Rerun the real MySQL 8.4 gate for the CURRENT baseline.",
    )
    args = parser.parse_args()
    if not args.execute:
        release_text = RELEASE.read_text(encoding="utf-8")
        recorded = (
            "PASS"
            if re.search(
                r"- gate_id: MYSQL84_EMPTY_DATABASE_EXECUTION\n\s+status: PASS", release_text
            )
            else "UNKNOWN"
        )
        print(f"CURRENT_BASELINE = {CURRENT_BASELINE}")
        print(f"MYSQL_8_4_RUNTIME_GATE_BASELINE_EVIDENCE = {recorded}")
        print("Use --execute to rerun the real MySQL 8.4 gate in the current environment.")
        return 0
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATION / "run_mysql84_gate.py"),
            "--root",
            str(BASELINE),
            "--compose",
            str(VALIDATION / "mysql84-compose.yml"),
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
