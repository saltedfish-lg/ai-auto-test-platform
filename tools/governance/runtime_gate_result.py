from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path
from typing import Any

RESULT_SCHEMA_VERSION = 1


def runtime_result_base(root: Path, *, gate_id: str, gate_source: Path, gate_capabilities: list[str]) -> dict[str, Any]:
    del root, gate_source
    return {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "gate": gate_id,
        "gate_id": gate_id,
        "status": "RUNNING",
        "result": "RUNNING",
        "command": " ".join(shlex.quote(x) for x in sys.argv),
        "exit_code": None,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate_capabilities": sorted(set(gate_capabilities)),
        "contains_secrets": False,
    }


def finalize_runtime_result(payload: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    del root
    result = str(payload.get("result") or payload.get("status") or "UNKNOWN")
    payload["status"] = result
    if payload.get("exit_code") is None:
        for key in ("pytest_exit_code", "browser_exit_code", "process_exit_code"):
            if isinstance(payload.get(key), int):
                payload["exit_code"] = payload[key]
                break
    return payload


def validate_runtime_result(root: Path, payload: dict[str, Any], *, expected_gate_id: str | None = None, **_: Any) -> list[str]:
    del root
    errors: list[str] = []
    gate = payload.get("gate") or payload.get("gate_id")
    if expected_gate_id and gate != expected_gate_id:
        errors.append(f"gate mismatch: {gate}")
    if not isinstance(payload.get("command"), str) or not payload.get("command"):
        errors.append("command missing")
    if not isinstance(payload.get("executed_at"), str) or not payload.get("executed_at"):
        errors.append("executed_at missing")
    if payload.get("status") not in {
        "PASS", "FAIL", "BLOCKED", "NOT_EXECUTED", "NOT_EXECUTED_THIS_RUN",
        "NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE", "RUNNING",
    }:
        errors.append("invalid status")
    if payload.get("contains_secrets") is not False:
        errors.append("contains_secrets must be false")
    return errors
