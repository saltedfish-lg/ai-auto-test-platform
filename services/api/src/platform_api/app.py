"""Application assembly for the current P1 platform API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from platform_observability import configure_logging

from platform_api.audit import AuthenticationAuditService
from platform_api.auth_hmac import AuthHmacKeyRing
from platform_api.auth_router import router as auth_router
from platform_api.auth_service import AuthenticationService
from platform_api.config import ApiSettings
from platform_api.database import create_database_engine, create_session_factory
from platform_api.errors import PlatformError, ProblemDetails
from platform_api.middleware import CorrelationIdMiddleware
from platform_api.rate_limit import AuthenticationRateLimitService
from platform_api.security import JwtKeyRing, JwtService, PasswordService
from platform_api.user_admin_router import router as user_admin_router
from platform_api.user_admin_service import UserAdministrationService

LOGGER = logging.getLogger(__name__)


def create_app(settings: ApiSettings) -> FastAPI:
    configure_logging(settings.log_level)
    jwt_service = JwtService(JwtKeyRing.load(settings.jwt_key_ring_file))
    auth_hmac = AuthHmacKeyRing.load(settings.auth_hmac_master_key_file)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        LOGGER.info("api process started", extra={"service": settings.service_name})
        yield
        engine.dispose()
        LOGGER.info("api process stopped", extra={"service": settings.service_name})

    app = FastAPI(
        title="AI automation test execution platform",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    engine = create_database_engine(settings.database_url)
    app.state.database_engine = engine
    app.state.session_factory = create_session_factory(engine)
    password_service = PasswordService()
    audit_service = AuthenticationAuditService()
    app.state.auth_rate_limit_service = AuthenticationRateLimitService(
        app.state.session_factory, auth_hmac, audit_service
    )
    app.state.auth_service = AuthenticationService(
        app.state.session_factory,
        password_service,
        jwt_service,
        audit_service,
        auth_hmac,
        app.state.auth_rate_limit_service,
    )
    app.state.user_admin_service = UserAdministrationService(
        app.state.session_factory,
        password_service,
        app.state.auth_service,
        audit_service,
        auth_hmac,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(auth_router)
    app.include_router(user_admin_router)

    @app.exception_handler(PlatformError)
    async def handle_platform_error(request: Request, error: PlatformError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        problem = ProblemDetails(
            type=error.type,
            title=error.title,
            status=error.status,
            code=error.code,
            detail=error.detail,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=error.status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # Pydantic/FastAPI shape validation is a request-contract failure, not an
        # authentication credential/state failure. Keep one stable 422 semantic for
        # every formal API so clients can distinguish malformed input from business denial.
        status = 422
        code = "AUTH_REQUEST_VALIDATION_FAILED"
        field_errors = []
        for item in error.errors():
            location = item.get("loc", ())
            field = ".".join(str(part) for part in location if part not in {"body", "query"})
            field_errors.append(
                {
                    "field": field or "request",
                    "message": "Field validation failed.",
                }
            )
        problem = ProblemDetails(
            type="urn:problem:validation",
            title="Request validation failed",
            status=status,
            code=code,
            detail="One or more request fields failed validation.",
            correlation_id=getattr(request.state, "correlation_id", None),
            field_errors=field_errors,
        )
        return JSONResponse(
            status_code=status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    return app
