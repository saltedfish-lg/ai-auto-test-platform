#!/usr/bin/env python3
"""Run the canonical Living Authority validator set without producing release snapshots."""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTHORITY_ROOT = HERE.parent
REPO_ROOT = AUTHORITY_ROOT.parents[1]


def _validator_commands() -> dict[str, list[str]]:
    path = REPO_ROOT / "tools" / "authority_validation.py"
    spec = importlib.util.spec_from_file_location("_run_all_authority_validation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AUTHORITY_VALIDATOR_DEFINITION_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {str(name): [str(arg) for arg in argv] for name, argv in module.validator_commands().items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    steps: list[dict[str, object]] = []
    failed = False
    for name, argv in _validator_commands().items():
        proc = subprocess.run(
            [sys.executable, *argv],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        steps.append(
            {
                "validator": name,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-4000:],
                "stderr_tail": proc.stderr[-2000:],
            }
        )
        failed |= proc.returncode != 0
    report = {
        "authority_model": "SINGLE_LIVING_AUTHORITY",
        "authority_root": "docs/authority",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "FAIL" if failed else "PASS",
        "steps": steps,
    }
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
