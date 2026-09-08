from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from platform_api.execution_binding_service import _TERMINAL_CAPABILITIES
from platform_api.execution_slot_service import ExecutionSlotService
from platform_api.models import ExecutionSlot

NOW = datetime(2026, 9, 8, 0, 0, 0)


def _runner(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "runner_id": "R" * 26,
        "project_id": "P" * 26,
        "lifecycle_status": "ACTIVE",
        "registration_status": "REGISTERED",
        "enable_status": "ENABLED",
        "project_binding_status": "BOUND",
        "connection_status": "ONLINE",
        "health_status": "HEALTHY",
        "last_heartbeat_at": NOW,
        "version_compatibility": "COMPATIBLE",
        "scheduling_status": "IDLE",
        "resource_status": "AVAILABLE",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _slot(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "execution_slot_id": "S" * 26,
        "project_id": "P" * 26,
        "runner_id": "R" * 26,
        "slot_no": "0",
        "display_name": "正式执行槽位 1",
        "lifecycle_status": "ACTIVE",
        "row_version": 0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _formal_capability(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "availability_status": "CONFIGURED",
        "validation_status": "VALID",
        "lifecycle_status": "ACTIVE",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _DiscoverySession:
    def __init__(
        self,
        *,
        runner: SimpleNamespace | None = None,
        capability: SimpleNamespace | None = None,
        active_lease: SimpleNamespace | None = None,
    ) -> None:
        self.runner = runner or _runner()
        self.capability = capability or _formal_capability()
        self.active_lease = active_lease

    def get(self, model: object, identity: object) -> object | None:
        if getattr(model, "__name__", "") == "Runner" and identity == self.runner.runner_id:
            return self.runner
        return None

    def scalar(self, statement: object) -> object | None:
        sql = str(statement)
        if "atp_runner_capability" in sql:
            return self.capability
        if "atp_resource_lease" in sql:
            return self.active_lease
        raise AssertionError(sql)


def test_execution_slot_resource_is_available_only_when_runner_and_formal_capability_are_ready() -> None:
    db = _DiscoverySession()
    project = SimpleNamespace(project_id="P" * 26, lifecycle_status="ACTIVE")

    resource = ExecutionSlotService._resource(db, project, _slot())  # type: ignore[arg-type]

    assert resource.availability_status == "AVAILABLE"
    assert resource.active_lease_owner is None
    assert resource.slot_no == "0"


def test_execution_slot_resource_is_occupied_by_existing_runner_lease() -> None:
    lease = SimpleNamespace(owner_id="A" * 26)
    db = _DiscoverySession(active_lease=lease)
    project = SimpleNamespace(project_id="P" * 26, lifecycle_status="ACTIVE")

    resource = ExecutionSlotService._resource(db, project, _slot())  # type: ignore[arg-type]

    assert resource.availability_status == "OCCUPIED"
    assert resource.active_lease_owner == "A" * 26


def test_execution_slot_remains_historical_but_is_unavailable_while_runner_is_offline() -> None:
    db = _DiscoverySession(runner=_runner(connection_status="OFFLINE"))
    project = SimpleNamespace(project_id="P" * 26, lifecycle_status="ACTIVE")
    slot = _slot(lifecycle_status="ACTIVE")

    resource = ExecutionSlotService._resource(db, project, slot)  # type: ignore[arg-type]

    assert resource.lifecycle_status == "ACTIVE"
    assert resource.availability_status == "UNAVAILABLE"


def test_execution_slot_is_unavailable_when_formal_execution_capability_is_not_valid() -> None:
    db = _DiscoverySession(capability=_formal_capability(validation_status="PENDING"))
    project = SimpleNamespace(project_id="P" * 26, lifecycle_status="ACTIVE")

    resource = ExecutionSlotService._resource(db, project, _slot())  # type: ignore[arg-type]

    assert resource.availability_status == "UNAVAILABLE"



def test_execution_slot_resource_becomes_available_again_after_runner_lease_release() -> None:
    db = _DiscoverySession(active_lease=SimpleNamespace(owner_id="A" * 26))
    project = SimpleNamespace(project_id="P" * 26, lifecycle_status="ACTIVE")
    slot = _slot()

    occupied = ExecutionSlotService._resource(db, project, slot)  # type: ignore[arg-type]
    assert occupied.availability_status == "OCCUPIED"

    db.active_lease = None
    released = ExecutionSlotService._resource(db, project, slot)  # type: ignore[arg-type]
    assert released.availability_status == "AVAILABLE"
    assert released.execution_slot_id == occupied.execution_slot_id


@pytest.mark.parametrize(
    ("runner_overrides", "project_status"),
    [
        ({"enable_status": "DISABLED"}, "ACTIVE"),
        ({"project_binding_status": "UNBOUND"}, "ACTIVE"),
        ({"version_compatibility": "INCOMPATIBLE"}, "ACTIVE"),
        ({"lifecycle_status": "ARCHIVED"}, "ACTIVE"),
        ({}, "DISABLED"),
    ],
)
def test_execution_slot_resource_is_unavailable_for_static_runner_readiness_blockers(
    runner_overrides: dict[str, object], project_status: str
) -> None:
    db = _DiscoverySession(runner=_runner(**runner_overrides))
    project = SimpleNamespace(project_id="P" * 26, lifecycle_status=project_status)

    resource = ExecutionSlotService._resource(db, project, _slot())  # type: ignore[arg-type]

    assert resource.availability_status == "UNAVAILABLE"

def test_execution_slot_orm_maps_full_existing_table_shape_without_new_lock_state() -> None:
    columns = set(ExecutionSlot.__table__.columns.keys())
    assert {
        "execution_slot_id",
        "project_id",
        "runner_id",
        "slot_no",
        "lifecycle_status",
        "display_name",
        "row_version",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "extension_json",
    }.issubset(columns)
    assert not {"is_locked", "current_attempt_id", "busy_flag"}.intersection(columns)


def test_terminal_capability_mapping_uses_real_business_terminal_codes() -> None:
    assert _TERMINAL_CAPABILITIES == {
        "MANAGEMENT": "TERMINAL_ADMIN_WEB",
        "CLIENT": "TERMINAL_CLIENT_WEB",
        "PDA": "TERMINAL_PDA_WEB",
    }
