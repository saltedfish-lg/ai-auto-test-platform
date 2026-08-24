"""Validated API settings loaded from the repository-root local environment."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from platform_common.environment import load_project_environment
from pydantic import AliasChoices, Field, IPvAnyAddress, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local processes always resolve repo/.env from this module location; shell/process env wins.
load_project_environment(anchor=Path(__file__))


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="PLATFORM_",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"]
    database_url: str = Field(
        min_length=1,
        repr=False,
        validation_alias=AliasChoices("ATP_DATABASE_URL", "database_url"),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "platform-api"
    host: IPvAnyAddress = Field(IPv4Address("127.0.0.1"), validation_alias="API_HOST")
    port: int = Field(8000, ge=1, le=65535, validation_alias="API_PORT")
    jwt_key_ring_file: Path = Field(validation_alias="ATP_JWT_KEY_RING_FILE", repr=False)
    auth_hmac_master_key_file: Path = Field(
        validation_alias="ATP_AUTH_HMAC_MASTER_KEY_FILE",
        repr=False,
    )
    trusted_proxy_cidrs: str = Field(
        default="",
        validation_alias="ATP_TRUSTED_PROXY_CIDRS",
        repr=False,
    )
    bootstrap_admin_password_file: Path | None = Field(
        default=None,
        validation_alias="ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE",
        repr=False,
    )
    model_secret_key_ring_file: Path | None = Field(
        default=None,
        validation_alias="ATP_MODEL_SECRET_KEY_RING_FILE",
        repr=False,
    )
    litellm_proxy_url: str | None = Field(
        default=None,
        validation_alias="ATP_LITELLM_PROXY_URL",
        repr=False,
    )
    litellm_proxy_api_key_file: Path | None = Field(
        default=None,
        validation_alias="ATP_LITELLM_PROXY_API_KEY_FILE",
        repr=False,
    )
    litellm_dynamic_credentials_enabled: bool = Field(
        default=False,
        validation_alias="ATP_LITELLM_DYNAMIC_CREDENTIALS_ENABLED",
        repr=False,
    )

    @field_validator("database_url")
    @classmethod
    def require_mysql_driver(cls, value: str) -> str:
        if not value.startswith("mysql+pymysql://"):
            raise ValueError("database_url must use the MySQL PyMySQL driver")
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, value: str) -> str:
        if not value.strip():
            return ""
        for raw_value in value.split(","):
            candidate = raw_value.strip()
            if not candidate:
                raise ValueError("ATP_TRUSTED_PROXY_CIDRS contains an empty entry")
            ip_network(candidate, strict=True)
        return value

    @model_validator(mode="after")
    def validate_litellm_proxy_url(self) -> ApiSettings:
        if self.litellm_proxy_url is None:
            return self
        parsed = urlsplit(self.litellm_proxy_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ATP_LITELLM_PROXY_URL must be a credential-free HTTP(S) base URL")
        if self.environment in {"staging", "production"} and parsed.scheme != "https":
            raise ValueError("ATP_LITELLM_PROXY_URL must use HTTPS outside local/test")
        return self

    @property
    def refresh_cookie_secure(self) -> bool:
        """Only loopback local/test processes may use the current TLS exception."""
        return not (
            self.environment in {"local", "test"} and str(self.host) in {"127.0.0.1", "localhost"}
        )

    @property
    def trusted_proxy_networks(self) -> tuple[IPv4Network | IPv6Network, ...]:
        """Parse the deployment allow-list without accepting host-bit ambiguity."""
        if not self.trusted_proxy_cidrs.strip():
            return ()
        networks: list[IPv4Network | IPv6Network] = []
        for raw_value in self.trusted_proxy_cidrs.split(","):
            value = raw_value.strip()
            if not value:
                raise ValueError("ATP_TRUSTED_PROXY_CIDRS contains an empty entry")
            networks.append(ip_network(value, strict=True))
        return tuple(networks)
