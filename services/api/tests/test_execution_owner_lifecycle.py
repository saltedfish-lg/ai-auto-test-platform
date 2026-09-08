from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from platform_api.audit import AuditContext
from platform_api.execution_owner_transitions import (
    complete_execution_attempt,
    complete_run_task,
    prepare_execution_attempt,
    prepare_run_task,
    run_execution_attempt,
    run_run_task,
)
from platform_api.models import ExecutionOwnerAudit, OutboxEvent


class _EvidenceDB:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None

    def scalar(self, statement: object) -> int:
        del statement
        return len([item for item in self.added if isinstance(item, OutboxEvent)])


def _context() -> AuditContext:
    return AuditContext(correlation_id="corr-owner-lifecycle", source_context="test")


def _now() -> datetime:
    return datetime(2026, 9, 7, 0, 0, tzinfo=UTC)


def _task() -> SimpleNamespace:
    return SimpleNamespace(
        run_task_id="T" * 26,
        project_id="P" * 26,
        lifecycle_status="CREATED",
        task_state="CREATED",
        final_result="UNKNOWN",
        row_version=0,
        updated_at=_now(),
        updated_by=None,
    )


def _attempt() -> SimpleNamespace:
    return SimpleNamespace(
        execution_attempt_id="A" * 26,
        project_id="P" * 26,
        lifecycle_status="CREATED",
        execution_status="READY",
        finalization_status="INITIAL",
        row_version=0,
        updated_at=_now(),
        updated_by=None,
    )


def _edges(db: _EvidenceDB, aggregate_type: str) -> list[tuple[str | None, str | None]]:
    return [
        (item.previous_status, item.new_status)
        for item in db.added
        if isinstance(item, ExecutionOwnerAudit) and item.aggregate_type == aggregate_type
    ]


def test_ai_exploration_run_task_uses_full_canonical_success_path() -> None:
    db = _EvidenceDB()
    task = _task()
    prepare_run_task(
        db,
        task,
        actor_user_id="U" * 26,
        operation_id="create_execution_binding_snapshot",
        context=_context(),
        now=_now(),
    )
    assert task.lifecycle_status == "PREPARING"
    assert task.task_state == "WAITING_RESOURCE"
    run_run_task(
        db,
        task,
        actor_user_id="U" * 26,
        operation_id="start_ai_exploration_session",
        context=_context(),
        now=_now(),
    )
    complete_run_task(
        db,
        task,
        outcome="SUCCEEDED",
        actor_user_id="U" * 26,
        operation_id="start_ai_exploration_session",
        context=_context(),
        now=_now(),
    )
    assert task.lifecycle_status == "COMPLETED"
    assert task.task_state == "COMPLETED"
    assert task.final_result == "PASSED"
    assert _edges(db, "RUN_TASK") == [
        ("CREATED", "SNAPSHOTTED"),
        ("SNAPSHOTTED", "VALIDATING"),
        ("VALIDATING", "WAITING_RESOURCE"),
        ("WAITING_RESOURCE", "DISPATCHING"),
        ("DISPATCHING", "PREPARING"),
        ("PREPARING", "RUNNING"),
        ("RUNNING", "COMPLETED"),
    ]


def test_ai_exploration_attempt_uses_result_stage_before_completed() -> None:
    db = _EvidenceDB()
    attempt = _attempt()
    prepare_execution_attempt(
        db,
        attempt,
        actor_user_id="U" * 26,
        operation_id="create_execution_binding_snapshot",
        context=_context(),
        now=_now(),
    )
    run_execution_attempt(
        db,
        attempt,
        actor_user_id="U" * 26,
        operation_id="start_ai_exploration_session",
        context=_context(),
        now=_now(),
    )
    complete_execution_attempt(
        db,
        attempt,
        outcome="SUCCEEDED",
        actor_user_id="U" * 26,
        operation_id="start_ai_exploration_session",
        context=_context(),
        now=_now(),
    )
    assert attempt.lifecycle_status == "COMPLETED"
    assert attempt.execution_status == "SUCCEEDED"
    assert attempt.finalization_status == "COMPLETED"
    assert _edges(db, "EXECUTION_ATTEMPT") == [
        ("CREATED", "PREPARING"),
        ("PREPARING", "RUNNING"),
        ("RUNNING", "PASSED"),
        ("PASSED", "COMPLETED"),
    ]


def test_ai_exploration_cancellation_does_not_skip_canceling_or_canceled() -> None:
    db = _EvidenceDB()
    task = _task()
    attempt = _attempt()
    prepare_run_task(
        db, task, actor_user_id="U" * 26, operation_id="binding", context=_context(), now=_now()
    )
    prepare_execution_attempt(
        db,
        attempt,
        actor_user_id="U" * 26,
        operation_id="binding",
        context=_context(),
        now=_now(),
    )
    run_run_task(
        db, task, actor_user_id="U" * 26, operation_id="start", context=_context(), now=_now()
    )
    run_execution_attempt(
        db,
        attempt,
        actor_user_id="U" * 26,
        operation_id="start",
        context=_context(),
        now=_now(),
    )
    complete_execution_attempt(
        db,
        attempt,
        outcome="CANCELLED",
        actor_user_id="U" * 26,
        operation_id="cancel",
        context=_context(),
        now=_now(),
    )
    complete_run_task(
        db,
        task,
        outcome="CANCELLED",
        actor_user_id="U" * 26,
        operation_id="cancel",
        context=_context(),
        now=_now(),
    )
    assert _edges(db, "EXECUTION_ATTEMPT")[-2:] == [
        ("RUNNING", "CANCELED"),
        ("CANCELED", "COMPLETED"),
    ]
    assert _edges(db, "RUN_TASK")[-2:] == [
        ("RUNNING", "CANCELING"),
        ("CANCELING", "COMPLETED"),
    ]
    assert task.task_state == "CANCELED"
    assert task.final_result == "CANCELED"
