"""FastAPI adapter for the six current P1 user-governance operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Request, Response

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.auth_schemas import (
    CreateUserRequest,
    CreateUserResponse,
    CreateUserRoleBindingRequest,
    OneTimeCredentialDeliveryResponse,
    ResetUserCredentialRequest,
    RevokeUserRoleBindingRequest,
    UpdateUserResponse,
    UserRoleBindingResponse,
    UserStateCommandRequest,
)
from platform_api.errors import PlatformError
from platform_api.user_admin_service import UserAdministrationService

router = APIRouter(tags=["用户"])


def _service(request: Request) -> UserAdministrationService:
    service = getattr(request.app.state, "user_admin_service", None)
    if not isinstance(service, UserAdministrationService):
        raise PlatformError(
            title="User administration is unavailable",
            detail="The user administration service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.post(
    "/api/v1/user",
    response_model=CreateUserResponse,
    response_model_exclude_none=True,
    operation_id="create_user",
)
def create_user(
    body: CreateUserRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> CreateUserResponse:
    result = _service(request).create_user(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    response.status_code = result.status_code
    return CreateUserResponse(data=result.data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/user/{id}/credential-reset",
    response_model=OneTimeCredentialDeliveryResponse,
    response_model_exclude_none=True,
    operation_id="reset_user_credential",
)
def reset_user_credential(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: ResetUserCredentialRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> OneTimeCredentialDeliveryResponse:
    result = _service(request).reset_credential(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return OneTimeCredentialDeliveryResponse(
        data=result.data, correlation_id=_correlation_id(request)
    )


@router.post(
    "/api/v1/user/{id}/enable",
    response_model=UpdateUserResponse,
    operation_id="enable_user",
)
def enable_user(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UserStateCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> UpdateUserResponse:
    user = _service(request).set_user_state(
        _bearer(authorization),
        id,
        body,
        idempotency_key,
        _audit_context(request),
        enable=True,
    )
    return UpdateUserResponse(data=user, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/user/{id}/disable",
    response_model=UpdateUserResponse,
    operation_id="disable_user",
)
def disable_user(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: UserStateCommandRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> UpdateUserResponse:
    user = _service(request).set_user_state(
        _bearer(authorization),
        id,
        body,
        idempotency_key,
        _audit_context(request),
        enable=False,
    )
    return UpdateUserResponse(data=user, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/user-role-binding",
    status_code=201,
    response_model=UserRoleBindingResponse,
    operation_id="create_user_role_binding",
)
def create_user_role_binding(
    body: CreateUserRoleBindingRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> UserRoleBindingResponse:
    binding = _service(request).create_role_binding(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return UserRoleBindingResponse(data=binding, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/user-role-binding/{id}/revoke",
    response_model=UserRoleBindingResponse,
    operation_id="revoke_user_role_binding",
)
def revoke_user_role_binding(
    id: Annotated[str, Path(min_length=26, max_length=26)],
    body: RevokeUserRoleBindingRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> UserRoleBindingResponse:
    binding = _service(request).revoke_role_binding(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return UserRoleBindingResponse(data=binding, correlation_id=_correlation_id(request))
