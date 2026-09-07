"""FastAPI adapter for Business Terminal Foundation."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.automation_asset_service import AutomationAssetService
from platform_api.business_terminal_schemas import (
    AutomationAssetListData,
    AutomationAssetResponse,
    BusinessTerminalListData,
    BusinessTerminalResponse,
    CreateAutomationAssetRequest,
    CreateBusinessTerminalRequest,
    CreateLoginStrategyRequest,
    CreateTerminalAccessRevisionRequest,
    LifecycleCommandRequest,
    LoginStrategyListData,
    LoginStrategyResponse,
    PublishTerminalAccessRevisionRequest,
    TerminalAccessRevisionListData,
    TerminalAccessRevisionResponse,
    UpdateAutomationAssetRequest,
    UpdateBusinessTerminalRequest,
    UpdateLoginStrategyRequest,
    UpdateTerminalAccessRevisionRequest,
)
from platform_api.business_terminal_service import BusinessTerminalService
from platform_api.errors import PlatformError

router = APIRouter(tags=["业务终端"])


def _service(request: Request) -> BusinessTerminalService:
    value = getattr(request.app.state, "business_terminal_service", None)
    if not isinstance(value, BusinessTerminalService):
        raise PlatformError(
            title="Business Terminal management is unavailable",
            detail="The Business Terminal service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return value


def _automation_asset_service(request: Request) -> AutomationAssetService:
    value = getattr(request.app.state, "automation_asset_service", None)
    if not isinstance(value, AutomationAssetService):
        raise PlatformError(
            title="Automation Asset management is unavailable",
            detail="The Automation Asset service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return value


@router.get(
    "/api/v1/business-terminal",
    response_model=BusinessTerminalListData,
    operation_id="list_business_terminal",
)
def list_business_terminal(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: str | None = Query(None, max_length=1000),
    authorization: str | None = Header(None),
) -> BusinessTerminalListData:
    return _service(request).list_terminals(
        _bearer(authorization), page, page_size, filter, _audit_context(request)
    )


@router.post(
    "/api/v1/business-terminal",
    status_code=201,
    response_model=BusinessTerminalResponse,
    operation_id="create_business_terminal",
)
def create_business_terminal(
    body: CreateBusinessTerminalRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> BusinessTerminalResponse:
    data = _service(request).create_terminal(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return BusinessTerminalResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/business-terminal/{id}",
    response_model=BusinessTerminalResponse,
    operation_id="get_business_terminal",
)
def get_business_terminal(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> BusinessTerminalResponse:
    data = _service(request).get_terminal(_bearer(authorization), id, _audit_context(request))
    return BusinessTerminalResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/business-terminal/{id}",
    response_model=BusinessTerminalResponse,
    operation_id="update_business_terminal",
)
def update_business_terminal(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateBusinessTerminalRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> BusinessTerminalResponse:
    data = _service(request).update_terminal(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return BusinessTerminalResponse(data=data, correlation_id=_correlation_id(request))


def _terminal_command(
    action: str,
    id: str,
    body: LifecycleCommandRequest,
    request: Request,
    key: str,
    authorization: str | None,
) -> BusinessTerminalResponse:
    data = _service(request).transition_terminal(
        _bearer(authorization), id, action, body, key, _audit_context(request)
    )
    return BusinessTerminalResponse(data=data, correlation_id=_correlation_id(request))


def _command_route(action: str) -> Callable[..., BusinessTerminalResponse]:
    def command(
        id: Annotated[str, Path(min_length=26, max_length=26)],
        body: LifecycleCommandRequest,
        request: Request,
        idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
        authorization: str | None = Header(None),
    ) -> BusinessTerminalResponse:
        return _terminal_command(action, id, body, request, idempotency_key, authorization)

    command.__name__ = f"{action.replace('-', '_')}_business_terminal"
    return command


for _action in (
    "validate",
    "reconfigure",
    "activate",
    "mark-unreachable",
    "recover",
    "disable",
    "archive",
):
    router.add_api_route(
        f"/api/v1/business-terminal/{{id}}/{_action}",
        _command_route(_action),
        methods=["POST"],
        response_model=BusinessTerminalResponse,
        operation_id=f"{_action.replace('-', '_')}_business_terminal",
    )


@router.get(
    "/api/v1/automation-asset",
    response_model=AutomationAssetListData,
    operation_id="list_automation_asset",
)
def list_automation_asset(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: str | None = Query(None, max_length=1000),
    authorization: str | None = Header(None),
) -> AutomationAssetListData:
    return _automation_asset_service(request).list_automation_assets(
        _bearer(authorization), page, page_size, filter, _audit_context(request)
    )


@router.post(
    "/api/v1/automation-asset",
    status_code=201,
    response_model=AutomationAssetResponse,
    operation_id="create_automation_asset",
)
def create_automation_asset(
    body: CreateAutomationAssetRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> AutomationAssetResponse:
    data = _automation_asset_service(request).create_automation_asset(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return AutomationAssetResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/automation-asset/{id}",
    response_model=AutomationAssetResponse,
    operation_id="get_automation_asset",
)
def get_automation_asset(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> AutomationAssetResponse:
    data = _automation_asset_service(request).get_automation_asset(
        _bearer(authorization), id, _audit_context(request)
    )
    return AutomationAssetResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/automation-asset/{id}",
    response_model=AutomationAssetResponse,
    operation_id="update_automation_asset",
)
def update_automation_asset(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateAutomationAssetRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> AutomationAssetResponse:
    data = _automation_asset_service(request).update_automation_asset(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return AutomationAssetResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/login-strategy",
    response_model=LoginStrategyListData,
    operation_id="list_login_strategy",
)
def list_login_strategy(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: str | None = Query(None, max_length=1000),
    authorization: str | None = Header(None),
) -> LoginStrategyListData:
    return _automation_asset_service(request).list_login_strategies(
        _bearer(authorization), page, page_size, filter, _audit_context(request)
    )


@router.post(
    "/api/v1/login-strategy",
    status_code=201,
    response_model=LoginStrategyResponse,
    operation_id="create_login_strategy",
)
def create_login_strategy(
    body: CreateLoginStrategyRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> LoginStrategyResponse:
    data = _automation_asset_service(request).create_login_strategy(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return LoginStrategyResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/login-strategy/{id}/activate",
    response_model=LoginStrategyResponse,
    operation_id="activate_login_strategy",
)
def activate_login_strategy(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: LifecycleCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> LoginStrategyResponse:
    data = _automation_asset_service(request).activate_login_strategy(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return LoginStrategyResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/login-strategy/{id}",
    response_model=LoginStrategyResponse,
    operation_id="get_login_strategy",
)
def get_login_strategy(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> LoginStrategyResponse:
    data = _automation_asset_service(request).get_login_strategy(
        _bearer(authorization), id, _audit_context(request)
    )
    return LoginStrategyResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/login-strategy/{id}",
    response_model=LoginStrategyResponse,
    operation_id="update_login_strategy",
)
def update_login_strategy(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateLoginStrategyRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> LoginStrategyResponse:
    data = _automation_asset_service(request).update_login_strategy(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return LoginStrategyResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/environment-terminal-access-revision",
    response_model=TerminalAccessRevisionListData,
    operation_id="list_environment_terminal_access_revision",
)
def list_environment_terminal_access_revision(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: str | None = Query(None, max_length=1000),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionListData:
    return _service(request).list_revisions(
        _bearer(authorization), page, page_size, filter, _audit_context(request)
    )


@router.post(
    "/api/v1/environment-terminal-access-revision",
    status_code=201,
    response_model=TerminalAccessRevisionResponse,
    operation_id="create_environment_terminal_access_revision",
)
def create_environment_terminal_access_revision(
    body: CreateTerminalAccessRevisionRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).create_revision(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/environment-terminal-access-revision/{id}",
    response_model=TerminalAccessRevisionResponse,
    operation_id="get_environment_terminal_access_revision",
)
def get_environment_terminal_access_revision(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).get_revision(_bearer(authorization), id, _audit_context(request))
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/environment-terminal-access-revision/{id}",
    response_model=TerminalAccessRevisionResponse,
    operation_id="update_environment_terminal_access_revision",
)
def update_environment_terminal_access_revision(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateTerminalAccessRevisionRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).update_revision(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/environment-terminal-access-revision/{id}/validate",
    response_model=TerminalAccessRevisionResponse,
    operation_id="validate_environment_terminal_access_revision",
)
def validate_environment_terminal_access_revision(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: LifecycleCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).validate_revision(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/environment-terminal-access-revision/{id}/return-to-draft",
    response_model=TerminalAccessRevisionResponse,
    operation_id="return_to_draft_environment_terminal_access_revision",
)
def return_to_draft_environment_terminal_access_revision(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: LifecycleCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).return_revision_to_draft(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/environment-terminal-access-revision/{id}/abandon",
    response_model=TerminalAccessRevisionResponse,
    operation_id="abandon_environment_terminal_access_revision",
)
def abandon_environment_terminal_access_revision(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: LifecycleCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).abandon_revision(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/environment-terminal-access-revision/{id}/publish",
    response_model=TerminalAccessRevisionResponse,
    operation_id="publish_environment_terminal_access_revision",
)
def publish_environment_terminal_access_revision(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: PublishTerminalAccessRevisionRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TerminalAccessRevisionResponse:
    data = _service(request).publish_revision(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TerminalAccessRevisionResponse(data=data, correlation_id=_correlation_id(request))
