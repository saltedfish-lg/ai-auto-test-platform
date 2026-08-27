"""Contracts for terminal-owned Web access revisions and login strategies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TerminalType = Literal["MANAGEMENT", "CLIENT", "PDA"]
TerminalLifecycleStatus = Literal[
    "CREATED",
    "CONFIGURING",
    "VALIDATING",
    "ACTIVE",
    "UNREACHABLE",
    "DISABLED",
    "RECOVERING",
    "ARCHIVED",
]
RevisionLifecycleStatus = Literal[
    "DRAFT",
    "VALIDATING",
    "PUBLISHED",
    "SUPERSEDED",
    "RETIRED",
    "ARCHIVED",
]
CaptchaPolicy = Literal["NONE", "RESPONSE_HEADER"]

_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "cookie",
    "credential",
    "jwt",
    "passwd",
    "password",
    "secret",
    "sessionid",
    "token",
)


def _reject_secret_keys(value: Any, path: str = "policy") -> Any:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).casefold()
            if any(marker in lowered for marker in _SECRET_MARKERS):
                raise ValueError(f"{path} must not contain credential or secret fields")
            _reject_secret_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_keys(nested, f"{path}[{index}]")
    return value


def normalize_web_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only absolute http/https URLs are allowed")
    host = parsed.hostname.lower()
    port = parsed.port
    if port is not None and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    if parsed.username or parsed.password:
        raise ValueError("URL user information is not allowed")
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), host, path, parsed.query, parsed.fragment))


class LocalStoragePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=191)
    value: str = Field(max_length=4000)
    scope: Literal["ORIGIN"] = "ORIGIN"
    set_before_login: bool = True

    @field_validator("key")
    @classmethod
    def reject_secret_key(cls, value: str) -> str:
        lowered = value.casefold()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            raise ValueError("localStorage preset keys must not represent credentials or secrets")
        return value


class AutomationAssetResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    automation_asset_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    lifecycle_status: str
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CreateAutomationAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=26, max_length=26)
    automation_asset_id: str | None = Field(default=None, min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)


class UpdateAutomationAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)


class LoginStrategyResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login_strategy_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    automation_asset_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    local_storage_presets: list[LocalStoragePreset]
    refresh_after_local_storage: bool
    captcha_policy: CaptchaPolicy
    captcha_request_header_name: str | None = None
    captcha_request_header_value: str | None = None
    captcha_response_header_name: str | None = None
    session_policy: dict[str, Any] | None = None
    lifecycle_status: str
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CreateLoginStrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=26, max_length=26)
    automation_asset_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    local_storage_presets: list[LocalStoragePreset] = Field(default_factory=list, max_length=50)
    refresh_after_local_storage: bool = False
    captcha_policy: CaptchaPolicy = "NONE"
    captcha_request_header_name: str | None = Field(default=None, max_length=191)
    captcha_request_header_value: str | None = Field(default=None, max_length=191)
    captcha_response_header_name: str | None = Field(default=None, max_length=191)
    session_policy: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_captcha_headers(self) -> CreateLoginStrategyRequest:
        headers = (
            self.captcha_request_header_name,
            self.captcha_request_header_value,
            self.captcha_response_header_name,
        )
        if self.captcha_policy == "NONE" and any(headers):
            raise ValueError("captcha headers require RESPONSE_HEADER policy")
        if self.captcha_policy == "RESPONSE_HEADER" and not all(headers):
            raise ValueError("RESPONSE_HEADER requires request name/value and response name")
        for name in (
            self.captcha_request_header_name,
            self.captcha_response_header_name,
        ):
            if name and any(marker in name.casefold() for marker in _SECRET_MARKERS):
                raise ValueError("captcha headers must not be credential or secret headers")
        _reject_secret_keys(self.session_policy)
        return self


class UpdateLoginStrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    local_storage_presets: list[LocalStoragePreset] | None = Field(default=None, max_length=50)
    refresh_after_local_storage: bool | None = None
    captcha_policy: CaptchaPolicy | None = None
    captcha_request_header_name: str | None = Field(default=None, max_length=191)
    captcha_request_header_value: str | None = Field(default=None, max_length=191)
    captcha_response_header_name: str | None = Field(default=None, max_length=191)
    session_policy: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reject_secret_policy(self) -> UpdateLoginStrategyRequest:
        for field in (
            "local_storage_presets",
            "refresh_after_local_storage",
            "captcha_policy",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} may be omitted but must not be null")
        for name in (
            self.captcha_request_header_name,
            self.captcha_response_header_name,
        ):
            if name and any(marker in name.casefold() for marker in _SECRET_MARKERS):
                raise ValueError("captcha headers must not be credential or secret headers")
        _reject_secret_keys(self.session_policy)
        return self


class BusinessTerminalResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_terminal_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    environment_id: str = Field(min_length=26, max_length=26)
    terminal_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    terminal_type: TerminalType
    current_published_revision_id: str | None = Field(default=None, min_length=26, max_length=26)
    lifecycle_status: TerminalLifecycleStatus
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CreateBusinessTerminalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment_id: str = Field(min_length=26, max_length=26)
    terminal_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    terminal_type: TerminalType
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("terminal_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("terminal_code must not contain edge whitespace")
        return value


class UpdateBusinessTerminalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)


class LifecycleCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class TerminalAccessRevisionResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment_terminal_access_revision_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    environment_id: str = Field(min_length=26, max_length=26)
    business_terminal_id: str = Field(min_length=26, max_length=26)
    revision_no: int = Field(ge=1)
    entry_url: str
    login_url: str | None = None
    login_strategy_id: str | None = Field(default=None, min_length=26, max_length=26)
    login_prerequisites: dict[str, Any] | None = None
    network_requirements: dict[str, Any] | None = None
    display_name: str | None = Field(default=None, max_length=255)
    lifecycle_status: RevisionLifecycleStatus
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CreateTerminalAccessRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_terminal_id: str = Field(min_length=26, max_length=26)
    entry_url: str = Field(min_length=1, max_length=2048)
    login_url: str | None = Field(default=None, max_length=2048)
    login_strategy_id: str | None = Field(default=None, min_length=26, max_length=26)
    login_prerequisites: dict[str, Any] | None = None
    network_requirements: dict[str, Any] | None = None
    display_name: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("entry_url", "login_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return normalize_web_url(value)


class PublishTerminalAccessRevisionRequest(LifecycleCommandRequest):
    expected_terminal_version: int = Field(ge=0)


class BusinessTerminalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: BusinessTerminalResource
    correlation_id: str


class LoginStrategyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: LoginStrategyResource
    correlation_id: str


class AutomationAssetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: AutomationAssetResource
    correlation_id: str


class TerminalAccessRevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: TerminalAccessRevisionResource
    correlation_id: str


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class BusinessTerminalListData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BusinessTerminalResource]
    page: PageMeta


class LoginStrategyListData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LoginStrategyResource]
    page: PageMeta


class AutomationAssetListData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AutomationAssetResource]
    page: PageMeta


class TerminalAccessRevisionListData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TerminalAccessRevisionResource]
    page: PageMeta
