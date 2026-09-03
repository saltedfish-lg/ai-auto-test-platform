"""FastAPI adapters for Runner human management and Runner Agent machine calls."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.runner_browser_channel import RunnerBrowserCommandBroker
from platform_api.runner_schemas import (
    CreateRunnerEnrollmentRequest,
    HeartbeatRunnerRequest,
    RegisterRunnerRequest,
    RegisterRunnerResponse,
    ReportRunnerCapabilitiesRequest,
    RotateRunnerAgentTokenResponse,
    RunnerEnrollmentResponse,
    RunnerLifecycleRequest,
    RunnerListResponse,
    RunnerResponse,
    UpdateRunnerRequest,
)
from platform_api.runner_service import RunnerService

router = APIRouter(tags=["Runner"])


class _CompleteBrowserCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: dict[str, object] | None = None
    error_code: str | None = Field(default=None, max_length=64)


def _service(request: Request) -> RunnerService:
    value = getattr(request.app.state, "runner_service", None)
    if not isinstance(value, RunnerService):
        raise PlatformError(
            title="Runner management is unavailable",
            detail="The Runner service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return value


def _browser_broker(request: Request) -> RunnerBrowserCommandBroker:
    value = getattr(request.app.state, "runner_browser_command_broker", None)
    if not isinstance(value, RunnerBrowserCommandBroker):
        raise PlatformError(
            title="Runner browser channel unavailable",
            detail="The bound direct Runner command channel has not been configured.",
            status=503,
            code="AI_EXPLORATION_RUNNER_UNAVAILABLE",
        )
    return value


@router.get(
    "/api/v1/runner",
    response_model=RunnerListResponse,
    operation_id="list_runner",
)
def list_runner(
    request: Request,
    project_id: str = Query(min_length=26, max_length=26),
    lifecycle_status: str | None = Query(None),
    health_status: str | None = Query(None),
    capability_code: str | None = Query(None, max_length=64),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    authorization: str | None = Header(None),
) -> RunnerListResponse:
    return _service(request).list(
        _bearer(authorization),
        project_id,
        page,
        page_size,
        lifecycle_status,
        health_status,
        capability_code,
        _audit_context(request),
    )


@router.post(
    "/api/v1/runner-enrollments",
    status_code=201,
    response_model=RunnerEnrollmentResponse,
    operation_id="create_runner_enrollment",
)
def create_runner_enrollment(
    body: CreateRunnerEnrollmentRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> RunnerEnrollmentResponse:
    data = _service(request).create_enrollment(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return RunnerEnrollmentResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/runners/register",
    status_code=201,
    response_model=RegisterRunnerResponse,
    operation_id="register_runner",
)
def register_runner(
    body: RegisterRunnerRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
) -> RegisterRunnerResponse:
    data = _service(request).register(body, idempotency_key, _audit_context(request))
    return RegisterRunnerResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/runner/{id}",
    response_model=RunnerResponse,
    operation_id="get_runner",
)
def get_runner(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> RunnerResponse:
    data = _service(request).get(_bearer(authorization), id, _audit_context(request))
    return RunnerResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/runner/{id}",
    response_model=RunnerResponse,
    operation_id="update_runner",
)
def update_runner(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateRunnerRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> RunnerResponse:
    data = _service(request).update(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return RunnerResponse(data=data, correlation_id=_correlation_id(request))


def _command_route(action: str) -> Callable[..., RunnerResponse]:
    def command(
        id: Annotated[str, Path(min_length=26, max_length=26)],
        body: RunnerLifecycleRequest,
        request: Request,
        idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
        authorization: str | None = Header(None),
    ) -> RunnerResponse:
        data = _service(request).transition(
            _bearer(authorization),
            id,
            action,
            body,
            idempotency_key,
            _audit_context(request),
        )
        return RunnerResponse(data=data, correlation_id=_correlation_id(request))

    command.__name__ = f"{action}_runner"
    return command


for _action in ("enable", "disable", "archive"):
    router.add_api_route(
        f"/api/v1/runner/{{id}}/{_action}",
        _command_route(_action),
        methods=["POST"],
        response_model=RunnerResponse,
        operation_id=f"{_action}_runner",
    )


@router.post(
    "/api/v1/runner/{id}/agent-token/rotate",
    response_model=RotateRunnerAgentTokenResponse,
    operation_id="rotate_runner_agent_token",
)
def rotate_runner_agent_token(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: RunnerLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> RotateRunnerAgentTokenResponse:
    data = _service(request).rotate_token(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return RotateRunnerAgentTokenResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/runner/{id}/agent-token/revoke",
    response_model=RunnerResponse,
    operation_id="revoke_runner_agent_token",
)
def revoke_runner_agent_token(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: RunnerLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> RunnerResponse:
    data = _service(request).revoke_token(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return RunnerResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/runners/{id}/heartbeat",
    response_model=RunnerResponse,
    operation_id="heartbeat_runner",
)
def heartbeat_runner(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: HeartbeatRunnerRequest,
    request: Request,
    agent_token: str = Header(min_length=32, max_length=512, alias="X-Runner-Agent-Token"),
) -> RunnerResponse:
    data = _service(request).heartbeat(id, agent_token, body, _audit_context(request))
    return RunnerResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/runners/{id}/capabilities",
    response_model=RunnerResponse,
    operation_id="report_runner_capabilities",
)
def report_runner_capabilities(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: ReportRunnerCapabilitiesRequest,
    request: Request,
    agent_token: str = Header(min_length=32, max_length=512, alias="X-Runner-Agent-Token"),
) -> RunnerResponse:
    data = _service(request).report_capabilities(id, agent_token, body, _audit_context(request))
    return RunnerResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/runners/{id}/browser-runtime/commands:claim",
    include_in_schema=False,
)
def claim_bound_browser_command(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    agent_token: str = Header(min_length=32, max_length=512, alias="X-Runner-Agent-Token"),
) -> dict[str, object]:
    _service(request).require_machine_identity(id, agent_token)
    return {"data": _browser_broker(request).claim(id), "correlation_id": _correlation_id(request)}


@router.post(
    "/api/v1/runners/{id}/browser-runtime/cancellations:claim",
    include_in_schema=False,
)
def claim_bound_browser_cancellation(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    agent_token: str = Header(min_length=32, max_length=512, alias="X-Runner-Agent-Token"),
) -> dict[str, object]:
    _service(request).require_machine_identity(id, agent_token)
    return {
        "data": _browser_broker(request).claim_cancel(id),
        "correlation_id": _correlation_id(request),
    }


@router.post(
    "/api/v1/runners/{id}/browser-runtime/commands/{command_id}:complete",
    include_in_schema=False,
)
def complete_bound_browser_command(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    command_id: Annotated[str, Path(min_length=26, max_length=26)],
    body: _CompleteBrowserCommandRequest,
    request: Request,
    agent_token: str = Header(min_length=32, max_length=512, alias="X-Runner-Agent-Token"),
) -> dict[str, object]:
    _service(request).require_machine_identity(id, agent_token)
    _browser_broker(request).complete(id, command_id, body.response, body.error_code)
    return {"data": {"accepted": True}, "correlation_id": _correlation_id(request)}
