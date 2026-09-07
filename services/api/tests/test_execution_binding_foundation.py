from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_api.execution_binding_router import router
from platform_api.execution_binding_schemas import (
    CreateRuntimePolicyRevisionRequest,
    ExecutionBindingInput,
    RuntimePolicyRevisionResource,
    RuntimePolicySnapshot,
)
from platform_api.execution_binding_service import (
    IDENTITY_LEASE_RENEW_SECONDS,
    IDENTITY_LEASE_TTL_SECONDS,
    RUNNER_LEASE_RENEW_SECONDS,
    RUNNER_LEASE_TTL_SECONDS,
    ExecutionBindingService,
    _policy_resource,
    _resource_hash,
)
from platform_api.models import ProjectRuntimePolicyRevision, ResourceLease
from pydantic import ValidationError
from sqlalchemy import JSON
from sqlalchemy.dialects.mysql import INTEGER as MySQLInteger

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "docs"
    / "authority"
    / "编码权威事实"
    / "DATABASE_DDL"
    / "V16__execution_binding_snapshot_foundation.sql"
)
AUTHORITY = (
    ROOT
    / "docs"
    / "authority"
    / "核心对象、业务规则与生命周期"
    / "execution-binding-snapshot-foundation.yaml"
)


def _body() -> dict[str, object]:
    return {
        "execution_attempt_id": "A" * 26,
        "project_id": "P" * 26,
        "environment_id": "E" * 26,
        "business_terminal_id": "T" * 26,
        "test_account_id": "C" * 26,
        "runner_id": "R" * 26,
        "runtime_policy_revision_id": "Y" * 26,
        "runner_resource_type": "FORMAL_EXECUTION_SLOT",
        "runner_resource_identity": "formal-execution-default",
        "owner_execution_identity": "attempt-owner",
        "required_capabilities": ["FORMAL_EXECUTION"],
    }


def _policy(
    *,
    policy_id: str = "Y" * 26,
    revision_no: int = 1,
    max_steps: int = 50,
    total_timeout: int = 1800,
    retry_per_step: int = 2,
    allowed_origins: list[str] | None = None,
    redirect_origins: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        runtime_policy_revision_id=policy_id,
        project_id="P" * 26,
        revision_no=revision_no,
        browser_runtime="CHROMIUM",
        artifact_policy="SCREENSHOT",
        timeout_seconds=300,
        max_steps=max_steps,
        total_exploration_timeout_seconds=total_timeout,
        model_transient_retry_per_step=retry_per_step,
        allowed_origins=[] if allowed_origins is None else allowed_origins,
        authentication_redirect_origins=([] if redirect_origins is None else redirect_origins),
        retry_mode="UNIFIED",
        network_requirement="INTRANET",
        serial_execution_policy="SINGLE_PROCESS_UNIFIED_RETRY",
        lifecycle_status="PUBLISHED",
        row_version=1,
    )


def _lease(lease_id: str, resource_type: str) -> SimpleNamespace:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return SimpleNamespace(
        resource_lease_id=lease_id,
        resource_type=resource_type,
        resource_identity=f"{resource_type.lower()}-resource",
        owner_type="EXECUTION_ATTEMPT",
        owner_id="A" * 26,
        status="ACTIVE",
        acquired_at=now,
        expires_at=now,
        released_at=None,
        fencing_generation=1,
        row_version=1,
    )


def _binding(policy_id: str) -> SimpleNamespace:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return SimpleNamespace(
        execution_binding_snapshot_id="B" * 26,
        execution_attempt_id="A" * 26,
        project_id="P" * 26,
        environment_id="E" * 26,
        business_terminal_id="T" * 26,
        terminal_access_revision_id="V" * 26,
        login_strategy_id="L" * 26,
        login_strategy_row_version=1,
        test_account_id="C" * 26,
        credential_revision_id="D" * 26,
        account_mapping_revision_id="M" * 26,
        runner_id="R" * 26,
        runner_row_version=1,
        runner_heartbeat_at=now,
        runner_capability_snapshot=[],
        runtime_policy_revision_id=policy_id,
        identity_lease_id="I" * 26,
        runner_lease_id="N" * 26,
        owner_execution_identity="attempt-owner",
        correlation_id="correlation-id",
        status="READY",
        row_version=1,
        created_at=now,
        updated_at=now,
        released_at=None,
        expired_at=None,
    )


class _ResourceSession:
    def __init__(self, policies: dict[str, SimpleNamespace]) -> None:
        self.policies = policies
        self.leases = {
            "I" * 26: _lease("I" * 26, "IDENTITY"),
            "N" * 26: _lease("N" * 26, "RUNNER"),
        }
        self.policy_ids_requested: list[str] = []

    def get(self, model: type[object], identity: str) -> SimpleNamespace | None:
        if model is ResourceLease:
            return self.leases.get(identity)
        if model is ProjectRuntimePolicyRevision:
            self.policy_ids_requested.append(identity)
            return self.policies.get(identity)
        return None


