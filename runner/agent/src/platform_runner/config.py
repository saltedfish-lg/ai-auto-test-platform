"""Validated Runner Agent configuration without credentials."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
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
    enrollment_credential: SecretStr | None = None
    heartbeat_interval_seconds: float = Field(default=15.0, ge=1.0, le=300.0)
    declared_capabilities: list[str] = Field(default_factory=list)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", validation_alias="PLATFORM_LOG_LEVEL"
    )
    service_name: str = "platform-runner"

    @field_validator("declared_capabilities")
    @classmethod
    def validate_declared_capabilities(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("declared capabilities must be unique")
        return value
