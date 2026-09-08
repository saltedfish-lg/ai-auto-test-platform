"""Canonical RunTask/ExecutionAttempt lifecycle transitions with durable evidence.

The helpers in this module keep AI exploration and binding orchestration on the
existing LC-035 / LC-036 lifecycle paths.  They deliberately do not select a
Runner or schedule work; they only project lifecycle stages for work whose
resources/binding have already been resolved by the caller.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from platform_api.audit import AuditContext
from platform_api.models import ExecutionAttempt, ExecutionOwnerAudit, OutboxEvent, RunTask
from platform_api.security import new_ulid

_RUN_TASK_PREPARATION_PATH: tuple[tuple[str, str, str], ...] = (
    ("SNAPSHOTTED", "run_task.snapshotted", "RUN_TASK_SNAPSHOTTED"),
    ("VALIDATING", "run_task.validating", "RUN_TASK_VALIDATING"),
    ("WAITING_RESOURCE", "run_task.waiting_resource", "RUN_TASK_WAITING_RESOURCE"),
    ("DISPATCHING", "run_task.dispatching", "RUN_TASK_DISPATCHING"),
    ("PREPARING", "run_task.preparing", "RUN_TASK_PREPARING"),
)
_RUN_TASK_PREPARATION_ORDER = (
    "CREATED",
    *(item[0] for item in _RUN_TASK_PREPARATION_PATH),
)


def prepare_run_task(
    db: Session,
    task: RunTask,
    *,
    actor_user_id: str,
    operation_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object] | None = None,
) -> None:
    """Advance an execution task through LC-035 to PREPARING without skipping stages."""

    if task.lifecycle_status == "PREPARING":
        return
    try:
        start_index = _RUN_TASK_PREPARATION_ORDER.index(task.lifecycle_status)
    except ValueError as exc:
        raise RuntimeError(
            f"RunTask cannot enter preparation from {task.lifecycle_status}."
        ) from exc
    if start_index >= len(_RUN_TASK_PREPARATION_ORDER) - 1:
        return
    summary = dict(change_summary or {})
    for target, event_type, action in _RUN_TASK_PREPARATION_PATH[start_index:]:
        if target == "WAITING_RESOURCE":
            task.task_state = "WAITING_RESOURCE"
        _transition(
            db,
            aggregate=task,
            aggregate_type="RUN_TASK",
            project_id=_required_project(task.project_id, "RunTask"),
            target_status=target,
            event_type=event_type,
            action=action,
            operation_id=operation_id,
            actor_user_id=actor_user_id,
            context=context,
            now=now,
            change_summary={"task_state": task.task_state, **summary},
        )


def run_run_task(
    db: Session,
    task: RunTask,
    *,
    actor_user_id: str,
    operation_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object] | None = None,
) -> None:
    """Apply LC-035 PREPARING -> RUNNING."""

    if task.lifecycle_status != "PREPARING":
        raise RuntimeError(
            f"RunTask must be PREPARING before RUNNING, got {task.lifecycle_status}."
        )
    task.task_state = "RUNNING"
    task.final_result = "UNKNOWN"
    _transition(
        db,
        aggregate=task,
        aggregate_type="RUN_TASK",
        project_id=_required_project(task.project_id, "RunTask"),
        target_status="RUNNING",
        event_type="run_task.running",
        action="RUN_TASK_RUNNING",
        operation_id=operation_id,
        actor_user_id=actor_user_id,
        context=context,
        now=now,
        change_summary={"task_state": task.task_state, **dict(change_summary or {})},
    )


def complete_run_task(
    db: Session,
    task: RunTask,
    *,
    outcome: str,
    actor_user_id: str,
    operation_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object] | None = None,
) -> None:
    """Complete LC-035; cancellation preserves RUNNING -> CANCELING -> COMPLETED."""

    if task.lifecycle_status != "RUNNING":
        raise RuntimeError(
            f"RunTask must be RUNNING before completion, got {task.lifecycle_status}."
        )
    summary = dict(change_summary or {})
    if outcome == "CANCELLED":
        _transition(
            db,
            aggregate=task,
            aggregate_type="RUN_TASK",
            project_id=_required_project(task.project_id, "RunTask"),
            target_status="CANCELING",
            event_type="run_task.canceling",
            action="RUN_TASK_CANCELING",
            operation_id=operation_id,
            actor_user_id=actor_user_id,
            context=context,
            now=now,
            change_summary={"task_state": task.task_state, **summary},
        )
        task.task_state = "CANCELED"
        task.final_result = "CANCELED"
    else:
        task.task_state = "COMPLETED"
        task.final_result = "PASSED" if outcome == "SUCCEEDED" else "FAILED"
    _transition(
        db,
        aggregate=task,
        aggregate_type="RUN_TASK",
        project_id=_required_project(task.project_id, "RunTask"),
        target_status="COMPLETED",
        event_type="run_task.completed",
        action="RUN_TASK_COMPLETED",
        operation_id=operation_id,
        actor_user_id=actor_user_id,
        context=context,
        now=now,
        change_summary={
            "task_state": task.task_state,
            "final_result": task.final_result,
            **summary,
        },
    )


def prepare_execution_attempt(
    db: Session,
    attempt: ExecutionAttempt,
    *,
    actor_user_id: str,
    operation_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object] | None = None,
) -> None:
    """Apply LC-036 CREATED -> PREPARING, idempotently for an already prepared attempt."""

    if attempt.lifecycle_status == "PREPARING":
        return
    if attempt.lifecycle_status != "CREATED":
        raise RuntimeError(
            f"ExecutionAttempt cannot enter preparation from {attempt.lifecycle_status}."
        )
    _transition(
        db,
        aggregate=attempt,
        aggregate_type="EXECUTION_ATTEMPT",
        project_id=_required_project(attempt.project_id, "ExecutionAttempt"),
        target_status="PREPARING",
        event_type="execution_attempt.preparing",
        action="EXECUTION_ATTEMPT_PREPARING",
        operation_id=operation_id,
        actor_user_id=actor_user_id,
        context=context,
        now=now,
        change_summary={"execution_status": attempt.execution_status, **dict(change_summary or {})},
    )


def run_execution_attempt(
    db: Session,
    attempt: ExecutionAttempt,
    *,
    actor_user_id: str,
    operation_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object] | None = None,
) -> None:
    """Apply LC-036 PREPARING -> RUNNING."""

    if attempt.lifecycle_status != "PREPARING":
        raise RuntimeError(
            f"ExecutionAttempt must be PREPARING before RUNNING, got {attempt.lifecycle_status}."
        )
    attempt.execution_status = "RUNNING"
    _transition(
        db,
        aggregate=attempt,
        aggregate_type="EXECUTION_ATTEMPT",
        project_id=_required_project(attempt.project_id, "ExecutionAttempt"),
        target_status="RUNNING",
        event_type="execution_attempt.running",
        action="EXECUTION_ATTEMPT_RUNNING",
        operation_id=operation_id,
        actor_user_id=actor_user_id,
        context=context,
        now=now,
        change_summary={"execution_status": attempt.execution_status, **dict(change_summary or {})},
    )


def complete_execution_attempt(
    db: Session,
    attempt: ExecutionAttempt,
    *,
    outcome: str,
    actor_user_id: str,
    operation_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object] | None = None,
) -> None:
    """Apply LC-036 RUNNING -> result stage -> COMPLETED without collapsing stages."""

    if attempt.lifecycle_status != "RUNNING":
        raise RuntimeError(
            f"ExecutionAttempt must be RUNNING before completion, got {attempt.lifecycle_status}."
        )
    terminal = {
        "SUCCEEDED": ("PASSED", "execution_attempt.passed", "EXECUTION_ATTEMPT_PASSED"),
        "FAILED": ("FAILED", "execution_attempt.failed", "EXECUTION_ATTEMPT_FAILED"),
        "CANCELLED": ("CANCELED", "execution_attempt.canceled", "EXECUTION_ATTEMPT_CANCELED"),
    }.get(outcome)
    if terminal is None:
        raise RuntimeError(f"Unsupported ExecutionAttempt outcome: {outcome}.")
    result_stage, event_type, action = terminal
    attempt.execution_status = outcome
    summary = dict(change_summary or {})
    _transition(
        db,
        aggregate=attempt,
        aggregate_type="EXECUTION_ATTEMPT",
        project_id=_required_project(attempt.project_id, "ExecutionAttempt"),
        target_status=result_stage,
        event_type=event_type,
        action=action,
        operation_id=operation_id,
        actor_user_id=actor_user_id,
        context=context,
        now=now,
        change_summary={
            "execution_status": attempt.execution_status,
            "finalization_status": attempt.finalization_status,
            **summary,
        },
    )
    attempt.finalization_status = "COMPLETED"
    _transition(
        db,
        aggregate=attempt,
        aggregate_type="EXECUTION_ATTEMPT",
        project_id=_required_project(attempt.project_id, "ExecutionAttempt"),
        target_status="COMPLETED",
        event_type="execution_attempt.completed",
        action="EXECUTION_ATTEMPT_COMPLETED",
        operation_id=operation_id,
        actor_user_id=actor_user_id,
        context=context,
        now=now,
        change_summary={
            "execution_status": attempt.execution_status,
            "finalization_status": attempt.finalization_status,
            **summary,
        },
    )


def append_transition_evidence(
    db: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    project_id: str,
    event_type: str,
    operation_id: str,
    action: str,
    actor_user_id: str,
    previous_status: str | None,
    new_status: str,
    expected_version: int,
    new_version: int,
    change_summary: dict[str, object],
    context: AuditContext,
    now: datetime,
) -> None:
    """Append the common immutable audit/outbox evidence for one lifecycle edge."""

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
            reason=None,
            correlation_id=context.correlation_id,
            occurred_at=now,
            source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
        )
    )
    # SessionFactory disables autoflush. Flush pending lifecycle evidence before
    # deriving the next durable Outbox sequence so consecutive transitions in
    # one transaction cannot observe the same persisted MAX(sequence).
    db.flush()
    sequence = (
        int(
            db.scalar(
                select(func.max(OutboxEvent.sequence)).where(
                    OutboxEvent.aggregate_id == aggregate_id
                )
            )
            or 0
        )
        + 1
    )
    event_id = new_ulid()
    id_field = "run_task_id" if aggregate_type == "RUN_TASK" else "execution_attempt_id"
    db.add(
        OutboxEvent(
            event_id=event_id,
            aggregate_id=aggregate_id,
            sequence=sequence,
            event_type=event_type,
            payload_json={
                "event_id": event_id,
                "event_type": event_type,
                "event_version": "1.0.0",
                "occurred_at": now.replace(tzinfo=UTC).isoformat(),
                "aggregate_id": aggregate_id,
                "sequence": sequence,
                "correlation_id": context.correlation_id,
                "causation_id": context.correlation_id,
                "project_id": project_id,
                "payload": {
                    id_field: aggregate_id,
                    "project_id": project_id,
                    "from_state": previous_status,
                    "to_state": new_status,
                    "expected_version": expected_version,
                    "new_version": new_version,
                    "changed_by": actor_user_id,
                    "change_summary": change_summary,
                },
            },
            occurred_at=now,
            published_at=None,
            attempt_count=0,
        )
    )


def _transition(
    db: Session,
    *,
    aggregate: RunTask | ExecutionAttempt,
    aggregate_type: str,
    project_id: str,
    target_status: str,
    event_type: str,
    action: str,
    operation_id: str,
    actor_user_id: str,
    context: AuditContext,
    now: datetime,
    change_summary: dict[str, object],
) -> None:
    previous = aggregate.lifecycle_status
    expected_version = aggregate.row_version
    aggregate.lifecycle_status = target_status
    aggregate.row_version += 1
    aggregate.updated_at = now
    aggregate.updated_by = actor_user_id
    append_transition_evidence(
        db,
        aggregate_type=aggregate_type,
        aggregate_id=(
            aggregate.run_task_id
            if aggregate_type == "RUN_TASK"
            else aggregate.execution_attempt_id
        ),
        project_id=project_id,
        event_type=event_type,
        operation_id=operation_id,
        action=action,
        actor_user_id=actor_user_id,
        previous_status=previous,
        new_status=target_status,
        expected_version=expected_version,
        new_version=aggregate.row_version,
        change_summary=change_summary,
        context=context,
        now=now,
    )


def _required_project(project_id: str | None, label: str) -> str:
    if not project_id:
        raise RuntimeError(f"{label} has no Project identity.")
    return project_id
