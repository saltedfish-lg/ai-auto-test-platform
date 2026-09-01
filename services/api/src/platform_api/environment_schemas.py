"""Pydantic contracts for the Authority-defined Environment aggregate."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EnvironmentLifecycleStatus = Literal[
    "CREATED",
    "CONFIGURING",
    "VALIDATING",
    "ACTIVE",
    "UNREACHABLE",
    "DISABLED",
    "RECOVERING",
    "ARCHIVED",
]
EnablementState = Literal["ENABLED", "DISABLED"]
AccessibilityState = Literal["UNKNOWN", "REACHABLE", "UNREACHABLE"]


class EnvironmentResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    project_id: str = Field(min_length=26, max_length=26)
    environment_code: str = Field(min_length=1, max_length=191)
    lifecycle_status: EnvironmentLifecycleStatus
    enablement_state: EnablementState
    accessibility_state: AccessibilityState


class CreateEnvironmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    environment_id: str | None = Field(default=None, min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    environment_code: str | None = Field(default=None, min_length=1, max_length=191)
    enablement_state: EnablementState | None = None
    accessibility_state: AccessibilityState | None = None

    @field_validator("environment_code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise ValueError("environment_code must not contain edge whitespace")
        return value

    @model_validator(mode="after")
    def require_business_identity(self) -> CreateEnvironmentRequest:
        if self.project_id is None or self.environment_code is None:
            raise ValueError("project_id and environment_code are required")
        if self.environment_id is not None:
            raise ValueError("environment_id is server generated")
        return self


class UpdateEnvironmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    display_name: str | None = Field(default=None, max_length=255)
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    environment_code: str | None = Field(default=None, min_length=1, max_length=191)
    enablement_state: EnablementState | None = None
    accessibility_state: AccessibilityState | None = None


class LifecycleCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: EnvironmentResource
    correlation_id: str


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class EnvironmentListData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[EnvironmentResource]
    page: PageMeta
