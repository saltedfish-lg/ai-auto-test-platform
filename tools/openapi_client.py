#!/usr/bin/env python3
"""Generate or compare the TypeScript client using the frozen R4.1 generator."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "baseline" / "R4.1"
GENERATOR = BASELINE / "编码冻结基线" / "RELEASE" / "validation" / "generate_ts_client.py"
OUTPUT = ROOT / "apps" / "web" / "src" / "generated"
CHECK_OUTPUT = ROOT / ".openapi-client-check"
GENERATED_FILES = ("types.ts", "client.ts", "generation-report.json")


def generate(output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--root",
            str(BASELINE),
            "--out",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )


def check() -> int:
    if CHECK_OUTPUT.exists():
        shutil.rmtree(CHECK_OUTPUT)
    try:
        generate(CHECK_OUTPUT)
        differences = [
            name
            for name in GENERATED_FILES
            if not (OUTPUT / name).is_file()
            or (OUTPUT / name).read_bytes() != (CHECK_OUTPUT / name).read_bytes()
        ]
    finally:
        if CHECK_OUTPUT.exists():
            shutil.rmtree(CHECK_OUTPUT)
    if differences:
        print("Generated OpenAPI client differs: " + ", ".join(differences))
        return 1
    print("OpenAPI generated client check: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check"))
    args = parser.parse_args()
    if args.command == "generate":
        generate(OUTPUT)
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
