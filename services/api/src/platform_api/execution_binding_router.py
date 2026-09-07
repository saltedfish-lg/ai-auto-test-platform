"""FastAPI adapters for ExecutionBindingSnapshot and fenced lease commands."""

from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.execution_binding_schemas import (
    BindingCommandRequest,
    CreateRuntimePolicyRevisionRequest,
    ExecutionBindingInput,
    ExecutionBindingSnapshotListResponse,
    ExecutionBindingSnapshotResponse,
    PreflightResponse,
    RecoverBindingRequest,
    RuntimePolicyRevisionListResponse,
    RuntimePolicyRevisionResponse,
)
from platform_api.execution_binding_service import ExecutionBindingService

router = APIRouter(tags=["Execution Binding"])


def _service(request: Request) -> ExecutionBindingService:
    service = getattr(request.app.state, "execution_binding_service", None)
    if not isinstance(service, ExecutionBindingService):
        raise PlatformError(
            title="Execution binding is unavailable",
            detail="The Execution Binding service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.post(
    "/api/v1/execution-binding-snapshots/preflight",
    response_model=PreflightResponse,
    operation_id="preflight_execution_binding_snapshot",
)
def preflight_execution_binding_snapshot(
    body: ExecutionBindingInput,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> PreflightResponse:
    del idempotency_key
    data = _service(request).preflight(_bearer(authorization), body, _audit_context(request))
    return PreflightResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/execution-binding-snapshots",
    status_code=201,
    response_model=ExecutionBindingSnapshotResponse,
    operation_id="create_execution_binding_snapshot",
)
def create_execution_binding_snapshot(
    body: ExecutionBindingInput,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotResponse:
    data = _service(request).create(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return ExecutionBindingSnapshotResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/execution-binding-snapshots",
    response_model=ExecutionBindingSnapshotListResponse,
    operation_id="list_execution_binding_snapshots",
)
def list_execution_binding_snapshots(
    request: Request,
    project_id: str = Query(min_length=26, max_length=26),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotListResponse:
    return _service(request).list(
        _bearer(authorization), project_id, page, page_size, status, _audit_context(request)
    )


@router.get(
    "/api/v1/execution-binding-snapshots/{id}",
    response_model=ExecutionBindingSnapshotResponse,
    operation_id="get_execution_binding_snapshot",
)
def get_execution_binding_snapshot(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotResponse:
    data = _service(request).get(_bearer(authorization), id, _audit_context(request))
    return ExecutionBindingSnapshotResponse(data=data, correlation_id=_correlation_id(request))


def _execute_command(
    request: Request,
    authorization: str | None,
    binding_id: str,
    action: str,
    body: BindingCommandRequest | RecoverBindingRequest,
    idempotency_key: str,
) -> ExecutionBindingSnapshotResponse:
    data = _service(request).command(
        _bearer(authorization), binding_id, action, body, idempotency_key, _audit_context(request)
    )
    return ExecutionBindingSnapshotResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/execution-binding-snapshots/{id}/consume",
    response_model=ExecutionBindingSnapshotResponse,
    operation_id="consume_execution_binding_snapshot",
)
def consume_execution_binding_snapshot(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: BindingCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotResponse:
    return _execute_command(request, authorization, id, "consume", body, idempotency_key)


@router.post(
    "/api/v1/execution-binding-snapshots/{id}/leases/renew",
    response_model=ExecutionBindingSnapshotResponse,
    operation_id="renew_execution_binding_snapshot_leases",
)
def renew_execution_binding_snapshot_leases(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: BindingCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotResponse:
    return _execute_command(request, authorization, id, "renew", body, idempotency_key)


@router.post(
    "/api/v1/execution-binding-snapshots/{id}/release",
    response_model=ExecutionBindingSnapshotResponse,
    operation_id="release_execution_binding_snapshot",
)
def release_execution_binding_snapshot(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: BindingCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotResponse:
    return _execute_command(request, authorization, id, "release", body, idempotency_key)


@router.post(
    "/api/v1/execution-binding-snapshots/{id}/recover",
    response_model=ExecutionBindingSnapshotResponse,
    operation_id="recover_execution_binding_snapshot",
)
def recover_execution_binding_snapshot(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: RecoverBindingRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> ExecutionBindingSnapshotResponse:
    return _execute_command(request, authorization, id, "recover", body, idempotency_key)


@router.get(
    "/api/v1/project-runtime-policy-revisions",
    response_model=RuntimePolicyRevisionListResponse,
    operation_id="list_project_runtime_policy_revisions",
)
def list_project_runtime_policy_revisions(
    request: Request,
    project_id: str = Query(min_length=26, max_length=26),
    authorization: str | None = Header(None),
) -> RuntimePolicyRevisionListResponse:
    return _service(request).list_runtime_policies(
        _bearer(authorization), project_id, _audit_context(request)
    )


@router.post(
    "/api/v1/project-runtime-policy-revisions",
    status_code=201,
    response_model=RuntimePolicyRevisionResponse,
    operation_id="create_project_runtime_policy_revision",
)
def create_project_runtime_policy_revision(
    body: CreateRuntimePolicyRevisionRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> RuntimePolicyRevisionResponse:
    data = _service(request).create_runtime_policy(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return RuntimePolicyRevisionResponse(data=data, correlation_id=_correlation_id(request))
