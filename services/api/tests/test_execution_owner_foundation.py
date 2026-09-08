from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_api.execution_owner_router import router
from platform_api.execution_owner_schemas import (
    CreateExecutionAttemptRequest,
    CreateRunTaskRequest,
    ExecutionAttemptResource,
    RunTaskResource,
)
from platform_api.audit import AuditContext
from platform_api.errors import PlatformError
from platform_api.execution_owner_service import (
    ExecutionOwnerService,
    _require_scoped_reference,
    _required_id,
    _scoped_business_key,
)
from platform_api.models import ExecutionAttempt, ExecutionOwnerAudit, Project, RunTask, Runner
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "docs"
    / "authority"
    / "编码权威事实"
    / "DATABASE_DDL"
    / "V21__ai_exploration_execution_owner_provisioning.sql"
)
AI_AUTHORITY = (
    ROOT
    / "docs"
    / "authority"
    / "编码权威事实"
    / "AI_EXPLORATION_FOUNDATION"
    / "ai-exploration-foundation.yaml"
)


def test_execution_owner_routes_match_existing_public_contract() -> None:
    operations = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert operations == {
        ("GET", "/api/v1/run-task", "list_run_task"),
        ("POST", "/api/v1/run-task", "create_run_task"),
        ("GET", "/api/v1/run-task/{id}", "get_run_task"),
        ("PATCH", "/api/v1/run-task/{id}", "update_run_task"),
        ("GET", "/api/v1/execution-attempt", "list_execution_attempt"),
        ("POST", "/api/v1/execution-attempt", "create_execution_attempt"),
        ("GET", "/api/v1/execution-attempt/{id}", "get_execution_attempt"),
        ("PATCH", "/api/v1/execution-attempt/{id}", "update_execution_attempt"),
    }

    status_codes = {route.operation_id: route.status_code for route in router.routes}
    assert status_codes["create_run_task"] == 202
    assert status_codes["create_execution_attempt"] == 201


def test_ai_exploration_owner_contract_does_not_require_case_only_objects() -> None:
    run = CreateRunTaskRequest.model_validate(
        {"project_id": "P" * 26, "environment_id": "E" * 26, "task_type": "AI_EXPLORATION", "final_result": "UNKNOWN"}
    )
    attempt = CreateExecutionAttemptRequest.model_validate(
        {"run_task_id": "Q" * 26, "runner_id": "R" * 26}
    )
    assert run.case_suite_id is None
    assert run.task_type == "AI_EXPLORATION"
    assert attempt.case_attempt_id is None
    assert attempt.configuration_snapshot_id is None
    assert attempt.execution_batch_id is None


def test_execution_owner_orm_projects_v21_nullable_case_relationships() -> None:
    assert RunTask.__table__.c.case_suite_id.nullable is True
    for column in ("case_attempt_id", "configuration_snapshot_id", "execution_batch_id"):
        assert ExecutionAttempt.__table__.c[column].nullable is True
    assert ExecutionOwnerAudit.__table__.c.audit_id.primary_key is True


def test_v21_relaxes_only_case_specific_owner_dependencies_and_adds_audit() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "MODIFY COLUMN case_suite_id VARCHAR(26) NULL" in sql
    assert "MODIFY COLUMN case_attempt_id VARCHAR(26) NULL" in sql
    assert "MODIFY COLUMN configuration_snapshot_id VARCHAR(26) NULL" in sql
    assert "MODIFY COLUMN execution_batch_id VARCHAR(26) NULL" in sql
    assert "CREATE TABLE atp_execution_owner_audit" in sql
    assert "trg_atp_execution_owner_audit_no_update" in sql
    assert "trg_atp_execution_owner_audit_no_delete" in sql
    assert "runner_id" not in "\n".join(
        line for line in sql.splitlines() if "MODIFY COLUMN" in line
    )


def test_ai_authority_forbids_fake_case_placeholders_for_exploration() -> None:
    authority = AI_AUTHORITY.read_text(encoding="utf-8")
    assert "AI探索的RunTask不要求CaseSuite" in authority
    assert "CaseAttempt与ExecutionBatch只属于正式用例执行" in authority
    assert "create_run_task与create_execution_attempt" in authority


def test_business_key_is_project_scoped_and_does_not_store_raw_idempotency_key() -> None:
    key = "same-client-key"
    first = _scoped_business_key("P" * 26, key)
    second = _scoped_business_key("Q" * 26, key)
    assert first != second
    assert key not in first
    assert len(first) <= 191


