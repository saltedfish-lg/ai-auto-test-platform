"""Validated background worker configuration."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="PLATFORM_", extra="ignore", populate_by_name=True
    )

    environment: Literal["local", "test", "staging", "production"]
    database_url: str = Field(min_length=1, repr=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "platform-worker"

    @field_validator("database_url")
    @classmethod
    def require_mysql_driver(cls, value: str) -> str:
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("database_url must use the MySQL PyMySQL driver")
        return value
