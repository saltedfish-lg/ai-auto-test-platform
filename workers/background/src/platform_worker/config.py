"""Validated background worker configuration from the repository-root environment."""

from pathlib import Path
from typing import Literal

from platform_common.environment import load_project_environment
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_project_environment(anchor=Path(__file__))


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None, env_prefix="PLATFORM_", extra="ignore", populate_by_name=True
    )

    environment: Literal["local", "test", "staging", "production"]
    database_url: str = Field(
        min_length=1,
        repr=False,
        validation_alias=AliasChoices(
            "ATP_DATABASE_URL",
            "PLATFORM_DATABASE_URL",  # legacy compatibility only; ATP_DATABASE_URL wins
            "database_url",
        ),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "platform-worker"

    @field_validator("database_url")
    @classmethod
    def require_mysql_driver(cls, value: str) -> str:
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("database_url must use the MySQL PyMySQL driver")
        return value