def test_execution_binding_routes_are_command_oriented() -> None:
    operations = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert operations == {
        (
            "POST",
            "/api/v1/execution-binding-snapshots/preflight",
            "preflight_execution_binding_snapshot",
        ),
        ("POST", "/api/v1/execution-binding-snapshots", "create_execution_binding_snapshot"),
        ("GET", "/api/v1/execution-binding-snapshots", "list_execution_binding_snapshots"),
        ("GET", "/api/v1/execution-binding-snapshots/{id}", "get_execution_binding_snapshot"),
        (
            "POST",
            "/api/v1/execution-binding-snapshots/{id}/consume",
            "consume_execution_binding_snapshot",
        ),
        (
            "POST",
            "/api/v1/execution-binding-snapshots/{id}/leases/renew",
            "renew_execution_binding_snapshot_leases",
        ),
        (
            "POST",
            "/api/v1/execution-binding-snapshots/{id}/release",
            "release_execution_binding_snapshot",
        ),
        (
            "POST",
            "/api/v1/execution-binding-snapshots/{id}/recover",
            "recover_execution_binding_snapshot",
        ),
        (
            "GET",
            "/api/v1/project-runtime-policy-revisions",
            "list_project_runtime_policy_revisions",
        ),
        (
            "POST",
            "/api/v1/project-runtime-policy-revisions",
            "create_project_runtime_policy_revision",
        ),
    }
    assert all(method != "PATCH" for method, _, _ in operations)


def test_public_input_rejects_secret_and_runtime_bypass_fields() -> None:
    for forbidden in (
        "target_url",
        "password",
        "localStorage",
        "captcha_code",
        "runner_token",
        "capability_json",
    ):
        payload = _body()
        payload[forbidden] = "forbidden"
        with pytest.raises(ValidationError):
            ExecutionBindingInput.model_validate(payload)


def test_authoritative_lease_ttls_and_renew_intervals_are_exact() -> None:
    assert IDENTITY_LEASE_TTL_SECONDS == 600
    assert IDENTITY_LEASE_RENEW_SECONDS == 120
    assert RUNNER_LEASE_TTL_SECONDS == 120
    assert RUNNER_LEASE_RENEW_SECONDS == 30


def test_runtime_policy_orm_projects_all_browser_loop_columns() -> None:
    table = ProjectRuntimePolicyRevision.__table__
    for name in (
        "max_steps",
        "total_exploration_timeout_seconds",
        "model_transient_retry_per_step",
    ):
        column = table.c[name]
        assert column.nullable is False
        assert isinstance(column.type, MySQLInteger)
        assert column.type.unsigned is True
        assert column.default is None
    for name in ("allowed_origins", "authentication_redirect_origins"):
        column = table.c[name]
        assert column.nullable is False
        assert isinstance(column.type, JSON)
        assert column.default is None


def test_runtime_policy_resources_project_v17_values_and_json_origins() -> None:
    policy = _policy(
        allowed_origins=["https://app.example.test"],
        redirect_origins=["https://login.example.test"],
    )
    listed = _policy_resource(policy)
    assert isinstance(listed, RuntimePolicyRevisionResource)
    assert listed.model_dump()["max_steps"] == 50
    assert listed.total_exploration_timeout_seconds == 1800
    assert listed.model_transient_retry_per_step == 2
    assert listed.allowed_origins == ["https://app.example.test"]
    assert listed.authentication_redirect_origins == ["https://login.example.test"]

    snapshot = RuntimePolicySnapshot.model_validate(
        {
            key: value
            for key, value in listed.model_dump().items()
            if key not in {"project_id", "lifecycle_status", "row_version"}
        }
    )
    assert RuntimePolicySnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert (
        RuntimePolicySnapshot.model_validate(
            {**snapshot.model_dump(), "allowed_origins": [], "authentication_redirect_origins": []}
        ).allowed_origins
        == []
    )


def test_binding_snapshot_keeps_its_historical_runtime_policy_revision() -> None:
    revision_one = _policy(
        policy_id="1" * 26,
        revision_no=1,
        max_steps=11,
        total_timeout=1200,
        retry_per_step=1,
        allowed_origins=["https://v1.example.test"],
    )
    revision_two = _policy(policy_id="2" * 26, revision_no=2)
    db = _ResourceSession(
        {
            revision_one.runtime_policy_revision_id: revision_one,
            revision_two.runtime_policy_revision_id: revision_two,
        }
    )

    resource = ExecutionBindingService._resource(
        db, _binding(revision_one.runtime_policy_revision_id)
    )

    assert db.policy_ids_requested == [revision_one.runtime_policy_revision_id]
    assert (
        resource.runtime_policy.runtime_policy_revision_id
        == revision_one.runtime_policy_revision_id
    )
    assert resource.runtime_policy.revision_no == 1
    assert resource.runtime_policy.max_steps == 11
    assert resource.runtime_policy.total_exploration_timeout_seconds == 1200
    assert resource.runtime_policy.allowed_origins == ["https://v1.example.test"]


