#!/usr/bin/env python3
"""Generate or compare the TypeScript client from the CURRENT frozen baseline."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_BASELINE = (ROOT / "docs" / "baseline" / "CURRENT").read_text(encoding="utf-8").strip()
BASELINE = ROOT / "docs" / "baseline" / CURRENT_BASELINE
GENERATOR = BASELINE / "编码冻结基线" / "RELEASE" / "validation" / "generate_ts_client.py"
OUTPUT = ROOT / "apps" / "web" / "src" / "generated"
CHECK_OUTPUT = ROOT / ".openapi-client-check"
GENERATED_FILES = ("types.ts", "client.ts", "generation-report.json")


def _normalize_generated_files_to_lf(output: Path) -> None:
    """Normalize generated text artifacts to LF for byte-stable cross-platform checks."""
    for name in GENERATED_FILES:
        path = output / name
        if not path.is_file():
            continue
        content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        path.write_bytes(content)


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
    _normalize_generated_files_to_lf(output)


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
