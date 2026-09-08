"""Application assembly for the current P1 platform API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from platform_observability import configure_logging

from platform_api.ai_exploration_router import router as ai_exploration_router
from platform_api.ai_exploration_service import AIExplorationService, BoundRunnerBrowserRuntime
from platform_api.audit import AuthenticationAuditService
from platform_api.auth_hmac import AuthHmacKeyRing
from platform_api.auth_router import router as auth_router
from platform_api.auth_service import AuthenticationService
from platform_api.automation_asset_service import AutomationAssetService
from platform_api.business_terminal_router import router as business_terminal_router
from platform_api.business_terminal_service import BusinessTerminalService
from platform_api.config import ApiSettings
from platform_api.database import create_database_engine, create_session_factory
from platform_api.environment_router import router as environment_router
from platform_api.environment_service import EnvironmentService
from platform_api.errors import PlatformError, ProblemDetails
from platform_api.execution_binding_router import router as execution_binding_router
from platform_api.execution_binding_service import ExecutionBindingService
from platform_api.execution_owner_router import router as execution_owner_router
from platform_api.execution_owner_service import ExecutionOwnerService
from platform_api.execution_slot_router import router as execution_slot_router
from platform_api.execution_slot_service import ExecutionSlotService
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.middleware import CorrelationIdMiddleware
from platform_api.model_configuration_router import (
    router as model_configuration_router,
)
from platform_api.model_configuration_service import ModelConfigurationService
from platform_api.model_gateway import LiteLLMModelGateway
from platform_api.project_router import router as project_router
from platform_api.project_service import ProjectService
from platform_api.rate_limit import AuthenticationRateLimitService
from platform_api.runner_browser_channel import (
    DirectRunnerBrowserRuntime,
    RunnerBrowserCommandBroker,
)
from platform_api.runner_router import router as runner_router
from platform_api.runner_service import RunnerService
from platform_api.schema_preflight import SchemaPreflightFailure, run_schema_preflight
from platform_api.secret_store import AesGcmSecretProtector, UnavailableSecretProtector
from platform_api.security import JwtKeyRing, JwtService, PasswordService
from platform_api.session_service import SessionService
from platform_api.test_account_router import router as test_account_router
from platform_api.test_account_service import TestAccountService
from platform_api.user_admin_router import router as user_admin_router
from platform_api.user_admin_service import UserAdministrationService

LOGGER = logging.getLogger(__name__)


def _request_correlation_id(request: Request) -> str:
    """异常响应始终携带可追踪标识, 避免异常中间件路径产生无证据的 ProblemDetails。"""
    correlation_id = getattr(request.state, "correlation_id", None)
    return correlation_id if isinstance(correlation_id, str) and correlation_id else str(uuid4())


def create_app(
    settings: ApiSettings,
    *,
    ai_exploration_browser_runtime: BoundRunnerBrowserRuntime | None = None,
) -> FastAPI:
    configure_logging(settings.log_level)
    jwt_service = JwtService(JwtKeyRing.load(settings.jwt_key_ring_file))
    auth_hmac = AuthHmacKeyRing.load(settings.auth_hmac_master_key_file)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.schema_preflight_mode == "required":
            try:
                result = run_schema_preflight(
                    engine,
                    authority_root=settings.migration_authority_root,
                )
            except SchemaPreflightFailure as error:
                LOGGER.critical(
                    "database schema preflight failed",
                    extra={
                        "service": settings.service_name,
                        "preflight_code": error.code,
                        **error.metadata,
                    },
                )
                engine.dispose()
                raise RuntimeError(f"DATABASE_SCHEMA_PREFLIGHT_FAILED:{error.code}") from None
            app.state.schema_preflight = result
            LOGGER.info(
                "database schema preflight passed",
                extra={
                    "service": settings.service_name,
                    "migration_head": result["migration_head"],
                    "migration_version": result["migration_version"],
                },
            )
        else:
            app.state.schema_preflight = {"status": "DISABLED"}
        LOGGER.info("api process started", extra={"service": settings.service_name})
        try:
            yield
        finally:
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
    session_service = SessionService(audit_service)
    idempotency = IdempotencyCoordinator(auth_hmac)
    app.state.auth_rate_limit_service = AuthenticationRateLimitService(
        app.state.session_factory, auth_hmac, audit_service
    )
    app.state.auth_service = AuthenticationService(
        app.state.session_factory,
        password_service,
        jwt_service,
        audit_service,
        app.state.auth_rate_limit_service,
        session_service,
        idempotency,
    )
    app.state.user_admin_service = UserAdministrationService(
        app.state.session_factory,
        password_service,
        app.state.auth_service,
        audit_service,
        idempotency,
        session_service,
    )
    app.state.project_service = ProjectService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    app.state.environment_service = EnvironmentService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    app.state.business_terminal_service = BusinessTerminalService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    app.state.automation_asset_service = AutomationAssetService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    secret_protector = (
        AesGcmSecretProtector.load(settings.model_secret_key_ring_file)
        if settings.model_secret_key_ring_file is not None
        else UnavailableSecretProtector()
    )
    app.state.model_configuration_service = ModelConfigurationService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
        secret_protector,
        LiteLLMModelGateway(
            settings.litellm_proxy_url,
            settings.litellm_proxy_api_key_file,
            dynamic_credentials_enabled=settings.litellm_dynamic_credentials_enabled,
        ),
    )
    app.state.test_account_service = TestAccountService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
        secret_protector,
    )
    app.state.runner_service = RunnerService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    app.state.execution_binding_service = ExecutionBindingService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    app.state.execution_owner_service = ExecutionOwnerService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
    )
    app.state.execution_slot_service = ExecutionSlotService(
        app.state.session_factory,
        app.state.auth_service,
    )
    app.state.runner_browser_command_broker = RunnerBrowserCommandBroker()
    browser_runtime = ai_exploration_browser_runtime or DirectRunnerBrowserRuntime(
        app.state.runner_browser_command_broker
    )
    app.state.ai_exploration_service = AIExplorationService(
        app.state.session_factory,
        app.state.auth_service,
        idempotency,
        app.state.model_configuration_service,
        browser_runtime=browser_runtime,
        secret_protector=secret_protector,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(auth_router)
    app.include_router(user_admin_router)
    app.include_router(project_router)
    app.include_router(environment_router)
    app.include_router(business_terminal_router)
    app.include_router(test_account_router)
    app.include_router(runner_router)
    app.include_router(execution_binding_router)
    app.include_router(execution_owner_router)
    app.include_router(execution_slot_router)
    app.include_router(model_configuration_router)
    app.include_router(ai_exploration_router)

    @app.exception_handler(PlatformError)
    async def handle_platform_error(request: Request, error: PlatformError) -> JSONResponse:
        correlation_id = _request_correlation_id(request)
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
        # 校验错误只返回字段定位而不回显输入值, 避免密码等秘密进入 ProblemDetails。
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
            correlation_id=_request_correlation_id(request),
            field_errors=field_errors,
        )
        return JSONResponse(
            status_code=status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        # 异常消息和堆栈可能夹带凭据或数据库秘密, 因此日志仅保留类型与追踪标识。
        correlation_id = _request_correlation_id(request)
        LOGGER.error(
            "unhandled API exception",
            extra={
                "correlation_id": correlation_id,
                "exception_type": type(error).__name__,
            },
        )
        problem = ProblemDetails(
            type="about:blank",
            title="Internal server error",
            status=500,
            code="INTERNAL_ERROR",
            detail="The request could not be completed.",
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    return app
