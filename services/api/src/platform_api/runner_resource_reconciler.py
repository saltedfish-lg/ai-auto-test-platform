"""System-owned reconciliation for stable Runner execution capacity identities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.models import ExecutionSlot, Project, Runner, RunnerCapability
from platform_api.security import new_ulid, utc_now

FORMAL_EXECUTION_SLOT_NO = "0"
FORMAL_EXECUTION_CAPABILITY = "FORMAL_EXECUTION"


def reconcile_formal_execution_slot(
    db: Session,
    runner: Runner,
    project: Project | None,
) -> ExecutionSlot | None:
    """Reconcile the P0 one-slot formal execution capacity for ``runner``.

    The slot is a stable long-lived resource identity.  High-frequency ONLINE/HEALTHY
    state deliberately does not create, disable, or delete the row; those facts are
    evaluated when the slot is discovered and again during Binding preflight.
    """
    existing = db.scalar(
        select(ExecutionSlot)
        .where(
            ExecutionSlot.runner_id == runner.runner_id,
            ExecutionSlot.slot_no == FORMAL_EXECUTION_SLOT_NO,
        )
        .with_for_update()
    )
    capability = db.scalar(
        select(RunnerCapability).where(
            RunnerCapability.runner_id == runner.runner_id,
            RunnerCapability.capability_code == FORMAL_EXECUTION_CAPABILITY,
        )
    )
    statically_eligible = bool(
        project is not None
        and project.lifecycle_status == "ACTIVE"
        and runner.lifecycle_status == "ACTIVE"
        and runner.registration_status == "REGISTERED"
        and runner.enable_status == "ENABLED"
        and runner.project_binding_status == "BOUND"
        and runner.version_compatibility == "COMPATIBLE"
        and capability is not None
        and capability.availability_status == "CONFIGURED"
        and capability.validation_status == "VALID"
        and capability.lifecycle_status == "ACTIVE"
    )

    now = utc_now()
    actor_id = runner.updated_by
    if existing is None:
        if not statically_eligible:
            return None
        existing = ExecutionSlot(
            execution_slot_id=new_ulid(),
            project_id=runner.project_id,
            runner_id=runner.runner_id,
            slot_no=FORMAL_EXECUTION_SLOT_NO,
            lifecycle_status="ACTIVE",
            display_name="正式执行槽位 1",
            row_version=0,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
            updated_by=actor_id,
            extension_json={"resource_code": "FORMAL_EXECUTION_SLOT", "capacity": 1},
        )
        db.add(existing)
        db.flush()
        return existing

    target_status = (
        "ARCHIVED"
        if runner.lifecycle_status == "ARCHIVED"
        else "ACTIVE" if statically_eligible else "DISABLED"
    )
    changed = False
    if existing.lifecycle_status != target_status:
        existing.lifecycle_status = target_status
        changed = True
    if existing.project_id != runner.project_id:
        # A Runner is project-bound.  Keeping the stable slot identity while updating the
        # owning project is safer than creating a parallel slot identity after a formal rebind.
        existing.project_id = runner.project_id
        changed = True
    if existing.display_name != "正式执行槽位 1":
        existing.display_name = "正式执行槽位 1"
        changed = True
    if changed:
        existing.row_version += 1
        existing.updated_at = now
        existing.updated_by = actor_id
    return existing
