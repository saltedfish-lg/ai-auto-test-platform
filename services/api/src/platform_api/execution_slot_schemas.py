"""Contracts for system-managed Runner formal execution slots."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExecutionSlotLifecycleStatus = Literal[
    "CREATED",
    "DRAFT",
    "ACTIVE",
    "DISABLED",
    "RECOVERED",
    "ARCHIVED",
    "LOGICALLY_DELETED",
]
ExecutionSlotAvailabilityStatus = Literal["AVAILABLE", "OCCUPIED", "UNAVAILABLE"]


class ExecutionSlotResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_slot_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    runner_id: str = Field(min_length=26, max_length=26)
    slot_no: str | None = Field(default=None, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    lifecycle_status: ExecutionSlotLifecycleStatus
    availability_status: ExecutionSlotAvailabilityStatus
    active_lease_owner: str | None = Field(default=None, min_length=26, max_length=26)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ExecutionSlotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ExecutionSlotResource]
    page: PageMeta


class ExecutionSlotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ExecutionSlotResource
    correlation_id: str


class CreateExecutionSlotRequest(BaseModel):
    """Compatibility contract only; external creation is intentionally rejected."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    execution_slot_id: str | None = Field(default=None, min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    runner_id: str | None = Field(default=None, min_length=26, max_length=26)
    slot_no: str | None = Field(default=None, max_length=191)


class UpdateExecutionSlotRequest(BaseModel):
    """Compatibility contract only; external mutation is intentionally rejected."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)
    display_name: str | None = Field(default=None, max_length=255)
    runner_id: str | None = Field(default=None, min_length=26, max_length=26)
    slot_no: str | None = Field(default=None, max_length=191)
