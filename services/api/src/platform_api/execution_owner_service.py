"""Formal provisioning of RunTask and ExecutionAttempt execution owners."""

from __future__ import annotations

import hashlib
from datetime import UTC

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticationService
from platform_api.errors import PlatformError
from platform_api.execution_owner_schemas import (
    CreateExecutionAttemptRequest,
    CreateRunTaskRequest,
    ExecutionAttemptListResponse,
    ExecutionAttemptResource,
    PageMeta,
    RunTaskListResponse,
    RunTaskResource,
    UpdateExecutionAttemptRequest,
    UpdateRunTaskRequest,
)
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    Environment,
    ExecutionAttempt,
    ExecutionOwnerAudit,
    OutboxEvent,
    Project,
    ResourceLease,
    RunTask,
    Runner,
)
from platform_api.runner_readiness import runner_accept_new_execution_blockers
from platform_api.security import new_ulid, utc_now


class ExecutionOwnerService:
    """Create execution owners without fabricating case-only execution objects."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def create_run_task(
        self,
        token: str,
        body: CreateRunTaskRequest,
        key: str,
        context: AuditContext,
    ) -> RunTaskResource:
        project_id = _required_id(body.project_id, "project_id")
        environment_id = _required_id(body.environment_id, "environment_id")
        if (
            body.run_task_id is not None
            or body.expected_version is not None
            or body.idempotency_key is not None
        ):
            raise _invalid_creation(
                "RunTask identity/version/idempotency are server controlled; use Idempotency-Key."
            )
        if body.task_state not in {None, "CREATED"} or body.final_result != "UNKNOWN":
            raise _invalid_creation("RunTask creation must start in CREATED/UNKNOWN.")
        with self._factory.begin() as db:
            actor = self._authenticate(
                db, token, "create_run_task", project_id, context, "RUN_TASK_CREATE"
            )
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "create_run_task",
                key,
                body.model_dump_json().encode("utf-8"),
            )
            if replay:
                run_task_id = str((record.response_json or {}).get("run_task_id", ""))
                return self._run_task_resource(self._run_task(db, run_task_id))

            project = db.get(Project, project_id)
            environment = db.get(Environment, environment_id)
            if project is None or project.lifecycle_status != "ACTIVE":
                raise _state_conflict("Project must exist and be ACTIVE.")
            if (
                environment is None
                or environment.project_id != project_id
                or environment.lifecycle_status != "ACTIVE"
                or environment.enablement_state != "ENABLED"
            ):
                raise _state_conflict(
                    "Environment must belong to the Project and be ACTIVE and ENABLED."
                )
            if body.case_suite_id is not None:
                _require_scoped_reference(
                    db,
                    table="atp_case_suite",
                    id_column="case_suite_id",
                    reference_id=body.case_suite_id,
                    project_id=project_id,
                    label="CaseSuite",
                )

            now = utc_now()
            task = RunTask(
                run_task_id=new_ulid(),
                project_id=project_id,
                idempotency_key=_scoped_business_key(project_id, key),
                case_suite_id=body.case_suite_id,
                environment_id=environment_id,
                task_type=body.task_type,
                lifecycle_status="CREATED",
                task_state="CREATED",
                final_result="UNKNOWN",
                display_name=body.display_name,
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json=None,
            )
            db.add(task)
            try:
                db.flush()
            except IntegrityError as error:
                raise _persistence_conflict(error) from None
            self._audit(
                db,
                task.project_id,
                "RUN_TASK",
                task.run_task_id,
                "create_run_task",
                "RUN_TASK_CREATED",
                actor.user.user_id,
                None,
                "CREATED",
                body.reason,
                context,
                now,
            )
            self._event(
                db,
                task.run_task_id,
                task.project_id,
                "run_task.created",
                key,
                context,
                now,
                {
                    "run_task_id": task.run_task_id,
                    "project_id": task.project_id,
                    "environment_id": task.environment_id,
                    "case_suite_id": task.case_suite_id,
                    "task_type": task.task_type,
                    "lifecycle_status": task.lifecycle_status,
                    "task_state": task.task_state,
                },
            )
            self._idempotency.complete(record, 202, {"run_task_id": task.run_task_id})
            return self._run_task_resource(task)

    def create_execution_attempt(
        self,
        token: str,
        body: CreateExecutionAttemptRequest,
        key: str,
        context: AuditContext,
    ) -> ExecutionAttemptResource:
        run_task_id = _required_id(body.run_task_id, "run_task_id")
        runner_id = _required_id(body.runner_id, "runner_id")
        if (
            body.execution_attempt_id is not None
            or body.expected_version is not None
            or body.attempt_no is not None
        ):
            raise _invalid_creation(
                "ExecutionAttempt identity/version/attempt number are server controlled."
            )
        with self._factory.begin() as db:
            task = db.scalar(
                select(RunTask).where(RunTask.run_task_id == run_task_id).with_for_update()
            )
            if task is None or task.project_id is None:
                raise _not_found("RunTask does not exist.")
            actor = self._authenticate(
                db,
                token,
                "create_execution_attempt",
                task.project_id,
                context,
                "PROJECT_EDIT",
            )
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "create_execution_attempt",
                key,
                body.model_dump_json().encode("utf-8"),
            )
            if replay:
                attempt_id = str((record.response_json or {}).get("execution_attempt_id", ""))
                return self._attempt_resource(self._attempt(db, attempt_id))
            if task.lifecycle_status not in {
                "CREATED",
                "SNAPSHOTTED",
                "VALIDATING",
                "WAITING_RESOURCE",
                "PREPARING",
            }:
                raise _state_conflict("RunTask is not eligible for a new ExecutionAttempt.")
            runner = db.get(Runner, runner_id)
            project = db.get(Project, task.project_id)
            if runner is None:
                blockers = ["runner=MISSING"]
            elif runner.project_id != task.project_id:
                blockers = [f"project_id={runner.project_id}"]
            else:
                blockers = runner_accept_new_execution_blockers(
                    runner,
                    project_lifecycle_status=project.lifecycle_status if project else None,
                )
            if blockers:
                raise _state_conflict(
                    "Runner is not eligible for a new execution: " + "; ".join(blockers) + "."
                )
            _validate_optional_attempt_references(db, body, task)
            existing_count = int(
                db.scalar(
                    select(func.count(ExecutionAttempt.execution_attempt_id)).where(
                        ExecutionAttempt.run_task_id == run_task_id
                    )
                )
                or 0
            )
            attempt_no = str(existing_count + 1)
            now = utc_now()
            attempt = ExecutionAttempt(
                execution_attempt_id=new_ulid(),
                execution_binding_snapshot_id=None,
                project_id=task.project_id,
                run_task_id=task.run_task_id,
                attempt_no=attempt_no,
                case_attempt_id=body.case_attempt_id,
                runner_id=runner_id,
                configuration_snapshot_id=body.configuration_snapshot_id,
                execution_batch_id=body.execution_batch_id,
                lease_id=body.lease_id,
                execution_lock_id=body.execution_lock_id,
                execution_status="READY",
                finalization_status="INITIAL",
                lifecycle_status="CREATED",
                display_name=body.display_name,
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json=None,
            )
            db.add(attempt)
            try:
                db.flush()
            except IntegrityError as error:
                raise _persistence_conflict(error) from None
            self._audit(
                db,
                task.project_id,
                "EXECUTION_ATTEMPT",
                attempt.execution_attempt_id,
                "create_execution_attempt",
                "EXECUTION_ATTEMPT_CREATED",
                actor.user.user_id,
                None,
                "READY",
                body.reason,
                context,
                now,
            )
            self._event(
                db,
                attempt.execution_attempt_id,
                task.project_id,
                "execution_attempt.created",
                key,
                context,
                now,
                {
                    "execution_attempt_id": attempt.execution_attempt_id,
                    "run_task_id": task.run_task_id,
                    "runner_id": runner_id,
                    "attempt_no": attempt.attempt_no,
                    "execution_status": attempt.execution_status,
                    "lifecycle_status": attempt.lifecycle_status,
                },
            )
            self._idempotency.complete(
                record, 201, {"execution_attempt_id": attempt.execution_attempt_id}
            )
            return self._attempt_resource(attempt)

    def list_run_tasks(
        self, token: str, page: int, page_size: int, context: AuditContext
    ) -> RunTaskListResponse:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_run_task", context
            )
            visible = self._authentication.authorized_project_ids_in_transaction(
                db, actor, "PROJECT_VIEW"
            )
            query = select(RunTask)
            count = select(func.count(RunTask.run_task_id))
            if visible is not None:
                if not visible:
                    return RunTaskListResponse(
                        items=[], page=PageMeta(page=page, page_size=page_size, total=0)
                    )
                query = query.where(RunTask.project_id.in_(visible))
                count = count.where(RunTask.project_id.in_(visible))
            total = int(db.scalar(count) or 0)
            rows = list(
                db.scalars(
                    query.order_by(RunTask.updated_at.desc(), RunTask.run_task_id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return RunTaskListResponse(
                items=[self._run_task_resource(row) for row in rows],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get_run_task(self, token: str, task_id: str, context: AuditContext) -> RunTaskResource:
        with self._factory() as db:
            task = self._run_task(db, task_id)
            if task.project_id is None:
                raise _state_conflict("RunTask has no Project owner.")
            self._authenticate(db, token, "get_run_task", task.project_id, context, "PROJECT_VIEW")
            return self._run_task_resource(task)

    def update_run_task(
        self,
        token: str,
        task_id: str,
        body: UpdateRunTaskRequest,
        key: str,
        context: AuditContext,
    ) -> RunTaskResource:
        with self._factory.begin() as db:
            task = db.scalar(select(RunTask).where(RunTask.run_task_id == task_id).with_for_update())
            if task is None or task.project_id is None:
                raise _not_found("RunTask does not exist.")
            actor = self._authenticate(
                db, token, "update_run_task", task.project_id, context, "RUN_TASK_CREATE"
            )
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "update_run_task",
                key,
                (task_id + "\n" + body.model_dump_json()).encode("utf-8"),
            )
            if replay:
                return self._run_task_resource(task)
            _assert_version(task.row_version, body.expected_version, "RunTask")
            _assert_unchanged("project_id", body.project_id, task.project_id)
            _assert_unchanged("idempotency_key", body.idempotency_key, task.idempotency_key)
            _assert_unchanged("case_suite_id", body.case_suite_id, task.case_suite_id)
            _assert_unchanged("environment_id", body.environment_id, task.environment_id)
            _assert_unchanged("task_state", body.task_state, task.task_state)
            _assert_unchanged("final_result", body.final_result, task.final_result)
            previous = task.lifecycle_status
            task.display_name = body.display_name
            task.row_version += 1
            task.updated_at = utc_now()
            task.updated_by = actor.user.user_id
            self._audit(
                db,
                task.project_id,
                "RUN_TASK",
                task.run_task_id,
                "update_run_task",
                "RUN_TASK_UPDATED",
                actor.user.user_id,
                previous,
                task.lifecycle_status,
                body.reason,
                context,
                task.updated_at,
            )
            self._idempotency.complete(record, 200, {"run_task_id": task.run_task_id})
            return self._run_task_resource(task)

    def list_execution_attempts(
        self, token: str, page: int, page_size: int, context: AuditContext
    ) -> ExecutionAttemptListResponse:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_execution_attempt", context
            )
            visible = self._authentication.authorized_project_ids_in_transaction(
                db, actor, "PROJECT_VIEW"
            )
            query = select(ExecutionAttempt)
            count = select(func.count(ExecutionAttempt.execution_attempt_id))
            if visible is not None:
                if not visible:
                    return ExecutionAttemptListResponse(
                        items=[], page=PageMeta(page=page, page_size=page_size, total=0)
                    )
                query = query.where(ExecutionAttempt.project_id.in_(visible))
                count = count.where(ExecutionAttempt.project_id.in_(visible))
            total = int(db.scalar(count) or 0)
            rows = list(
                db.scalars(
                    query.order_by(ExecutionAttempt.updated_at.desc(), ExecutionAttempt.execution_attempt_id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return ExecutionAttemptListResponse(
                items=[self._attempt_resource(row) for row in rows],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get_execution_attempt(
        self, token: str, attempt_id: str, context: AuditContext
    ) -> ExecutionAttemptResource:
        with self._factory() as db:
            attempt = self._attempt(db, attempt_id)
            if attempt.project_id is None:
                raise _state_conflict("ExecutionAttempt has no Project owner.")
            self._authenticate(
                db, token, "get_execution_attempt", attempt.project_id, context, "PROJECT_VIEW"
            )
            return self._attempt_resource(attempt)

    def update_execution_attempt(
        self,
        token: str,
        attempt_id: str,
        body: UpdateExecutionAttemptRequest,
        key: str,
        context: AuditContext,
    ) -> ExecutionAttemptResource:
        with self._factory.begin() as db:
            attempt = db.scalar(
                select(ExecutionAttempt)
                .where(ExecutionAttempt.execution_attempt_id == attempt_id)
                .with_for_update()
            )
            if attempt is None or attempt.project_id is None:
                raise _not_found("ExecutionAttempt does not exist.")
            actor = self._authenticate(
                db,
                token,
                "update_execution_attempt",
                attempt.project_id,
                context,
                "PROJECT_EDIT",
            )
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "update_execution_attempt",
                key,
                (attempt_id + "\n" + body.model_dump_json()).encode("utf-8"),
            )
            if replay:
                return self._attempt_resource(attempt)
            _assert_version(attempt.row_version, body.expected_version, "ExecutionAttempt")
            for field in (
                "run_task_id",
                "attempt_no",
                "case_attempt_id",
                "runner_id",
                "configuration_snapshot_id",
                "execution_batch_id",
                "lease_id",
                "execution_lock_id",
            ):
                _assert_unchanged(field, getattr(body, field), getattr(attempt, field))
            previous = attempt.lifecycle_status
            attempt.display_name = body.display_name
            attempt.row_version += 1
            attempt.updated_at = utc_now()
            attempt.updated_by = actor.user.user_id
            self._audit(
                db,
                attempt.project_id,
                "EXECUTION_ATTEMPT",
                attempt.execution_attempt_id,
                "update_execution_attempt",
                "EXECUTION_ATTEMPT_UPDATED",
                actor.user.user_id,
                previous,
                attempt.lifecycle_status,
                body.reason,
                context,
                attempt.updated_at,
            )
            self._idempotency.complete(
                record, 200, {"execution_attempt_id": attempt.execution_attempt_id}
            )
            return self._attempt_resource(attempt)

    def _authenticate(
        self,
        db: Session,
        token: str,
        operation: str,
        project_id: str,
        context: AuditContext,
        permission: str,
    ):
        actor = self._authentication.authenticate_access_in_transaction(db, token, operation, context)
        self._authentication.require_project_permissions_in_transaction(
            db, actor, operation, (permission,), project_id, context
        )
        return actor

    @staticmethod
    def _run_task(db: Session, task_id: str) -> RunTask:
        row = db.get(RunTask, task_id)
        if row is None:
            raise _not_found("RunTask does not exist.")
        return row

    @staticmethod
    def _attempt(db: Session, attempt_id: str) -> ExecutionAttempt:
        row = db.get(ExecutionAttempt, attempt_id)
        if row is None:
            raise _not_found("ExecutionAttempt does not exist.")
        return row

    @staticmethod
    def _run_task_resource(row: RunTask) -> RunTaskResource:
        return RunTaskResource(
            run_task_id=row.run_task_id,
            display_name=row.display_name,
            row_version=row.row_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            project_id=row.project_id,
            idempotency_key=row.idempotency_key,
            case_suite_id=row.case_suite_id,
            environment_id=row.environment_id,
            task_type=row.task_type,
            lifecycle_status=row.lifecycle_status,
            task_state=row.task_state,
            final_result=row.final_result,
        )

    @staticmethod
    def _attempt_resource(row: ExecutionAttempt) -> ExecutionAttemptResource:
        return ExecutionAttemptResource(
            execution_attempt_id=row.execution_attempt_id,
            execution_binding_snapshot_id=row.execution_binding_snapshot_id,
            display_name=row.display_name,
            row_version=row.row_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            project_id=row.project_id,
            run_task_id=row.run_task_id,
            attempt_no=row.attempt_no,
            case_attempt_id=row.case_attempt_id,
            runner_id=row.runner_id,
            configuration_snapshot_id=row.configuration_snapshot_id,
            execution_batch_id=row.execution_batch_id,
            lease_id=row.lease_id,
            execution_lock_id=row.execution_lock_id,
            execution_status=row.execution_status,
            finalization_status=row.finalization_status,
            lifecycle_status=row.lifecycle_status,
        )

    @staticmethod
    def _audit(
        db: Session,
        project_id: str,
        aggregate_type: str,
        aggregate_id: str,
        operation_id: str,
        action: str,
        actor_user_id: str,
        previous_status: str | None,
        new_status: str | None,
        reason: str | None,
        context: AuditContext,
        now,
    ) -> None:
        db.add(
            ExecutionOwnerAudit(
                audit_id=new_ulid(),
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                operation_id=operation_id,
                action=action,
                actor_user_id=actor_user_id,
                previous_status=previous_status,
                new_status=new_status,
                result_code="SUCCESS",
                reason=reason,
                correlation_id=context.correlation_id,
                occurred_at=now,
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
            )
        )

    @staticmethod
    def _event(
        db: Session,
        aggregate_id: str,
        project_id: str,
        event_type: str,
        causation_id: str,
        context: AuditContext,
        now,
        payload: dict[str, object],
    ) -> None:
        event_id = new_ulid()
        db.add(
            OutboxEvent(
                event_id=event_id,
                aggregate_id=aggregate_id,
                sequence=1,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": now.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": aggregate_id,
                    "sequence": 1,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": project_id,
                    "payload": payload,
                },
                occurred_at=now,
                published_at=None,
                attempt_count=0,
            )
        )


def _validate_optional_attempt_references(
    db: Session, body: CreateExecutionAttemptRequest, task: RunTask
) -> None:
    """Fail closed when optional legacy execution relationships cross Project/RunTask scope."""
    if task.project_id is None:
        raise _state_conflict("RunTask has no Project owner.")
    scoped = (
        ("case_attempt_id", "atp_case_attempt", "case_attempt_id", "CaseAttempt", True),
        (
            "configuration_snapshot_id",
            "atp_configuration_snapshot",
            "configuration_snapshot_id",
            "ConfigurationSnapshot",
            True,
        ),
        ("execution_batch_id", "atp_execution_batch", "execution_batch_id", "ExecutionBatch", True),
        ("execution_lock_id", "atp_execution_lock", "execution_lock_id", "ExecutionLock", False),
    )
    for field, table, id_column, label, require_task in scoped:
        reference_id = getattr(body, field)
        if reference_id is None:
            continue
        _require_scoped_reference(
            db,
            table=table,
            id_column=id_column,
            reference_id=reference_id,
            project_id=task.project_id,
            label=label,
            run_task_id=task.run_task_id if require_task else None,
        )
    if body.lease_id is not None:
        lease = db.get(ResourceLease, body.lease_id)
        if lease is None or lease.project_id != task.project_id:
            raise _state_conflict("ResourceLease must belong to the same Project as the RunTask.")


def _require_scoped_reference(
    db: Session,
    *,
    table: str,
    id_column: str,
    reference_id: str,
    project_id: str,
    label: str,
    run_task_id: str | None = None,
) -> None:
    # table/id_column are internal constants only; caller values remain bound parameters.
    columns = "project_id" + (", run_task_id" if run_task_id is not None else "")
    row = db.execute(
        text(f"SELECT {columns} FROM {table} WHERE {id_column} = :reference_id"),
        {"reference_id": reference_id},
    ).mappings().first()
    if row is None or row.get("project_id") != project_id:
        raise _state_conflict(f"{label} must belong to the same Project as the RunTask.")
    if run_task_id is not None and row.get("run_task_id") != run_task_id:
        raise _state_conflict(f"{label} must belong to the same RunTask.")


def _required_id(value: str | None, field: str) -> str:
    if value is None or len(value) != 26:
        raise _invalid_creation(f"{field} is required and must be a 26-character id.")
    return value


def _scoped_business_key(project_id: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{project_id}:{digest}"


def _assert_version(actual: int, expected: int, label: str) -> None:
    if actual != expected:
        raise PlatformError(
            title=f"{label} concurrency conflict",
            detail=f"{label} changed after it was loaded.",
            status=409,
            code="EXECUTION_OWNER_CONCURRENCY_CONFLICT",
        )


def _assert_unchanged(field: str, requested: object, actual: object) -> None:
    if requested is not None and requested != actual:
        raise _state_conflict(f"{field} is immutable through the generic metadata update command.")


def _invalid_creation(detail: str) -> PlatformError:
    return PlatformError(
        title="Execution owner request invalid",
        detail=detail,
        status=400,
        code="EXECUTION_OWNER_REQUEST_INVALID",
    )


def _not_found(detail: str) -> PlatformError:
    return PlatformError(
        title="Execution owner not found",
        detail=detail,
        status=404,
        code="EXECUTION_OWNER_NOT_FOUND",
    )


def _state_conflict(detail: str) -> PlatformError:
    return PlatformError(
        title="Execution owner state conflict",
        detail=detail,
        status=409,
        code="EXECUTION_OWNER_STATE_CONFLICT",
    )


def _persistence_conflict(_error: IntegrityError) -> PlatformError:
    return PlatformError(
        title="Execution owner persistence conflict",
        detail="Execution owner persistence rejected the requested relationship or uniqueness constraint.",
        status=409,
        code="EXECUTION_OWNER_PERSISTENCE_CONFLICT",
    )