def test_required_id_fails_closed() -> None:
    with pytest.raises(Exception):
        _required_id("too-short", "project_id")


def test_resources_keep_contract_state_enums() -> None:
    task = RunTaskResource.model_validate(
        {
            "run_task_id": "Q" * 26,
            "row_version": 0,
            "created_at": "2026-09-07T00:00:00Z",
            "updated_at": "2026-09-07T00:00:00Z",
            "project_id": "P" * 26,
            "environment_id": "E" * 26,
            "lifecycle_status": "CREATED",
            "task_state": "CREATED",
            "final_result": "UNKNOWN",
        }
    )
    assert task.lifecycle_status == "CREATED"
    attempt = ExecutionAttemptResource.model_validate(
        {
            "execution_attempt_id": "A" * 26,
            "row_version": 0,
            "created_at": "2026-09-07T00:00:00Z",
            "updated_at": "2026-09-07T00:00:00Z",
            "project_id": "P" * 26,
            "run_task_id": "Q" * 26,
            "attempt_no": "1",
            "runner_id": "R" * 26,
            "execution_status": "READY",
            "finalization_status": "INITIAL",
            "lifecycle_status": "CREATED",
        }
    )
    assert attempt.execution_status == "READY"
    with pytest.raises(ValidationError):
        ExecutionAttemptResource.model_validate({**attempt.model_dump(), "execution_status": "QUEUED"})


class _MappingResult:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _ReferenceSession:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.params: dict[str, object] | None = None

    def execute(self, statement, params):
        del statement
        self.params = params
        return _MappingResult(self.row)


def test_scoped_reference_validation_rejects_cross_project_or_run_task() -> None:
    valid = _ReferenceSession({"project_id": "P" * 26, "run_task_id": "T" * 26})
    _require_scoped_reference(
        valid,
        table="atp_execution_batch",
        id_column="execution_batch_id",
        reference_id="B" * 26,
        project_id="P" * 26,
        label="ExecutionBatch",
        run_task_id="T" * 26,
    )
    assert valid.params == {"reference_id": "B" * 26}

    with pytest.raises(Exception, match="same Project"):
        _require_scoped_reference(
            _ReferenceSession({"project_id": "X" * 26, "run_task_id": "T" * 26}),
            table="atp_execution_batch",
            id_column="execution_batch_id",
            reference_id="B" * 26,
            project_id="P" * 26,
            label="ExecutionBatch",
            run_task_id="T" * 26,
        )

    with pytest.raises(Exception, match="same RunTask"):
        _require_scoped_reference(
            _ReferenceSession({"project_id": "P" * 26, "run_task_id": "X" * 26}),
            table="atp_execution_batch",
            id_column="execution_batch_id",
            reference_id="B" * 26,
            project_id="P" * 26,
            label="ExecutionBatch",
            run_task_id="T" * 26,
        )


class _OwnerBeginContext:
    def __init__(self, db) -> None:
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc, tb):
        return False


class _OwnerFactory:
    def __init__(self, db) -> None:
        self.db = db

    def begin(self):
        return _OwnerBeginContext(self.db)


class _OwnerIdempotency:
    def claim(self, *args, **kwargs):
        del args, kwargs
        return SimpleNamespace(response_json=None, response_status=None), False

    @staticmethod
    def complete(record, status: int, response_json: dict[str, object]) -> None:
        record.response_status = status
        record.response_json = response_json


class _OwnerSession:
    def __init__(self, task: RunTask, runner: Runner, project: Project) -> None:
        self.task = task
        self.runner = runner
        self.project = project
        self.added: list[object] = []

    def scalar(self, statement):
        text = str(statement)
        if "FROM atp_run_task" in text:
            return self.task
        if "count(atp_execution_attempt.execution_attempt_id)" in text:
            return 0
        if "max(atp_outbox_event.sequence)" in text:
            return 0
        raise AssertionError(f"unexpected scalar query: {text}")

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None

    def get(self, model, object_id):
        if model is Runner and object_id == self.runner.runner_id:
            return self.runner
        if model is Project and object_id == self.project.project_id:
            return self.project
        return None


