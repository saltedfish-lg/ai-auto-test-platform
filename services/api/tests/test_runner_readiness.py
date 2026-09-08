from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from platform_api.runner_readiness import (
    SUPPORTED_AGENT_VERSION,
    SUPPORTED_PLAYWRIGHT_VERSION,
    resolve_scheduling_status,
    resolve_version_compatibility,
    runner_accept_new_execution_blockers,
    runner_can_continue_bound_execution,
)


def _capability(
    code: str,
    version: str | None,
    *,
    availability: str = "CONFIGURED",
    lifecycle: str = "ACTIVE",
    validation: str = "VALID",
) -> SimpleNamespace:
    return SimpleNamespace(
        capability_code=code,
        observed_version=version,
        availability_status=availability,
        lifecycle_status=lifecycle,
        validation_status=validation,
    )


def _versions(
    *,
    agent: str = SUPPORTED_AGENT_VERSION,
    playwright: str = SUPPORTED_PLAYWRIGHT_VERSION,
) -> list[SimpleNamespace]:
    return [
        _capability("AGENT_VERSION", agent),
        _capability("PLAYWRIGHT_VERSION", playwright),
    ]


def _runner(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "lifecycle_status": "ACTIVE",
        "registration_status": "REGISTERED",
        "enable_status": "ENABLED",
        "project_binding_status": "BOUND",
        "connection_status": "ONLINE",
        "health_status": "HEALTHY",
        "last_heartbeat_at": datetime.now(UTC).replace(tzinfo=None),
        "version_compatibility": "COMPATIBLE",
        "resource_status": "AVAILABLE",
        "scheduling_status": "IDLE",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        ([_capability("PLAYWRIGHT_VERSION", SUPPORTED_PLAYWRIGHT_VERSION)], "UNKNOWN"),
        ([_capability("AGENT_VERSION", SUPPORTED_AGENT_VERSION)], "UNKNOWN"),
        (
            [
                _capability("AGENT_VERSION", SUPPORTED_AGENT_VERSION, validation="PENDING"),
                _capability("PLAYWRIGHT_VERSION", SUPPORTED_PLAYWRIGHT_VERSION),
            ],
            "UNKNOWN",
        ),
        (
            [
                _capability(
                    "AGENT_VERSION", SUPPORTED_AGENT_VERSION, availability="NOT_CONFIGURED", lifecycle="DISABLED"
                ),
                _capability("PLAYWRIGHT_VERSION", SUPPORTED_PLAYWRIGHT_VERSION),
            ],
            "UNKNOWN",
        ),
        (_versions(), "COMPATIBLE"),
        (_versions(agent="0.0.9"), "UPGRADE_REQUIRED"),
        (_versions(playwright="1.61.9"), "UPGRADE_REQUIRED"),
        (_versions(agent="0.2.0"), "INCOMPATIBLE"),
        (_versions(playwright="1.63.0"), "INCOMPATIBLE"),
        (_versions(agent="dev-build"), "INCOMPATIBLE"),
        (_versions(agent="0.0.9", playwright="1.63.0"), "INCOMPATIBLE"),
    ],
)
def test_version_compatibility_policy(capabilities: list[SimpleNamespace], expected: str) -> None:
    assert resolve_version_compatibility(capabilities) == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lifecycle_status", "DISABLED"),
        ("registration_status", "REVOKED"),
        ("enable_status", "DISABLED"),
        ("project_binding_status", "UNBOUND"),
        ("connection_status", "OFFLINE"),
        ("health_status", "UNHEALTHY"),
        ("last_heartbeat_at", None),
        ("version_compatibility", "UNKNOWN"),
        ("version_compatibility", "INCOMPATIBLE"),
        ("version_compatibility", "UPGRADE_REQUIRED"),
    ],
)
def test_scheduling_is_unschedulable_when_base_readiness_fails(field: str, value: object) -> None:
    assert (
        resolve_scheduling_status(
            _runner(**{field: value}), project_lifecycle_status="ACTIVE"
        )
        == "UNSCHEDULABLE"
    )


def test_scheduling_is_unschedulable_when_project_is_not_active() -> None:
    assert resolve_scheduling_status(_runner(), project_lifecycle_status="DISABLED") == "UNSCHEDULABLE"


@pytest.mark.parametrize(
    ("resource", "expected"),
    [
        ("AVAILABLE", "IDLE"),
        ("PARTIALLY_OCCUPIED", "PARTIALLY_OCCUPIED"),
        ("EXHAUSTED", "BUSY"),
        ("RECLAIMING", "DRAINING"),
    ],
)
def test_scheduling_projects_resource_status_when_runner_is_ready(resource: str, expected: str) -> None:
    assert (
        resolve_scheduling_status(
            _runner(resource_status=resource), project_lifecycle_status="ACTIVE"
        )
        == expected
    )


def test_new_execution_and_bound_execution_use_distinct_resource_semantics() -> None:
    busy = _runner(resource_status="EXHAUSTED", scheduling_status="BUSY")
    assert "scheduling_status=BUSY" in runner_accept_new_execution_blockers(
        busy, project_lifecycle_status="ACTIVE"
    )
    assert runner_can_continue_bound_execution(busy, project_lifecycle_status="ACTIVE")