def test_runtime_policy_api_constraints_match_database_checks() -> None:
    valid = _policy_resource(_policy()).model_dump()
    for field, value in (
        ("max_steps", 0),
        ("total_exploration_timeout_seconds", 0),
        ("model_transient_retry_per_step", 11),
    ):
        with pytest.raises(ValidationError):
            RuntimePolicyRevisionResource.model_validate({**valid, field: value})


def test_runtime_policy_create_is_atomic_publish_input_without_revision_mutation_fields() -> None:
    request = CreateRuntimePolicyRevisionRequest(
        project_id="P" * 26,
        browser_runtime="CHROMIUM",
        artifact_policy="SCREENSHOT",
        timeout_seconds=30,
        max_steps=20,
        total_exploration_timeout_seconds=600,
        model_transient_retry_per_step=1,
        allowed_origins=["https://app.example.test"],
        authentication_redirect_origins=["https://login.example.test"],
        retry_mode="UNIFIED_OWNER",
        network_requirement="INTERNET",
        serial_execution_policy="SINGLE_PROCESS_UNIFIED_RETRY",
        reason="publish project browser policy",
    )
    assert request.browser_runtime == "CHROMIUM"
    assert not {"revision_no", "lifecycle_status", "row_version"}.intersection(
        CreateRuntimePolicyRevisionRequest.model_fields
    )
    with pytest.raises(ValidationError):
        CreateRuntimePolicyRevisionRequest.model_validate(
            {**request.model_dump(mode="json"), "revision_no": 99}
        )


def test_v18_adds_only_append_only_runtime_policy_audit() -> None:
    migration = (
        ROOT
        / "docs"
        / "authority"
        / "编码权威事实"
        / "DATABASE_DDL"
        / "V18__runtime_policy_management_audit.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE atp_project_runtime_policy_audit" in migration
    assert "trg_atp_runtime_policy_audit_no_update" in migration
    assert "trg_atp_runtime_policy_audit_no_delete" in migration
    assert "ALTER TABLE atp_project_runtime_policy_revision" not in migration


def test_preflight_does_not_invent_an_environment_accessibility_requirement() -> None:
    source = (
        ROOT / "services" / "api" / "src" / "platform_api" / "execution_binding_service.py"
    ).read_text(encoding="utf-8")
    assert 'environment.enablement_state == "ENABLED"' in source
    assert "environment.accessibility_state" not in source
    assert 'environment.accessibility_state == "ACCESSIBLE"' not in source


def test_resource_identity_hash_is_framed_and_type_scoped() -> None:
    assert _resource_hash("IDENTITY", "abc") == _resource_hash("IDENTITY", "abc")
    assert _resource_hash("IDENTITY", "abc") != _resource_hash("RUNNER", "abc")
    assert _resource_hash("IDENTITY", "ab:c") != _resource_hash("IDENTITY", "a:bc")


def test_migration_has_atomic_snapshot_and_fencing_schema_without_scheduler() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE atp_project_runtime_policy_revision" in migration
    assert "CREATE TABLE atp_resource_lease_generation" in migration
    assert "CREATE TABLE atp_resource_lease" in migration
    assert "CREATE TABLE atp_execution_binding_snapshot" in migration
    assert "CREATE TABLE atp_execution_binding_audit" in migration
    assert "ADD COLUMN execution_binding_snapshot_id VARCHAR(26)" in migration
    assert "fk_atp_execution_attempt_binding" in migration
    assert "uq_atp_resource_lease_active" in migration
    assert "fencing_generation BIGINT UNSIGNED NOT NULL" in migration
    assert "GENERATED ALWAYS AS (CASE WHEN status = 'ACTIVE'" in migration
    assert "scheduler_queue" not in migration.casefold()
    assert "capacity_slot" not in migration.casefold()


def test_preflight_uses_stable_identity_and_real_runner_resource_facts() -> None:
    source = (
        ROOT / "services" / "api" / "src" / "platform_api" / "execution_binding_service.py"
    ).read_text(encoding="utf-8")
    assert "account.sso_identity_id or account.test_account_id" in source
    assert "account.sso_identity_id or account.account_identifier" not in source
    assert "ExecutionSlot.execution_slot_id == body.runner_resource_identity" in source
    assert "RunnerCapability.runner_capability_id" in source


def test_living_authority_preserves_obj_094_and_records_user_decision() -> None:
    authority = AUTHORITY.read_text(encoding="utf-8")
    assert "object_id: OBJ-094" in authority
    assert "ExecutionContext继续作为RunTask聚合成员" in authority
    assert "object_id: EBS-OBJ-001" in authority
    assert "ttl_seconds: 600" in authority
    assert "ttl_seconds: 120" in authority
    assert "SINGLE_LOCAL_DATABASE_TRANSACTION" in authority
    assert "saga: false" in authority
