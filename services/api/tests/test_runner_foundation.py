from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_api.errors import PlatformError
from platform_api.models import RunnerAgent
from platform_api.runner_router import router
from platform_api.runner_schemas import (
    CreateRunnerEnrollmentRequest,
    HeartbeatRunnerRequest,
    RegisterRunnerRequest,
    RunnerCapabilityReportItem,
    UpdateRunnerRequest,
)
from platform_api.runner_service import (
    _authenticate_agent,
    _registration_agent_token,
    _secret_hash,
    _validate_metadata,
)
from pydantic import ValidationError


def test_runner_routes_separate_human_management_and_machine_runtime() -> None:
    operations = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert operations == {
        ("GET", "/api/v1/runner", "list_runner"),
        ("POST", "/api/v1/runner-enrollments", "create_runner_enrollment"),
        ("POST", "/api/v1/runners/register", "register_runner"),
        ("GET", "/api/v1/runner/{id}", "get_runner"),
        ("PATCH", "/api/v1/runner/{id}", "update_runner"),
        ("POST", "/api/v1/runner/{id}/enable", "enable_runner"),
        ("POST", "/api/v1/runner/{id}/disable", "disable_runner"),
        ("POST", "/api/v1/runner/{id}/archive", "archive_runner"),
        (
            "POST",
            "/api/v1/runner/{id}/agent-token/rotate",
            "rotate_runner_agent_token",
        ),
        (
            "POST",
            "/api/v1/runner/{id}/agent-token/revoke",
            "revoke_runner_agent_token",
        ),
        ("POST", "/api/v1/runners/{id}/heartbeat", "heartbeat_runner"),
        (
            "POST",
            "/api/v1/runners/{id}/capabilities",
            "report_runner_capabilities",
        ),
        (
            "POST",
            "/api/v1/runners/{id}/browser-runtime/commands:claim",
            None,
        ),
        (
            "POST",
            "/api/v1/runners/{id}/browser-runtime/cancellations:claim",
            None,
        ),
        (
            "POST",
            "/api/v1/runners/{id}/browser-runtime/commands/{command_id}:complete",
            None,
        ),
    }


def test_enrollment_owns_project_and_runner_code_is_not_patchable() -> None:
    enrollment = CreateRunnerEnrollmentRequest(
        project_id="P" * 26,
        runner_code="RUNNER-01",
        display_name="Local Runner",
        reason="bootstrap local execution",
    )
    assert enrollment.project_id == "P" * 26
    assert enrollment.runner_code == "RUNNER-01"
    assert set(UpdateRunnerRequest.model_fields) == {
        "expected_version",
        "display_name",
        "reason",
    }
    with pytest.raises(ValidationError):
        UpdateRunnerRequest.model_validate(
            {
                "expected_version": 1,
                "runner_code": "MUTATION-FORBIDDEN",
                "reason": "must fail",
            }
        )


def test_registration_does_not_accept_project_or_unbound_runner() -> None:
    payload = {
        "enrollment_credential": "enr_" + "a" * 48,
        "machine_fingerprint": "machine-01",
        "agent_version": "1.0.0",
        "runtime_metadata": {"os": "Windows"},
        "capabilities": [],
    }
    RegisterRunnerRequest.model_validate(payload)
    assert "project_id" not in RegisterRunnerRequest.model_fields
    assert "runner_code" not in RegisterRunnerRequest.model_fields
    with pytest.raises(ValidationError):
        RegisterRunnerRequest.model_validate({**payload, "project_id": "P" * 26})


def test_capability_snapshot_is_controlled_and_duplicate_codes_are_rejected() -> None:
    capability = RunnerCapabilityReportItem(
        capability_code="BROWSER_CHROMIUM",
        availability_status="CONFIGURED",
        observed_version="143",
    )
    with pytest.raises(ValidationError):
        RegisterRunnerRequest(
            enrollment_credential="enr_" + "a" * 48,
            machine_fingerprint="machine-01",
            agent_version="1.0.0",
            capabilities=[capability, capability],
        )
    with pytest.raises(ValidationError):
        RunnerCapabilityReportItem.model_validate(
            {"capability_code": "SCHEDULER", "availability_status": "CONFIGURED"}
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"agent_token": "must-not-enter-metadata"},
        {"nested": {"enrollment_credential": "must-not-enter-metadata"}},
        {"Authorization": "Bearer must-not-enter-metadata"},
    ],
)
def test_runtime_metadata_rejects_secret_like_fields(metadata: dict[str, object]) -> None:
    with pytest.raises(PlatformError) as caught:
        _validate_metadata(metadata)
    assert caught.value.code == "RUNNER_METADATA_SECRET_FORBIDDEN"


