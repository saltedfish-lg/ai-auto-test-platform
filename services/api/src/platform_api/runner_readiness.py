"""Deterministic Runner version compatibility and scheduling projections."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

SUPPORTED_AGENT_VERSION = "0.1.0"
SUPPORTED_PLAYWRIGHT_VERSION = "1.62.0"

_VERSION_SUPPORT = {
    "AGENT_VERSION": SUPPORTED_AGENT_VERSION,
    "PLAYWRIGHT_VERSION": SUPPORTED_PLAYWRIGHT_VERSION,
}
_RESOURCE_TO_SCHEDULING = {
    "AVAILABLE": "IDLE",
    "PARTIALLY_OCCUPIED": "PARTIALLY_OCCUPIED",
    "EXHAUSTED": "BUSY",
    "RECLAIMING": "DRAINING",
}
_NEW_EXECUTION_SCHEDULING = {"IDLE", "PARTIALLY_OCCUPIED"}
_NEW_EXECUTION_RESOURCES = {"AVAILABLE", "PARTIALLY_OCCUPIED"}
_NUMERIC_VERSION = re.compile(r"^\d+(?:\.\d+)+$")


def _numeric_version(value: str) -> tuple[int, ...] | None:
    normalized = value.strip()
    if not _NUMERIC_VERSION.fullmatch(normalized):
        return None
    return tuple(int(part) for part in normalized.split("."))


def _compare_numeric_versions(left: str, right: str) -> int | None:
    left_parts = _numeric_version(left)
    right_parts = _numeric_version(right)
    if left_parts is None or right_parts is None:
        return None
    width = max(len(left_parts), len(right_parts))
    left_key = left_parts + (0,) * (width - len(left_parts))
    right_key = right_parts + (0,) * (width - len(right_parts))
    return (left_key > right_key) - (left_key < right_key)


def resolve_version_compatibility(capabilities: Iterable[Any]) -> str:
    """Resolve Runner compatibility from the two formally validated version capabilities."""
    by_code = {str(item.capability_code): item for item in capabilities}
    observed: dict[str, str] = {}
    for code in _VERSION_SUPPORT:
        capability = by_code.get(code)
        if (
            capability is None
            or capability.availability_status != "CONFIGURED"
            or capability.lifecycle_status != "ACTIVE"
            or capability.validation_status != "VALID"
            or not capability.observed_version
        ):
            return "UNKNOWN"
        observed[code] = str(capability.observed_version).strip()

    comparisons: list[int] = []
    for code, supported in _VERSION_SUPPORT.items():
        comparison = _compare_numeric_versions(observed[code], supported)
        if comparison is None:
            return "INCOMPATIBLE"
        comparisons.append(comparison)

    if all(value == 0 for value in comparisons):
        return "COMPATIBLE"
    if any(value > 0 for value in comparisons):
        return "INCOMPATIBLE"
    return "UPGRADE_REQUIRED"


def runner_base_execution_blockers(
    runner: Any,
    *,
    project_lifecycle_status: str | None,
) -> list[str]:
    """Return shared blockers for a Runner that is allowed to continue trusted execution."""
    checks = (
        (project_lifecycle_status == "ACTIVE", f"project_lifecycle_status={project_lifecycle_status or 'MISSING'}"),
        (runner.lifecycle_status == "ACTIVE", f"lifecycle_status={runner.lifecycle_status}"),
        (runner.registration_status == "REGISTERED", f"registration_status={runner.registration_status}"),
        (runner.enable_status == "ENABLED", f"enable_status={runner.enable_status}"),
        (runner.project_binding_status == "BOUND", f"project_binding_status={runner.project_binding_status}"),
        (runner.connection_status == "ONLINE", f"connection_status={runner.connection_status}"),
        (runner.health_status == "HEALTHY", f"health_status={runner.health_status}"),
        (runner.last_heartbeat_at is not None, "last_heartbeat_at=MISSING"),
        (
            runner.version_compatibility == "COMPATIBLE",
            f"version_compatibility={runner.version_compatibility}",
        ),
    )
    return [detail for passed, detail in checks if not passed]


def resolve_scheduling_status(
    runner: Any,
    *,
    project_lifecycle_status: str | None,
) -> str:
    """Project Scheduling Status from shared readiness plus the independent resource dimension."""
    if runner_base_execution_blockers(
        runner, project_lifecycle_status=project_lifecycle_status
    ):
        return "UNSCHEDULABLE"
    return _RESOURCE_TO_SCHEDULING.get(str(runner.resource_status), "UNSCHEDULABLE")


def runner_accept_new_execution_blockers(
    runner: Any,
    *,
    project_lifecycle_status: str | None,
) -> list[str]:
    """Return blockers that apply only while admitting a new execution attempt."""
    blockers = runner_base_execution_blockers(
        runner, project_lifecycle_status=project_lifecycle_status
    )
    if blockers:
        return blockers
    if runner.scheduling_status not in _NEW_EXECUTION_SCHEDULING:
        blockers.append(f"scheduling_status={runner.scheduling_status}")
    if runner.resource_status not in _NEW_EXECUTION_RESOURCES:
        blockers.append(f"resource_status={runner.resource_status}")
    return blockers


def runner_can_continue_bound_execution(
    runner: Any,
    *,
    project_lifecycle_status: str | None,
) -> bool:
    """Bound executions do not require IDLE; their lease/fencing owns resource continuity."""
    return not runner_base_execution_blockers(
        runner, project_lifecycle_status=project_lifecycle_status
    )
