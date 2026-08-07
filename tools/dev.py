#!/usr/bin/env python3
"""Vendor-neutral development and CI command entrypoint."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CURRENT_BASELINE = (ROOT / "docs" / "baseline" / "CURRENT").read_text(encoding="utf-8").strip()
BASELINE_ROOT = ROOT / "docs" / "baseline" / CURRENT_BASELINE
BASELINE_VALIDATION = BASELINE_ROOT / "编码冻结基线" / "RELEASE" / "validation"
BASELINE_RELATIVE = BASELINE_ROOT.relative_to(ROOT).as_posix()
PYTHON_SOURCE_PATHS = (
    "packages/domain-kernel/src",
    "packages/contracts/src",
    "packages/observability/src",
    "services/api/src",
    "workers/scheduler/src",
    "workers/background/src",
    "runner/agent/src",
    "tools",
)
UNIT_TEST_PATHS = (
    "packages/domain-kernel/tests",
    "packages/contracts/tests",
    "packages/observability/tests",
    "services/api/tests",
    "workers/scheduler/tests",
    "workers/background/tests",
    "runner/agent/tests",
)
BUILD_PROJECTS = (
    "packages/domain-kernel",
    "packages/contracts",
    "packages/observability",
    "services/api",
    "workers/scheduler",
    "workers/background",
    "runner/agent",
)


def run(command: Sequence[str], *, cwd: Path = ROOT) -> None:
    print("+ " + subprocess.list2cmdline(list(command)), flush=True)
    subprocess.run(list(command), cwd=cwd, check=True)


def npm(*arguments: str) -> None:
    executable = shutil.which("npm.cmd") if sys.platform == "win32" else shutil.which("npm")
    if executable is None:
        raise RuntimeError("npm is required but was not found on PATH")
    run((executable, *arguments))


def baseline() -> None:
    run((PYTHON, "tools/verify_baseline.py"))
    run(
        (
            PYTHON,
            str(BASELINE_VALIDATION / "validate_all.py"),
            "--root",
            BASELINE_RELATIVE,
        )
    )
    run(
        (
            PYTHON,
            str(BASELINE_VALIDATION / "validate_governance.py"),
            "--root",
            BASELINE_RELATIVE,
        )
    )
    auth_validator = BASELINE_VALIDATION / "validate_auth_contract.py"
    if auth_validator.is_file():
        run((PYTHON, str(auth_validator), "--root", BASELINE_RELATIVE))


def bootstrap() -> None:
    run((PYTHON, "-m", "pip", "install", "-r", "requirements-dev.lock"))
    npm("install")


def format_code() -> None:
    run((PYTHON, "-m", "ruff", "format", *PYTHON_SOURCE_PATHS, *UNIT_TEST_PATHS, "tests"))
    npm("run", "format:web")


def format_check() -> None:
    run(
        (
            PYTHON,
            "-m",
            "ruff",
            "format",
            "--check",
            *PYTHON_SOURCE_PATHS,
            *UNIT_TEST_PATHS,
            "tests",
        )
    )
    npm("run", "format:check:web")


def lint() -> None:
    run(
        (
            PYTHON,
            "-m",
            "ruff",
            "check",
            *PYTHON_SOURCE_PATHS,
            *UNIT_TEST_PATHS,
            "tests",
        )
    )
    npm("run", "lint:web")


def typecheck() -> None:
    run((PYTHON, "-m", "mypy", *PYTHON_SOURCE_PATHS))
    npm("run", "typecheck:web")


def test_unit() -> None:
    run((PYTHON, "-m", "pytest", *UNIT_TEST_PATHS))
    npm("run", "test:web")


def test_contract() -> None:
    run((PYTHON, "-m", "pytest", "tests/contract"))
    run((PYTHON, "tools/openapi_client.py", "check"))


def test_integration() -> None:
    run((PYTHON, "-m", "pytest", "tests/integration"))


def verify_migrations() -> None:
    run(
        (
            PYTHON,
            str(BASELINE_VALIDATION / "validate_all.py"),
            "--root",
            BASELINE_RELATIVE,
        )
    )
    print(
        "MYSQL_8_4_RUNTIME_GATE = "
        f"BASELINE_EVIDENCE_AVAILABLE ({CURRENT_BASELINE}); "
        "use tools/mysql84_gate.py --execute to rerun"
    )


def build() -> None:
    build_root = ROOT / ".build"
    web_dist = ROOT / "apps" / "web" / "dist"
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir()
    try:
        for project in BUILD_PROJECTS:
            run(
                (
                    PYTHON,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(build_root),
                    project,
                )
            )
        npm("run", "build:web")
    finally:
        if build_root.exists():
            shutil.rmtree(build_root)
        if web_dist.exists():
            shutil.rmtree(web_dist)


def verify() -> None:
    baseline()
    format_check()
    lint()
    typecheck()
    test_unit()
    test_contract()
    test_integration()
    build()


COMMANDS = {
    "bootstrap": bootstrap,
    "format": format_code,
    "format-check": format_check,
    "lint": lint,
    "typecheck": typecheck,
    "test-unit": test_unit,
    "test-contract": test_contract,
    "test-integration": test_integration,
    "verify-migrations": verify_migrations,
    "generate-openapi": lambda: run((PYTHON, "tools/openapi_client.py", "generate")),
    "check-openapi": lambda: run((PYTHON, "tools/openapi_client.py", "check")),
    "build": build,
    "baseline": baseline,
    "verify": verify,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    COMMANDS[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
