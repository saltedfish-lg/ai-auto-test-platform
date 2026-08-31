"""Public human-management and machine-runtime contracts for Runner Foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RunnerLifecycleStatus = Literal["REGISTERED", "ACTIVE", "DISABLED", "ARCHIVED"]
RunnerHealthStatus = Literal["UNKNOWN", "HEALTHY", "DEGRADED", "UNHEALTHY"]
RunnerCapabilityCode = Literal[
    "BROWSER_CHROMIUM",
    "BROWSER_CHROME",
    "BROWSER_EDGE",
    "MODE_HEADED",
    "MODE_HEADLESS",
    "TERMINAL_ADMIN_WEB",
    "TERMINAL_CLIENT_WEB",
    "TERMINAL_PDA_WEB",
    "SINGLE_TERMINAL",
    "CROSS_TERMINAL",
    "CAPTURE_SCREENSHOT",
    "CAPTURE_VIDEO",
    "CAPTURE_TRACE",
    "NETWORK_RESPONSE_LISTEN",
    "INTRANET_ACCESS",
    "PROXY_ACCESS",
    "FILE_TRANSFER",
    "MANUAL_RECORDING",
    "AI_EXPLORATION",
    "FORMAL_EXECUTION",
    "LOCAL_ARTIFACT_CACHE",
    "PLAYWRIGHT_VERSION",
    "AGENT_VERSION",
    "CONTEXT_ISOLATION",
]


class RunnerCapabilityResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runner_capability_id: str = Field(min_length=26, max_length=26)
    capability_code: RunnerCapabilityCode
    capability_type: Literal[
        "BROWSER",
        "SESSION",
        "TERMINAL",
        "FLOW",
        "ARTIFACT",
        "NETWORK",
        "IO",
        "STORAGE",
        "VERSION",
        "SECURITY",
    ]
    availability_status: Literal["CONFIGURED", "NOT_CONFIGURED"]
    validation_status: Literal["PENDING", "VALID", "INVALID"]
    observed_version: str | None = Field(default=None, max_length=64)
    observed_metadata: dict[str, object] | None = None
    lifecycle_status: Literal["ACTIVE", "DISABLED"]
    reported_at: datetime


class RunnerResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runner_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    runner_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    lifecycle_status: RunnerLifecycleStatus
    registration_status: Literal["REGISTERED"]
    connection_status: Literal["OFFLINE", "CONNECTING", "ONLINE", "LOST"]
    health_status: RunnerHealthStatus
    enable_status: Literal["ENABLED", "DISABLED"]
    project_binding_status: Literal["BOUND"]
    scheduling_status: Literal["UNSCHEDULABLE", "IDLE", "PARTIALLY_OCCUPIED", "BUSY", "DRAINING"]
    resource_status: Literal["AVAILABLE", "PARTIALLY_OCCUPIED", "EXHAUSTED", "RECLAIMING"]
    version_compatibility: Literal["UNKNOWN", "COMPATIBLE", "INCOMPATIBLE", "UPGRADE_REQUIRED"]
    last_heartbeat_at: datetime | None
    registered_at: datetime
    runtime_metadata: dict[str, object] | None
    capabilities: list[RunnerCapabilityResource]
    row_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class RunnerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RunnerResource
    correlation_id: str


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class RunnerListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RunnerResource]
    page: PageMeta


class CreateRunnerEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=26, max_length=26)
    runner_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("runner_code")
    @classmethod
    def validate_runner_code(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("runner_code must not contain edge whitespace")
        return value


class RunnerEnrollmentIssuedResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrollment_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    runner_code: str = Field(min_length=1, max_length=191)
    display_name: str | None = Field(default=None, max_length=255)
    enrollment_status: Literal["PENDING"]
    enrollment_credential: str = Field(min_length=32, max_length=512, repr=False)
    row_version: int = Field(ge=1)
    created_at: datetime


class RunnerEnrollmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RunnerEnrollmentIssuedResource
    correlation_id: str


class UpdateRunnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    display_name: str | None = Field(default=None, max_length=255)
    reason: str = Field(min_length=1, max_length=1000)


class RunnerLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class RunnerCapabilityReportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_code: RunnerCapabilityCode
    availability_status: Literal["CONFIGURED", "NOT_CONFIGURED"]
    observed_version: str | None = Field(default=None, max_length=64)
    observed_metadata: dict[str, object] | None = None


class RegisterRunnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrollment_credential: str = Field(min_length=32, max_length=512, repr=False)
    machine_fingerprint: str = Field(min_length=1, max_length=1024, repr=False)
    agent_version: str = Field(min_length=1, max_length=64)
    runtime_metadata: dict[str, object] | None = None
    capabilities: list[RunnerCapabilityReportItem] = Field(max_length=24)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(
        cls, value: list[RunnerCapabilityReportItem]
    ) -> list[RunnerCapabilityReportItem]:
        codes = [item.capability_code for item in value]
        if len(codes) != len(set(codes)):
            raise ValueError("capability_code values must be unique")
        return value


class RegisterRunnerData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runner: RunnerResource
    agent_token: str = Field(min_length=32, max_length=512, repr=False)
    token_version: int = Field(ge=1)


class RegisterRunnerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RegisterRunnerData
    correlation_id: str


class RotateRunnerAgentTokenData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runner: RunnerResource
    agent_token: str = Field(min_length=32, max_length=512, repr=False)
    token_version: int = Field(ge=2)


class RotateRunnerAgentTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RotateRunnerAgentTokenData
    correlation_id: str


class HeartbeatRunnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    health_status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
    agent_version: str = Field(min_length=1, max_length=64)
    runtime_metadata: dict[str, object] | None = None
    capabilities: list[RunnerCapabilityReportItem] | None = Field(default=None, max_length=24)


class ReportRunnerCapabilitiesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: list[RunnerCapabilityReportItem] = Field(max_length=24)
