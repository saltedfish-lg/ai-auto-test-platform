"""Public contracts for the Test Account aggregate and credential commands."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TestAccountLifecycleStatus = Literal[
    "CREATED",
    "CONFIGURING",
    "VALIDATING",
    "ACTIVE",
    "CREDENTIAL_EXPIRED",
    "DISABLED",
    "RECOVERING",
    "ARCHIVED",
]
CredentialState = Literal["VALID", "EXPIRING", "EXPIRED", "REVOKED"]


class TestAccountTerminalResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_terminal_id: str = Field(min_length=26, max_length=26)
    terminal_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    terminal_type: Literal["MANAGEMENT", "CLIENT", "PDA"]


class TestAccountResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_account_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    environment_id: str = Field(min_length=26, max_length=26)
    account_identifier: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    lifecycle_status: TestAccountLifecycleStatus
    credential_state: CredentialState
    credential_revision_no: int = Field(ge=1)
    business_terminals: list[TestAccountTerminalResource]
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class CreateTestAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment_id: str = Field(min_length=26, max_length=26)
    account_identifier: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    business_terminal_ids: list[str] = Field(min_length=1, max_length=50)
    secret_value: str = Field(min_length=1, max_length=4096, repr=False)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("account_identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("account_identifier must not contain edge whitespace")
        return value

    @field_validator("business_terminal_ids")
    @classmethod
    def validate_terminal_ids(cls, value: list[str]) -> list[str]:
        if any(len(item) != 26 for item in value):
            raise ValueError("every business terminal id must contain 26 characters")
        if len(set(value)) != len(value):
            raise ValueError("business terminal ids must be unique")
        return value


class UpdateTestAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str = Field(min_length=1, max_length=1000)


class RotateTestAccountSecretRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    secret_value: str = Field(min_length=1, max_length=4096, repr=False)
    reason: str = Field(min_length=1, max_length=1000)


class TestAccountLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class TestAccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: TestAccountResource
    correlation_id: str


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class TestAccountListData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TestAccountResource]
    page: PageMeta