class _AgentAuthenticationSession:
    def __init__(self, agent: RunnerAgent) -> None:
        self._values = iter([SimpleNamespace(runner_id="R" * 26), agent])

    def scalar(self, statement: object) -> object:
        del statement
        return next(self._values)


def _agent(token: str, *, status: str = "ACTIVE") -> RunnerAgent:
    return RunnerAgent(
        runner_agent_id="A" * 26,
        project_id="P" * 26,
        runner_id="R" * 26,
        token_hash=_secret_hash(token),
        token_status=status,
        token_version=1,
        machine_fingerprint_hash=_secret_hash("machine-01"),
        agent_version="1.0.0",
        lifecycle_status="ACTIVE",
        row_version=1,
    )


def test_machine_auth_uses_only_opaque_agent_token_hash() -> None:
    token = "rat_" + "b" * 48
    runner, agent = _authenticate_agent(  # type: ignore[arg-type]
        _AgentAuthenticationSession(_agent(token)), "R" * 26, token
    )
    assert runner.runner_id == "R" * 26
    assert agent.token_hash == _secret_hash(token)
    assert token.encode() != agent.token_hash

    with pytest.raises(PlatformError) as caught:
        _authenticate_agent(  # type: ignore[arg-type]
            _AgentAuthenticationSession(_agent(token)), "R" * 26, "rat_" + "x" * 48
        )
    assert caught.value.status == 401
    assert caught.value.code == "RUNNER_AGENT_UNAUTHENTICATED"


def test_registration_delivery_token_is_recoverable_only_from_same_input() -> None:
    enrollment = "enr_" + "e" * 48
    key = "runner-enrollment-stable-key"
    token = _registration_agent_token(enrollment, key)
    assert token == _registration_agent_token(enrollment, key)
    assert token != _registration_agent_token(enrollment, key + "-different")
    assert token.startswith("rat_")
    assert enrollment not in token


def test_heartbeat_contract_keeps_state_dimensions_separate() -> None:
    body = HeartbeatRunnerRequest(
        health_status="HEALTHY",
        agent_version="1.0.0",
        runtime_metadata={"os": "Windows"},
    )
    assert set(body.model_fields_set) == {"health_status", "agent_version", "runtime_metadata"}
    assert not {
        "lifecycle_status",
        "connection_status",
        "enable_status",
        "scheduling_status",
    }.intersection(HeartbeatRunnerRequest.model_fields)


def test_v15_schema_enforces_project_identity_hash_only_credentials_and_audit() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root / "docs/authority/编码权威事实/DATABASE_DDL/V15__runner_foundation.sql"
    ).read_text(encoding="utf-8")
    assert "UNIQUE (project_id, runner_code)" in migration
    assert "credential_hash BINARY(32) NOT NULL" in migration
    assert "token_hash BINARY(32) NOT NULL" in migration
    assert "enrollment_credential VARCHAR" not in migration
    assert "agent_token VARCHAR" not in migration
    assert "project_binding_status VARCHAR(7) NOT NULL DEFAULT 'BOUND'" in migration
    assert "CHECK (project_binding_status = 'BOUND')" in migration
    assert "CHECK (registration_status = 'REGISTERED')" in migration
    assert "CREATE TEMPORARY TABLE atp_v15_runner_scope_violation" in migration
    assert "runner.binding_state <> 'BOUND'" in migration
    assert "binding.runner_id <> runner.runner_id" in migration
    assert "runner.project_id <> binding.project_id" in migration
    assert "CREATE TABLE atp_runner_audit" in migration
    assert "trg_atp_runner_audit_no_update" in migration
    assert "trg_atp_runner_audit_no_delete" in migration

    openapi = (root / "docs/authority/编码权威事实/OPENAPI/openapi.yaml").read_text(
        encoding="utf-8"
    )
    assert "AgentTokenAuth:" in openapi
    assert "X-Runner-Agent-Token" in openapi
    assert "x-machine-auth: EnrollmentCredential" in openapi
