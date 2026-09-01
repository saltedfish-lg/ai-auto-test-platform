"""FastAPI adapter for Environment Management Foundation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.environment_schemas import (
    CreateEnvironmentRequest,
    EnvironmentListData,
    EnvironmentResponse,
    LifecycleCommandRequest,
    UpdateEnvironmentRequest,
)
from platform_api.environment_service import EnvironmentService
from platform_api.errors import PlatformError

router = APIRouter(tags=["环境"])


def _service(request: Request) -> EnvironmentService:
    service = getattr(request.app.state, "environment_service", None)
    if not isinstance(service, EnvironmentService):
        raise PlatformError(
            title="Environment management is unavailable",
            detail="The environment management service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.get(
    "/api/v1/environment",
    response_model=EnvironmentListData,
    response_model_exclude_none=True,
    operation_id="list_environment",
)
def list_environment(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str | None = Query(default=None, max_length=128),
    filter: str | None = Query(default=None, max_length=1000),
    authorization: str | None = Header(default=None),
) -> EnvironmentListData:
    return _service(request).list_environments(
        _bearer(authorization), page, page_size, sort, filter, _audit_context(request)
    )


@router.post(
    "/api/v1/environment",
    status_code=201,
    response_model=EnvironmentResponse,
    response_model_exclude_none=True,
    operation_id="create_environment",
)
def create_environment(
    body: CreateEnvironmentRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> EnvironmentResponse:
    resource = _service(request).create_environment(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return EnvironmentResponse(data=resource, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/environment/{id}",
    response_model=EnvironmentResponse,
    response_model_exclude_none=True,
    operation_id="get_environment",
)
def get_environment(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(default=None),
) -> EnvironmentResponse:
    resource = _service(request).get_environment(
        _bearer(authorization), id, _audit_context(request)
    )
    return EnvironmentResponse(data=resource, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/environment/{id}",
    response_model=EnvironmentResponse,
    response_model_exclude_none=True,
    operation_id="update_environment",
)
def update_environment(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateEnvironmentRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> EnvironmentResponse:
    resource = _service(request).update_environment(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return EnvironmentResponse(data=resource, correlation_id=_correlation_id(request))


def _environment_command(
    action: str,
    id: str,
    body: LifecycleCommandRequest,
    request: Request,
    key: str,
    authorization: str | None,
) -> EnvironmentResponse:
    resource = _service(request).transition_environment(
        _bearer(authorization), id, action, body, key, _audit_context(request)
    )
    return EnvironmentResponse(data=resource, correlation_id=_correlation_id(request))


def _command_route(action: str) -> Callable[..., EnvironmentResponse]:
    def command(
        id: Annotated[str, Path(min_length=26, max_length=26)],
        body: LifecycleCommandRequest,
        request: Request,
        idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
        authorization: str | None = Header(default=None),
    ) -> EnvironmentResponse:
        return _environment_command(action, id, body, request, idempotency_key, authorization)

    command.__name__ = f"{action}_environment"
    return command


for _action in ("validate", "reconfigure", "activate"):
    router.add_api_route(
        f"/api/v1/environment/{{id}}/{_action}",
        _command_route(_action),
        methods=["POST"],
        response_model=EnvironmentResponse,
        response_model_exclude_none=True,
        operation_id=f"{_action}_environment",
    )
