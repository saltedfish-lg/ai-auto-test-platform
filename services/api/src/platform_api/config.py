"""Validated API settings loaded from environment or a local .env file."""

from __future__ import annotations

from ipaddress import IPv4Address
from typing import Literal

from pydantic import Field, IPvAnyAddress, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PLATFORM_",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"]
    database_url: str = Field(min_length=1, repr=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "platform-api"
    host: IPvAnyAddress = Field(IPv4Address("127.0.0.1"), validation_alias="API_HOST")
    port: int = Field(8000, ge=1, le=65535, validation_alias="API_PORT")

    @field_validator("database_url")
    @classmethod
    def require_mysql_driver(cls, value: str) -> str:
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("database_url must use the MySQL PyMySQL driver")
        return value
