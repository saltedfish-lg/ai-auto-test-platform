from __future__ import annotations

from pathlib import Path

import pytest
from platform_api.execution_binding_router import router
from platform_api.execution_binding_schemas import ExecutionBindingInput
from platform_api.execution_binding_service import (
    IDENTITY_LEASE_RENEW_SECONDS,
    IDENTITY_LEASE_TTL_SECONDS,
    RUNNER_LEASE_RENEW_SECONDS,
    RUNNER_LEASE_TTL_SECONDS,
    _resource_hash,
)
from pydantic import ValidationError

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
