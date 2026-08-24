"""Public contracts for platform-level AI model configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

ProviderCode = Literal["OPENAI", "ANTHROPIC", "DEEPSEEK", "QWEN", "DOUBAO"]
ModelConfigurationLifecycleStatus = Literal[
    "CREATED",
    "CONFIGURING",
    "VALIDATING",
    "ACTIVE",
    "DEGRADED",
    "UNAVAILABLE",
    "DISABLED",
    "RECOVERING",
    "ARCHIVED",
]
ModelConnectionStatus = Literal[
    "SUCCESS",
    "AUTHENTICATION_FAILED",
    "MODEL_NOT_FOUND",
    "TIMEOUT",
    "RATE_LIMITED",
    "PROVIDER_ERROR",
    "INVALID_CONFIGURATION",
]


def _without_edge_whitespace(value: str, field_name: str) -> str:
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain edge whitespace")
    return value


class ModelConfigResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_config_id: str = Field(min_length=26, max_length=26)
    config_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    provider_code: ProviderCode
    model_name: str = Field(min_length=1, max_length=191)
    request_timeout_seconds: int = Field(ge=1, le=300)
    lifecycle_status: ModelConfigurationLifecycleStatus
    secret_configured: bool
    is_ai_exploration_default: bool
    ai_exploration_default_version: int | None = Field(default=None, ge=0)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CreateModelConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    provider_code: ProviderCode
    model_name: str = Field(min_length=1, max_length=191)
    secret_value: SecretStr = Field(min_length=1, max_length=4096, repr=False)
    request_timeout_seconds: int = Field(default=30, ge=1, le=300)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("config_code", "model_name")
    @classmethod
    def validate_text(cls, value: str, info: object) -> str:
        return _without_edge_whitespace(value, getattr(info, "field_name", "value"))


class UpdateModelConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    provider_code: ProviderCode | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=191)
    secret_value: SecretStr | None = Field(
        default=None, min_length=1, max_length=4096, repr=False
    )
    request_timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _without_edge_whitespace(value, "model_name")


class ModelConfigLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return _without_edge_whitespace(value, "reason")


class TestModelConfigConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


class ModelConnectionTestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ModelConnectionStatus
    provider_code: ProviderCode
    model_name: str
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, max_length=128)
    message: str | None = Field(default=None, max_length=1000)


class CapabilityDefaultResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_code: Literal["AI_EXPLORATION"]
    model_config_id: str = Field(min_length=26, max_length=26)
    row_version: int = Field(ge=0)
    updated_at: datetime


class SetCapabilityDefaultModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_config_id: str = Field(min_length=26, max_length=26)
    expected_version: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class ClearCapabilityDefaultModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class ClearCapabilityDefaultResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_code: Literal["AI_EXPLORATION"]
    cleared: Literal[True]


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ModelConfigListData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ModelConfigResource]
    page: PageMeta


class ModelConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ModelConfigResource
    correlation_id: str


class TestModelConfigConnectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ModelConnectionTestResult
    correlation_id: str


class SetCapabilityDefaultModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: CapabilityDefaultResource
    correlation_id: str


class ClearCapabilityDefaultModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ClearCapabilityDefaultResult
    correlation_id: str
