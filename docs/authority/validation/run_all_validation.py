#!/usr/bin/env python3
"""Run the canonical Living Authority validator set with per-validator timeout control."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Mapping, Sequence

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[3]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))
from tools._bootstrap import ensure_repo_root_on_path

REPO_ROOT = ensure_repo_root_on_path(__file__)

from tools.authority_validation import validator_commands, validator_timeout_seconds
from tools.environment import project_environment, sanitize_database_error


def _display_command(argv: Sequence[str]) -> str:
    return " ".join([Path(sys.executable).name, *(str(arg) for arg in argv)])


def _execute_one(*, name: str, argv: Sequence[str], root: Path, env: dict[str, str], timeout: float) -> dict[str, object]:
    started = time.monotonic()
    step: dict[str, object] = {"validator": name, "command": _display_command(argv), "timeout_seconds": timeout}
    with tempfile.TemporaryDirectory(prefix="authority-validator-") as tmp:
        stdout_path = Path(tmp) / "stdout.log"; stderr_path = Path(tmp) / "stderr.log"
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
                proc = subprocess.run([sys.executable, *argv], cwd=root, text=True, stdout=stdout_file, stderr=stderr_file, check=False, timeout=timeout, env=env)
            stdout=stdout_path.read_text(encoding="utf-8",errors="replace") if stdout_path.exists() else ""; stderr=stderr_path.read_text(encoding="utf-8",errors="replace") if stderr_path.exists() else ""
            step.update({"status":"PASS" if proc.returncode==0 else "FAIL","returncode":proc.returncode,"stdout_tail":sanitize_database_error(stdout[-4000:]),"stderr_tail":sanitize_database_error(stderr[-2000:])})
        except subprocess.TimeoutExpired:
            stdout=stdout_path.read_text(encoding="utf-8",errors="replace") if stdout_path.exists() else ""; stderr=stderr_path.read_text(encoding="utf-8",errors="replace") if stderr_path.exists() else ""
            step.update({"status":"TIMEOUT","returncode":None,"stdout_tail":sanitize_database_error(stdout[-4000:]),"stderr_tail":sanitize_database_error(stderr[-2000:])})
        except (OSError, subprocess.SubprocessError) as exc:
            step.update({"status":"ERROR","returncode":None,"stdout_tail":"","stderr_tail":sanitize_database_error(str(exc)[-2000:])})
    step["duration_ms"]=round((time.monotonic()-started)*1000); return step


def execute_validators(*, root: Path = REPO_ROOT, commands: Mapping[str, Sequence[str]] | None = None, env: dict[str, str] | None = None, timeout_seconds: float | None = None) -> dict[str, object]:
    """Execute the canonical registry in registry order with strict failure propagation."""
    root = root.resolve()
    effective_env = dict(env) if env is not None else project_environment(root=root)
    timeout = timeout_seconds if timeout_seconds is not None else validator_timeout_seconds(effective_env)
    registry = commands if commands is not None else validator_commands()
    items = [(str(name), [str(arg) for arg in raw_argv]) for name, raw_argv in registry.items()]
    steps = [_execute_one(name=name, argv=argv, root=root, env=effective_env, timeout=timeout) for name, argv in items]
    counts = {status: sum(1 for step in steps if step.get("status") == status) for status in ("PASS", "FAIL", "ERROR", "TIMEOUT")}
    overall = "PASS" if steps and counts["PASS"] == len(steps) else "FAIL"
    return {
        "authority_model": "SINGLE_LIVING_AUTHORITY",
        "authority_root": "docs/authority",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timeout_seconds": timeout,
        "status": overall,
        "summary": {"total": len(steps), "passed": counts["PASS"], "failed": counts["FAIL"], "errors": counts["ERROR"], "timeouts": counts["TIMEOUT"], "overall_status": overall},
        "steps": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = execute_validators()
    except ValueError as exc:
        report = {
            "authority_model": "SINGLE_LIVING_AUTHORITY", "authority_root": "docs/authority",
            "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "FAIL",
            "summary": {"total": 0, "passed": 0, "failed": 0, "errors": 1, "timeouts": 0, "overall_status": "FAIL"},
            "errors": [sanitize_database_error(str(exc))], "steps": [],
        }
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
