"""FastAPI adapter for the five current P1 authentication operations."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Header, Request, Response

from platform_api.audit import AuditContext
from platform_api.auth_schemas import (
    AuthCookieActionRequest,
    AuthenticationResponse,
    AuthenticationTokenResource,
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
)
from platform_api.auth_service import AuthenticationResult, AuthenticationService
from platform_api.errors import PlatformError

REFRESH_COOKIE_NAME = "atp_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE = 604800

router = APIRouter(prefix="/api/v1/auth", tags=["身份认证"])


def _service(request: Request) -> AuthenticationService:
    service = getattr(request.app.state, "auth_service", None)
    if not isinstance(service, AuthenticationService):
        raise PlatformError(
            title="Authentication is unavailable",
            detail="Authentication key material has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


def _correlation_id(request: Request) -> str:
    return str(request.state.correlation_id)


def _source_context(request: Request) -> str:
    user_agent = request.headers.get("user-agent", "")[:512]
    client = request.client.host if request.client is not None else ""
    return f"{client}|{user_agent}"


def _audit_context(request: Request) -> AuditContext:
    return AuditContext(_correlation_id(request), _source_context(request))


def _bearer(authorization: str | None) -> str:
    if authorization is None:
        raise PlatformError(
            title="Authentication required",
            detail="A Bearer access token is required.",
            status=401,
            code="AUTH_REQUIRED",
        )
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.casefold() != "bearer" or not token:
        raise PlatformError(
            title="Invalid access token",
            detail="The Authorization header is invalid.",
            status=401,
            code="AUTH_TOKEN_INVALID",
        )
    return token


def _require_same_origin(request: Request) -> None:
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        if fetch_site in {"same-origin", "none"}:
            return
        raise _same_origin_error()
    origin = request.headers.get("origin")
    if origin is None:
        raise _same_origin_error()
    parsed = urlsplit(origin)
    expected_host = request.headers.get("host")
    expected_scheme = request.url.scheme
    if (
        parsed.scheme != expected_scheme
        or parsed.scheme not in {"http", "https"}
        or parsed.netloc.casefold() != (expected_host or "").casefold()
    ):
        raise _same_origin_error()


def _same_origin_error() -> PlatformError:
    return PlatformError(
        title="Same-origin request required",
        detail="This cookie operation requires a same-origin browser request.",
        status=403,
        code="AUTH_OPERATION_FORBIDDEN_FOR_STATE",
    )


def _set_refresh_cookie(response: Response, request: Request, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=request.app.state.settings.refresh_cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        httponly=True,
        secure=request.app.state.settings.refresh_cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _authentication_response(
    result: AuthenticationResult, correlation_id: str
) -> AuthenticationResponse:
    return AuthenticationResponse(
        data=AuthenticationTokenResource(
            access_token=result.access_token,
            expires_in=900,
            current_user=result.current_user,
        ),
        correlation_id=correlation_id,
    )


@router.post("/login", response_model=AuthenticationResponse, operation_id="login_platform_user")
def login_platform_user(
    body: LoginRequest, request: Request, response: Response
) -> AuthenticationResponse:
    result = _service(request).login(body.username, body.password, _audit_context(request))
    _set_refresh_cookie(response, request, result.refresh_token)
    return _authentication_response(result, _correlation_id(request))


@router.post(
    "/refresh", response_model=AuthenticationResponse, operation_id="refresh_platform_session"
)
def refresh_platform_session(
    request: Request,
    response: Response,
    body: AuthCookieActionRequest | None = None,
) -> AuthenticationResponse:
    del body
    _require_same_origin(request)
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    result = _service(request).refresh(token, _audit_context(request))
    _set_refresh_cookie(response, request, result.refresh_token)
    return _authentication_response(result, _correlation_id(request))


@router.post(
    "/logout",
    status_code=204,
    response_model=None,
    response_class=Response,
    operation_id="logout_platform_user",
)
def logout_platform_user(
    request: Request,
    response: Response,
    body: AuthCookieActionRequest | None = None,
) -> None:
    del body
    _require_same_origin(request)
    _service(request).logout(request.cookies.get(REFRESH_COOKIE_NAME), _audit_context(request))
    _clear_refresh_cookie(response, request)


@router.get("/me", response_model=CurrentUserResponse, operation_id="get_current_user")
def get_current_user(
    request: Request, authorization: str | None = Header(default=None)
) -> CurrentUserResponse:
    token = _bearer(authorization)
    _, current_user = _service(request).authenticate_access(
        token, "get_current_user", _audit_context(request)
    )
    return CurrentUserResponse(data=current_user, correlation_id=_correlation_id(request))


@router.post(
    "/change-password",
    response_model=AuthenticationResponse,
    operation_id="change_current_user_password",
)
def change_current_user_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> AuthenticationResponse:
    token = _bearer(authorization)
    result = _service(request).change_password(
        token,
        body.current_password,
        body.new_password,
        idempotency_key,
        _audit_context(request),
    )
    _set_refresh_cookie(response, request, result.refresh_token)
    return _authentication_response(result, _correlation_id(request))
