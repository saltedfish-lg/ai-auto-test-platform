"""FastAPI adapter for system-managed Runner execution slot discovery."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.execution_slot_schemas import (
    CreateExecutionSlotRequest,
    ExecutionSlotListResponse,
    ExecutionSlotResponse,
    PageMeta,
    UpdateExecutionSlotRequest,
)
from platform_api.execution_slot_service import ExecutionSlotService

router = APIRouter(tags=["执行槽位"])


def _service(request: Request) -> ExecutionSlotService:
    service = getattr(request.app.state, "execution_slot_service", None)
    if not isinstance(service, ExecutionSlotService):
        raise PlatformError(
            title="Execution slot service unavailable",
            detail="Execution slot resource discovery has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.get(
    "/api/v1/execution-slot",
    response_model=ExecutionSlotListResponse,
    response_model_exclude_none=True,
    operation_id="list_execution_slot",
)
def list_execution_slot(
    request: Request,
    project_id: str = Query(min_length=26, max_length=26),
    runner_id: str | None = Query(default=None, min_length=26, max_length=26),
    lifecycle_status: Literal["ACTIVE", "DISABLED", "ARCHIVED"] | None = Query(default=None),
    available_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str | None = Query(default=None, max_length=128),
    filter: str | None = Query(default=None, max_length=1000),
    authorization: str | None = Header(default=None),
) -> ExecutionSlotListResponse:
    del sort, filter
    items, total = _service(request).list_slots(
        _bearer(authorization),
        project_id=project_id,
        runner_id=runner_id,
        lifecycle_status=lifecycle_status,
        available_only=available_only,
        page=page,
        page_size=page_size,
        audit_context=_audit_context(request),
    )
    return ExecutionSlotListResponse(
        items=items, page=PageMeta(page=page, page_size=page_size, total=total)
    )


@router.post(
    "/api/v1/execution-slot",
    status_code=201,
    response_model=ExecutionSlotResponse,
    operation_id="create_execution_slot",
)
def create_execution_slot(
    body: CreateExecutionSlotRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ExecutionSlotResponse:
    del body, idempotency_key
    _service(request).reject_external_mutation(
        _bearer(authorization), "create_execution_slot", _audit_context(request)
    )
    raise AssertionError("unreachable")


@router.get(
    "/api/v1/execution-slot/{id}",
    response_model=ExecutionSlotResponse,
    response_model_exclude_none=True,
    operation_id="get_execution_slot",
)
def get_execution_slot(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(default=None),
) -> ExecutionSlotResponse:
    item = _service(request).get_slot(_bearer(authorization), id, _audit_context(request))
    return ExecutionSlotResponse(data=item, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/execution-slot/{id}",
    response_model=ExecutionSlotResponse,
    operation_id="update_execution_slot",
)
def update_execution_slot(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateExecutionSlotRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ExecutionSlotResponse:
    del id, body, idempotency_key
    _service(request).reject_external_mutation(
        _bearer(authorization), "update_execution_slot", _audit_context(request)
    )
    raise AssertionError("unreachable")
