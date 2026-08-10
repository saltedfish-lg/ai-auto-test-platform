"""Validated API settings loaded from environment or a local .env file."""

from __future__ import annotations

from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from pydantic import Field, IPvAnyAddress, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PLATFORM_",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"]
    database_url: str = Field(min_length=1, repr=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "platform-api"
    host: IPvAnyAddress = Field(IPv4Address("127.0.0.1"), validation_alias="API_HOST")
    port: int = Field(8000, ge=1, le=65535, validation_alias="API_PORT")
    jwt_private_key_file: Path | None = Field(
        default=None, validation_alias="ATP_JWT_PRIVATE_KEY_FILE", repr=False
    )
    jwt_public_key_file: Path | None = Field(
        default=None, validation_alias="ATP_JWT_PUBLIC_KEY_FILE", repr=False
    )
    jwt_key_id: str = Field("atp-local-rs256-v1", validation_alias="ATP_JWT_KEY_ID")
    bootstrap_admin_password_file: Path | None = Field(
        default=None,
        validation_alias="ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE",
        repr=False,
    )

    @field_validator("database_url")
    @classmethod
    def require_mysql_driver(cls, value: str) -> str:
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("database_url must use the MySQL PyMySQL driver")
        return value

    @property
    def refresh_cookie_secure(self) -> bool:
        """Only loopback local/test processes may use the frozen TLS exception."""
        return not (
            self.environment in {"local", "test"} and str(self.host) in {"127.0.0.1", "localhost"}
        )
