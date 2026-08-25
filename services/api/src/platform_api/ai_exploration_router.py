"""FastAPI adapter for AI exploration foundation planning."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from platform_api.ai_exploration_schemas import (
    CreateAIExplorationRequest,
    CreateAIExplorationResponse,
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