def _owner_runner(*, compatibility: str, scheduling: str, resource: str = "AVAILABLE") -> Runner:
    now = datetime(2026, 9, 8, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    return Runner(
        runner_id="R" * 26,
        project_id="P" * 26,
        runner_code="runner-local",
        health_status="HEALTHY",
        scheduling_status=scheduling,
        resource_status=resource,
        version_compatibility=compatibility,
        last_heartbeat_at=now,
        registered_at=now,
        runtime_metadata_json=None,
        registration_status="REGISTERED",
        connection_status="ONLINE",
        enable_status="ENABLED",
        project_binding_status="BOUND",
        lifecycle_status="ACTIVE",
        display_name="runner-local",
        row_version=1,
        created_at=now,
        updated_at=now,
        created_by=None,
        updated_by=None,
        extension_json=None,
    )


def _owner_task_and_project() -> tuple[RunTask, Project]:
    now = datetime(2026, 9, 8, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    task = RunTask(
        run_task_id="T" * 26,
        project_id="P" * 26,
        idempotency_key="task",
        case_suite_id=None,
        environment_id="E" * 26,
        task_type="AI_EXPLORATION",
        lifecycle_status="CREATED",
        task_state="CREATED",
        final_result="UNKNOWN",
        display_name=None,
        row_version=0,
        created_at=now,
        updated_at=now,
        created_by="U" * 26,
        updated_by="U" * 26,
        extension_json=None,
    )
    project = Project(
        project_id="P" * 26,
        project_code="project",
        lifecycle_status="ACTIVE",
        display_name="project",
        row_version=0,
        created_at=now,
        updated_at=now,
        created_by="U" * 26,
        updated_by="U" * 26,
        extension_json=None,
    )
    return task, project


@pytest.mark.parametrize(
    ("compatibility", "scheduling", "resource", "expected_detail"),
    [
        ("UNKNOWN", "UNSCHEDULABLE", "AVAILABLE", "version_compatibility=UNKNOWN"),
        ("COMPATIBLE", "BUSY", "EXHAUSTED", "scheduling_status=BUSY"),
        ("COMPATIBLE", "DRAINING", "RECLAIMING", "scheduling_status=DRAINING"),
    ],
)
def test_execution_attempt_reports_specific_runner_readiness_blocker(
    compatibility: str,
    scheduling: str,
    resource: str,
    expected_detail: str,
) -> None:
    task, project = _owner_task_and_project()
    runner = _owner_runner(
        compatibility=compatibility,
        scheduling=scheduling,
        resource=resource,
    )
    service = ExecutionOwnerService(
        _OwnerFactory(_OwnerSession(task, runner, project)),
        authentication=SimpleNamespace(),
        idempotency=_OwnerIdempotency(),
    )
    service._authenticate = lambda *args, **kwargs: SimpleNamespace(  # type: ignore[method-assign]
        user=SimpleNamespace(user_id="U" * 26)
    )

    with pytest.raises(PlatformError) as caught:
        service.create_execution_attempt(
            "token",
            CreateExecutionAttemptRequest(run_task_id=task.run_task_id, runner_id=runner.runner_id),
            "key",
            SimpleNamespace(correlation_id="corr"),
        )

    assert caught.value.status == 409
    assert caught.value.code == "EXECUTION_OWNER_STATE_CONFLICT"
    assert expected_detail in caught.value.detail


def test_execution_attempt_is_created_after_runner_becomes_compatible_and_idle() -> None:
    task, project = _owner_task_and_project()
    runner = _owner_runner(compatibility="COMPATIBLE", scheduling="IDLE")
    db = _OwnerSession(task, runner, project)
    service = ExecutionOwnerService(
        _OwnerFactory(db),
        authentication=SimpleNamespace(),
        idempotency=_OwnerIdempotency(),
    )
    service._authenticate = lambda *args, **kwargs: SimpleNamespace(  # type: ignore[method-assign]
        user=SimpleNamespace(user_id="U" * 26)
    )

    resource = service.create_execution_attempt(
        "token",
        CreateExecutionAttemptRequest(run_task_id=task.run_task_id, runner_id=runner.runner_id),
        "new-attempt",
        AuditContext(correlation_id="attempt-ready", source_context="test"),
    )

    assert resource.execution_status == "READY"
    assert resource.runner_id == runner.runner_id
    assert resource.run_task_id == task.run_task_id
    assert any(isinstance(item, ExecutionAttempt) for item in db.added)
