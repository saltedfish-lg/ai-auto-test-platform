"""FastAPI adapter for AI exploration foundation planning."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Header, Request

from platform_api.ai_exploration_schemas import (
    AIExplorationSessionResponse,
    AIExplorationStepListResponse,
    CancelAIExplorationSessionRequest,
    CreateAIExplorationRequest,
    CreateAIExplorationResponse,
    StartAIExplorationSessionRequest,
)
from platform_api.ai_exploration_service import AIExplorationService
from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError

router = APIRouter(tags=["AI 探索"])


def _service(request: Request) -> AIExplorationService:
    service = getattr(request.app.state, "ai_exploration_service", None)
    if not isinstance(service, AIExplorationService):
        raise PlatformError(
            title="AI exploration unavailable",
            detail="The AI exploration service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.post(
    "/api/v1/ai-exploration-sessions",
    status_code=201,
    response_model=CreateAIExplorationResponse,
    response_model_exclude_none=True,
    operation_id="create_ai_exploration_session",
)
def create_ai_exploration_session(
    body: CreateAIExplorationRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> CreateAIExplorationResponse:
    session = _service(request).create(
        _bearer(authorization),
        body,
        idempotency_key,
        _audit_context(request),
    )
    return CreateAIExplorationResponse(
        data=session,
        correlation_id=_correlation_id(request),
    )


@router.get(
    "/api/v1/ai-exploration-sessions/{session_id}",
    response_model=AIExplorationSessionResponse,
    response_model_exclude_none=False,
    operation_id="get_ai_exploration_session",
)
def get_ai_exploration_session(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> AIExplorationSessionResponse:
    data = _service(request).get(_bearer(authorization), session_id, _audit_context(request))
    return AIExplorationSessionResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/ai-exploration-sessions/{session_id}/start",
    status_code=202,
    response_model=AIExplorationSessionResponse,
    response_model_exclude_none=False,
    operation_id="start_ai_exploration_session",
)
def start_ai_exploration_session(
    session_id: str,
    body: StartAIExplorationSessionRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> AIExplorationSessionResponse:
    service = _service(request)
    context = _audit_context(request)
    data, should_dispatch = service.start(
        _bearer(authorization), session_id, body, idempotency_key, context
    )
    if should_dispatch:
        background_tasks.add_task(service.run, session_id, context)
    return AIExplorationSessionResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/ai-exploration-sessions/{session_id}/steps",
    response_model=AIExplorationStepListResponse,
    response_model_exclude_none=False,
    operation_id="list_ai_exploration_steps",
)
def list_ai_exploration_steps(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> AIExplorationStepListResponse:
    items = _service(request).list_steps(
        _bearer(authorization), session_id, _audit_context(request)
    )
    return AIExplorationStepListResponse(items=items, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/ai-exploration-sessions/{session_id}/cancel",
    response_model=AIExplorationSessionResponse,
    response_model_exclude_none=False,
    operation_id="cancel_ai_exploration_session",
)
def cancel_ai_exploration_session(
    session_id: str,
    body: CancelAIExplorationSessionRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> AIExplorationSessionResponse:
    service = _service(request)
    data, command, browser_session_id = service.cancel(
        _bearer(authorization), session_id, body, idempotency_key, _audit_context(request)
    )
    service.close_cancelled_runtime(command, browser_session_id)
    service.finalize_cancel(session_id, command, _audit_context(request))
    return AIExplorationSessionResponse(data=data, correlation_id=_correlation_id(request))
