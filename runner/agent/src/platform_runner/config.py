"""Validated Runner Agent configuration without credentials."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunnerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="RUNNER_", extra="ignore", populate_by_name=True
    )

    environment: Literal["local", "test", "staging", "production"] = Field(
        validation_alias="PLATFORM_ENVIRONMENT"
    )
    platform_url: AnyHttpUrl
    work_dir: Path
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", validation_alias="PLATFORM_LOG_LEVEL"
    )
    service_name: str = "platform-runner"
