#!/usr/bin/env python3
"""Explicit entrypoint for the R4.1 MySQL 8.4 runtime gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "docs" / "baseline" / "R4.1" / "编码冻结基线" / "RELEASE" / "validation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the real MySQL 8.4 Compose gate instead of reporting its pending status.",
    )
    args = parser.parse_args()
    if not args.execute:
        print("MYSQL_8_4_RUNTIME_GATE = NOT_EXECUTED")
        print("Use --execute only in an environment with the required MySQL 8.4 runtime.")
        return 0
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATION / "run_mysql84_gate.py"),
            "--compose",
            str(VALIDATION / "mysql84-compose.yml"),
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
