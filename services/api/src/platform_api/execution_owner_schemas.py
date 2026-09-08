"""Public contracts for formal RunTask and ExecutionAttempt provisioning."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunTaskLifecycle = Literal[
    "CREATED",
    "SNAPSHOTTED",
    "VALIDATING",
    "WAITING_RESOURCE",
    "DISPATCHING",
    "PREPARING",
    "RUNNING",
    "RETRYING",
    "CANCELING",
    "ABORTING",
    "EXCEPTION",
    "RECOVERING",
    "COMPLETED",
    "REPORTING",
    "ARCHIVED",
]
RunTaskState = Literal[
    "CREATED",
    "WAITING_RESOURCE",
    "RUNNING",
    "RETRYING",
    "COMPLETED",
    "CANCELED",
    "ABORTED",
    "EXCEPTION",
]
RunTaskFinalResult = Literal[
    "PASSED", "FAILED", "CANCELED", "ABORTED", "PARTIAL", "UNKNOWN"
]
RunTaskType = Literal["FORMAL_EXECUTION", "AI_EXPLORATION", "AI_VALIDATION"]
ExecutionStatus = Literal[
    "ABORTED",
    "BROKEN",
    "CANCELLED",
    "FAILED",
    "PRESTART_BLOCKED",
    "READY",
    "RUNNING",
    "SUCCEEDED",
]
FinalizationStatus = Literal["COMPLETED", "INITIAL", "IN_PROGRESS", "PENDING_RECOVERY"]
ExecutionLifecycle = Literal[
    "CREATED",
    "PREPARING",
    "RUNNING",
    "PASSED",
    "FAILED",
    "SKIPPED",
    "NOT_EXECUTED",
    "CANCELED",
    "ABORTED",
    "TIMED_OUT",
    "EXCEPTION",
    "COMPLETED",
]


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class RunTaskResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_task_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    project_id: str | None = Field(default=None, max_length=191)
    idempotency_key: str | None = Field(default=None, max_length=191)
    case_suite_id: str | None = Field(default=None, min_length=26, max_length=26)
    environment_id: str | None = Field(default=None, min_length=26, max_length=26)
    task_type: RunTaskType | None = None
    lifecycle_status: RunTaskLifecycle
    task_state: RunTaskState
    final_result: RunTaskFinalResult = "UNKNOWN"


class CreateRunTaskRequest(BaseModel):
    """Keep the existing public contract but enforce immutable creation state in service."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    run_task_id: str | None = Field(default=None, min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    project_id: str | None = Field(default=None, max_length=191)
    idempotency_key: str | None = Field(default=None, max_length=191)
    case_suite_id: str | None = Field(default=None, min_length=26, max_length=26)
    environment_id: str | None = Field(default=None, min_length=26, max_length=26)
    task_type: RunTaskType
    task_state: RunTaskState | None = None
    final_result: RunTaskFinalResult = "UNKNOWN"


class UpdateRunTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    display_name: str | None = Field(default=None, max_length=255)
    project_id: str | None = Field(default=None, max_length=191)
    idempotency_key: str | None = Field(default=None, max_length=191)
    case_suite_id: str | None = Field(default=None, min_length=26, max_length=26)
    environment_id: str | None = Field(default=None, min_length=26, max_length=26)
    task_state: RunTaskState | None = None
    final_result: RunTaskFinalResult | None = None


class RunTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RunTaskResource
    correlation_id: str


class RunTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RunTaskResource]
    page: PageMeta


class ExecutionAttemptResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_attempt_id: str = Field(min_length=26, max_length=26)
    execution_binding_snapshot_id: str | None = Field(default=None, min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    run_task_id: str | None = Field(default=None, min_length=26, max_length=26)
    attempt_no: str | None = Field(default=None, max_length=191)
    case_attempt_id: str | None = Field(default=None, min_length=26, max_length=26)
    runner_id: str | None = Field(default=None, min_length=26, max_length=26)
    configuration_snapshot_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_batch_id: str | None = Field(default=None, min_length=26, max_length=26)
    lease_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_lock_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_status: ExecutionStatus
    finalization_status: FinalizationStatus
    lifecycle_status: ExecutionLifecycle


class CreateExecutionAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    execution_attempt_id: str | None = Field(default=None, min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    run_task_id: str | None = Field(default=None, min_length=26, max_length=26)
    attempt_no: str | None = Field(default=None, max_length=191)
    case_attempt_id: str | None = Field(default=None, min_length=26, max_length=26)
    runner_id: str | None = Field(default=None, min_length=26, max_length=26)
    configuration_snapshot_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_batch_id: str | None = Field(default=None, min_length=26, max_length=26)
    lease_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_lock_id: str | None = Field(default=None, min_length=26, max_length=26)


class UpdateExecutionAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    display_name: str | None = Field(default=None, max_length=255)
    run_task_id: str | None = Field(default=None, min_length=26, max_length=26)
    attempt_no: str | None = Field(default=None, max_length=191)
    case_attempt_id: str | None = Field(default=None, min_length=26, max_length=26)
    runner_id: str | None = Field(default=None, min_length=26, max_length=26)
    configuration_snapshot_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_batch_id: str | None = Field(default=None, min_length=26, max_length=26)
    lease_id: str | None = Field(default=None, min_length=26, max_length=26)
    execution_lock_id: str | None = Field(default=None, min_length=26, max_length=26)


class ExecutionAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ExecutionAttemptResource
    correlation_id: str


class ExecutionAttemptListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ExecutionAttemptResource]
    page: PageMeta
