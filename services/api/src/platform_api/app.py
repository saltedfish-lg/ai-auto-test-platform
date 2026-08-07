"""Application assembly for the P0 API process."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from platform_observability import configure_logging

from platform_api.config import ApiSettings
from platform_api.errors import PlatformError, ProblemDetails
from platform_api.middleware import CorrelationIdMiddleware

LOGGER = logging.getLogger(__name__)


def create_app(settings: ApiSettings) -> FastAPI:
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        LOGGER.info("api process started", extra={"service": settings.service_name})
        yield
        LOGGER.info("api process stopped", extra={"service": settings.service_name})

    app = FastAPI(
        title="AI automation test platform process foundation",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(CorrelationIdMiddleware)

    @app.exception_handler(PlatformError)
    async def handle_platform_error(request: Request, error: PlatformError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        problem = ProblemDetails(
            type=error.type,
            title=error.title,
            status=error.status,
            detail=error.detail,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=error.status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    return app
