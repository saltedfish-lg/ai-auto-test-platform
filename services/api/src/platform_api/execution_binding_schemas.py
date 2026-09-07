"""Public contracts for deterministic execution binding and resource leases."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

BindingStatus = Literal["READY", "IN_USE", "RELEASED", "EXPIRED"]
LeaseStatus = Literal["ACTIVE", "EXPIRED", "FENCED", "RELEASED"]
RunnerResourceType = Literal["FORMAL_EXECUTION_SLOT", "BROWSER_SESSION"]


class ExecutionBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_attempt_id: str = Field(min_length=26, max_length=26)
    project_id: str = Field(min_length=26, max_length=26)
    environment_id: str = Field(min_length=26, max_length=26)
    business_terminal_id: str = Field(min_length=26, max_length=26)
    test_account_id: str = Field(min_length=26, max_length=26)
    runner_id: str = Field(min_length=26, max_length=26)
    runtime_policy_revision_id: str = Field(min_length=26, max_length=26)
    runner_resource_type: RunnerResourceType
    runner_resource_identity: str = Field(min_length=1, max_length=191)
    owner_execution_identity: str = Field(min_length=1, max_length=191)
    required_capabilities: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("required_capabilities")
    @classmethod
    def unique_capabilities(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 64 for item in value):
            raise ValueError("required_capabilities values must be 1..64 characters")
        if len(value) != len(set(value)):
            raise ValueError("required_capabilities values must be unique")
        return value


class PreflightCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    status: Literal["PASS", "FAIL"]
    detail: str


class PreflightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ready: bool
    checks: list[PreflightCheck]
    terminal_access_revision_id: str | None = None
    login_strategy_id: str | None = None
    login_strategy_row_version: int | None = None
    credential_revision_id: str | None = None
    account_mapping_revision_id: str | None = None
    sso_identity_key: str | None = None
    runner_capability_codes: list[str] = Field(default_factory=list)


class PreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: PreflightResult
    correlation_id: str


class ResourceLeaseResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_lease_id: str
    resource_type: Literal["IDENTITY", "RUNNER"]
    resource_identity: str
    owner_type: str
    owner_id: str
    status: LeaseStatus
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None
    fencing_generation: int = Field(ge=1)
    row_version: int = Field(ge=1)


class RuntimePolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime_policy_revision_id: str
    revision_no: int = Field(ge=1)
    browser_runtime: str
    artifact_policy: str
    timeout_seconds: int = Field(gt=0)
    max_steps: int = Field(gt=0)
    total_exploration_timeout_seconds: int = Field(gt=0)
    model_transient_retry_per_step: int = Field(ge=0, le=10)
    allowed_origins: list[str]
    authentication_redirect_origins: list[str]
    retry_mode: str
    network_requirement: str
    serial_execution_policy: Literal["SINGLE_PROCESS_UNIFIED_RETRY"]


class ExecutionBindingSnapshotResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_binding_snapshot_id: str
    execution_attempt_id: str
    project_id: str
    environment_id: str
    business_terminal_id: str
    terminal_access_revision_id: str
    login_strategy_id: str
    login_strategy_row_version: int
    test_account_id: str
    credential_revision_id: str
    account_mapping_revision_id: str
    runner_id: str
    runner_row_version: int
    runner_heartbeat_at: datetime
    runner_capabilities: list[dict[str, object]]
    runtime_policy: RuntimePolicySnapshot
    identity_lease: ResourceLeaseResource
    runner_lease: ResourceLeaseResource
    owner_execution_identity: str
    correlation_id: str
    status: BindingStatus
    row_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    released_at: datetime | None
    expired_at: datetime | None


class ExecutionBindingSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ExecutionBindingSnapshotResource
    correlation_id: str


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ExecutionBindingSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ExecutionBindingSnapshotResource]
    page: PageMeta


class BindingCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_execution_identity: str = Field(min_length=1, max_length=191)
    expected_version: int = Field(ge=1)
    identity_lease_generation: int = Field(ge=1)
    runner_lease_generation: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class RecoverBindingRequest(BindingCommandRequest):
    recovery_evidence: str = Field(min_length=1, max_length=2000)


class RuntimePolicyRevisionResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime_policy_revision_id: str
    project_id: str
    revision_no: int
    browser_runtime: str
    artifact_policy: str
    timeout_seconds: int = Field(gt=0)
    max_steps: int = Field(gt=0)
    total_exploration_timeout_seconds: int = Field(gt=0)
    model_transient_retry_per_step: int = Field(ge=0, le=10)
    allowed_origins: list[str]
    authentication_redirect_origins: list[str]
    retry_mode: str
    network_requirement: str
    serial_execution_policy: str
    lifecycle_status: Literal["PUBLISHED", "RETIRED"]
    row_version: int


class CreateRuntimePolicyRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=26, max_length=26)
    browser_runtime: Literal["CHROMIUM", "CHROME", "EDGE"]
    artifact_policy: Literal["SCREENSHOT", "VIDEO", "TRACE"]
    timeout_seconds: int = Field(gt=0)
    max_steps: int = Field(gt=0)
    total_exploration_timeout_seconds: int = Field(gt=0)
    model_transient_retry_per_step: int = Field(ge=0, le=10)
    allowed_origins: list[AnyHttpUrl] = Field(min_length=1, max_length=32)
    authentication_redirect_origins: list[AnyHttpUrl] = Field(max_length=32)
    retry_mode: Literal["UNIFIED_OWNER"]
    network_requirement: Literal["INTERNET", "INTRANET", "PROXY"]
    serial_execution_policy: Literal["SINGLE_PROCESS_UNIFIED_RETRY"]
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("allowed_origins", "authentication_redirect_origins")
    @classmethod
    def validate_origins(cls, value: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        normalized = [str(item).rstrip("/") for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("origin values must be unique")
        for item in value:
            if (
                item.path not in {None, "", "/"}
                or item.query is not None
                or item.fragment is not None
            ):
                raise ValueError("origin values must contain only scheme, host, and optional port")
        return value


class RuntimePolicyRevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: RuntimePolicyRevisionResource
    correlation_id: str


class RuntimePolicyRevisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[RuntimePolicyRevisionResource]
