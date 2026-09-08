"""FastAPI adapter for formal RunTask and ExecutionAttempt provisioning."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.execution_owner_schemas import (
    CreateExecutionAttemptRequest,
    CreateRunTaskRequest,
    ExecutionAttemptListResponse,
    ExecutionAttemptResponse,
    RunTaskListResponse,
    RunTaskResponse,
    UpdateExecutionAttemptRequest,
    UpdateRunTaskRequest,
)
from platform_api.execution_owner_service import ExecutionOwnerService

router = APIRouter()


def _service(request: Request) -> ExecutionOwnerService:
    service = getattr(request.app.state, "execution_owner_service", None)
    if not isinstance(service, ExecutionOwnerService):
        raise PlatformError(
            title="Execution owner management is unavailable",
            detail="The execution owner service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.get("/api/v1/run-task", response_model=RunTaskListResponse, operation_id="list_run_task", tags=["执行任务"])
def list_run_task(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str | None = Query(default=None, max_length=128),
    filter: str | None = Query(default=None, max_length=1000),
    authorization: str | None = Header(default=None),
) -> RunTaskListResponse:
    del sort, filter
    return _service(request).list_run_tasks(
        _bearer(authorization), page, page_size, _audit_context(request)
    )


@router.post("/api/v1/run-task", status_code=202, response_model=RunTaskResponse, operation_id="create_run_task", tags=["执行任务"])
def create_run_task(
    body: CreateRunTaskRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> RunTaskResponse:
    resource = _service(request).create_run_task(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return RunTaskResponse(data=resource, correlation_id=_correlation_id(request))


@router.get("/api/v1/run-task/{id}", response_model=RunTaskResponse, operation_id="get_run_task", tags=["执行任务"])
def get_run_task(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(default=None),
) -> RunTaskResponse:
    resource = _service(request).get_run_task(_bearer(authorization), id, _audit_context(request))
    return RunTaskResponse(data=resource, correlation_id=_correlation_id(request))


@router.patch("/api/v1/run-task/{id}", response_model=RunTaskResponse, operation_id="update_run_task", tags=["执行任务"])
def update_run_task(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateRunTaskRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> RunTaskResponse:
    resource = _service(request).update_run_task(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return RunTaskResponse(data=resource, correlation_id=_correlation_id(request))


@router.get("/api/v1/execution-attempt", response_model=ExecutionAttemptListResponse, operation_id="list_execution_attempt", tags=["执行尝试"])
def list_execution_attempt(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str | None = Query(default=None, max_length=128),
    filter: str | None = Query(default=None, max_length=1000),
    authorization: str | None = Header(default=None),
) -> ExecutionAttemptListResponse:
    del sort, filter
    return _service(request).list_execution_attempts(
        _bearer(authorization), page, page_size, _audit_context(request)
    )


@router.post("/api/v1/execution-attempt", status_code=201, response_model=ExecutionAttemptResponse, operation_id="create_execution_attempt", tags=["执行尝试"])
def create_execution_attempt(
    body: CreateExecutionAttemptRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ExecutionAttemptResponse:
    resource = _service(request).create_execution_attempt(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return ExecutionAttemptResponse(data=resource, correlation_id=_correlation_id(request))


@router.get("/api/v1/execution-attempt/{id}", response_model=ExecutionAttemptResponse, operation_id="get_execution_attempt", tags=["执行尝试"])
def get_execution_attempt(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(default=None),
) -> ExecutionAttemptResponse:
    resource = _service(request).get_execution_attempt(
        _bearer(authorization), id, _audit_context(request)
    )
    return ExecutionAttemptResponse(data=resource, correlation_id=_correlation_id(request))


@router.patch("/api/v1/execution-attempt/{id}", response_model=ExecutionAttemptResponse, operation_id="update_execution_attempt", tags=["执行尝试"])
def update_execution_attempt(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateExecutionAttemptRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ExecutionAttemptResponse:
    resource = _service(request).update_execution_attempt(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return ExecutionAttemptResponse(data=resource, correlation_id=_correlation_id(request))
