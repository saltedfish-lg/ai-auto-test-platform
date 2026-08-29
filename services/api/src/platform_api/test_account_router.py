"""FastAPI adapter for Test Account Foundation."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.test_account_schemas import (
    CreateTestAccountRequest,
    RotateTestAccountSecretRequest,
    TestAccountLifecycleRequest,
    TestAccountListData,
    TestAccountResponse,
    UpdateTestAccountRequest,
)
from platform_api.test_account_service import TestAccountService

router = APIRouter(tags=["测试账号"])


def _service(request: Request) -> TestAccountService:
    value = getattr(request.app.state, "test_account_service", None)
    if not isinstance(value, TestAccountService):
        raise PlatformError(
            title="Test Account management is unavailable",
            detail="The Test Account service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return value


@router.get(
    "/api/v1/test-account",
    response_model=TestAccountListData,
    operation_id="list_test_account",
)
def list_test_account(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    filter: str | None = Query(None, max_length=1000),
    authorization: str | None = Header(None),
) -> TestAccountListData:
    return _service(request).list(
        _bearer(authorization), page, page_size, filter, _audit_context(request)
    )


@router.post(
    "/api/v1/test-account",
    status_code=201,
    response_model=TestAccountResponse,
    operation_id="create_test_account",
)
def create_test_account(
    body: CreateTestAccountRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TestAccountResponse:
    data = _service(request).create(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return TestAccountResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/test-account/{id}",
    response_model=TestAccountResponse,
    operation_id="get_test_account",
)
def get_test_account(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    request: Request,
    authorization: str | None = Header(None),
) -> TestAccountResponse:
    data = _service(request).get(_bearer(authorization), id, _audit_context(request))
    return TestAccountResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/test-account/{id}",
    response_model=TestAccountResponse,
    operation_id="update_test_account",
)
def update_test_account(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UpdateTestAccountRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TestAccountResponse:
    data = _service(request).update(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TestAccountResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/test-account/{id}/credential-rotate",
    response_model=TestAccountResponse,
    operation_id="rotate_test_account_secret",
)
def rotate_test_account_secret(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: RotateTestAccountSecretRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(None),
) -> TestAccountResponse:
    data = _service(request).rotate_secret(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TestAccountResponse(data=data, correlation_id=_correlation_id(request))


def _command_route(action: str) -> Callable[..., TestAccountResponse]:
    def command(
        id: Annotated[str, Path(min_length=26, max_length=26)],
        body: TestAccountLifecycleRequest,
        request: Request,
        idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
        authorization: str | None = Header(None),
    ) -> TestAccountResponse:
        data = _service(request).transition(
            _bearer(authorization),
            id,
            action,
            body,
            idempotency_key,
            _audit_context(request),
        )
        return TestAccountResponse(data=data, correlation_id=_correlation_id(request))

    command.__name__ = f"{action.replace('-', '_')}_test_account"
    return command


for _action in (
    "validate",
    "reconfigure",
    "activate",
    "mark-credential-expired",
    "recover",
    "disable",
    "archive",
):
    router.add_api_route(
        f"/api/v1/test-account/{{id}}/{_action}",
        _command_route(_action),
        methods=["POST"],
        response_model=TestAccountResponse,
        operation_id=f"{_action.replace('-', '_')}_test_account",
    )
