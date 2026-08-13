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
from platform_api.rate_limit import resolve_source_ip

REFRESH_COOKIE_NAME = "atp_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE = 604800

router = APIRouter(prefix="/api/v1/auth", tags=["身份认证"])


def _service(request: Request) -> AuthenticationService:
    """路由层只构造认证服务依赖，确保HTTP入口不会复制或分叉核心认证安全规则。"""
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


def _source_ip(request: Request) -> str:
    """来源地址只作为审计上下文提取，避免把不可信代理头直接提升为认证或授权依据。"""
    peer = request.client.host if request.client is not None else ""
    return resolve_source_ip(
        peer,
        request.headers.get("forwarded"),
        request.headers.get("x-forwarded-for"),
        request.app.state.settings.trusted_proxy_networks,
    )


def _audit_context(request: Request) -> AuditContext:
    """审计上下文统一从请求提取，确保各认证端点记录一致的来源与客户端证据。"""
    return AuditContext(_correlation_id(request), _source_context(request))


def _bearer(authorization: str | None) -> str:
    """Bearer解析必须严格拒绝缺失或畸形头，避免宽松解析让非标准凭据进入认证服务。"""
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
    """状态变更请求需要同源约束，避免浏览器携带会话时被跨站请求触发敏感认证操作。"""
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
    """登录路由只负责协议转换并委托认证服务，避免HTTP层绕过事务、锁定和审计规则。"""
    result = _service(request).login(
        body.username,
        body.password,
        _audit_context(request),
        _source_ip(request),
    )
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
    """刷新路由统一传递刷新凭据和审计上下文，确保旋转与重放检测只由认证服务裁决。"""
    del body
    _require_same_origin(request)
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    result = _service(request).refresh(token, _audit_context(request), _source_ip(request))
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
    """登出路由统一委托服务撤销会话，确保客户端响应与服务端失效语义保持一致。"""
    del body
    _require_same_origin(request)
    _service(request).logout(request.cookies.get(REFRESH_COOKIE_NAME), _audit_context(request))
    _clear_refresh_cookie(response, request)


@router.get("/me", response_model=CurrentUserResponse, operation_id="get_current_user")
def get_current_user(
    request: Request, authorization: str | None = Header(default=None)
) -> CurrentUserResponse:
    """当前用户接口必须基于已验证访问令牌获取身份，避免仅凭请求参数读取受保护用户信息。"""
    token = _bearer(authorization)
    _, current_user = _service(request).authenticate_access(
        token, "get_current_user", _audit_context(request)
    )
    return CurrentUserResponse(data=current_user, correlation_id=_correlation_id(request))


@router.post(
    "/change-password",
    status_code=204,
    response_model=None,
    response_class=Response,
    operation_id="change_current_user_password",
)
def change_current_user_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """改密路由必须传递幂等键和已验证身份，确保重试与安全事务由认证服务统一处理。"""
    token = _bearer(authorization)
    _service(request).change_password(
        token,
        body.current_password,
        body.new_password,
        idempotency_key,
        _audit_context(request),
    )
    _clear_refresh_cookie(response, request)
