"""Pydantic DTOs aligned to the frozen five authentication operations."""

from __future__ import annotations

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
