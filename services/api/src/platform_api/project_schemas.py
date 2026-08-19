"""Pydantic contracts for the governed Project aggregate foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectLifecycleStatus = Literal[
    "CREATED",
    "CONFIGURING",
    "VALIDATING",
    "ACTIVE",
    "DISABLED",
    "RECOVERING",
    "ARCHIVED",
    "CLEANUP_PENDING",
    "LOGICALLY_DELETED",
]


class ProjectOwnerResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    membership_status: Literal["ACTIVE"]


class ProjectResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    project_code: str = Field(min_length=1, max_length=191)
    lifecycle_status: ProjectLifecycleStatus
    owners: list[ProjectOwnerResource] = Field(min_length=1)


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    owner_user_id: str | None = Field(default=None, min_length=26, max_length=26)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("project_code")
    @classmethod
    def validate_project_code(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("project_code must not contain edge whitespace")
        return value


class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=1000)


class ProjectStateCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ProjectResource
    correlation_id: str


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ProjectListData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProjectResource]
    page: PageMeta


