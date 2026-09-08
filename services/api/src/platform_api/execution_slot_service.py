"""Read-only resource discovery for system-managed Runner execution slots."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticationService
from platform_api.errors import PlatformError
from platform_api.execution_slot_schemas import ExecutionSlotResource
from platform_api.models import ExecutionSlot, Project, ResourceLease, Runner, RunnerCapability
from platform_api.runner_readiness import runner_accept_new_execution_blockers


class ExecutionSlotService:
    def __init__(self, factory: sessionmaker[Session], authentication: AuthenticationService) -> None:
        self._factory = factory
        self._authentication = authentication

    def list_slots(
        self,
        token: str,
        *,
        project_id: str,
        runner_id: str | None,
        lifecycle_status: str | None,
        available_only: bool,
        page: int,
        page_size: int,
        audit_context: AuditContext,
    ) -> tuple[list[ExecutionSlotResource], int]:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_execution_slot", audit_context
            )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "list_execution_slot", ("PROJECT_VIEW",), project_id, audit_context
            )
            project = db.get(Project, project_id)
            if project is None:
                raise _not_found()
            query = select(ExecutionSlot).where(
                ExecutionSlot.project_id == project_id,
                ExecutionSlot.runner_id.is_not(None),
                ExecutionSlot.slot_no.is_not(None),
            )
            if runner_id is not None:
                query = query.where(ExecutionSlot.runner_id == runner_id)
            if lifecycle_status is not None:
                query = query.where(ExecutionSlot.lifecycle_status == lifecycle_status)
            slots = list(db.scalars(query.order_by(ExecutionSlot.runner_id, ExecutionSlot.slot_no)))
            resources = [self._resource(db, project, slot) for slot in slots]
            if available_only:
                resources = [item for item in resources if item.availability_status == "AVAILABLE"]
            total = len(resources)
            start = (page - 1) * page_size
            return resources[start : start + page_size], total

    def get_slot(
        self, token: str, slot_id: str, audit_context: AuditContext
    ) -> ExecutionSlotResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_execution_slot", audit_context
            )
            slot = db.get(ExecutionSlot, slot_id)
            if (
                slot is None
                or slot.project_id is None
                or slot.runner_id is None
                or slot.slot_no is None
            ):
                raise _not_found()
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "get_execution_slot", ("PROJECT_VIEW",), slot.project_id, audit_context
            )
            project = db.get(Project, slot.project_id)
            if project is None:
                raise _not_found()
            return self._resource(db, project, slot)

    def reject_external_mutation(
        self, token: str, operation: str, audit_context: AuditContext
    ) -> None:
        with self._factory() as db:
            self._authentication.authenticate_access_in_transaction(
                db, token, operation, audit_context
            )
        raise PlatformError(
            title="Execution slot is system managed",
            detail=(
                "Formal ExecutionSlot identities are reconciled from Runner readiness and "
                "FORMAL_EXECUTION capability evidence; external create/update is forbidden."
            ),
            status=409,
            code="EXECUTION_SLOT_SYSTEM_MANAGED",
        )

    @staticmethod
    def _resource(db: Session, project: Project, slot: ExecutionSlot) -> ExecutionSlotResource:
        if slot.project_id is None or slot.runner_id is None or slot.slot_no is None:
            raise _not_found()
        runner = db.get(Runner, slot.runner_id)
        capability = db.scalar(
            select(RunnerCapability).where(
                RunnerCapability.runner_id == slot.runner_id,
                RunnerCapability.capability_code == "FORMAL_EXECUTION",
            )
        )
        lease_identity = f"{slot.runner_id}:FORMAL_EXECUTION_SLOT:{slot.execution_slot_id}"
        active_lease = db.scalar(
            select(ResourceLease).where(
                ResourceLease.project_id == slot.project_id,
                ResourceLease.resource_type == "RUNNER",
                ResourceLease.resource_identity == lease_identity,
                ResourceLease.status == "ACTIVE",
            )
        )
        static_capability_ready = bool(
            capability is not None
            and capability.availability_status == "CONFIGURED"
            and capability.validation_status == "VALID"
            and capability.lifecycle_status == "ACTIVE"
        )
        currently_ready = bool(
            slot.lifecycle_status == "ACTIVE"
            and runner is not None
            and static_capability_ready
            and not runner_accept_new_execution_blockers(
                runner, project_lifecycle_status=project.lifecycle_status
            )
        )
        if not currently_ready:
            availability = "UNAVAILABLE"
        elif active_lease is not None:
            availability = "OCCUPIED"
        else:
            availability = "AVAILABLE"
        return ExecutionSlotResource(
            execution_slot_id=slot.execution_slot_id,
            project_id=slot.project_id,
            runner_id=slot.runner_id,
            slot_no=slot.slot_no,
            display_name=slot.display_name,
            lifecycle_status=slot.lifecycle_status,
            availability_status=availability,
            active_lease_owner=None if active_lease is None else active_lease.owner_id,
            row_version=slot.row_version,
            created_at=slot.created_at,
            updated_at=slot.updated_at,
        )


def _not_found() -> PlatformError:
    return PlatformError(
        title="Execution slot not found",
        detail="The requested execution slot is unavailable in the authorized Project scope.",
        status=404,
        code="EXECUTION_SLOT_NOT_FOUND",
    )
