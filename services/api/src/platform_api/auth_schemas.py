"""Pydantic DTOs aligned to the current five authentication operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=191)
    password: str = Field(min_length=1, max_length=128)


class AuthCookieActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(
        min_length=12,
        max_length=128,
        json_schema_extra={"pattern": r"^(?=.*[A-Za-z])(?=.*[0-9])(?!\s)(?!.*\s$).+$"},
    )

    @field_validator("new_password")
    @classmethod
    def validate_frozen_shape(cls, value: str) -> str:
        if (
            value != value.strip()
            or not any(char.isalpha() for char in value)
            or not any(char.isdigit() for char in value)
        ):
            raise ValueError("new password must contain a letter and digit without edge whitespace")
        return value


class CurrentUserResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=26, max_length=26, pattern=r"^[0-9A-HJKMNP-TV-Z]{26}$")
    username: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    lifecycle_status: Literal["ACTIVE"]
    roles: list[str]
    permissions: list[str]
    force_password_change: bool


class AuthenticationTokenResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(min_length=32, max_length=4096)
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(ge=1, le=900)
    current_user: CurrentUserResource


class AuthenticationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: AuthenticationTokenResource
    correlation_id: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: CurrentUserResource
    correlation_id: str


class DataScopeGrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_type: str = Field(min_length=1, max_length=32)
    scope_id: str | None = Field(default=None, min_length=26, max_length=26)
    permission_code: str | None = Field(default=None, min_length=1, max_length=128)


class UserRoleBindingAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role_id: str = Field(min_length=26, max_length=26)
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    data_scope_grants: list[DataScopeGrantInput] = Field(default_factory=list)


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=191)
    display_name: str = Field(min_length=1, max_length=255)
    role_bindings: list[UserRoleBindingAssignmentInput] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=1000)


class UserResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=26, max_length=26)
    display_name: str | None = Field(default=None, max_length=255)
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    username: str | None = Field(default=None, max_length=191)
    role_binding_id: str | None = Field(default=None, min_length=26, max_length=26)
    lifecycle_status: Literal[
        "CREATED",
        "DRAFT",
        "ACTIVE",
        "LOCKED",
        "DISABLED",
        "RECOVERING",
        "ARCHIVED",
        "LOGICALLY_DELETED",
    ]


class OneTimeCredentialDeliveryResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: UserResource
    delivery_status: Literal["ISSUED", "ALREADY_DELIVERED"]
    temporary_password: str | None = Field(default=None, min_length=1)
    force_password_change: Literal[True] = True


class CreateUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: OneTimeCredentialDeliveryResource
    correlation_id: str


class OneTimeCredentialDeliveryResponse(CreateUserResponse):
    pass


class ResetUserCredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class UserStateCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class UpdateUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: UserResource
    correlation_id: str


class CreateUserRoleBindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=26, max_length=26)
    role_id: str = Field(min_length=26, max_length=26)
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    data_scope_grants: list[DataScopeGrantInput] = Field(default_factory=list)
    expected_user_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class RevokeUserRoleBindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1000)


class UserRoleBindingResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding_id: str = Field(min_length=26, max_length=26)
    user_id: str = Field(min_length=26, max_length=26)
    role_id: str = Field(min_length=26, max_length=26)
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    valid_from: datetime
    valid_to: datetime | None = None
    row_version: int = Field(ge=0)


class UserRoleBindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: UserRoleBindingResource
    correlation_id: str
