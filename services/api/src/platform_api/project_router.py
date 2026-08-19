"""FastAPI adapter for the Project aggregate foundation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.project_schemas import (
    CreateProjectRequest,
    ProjectListData,
    ProjectResponse,
    ProjectStateCommandRequest,
    UpdateProjectRequest,
)
from platform_api.project_service import ProjectService

router = APIRouter(tags=["项目"])


def _service(request: Request) -> ProjectService:
    service = getattr(request.app.state, "project_service", None)
    if not isinstance(service, ProjectService):
        raise PlatformError(
            title="Project management is unavailable",
            detail="The project management service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.get(
    "/api/v1/project",
    response_model=ProjectListData,
    response_model_exclude_none=True,
    operation_id="list_project",
)
def list_project(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ProjectListData:
    return _service(request).list_projects(
        _bearer(authorization), page, page_size, _audit_context(request)
    )


@router.post(
    "/api/v1/project",
    status_code=201,
    response_model=ProjectResponse,
    response_model_exclude_none=True,
    operation_id="create_project",
)
def create_project(
    body: CreateProjectRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    project = _service(request).create_project(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return ProjectResponse(data=project, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/project/{id}",
    response_model=ProjectResponse,
    response_model_exclude_none=True,
    operation_id="get_project",
)
def get_project(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    project = _service(request).get_project(
        _bearer(authorization), id, _audit_context(request)
    )
    return ProjectResponse(data=project, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/project/{id}",
    response_model=ProjectResponse,
    response_model_exclude_none=True,
    operation_id="update_project",
)
def update_project(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateProjectRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    project = _service(request).update_project(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return ProjectResponse(data=project, correlation_id=_correlation_id(request))


def _transition(
    *,
    id: str,
    body: ProjectStateCommandRequest,
    request: Request,
    idempotency_key: str,
    authorization: str | None,
    action: str,
) -> ProjectResponse:
    project = _service(request).transition_project(
        _bearer(authorization),
        id,
        body,
        idempotency_key,
        _audit_context(request),
        action=action,
    )
    return ProjectResponse(data=project, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/project/{id}/disable",
    response_model=ProjectResponse,
    response_model_exclude_none=True,
    operation_id="disable_project",
)
def disable_project(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: ProjectStateCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="disable",
    )


@router.post(
    "/api/v1/project/{id}/recover",
    response_model=ProjectResponse,
    response_model_exclude_none=True,
    operation_id="recover_project",
)
def recover_project(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: ProjectStateCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="recover",
    )


@router.post(
    "/api/v1/project/{id}/archive",
    response_model=ProjectResponse,
    response_model_exclude_none=True,
    operation_id="archive_project",
)
def archive_project(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: ProjectStateCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="archive",
    )
