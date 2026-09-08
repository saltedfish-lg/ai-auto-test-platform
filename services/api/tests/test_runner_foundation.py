from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Event, Lock
from types import SimpleNamespace

import pytest
from platform_api import runner_router
from platform_api.audit import AuditContext
from platform_api.errors import PlatformError
from platform_api.models import ExecutionSlot, OutboxEvent, Runner, RunnerAgent, RunnerAudit, RunnerCapability
from platform_api.runner_router import router
from platform_api.runner_schemas import (
    CreateRunnerEnrollmentRequest,
    HeartbeatRunnerRequest,
    RegisterRunnerRequest,
    ReportRunnerCapabilitiesRequest,
    RunnerCapabilityReportItem,
    RunnerLifecycleRequest,
    UpdateRunnerRequest,
    ValidateRunnerCapabilityRequest,
)
from platform_api.runner_service import (
    RunnerService,
    _authenticate_agent,
    _registration_agent_token,
    _runner_execution_eligible,
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
        (
            "POST",
            "/api/v1/runner/{id}/capabilities/{capability_code}/validate",
            "validate_runner_capability",
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
            agent_version="0.1.0",
            capabilities=[capability, capability],
        )


def test_capability_validation_requires_existing_report_versions_and_evidence() -> None:
    request = ValidateRunnerCapabilityRequest(
        expected_capability_version=2,
        evidence_summary="Chromium launched and reached the approved origin.",
        reason="validate current machine report",
    )
    assert request.expected_capability_version == 2
    assert "expected_runner_version" not in ValidateRunnerCapabilityRequest.model_fields
    assert not {
        "project_id",
        "availability_status",
        "validation_status",
        "observed_metadata",
    }.intersection(ValidateRunnerCapabilityRequest.model_fields)
    with pytest.raises(ValidationError):
        ValidateRunnerCapabilityRequest.model_validate(
            {
                "expected_capability_version": 2,
                "evidence_summary": "",
                "reason": "validate",
            }
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


def test_machine_identity_and_execution_eligibility_are_distinct() -> None:
    registered = SimpleNamespace(
        lifecycle_status="REGISTERED",
        registration_status="REGISTERED",
        enable_status="DISABLED",
        project_binding_status="BOUND",
        connection_status="ONLINE",
        health_status="HEALTHY",
        last_heartbeat_at=datetime.now(UTC).replace(tzinfo=None),
        version_compatibility="UNKNOWN",
    )
    active = SimpleNamespace(
        lifecycle_status="ACTIVE",
        registration_status="REGISTERED",
        enable_status="ENABLED",
        project_binding_status="BOUND",
        connection_status="ONLINE",
        health_status="HEALTHY",
        last_heartbeat_at=datetime.now(UTC).replace(tzinfo=None),
        version_compatibility="COMPATIBLE",
    )

    assert _runner_execution_eligible(registered) is False  # type: ignore[arg-type]
    assert _runner_execution_eligible(active) is True  # type: ignore[arg-type]
    active.connection_status = "OFFLINE"
    assert _runner_execution_eligible(active) is False  # type: ignore[arg-type]


def test_ineligible_machine_claim_returns_empty_without_touching_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(machine_execution_eligible=lambda *_args: False)
    broker = SimpleNamespace(claim=lambda *_args: pytest.fail("broker must not be called"))
    request = SimpleNamespace(state=SimpleNamespace(correlation_id="correlation-1"))
    monkeypatch.setattr(runner_router, "_service", lambda _request: service)
    monkeypatch.setattr(runner_router, "_browser_broker", lambda _request: broker)

    response = runner_router.claim_bound_browser_command(  # type: ignore[arg-type]
        "R" * 26, request, "rat_" + "b" * 48
    )

    assert response == {"data": None, "correlation_id": "correlation-1"}


class _RunnerValidationTransaction:
    def __init__(self, session: _RunnerValidationSession, lock: Lock) -> None:
        self._session = session
        self._lock = lock

    def __enter__(self) -> _RunnerValidationSession:
        self._lock.acquire()
        return self._session

    def __exit__(self, *_args: object) -> None:
        self._lock.release()


class _RunnerValidationFactory:
    def __init__(self, session: _RunnerValidationSession) -> None:
        self.session = session
        self.lock = Lock()

    def begin(self) -> _RunnerValidationTransaction:
        return _RunnerValidationTransaction(self.session, self.lock)


class _RunnerValidationSession:
    def __init__(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        self.runner = Runner(
            runner_id="R" * 26,
            project_id="P" * 26,
            runner_code="RUNNER-01",
            health_status="HEALTHY",
            scheduling_status="IDLE",
            resource_status="AVAILABLE",
            version_compatibility="COMPATIBLE",
            last_heartbeat_at=now,
            registered_at=now,
            runtime_metadata_json={"os": "Windows"},
            registration_status="REGISTERED",
            connection_status="ONLINE",
            enable_status="ENABLED",
            project_binding_status="BOUND",
            lifecycle_status="ACTIVE",
            display_name="Windows Runner",
            row_version=7,
            created_at=now,
            updated_at=now,
            created_by="U" * 26,
            updated_by="U" * 26,
            extension_json=None,
        )
        self.agent_token = "rat_" + "b" * 48
        self.agent = RunnerAgent(
            runner_agent_id="A" * 26,
            project_id=self.runner.project_id,
            runner_id=self.runner.runner_id,
            token_hash=_secret_hash(self.agent_token),
            token_status="ACTIVE",
            token_version=1,
            machine_fingerprint_hash=_secret_hash("machine-01"),
            agent_version="1.0.0",
            last_authenticated_at=now,
            credential_rotated_at=None,
            revoked_at=None,
            lifecycle_status="ACTIVE",
            display_name=None,
            row_version=1,
            created_at=now,
            updated_at=now,
            created_by=None,
            updated_by=None,
            extension_json=None,
        )
        self.capability = RunnerCapability(
            runner_capability_id="C" * 26,
            project_id=self.runner.project_id,
            runner_id=self.runner.runner_id,
            capability_code="AGENT_VERSION",
            capability_type="VERSION",
            availability_status="CONFIGURED",
            validation_status="PENDING",
            observed_version="0.1.0",
            observed_metadata_json=None,
            reported_at=now,
            lifecycle_status="ACTIVE",
            display_name=None,
            row_version=1,
            created_at=now,
            updated_at=now,
            created_by=self.agent.runner_agent_id,
            updated_by=self.agent.runner_agent_id,
            extension_json=None,
        )
        self.playwright_capability = RunnerCapability(
            runner_capability_id="D" * 26,
            project_id=self.runner.project_id,
            runner_id=self.runner.runner_id,
            capability_code="PLAYWRIGHT_VERSION",
            capability_type="VERSION",
            availability_status="CONFIGURED",
            validation_status="VALID",
            observed_version="1.62.0",
            observed_metadata_json=None,
            reported_at=now,
            lifecycle_status="ACTIVE",
            display_name=None,
            row_version=1,
            created_at=now,
            updated_at=now,
            created_by=self.agent.runner_agent_id,
            updated_by=self.agent.runner_agent_id,
            extension_json=None,
        )
        self.formal_capability = RunnerCapability(
            runner_capability_id="F" * 26,
            project_id=self.runner.project_id,
            runner_id=self.runner.runner_id,
            capability_code="FORMAL_EXECUTION",
            capability_type="SESSION",
            availability_status="CONFIGURED",
            validation_status="VALID",
            observed_version=None,
            observed_metadata_json=None,
            reported_at=now,
            lifecycle_status="ACTIVE",
            display_name=None,
            row_version=1,
            created_at=now,
            updated_at=now,
            created_by=self.agent.runner_agent_id,
            updated_by=self.agent.runner_agent_id,
            extension_json=None,
        )
        self.execution_slot: ExecutionSlot | None = None
        self.project = SimpleNamespace(project_id=self.runner.project_id, lifecycle_status="ACTIVE")
        self.added: list[object] = []

    def scalar(self, statement: object) -> object | None:
        sql = str(statement)
        if "max(atp_outbox_event.sequence)" in sql:
            sequences = [item.sequence for item in self.added if isinstance(item, OutboxEvent)]
            return max(sequences, default=0)
        if "FROM atp_runner_agent" in sql:
            return self.agent
        if "FROM atp_execution_slot" in sql:
            return self.execution_slot
        if "FROM atp_runner_capability" in sql:
            params = getattr(statement.compile(), "params", {})
            code = next(
                (value for key, value in params.items() if "capability_code" in key),
                "AGENT_VERSION",
            )
            if code == "PLAYWRIGHT_VERSION":
                return self.playwright_capability
            if code == "FORMAL_EXECUTION":
                return self.formal_capability
            return self.capability
        if "FROM atp_runner" in sql:
            return self.runner
        if "FROM atp_project" in sql:
            return self.project
        raise AssertionError(f"unexpected scalar query: {sql}")

    def scalars(self, statement: object) -> list[RunnerCapability]:
        assert "FROM atp_runner_capability" in str(statement)
        return [self.capability, self.playwright_capability, self.formal_capability]

    def get(self, model: object, identity: object) -> object | None:
        del identity
        if getattr(model, "__name__", "") == "Project":
            return self.project
        if getattr(model, "__name__", "") == "Runner":
            return self.runner
        return None

    def add(self, value: object) -> None:
        self.added.append(value)
        if isinstance(value, ExecutionSlot):
            self.execution_slot = value

    def flush(self) -> None:
        return None


class _RunnerValidationAuthentication:
    @staticmethod
    def authenticate_access_in_transaction(*_args: object) -> object:
        return SimpleNamespace(user=SimpleNamespace(user_id="U" * 26))

    @staticmethod
    def require_project_permissions_in_transaction(*_args: object) -> None:
        return None


class _RunnerValidationIdempotency:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], SimpleNamespace] = {}

    def claim(
        self,
        _db: object,
        principal_id: str,
        operation: str,
        key: str,
        _payload: bytes,
    ) -> tuple[SimpleNamespace, bool]:
        identity = (principal_id, operation, key)
        existing = self.records.get(identity)
        if existing is not None:
            return existing, True
        record = SimpleNamespace(response_status=None, response_json=None)
        self.records[identity] = record
        return record, False

    @staticmethod
    def complete(record: SimpleNamespace, status: int, response_json: dict[str, object]) -> None:
        record.response_status = status
        record.response_json = response_json


def _runner_validation_service() -> tuple[RunnerService, _RunnerValidationSession]:
    session = _RunnerValidationSession()
    service = RunnerService(  # type: ignore[arg-type]
        _RunnerValidationFactory(session),
        _RunnerValidationAuthentication(),
        _RunnerValidationIdempotency(),
    )
    return service, session


def _validation_request(expected_capability_version: int = 1) -> ValidateRunnerCapabilityRequest:
    return ValidateRunnerCapabilityRequest(
        expected_capability_version=expected_capability_version,
        evidence_summary="Runner reported AGENT_VERSION and remained healthy.",
        reason="validate current machine report",
    )


def _audit_and_outbox_counts(session: _RunnerValidationSession) -> tuple[int, int]:
    return (
        sum(isinstance(item, RunnerAudit) for item in session.added),
        sum(isinstance(item, OutboxEvent) for item in session.added),
    )


def test_heartbeat_before_and_after_capability_validation_is_not_a_concurrency_owner() -> None:
    service, session = _runner_validation_service()
    initial_runner_version = session.runner.row_version
    heartbeat = HeartbeatRunnerRequest(
        health_status="HEALTHY", agent_version="1.0.1", runtime_metadata={"os": "Windows"}
    )
    context = AuditContext(correlation_id="heartbeat-validation", source_context="test")
    heartbeat_before_validation = Event()
    validation_finished = Event()

    def heartbeat_worker() -> None:
        for _ in range(3):
            service.heartbeat(session.runner.runner_id, session.agent_token, heartbeat, context)
        heartbeat_before_validation.set()
        assert validation_finished.wait(timeout=5)
        for _ in range(3):
            service.heartbeat(session.runner.runner_id, session.agent_token, heartbeat, context)

    with ThreadPoolExecutor(max_workers=1) as executor:
        worker = executor.submit(heartbeat_worker)
        assert heartbeat_before_validation.wait(timeout=5)
        try:
            resource = service.validate_capability(
                "bearer",
                session.runner.runner_id,
                "AGENT_VERSION",
                _validation_request(),
                "validate-1",
                context,
            )
        finally:
            validation_finished.set()
        worker.result(timeout=5)

    assert resource.capabilities[0].validation_status == "VALID"
    assert session.runner.row_version == initial_runner_version
    assert session.capability.row_version == 2
    assert _audit_and_outbox_counts(session) == (1, 1)


def test_concurrent_capability_validation_transitions_once_and_does_not_duplicate_evidence() -> (
    None
):
    service, session = _runner_validation_service()
    barrier = Barrier(2)
    context = AuditContext(correlation_id="concurrent-validation", source_context="test")

    def validate(key: str) -> str:
        barrier.wait()
        try:
            service.validate_capability(
                "bearer",
                session.runner.runner_id,
                "AGENT_VERSION",
                _validation_request(),
                key,
                context,
            )
        except PlatformError as error:
            return error.code
        return "PASS"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(validate, ("validate-a", "validate-b")))

    assert sorted(results) == ["PASS", "RUNNER_STATE_CONFLICT"]
    assert session.capability.validation_status == "VALID"
    assert session.capability.row_version == 2
    assert _audit_and_outbox_counts(session) == (1, 1)


def test_stale_capability_version_fails_closed_without_audit_or_outbox() -> None:
    service, session = _runner_validation_service()
    session.capability.row_version = 2

    with pytest.raises(PlatformError, match="reported capability changed") as caught:
        service.validate_capability(
            "bearer",
            session.runner.runner_id,
            "AGENT_VERSION",
            _validation_request(expected_capability_version=1),
            "stale-capability",
            AuditContext(correlation_id="stale", source_context="test"),
        )

    assert caught.value.status == 409
    assert _audit_and_outbox_counts(session) == (0, 0)


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    [
        ("lifecycle_status", "DISABLED", "lifecycle must be ACTIVE"),
        ("enable_status", "DISABLED", "must be enabled"),
        ("connection_status", "OFFLINE", "must be ONLINE"),
        ("health_status", "UNHEALTHY", "must be HEALTHY"),
    ],
)
def test_capability_validation_rejects_actual_runner_state_with_specific_business_conflict(
    field: str, value: str, detail: str
) -> None:
    service, session = _runner_validation_service()
    setattr(session.runner, field, value)

    with pytest.raises(PlatformError, match=detail) as caught:
        service.validate_capability(
            "bearer",
            session.runner.runner_id,
            "AGENT_VERSION",
            _validation_request(),
            f"invalid-{field}",
            AuditContext(correlation_id="invalid-state", source_context="test"),
        )

    assert caught.value.code == "RUNNER_STATE_CONFLICT"
    assert _audit_and_outbox_counts(session) == (0, 0)


def test_capability_validation_idempotency_replays_without_duplicate_audit_or_outbox() -> None:
    service, session = _runner_validation_service()
    context = AuditContext(correlation_id="idempotent-validation", source_context="test")

    first = service.validate_capability(
        "bearer",
        session.runner.runner_id,
        "AGENT_VERSION",
        _validation_request(),
        "same-key",
        context,
    )
    second = service.validate_capability(
        "bearer",
        session.runner.runner_id,
        "AGENT_VERSION",
        _validation_request(),
        "same-key",
        context,
    )

    assert first == second
    assert _audit_and_outbox_counts(session) == (1, 1)


def test_validated_version_capabilities_recompute_compatibility_and_scheduling() -> None:
    service, session = _runner_validation_service()
    session.runner.version_compatibility = "UNKNOWN"
    session.runner.scheduling_status = "UNSCHEDULABLE"
    session.playwright_capability.validation_status = "PENDING"
    context = AuditContext(correlation_id="compatibility-formation", source_context="test")

    first = service.validate_capability(
        "bearer",
        session.runner.runner_id,
        "AGENT_VERSION",
        _validation_request(),
        "validate-agent-version",
        context,
    )
    assert first.version_compatibility == "UNKNOWN"
    assert first.scheduling_status == "UNSCHEDULABLE"

    second = service.validate_capability(
        "bearer",
        session.runner.runner_id,
        "PLAYWRIGHT_VERSION",
        ValidateRunnerCapabilityRequest(
            expected_capability_version=1,
            evidence_summary="Playwright 1.62.0 launched the configured Chromium runtime.",
            reason="validate current Playwright version",
        ),
        "validate-playwright-version",
        context,
    )
    assert second.version_compatibility == "COMPATIBLE"
    assert second.scheduling_status == "IDLE"
    assert session.execution_slot is not None
    assert session.execution_slot.slot_no == "0"
    assert session.execution_slot.lifecycle_status == "ACTIVE"
    assert session.runner.row_version == 7


def test_unchanged_valid_version_report_repairs_legacy_unknown_aggregate_state() -> None:
    service, session = _runner_validation_service()
    session.capability.validation_status = "VALID"
    session.playwright_capability.validation_status = "VALID"
    session.runner.version_compatibility = "UNKNOWN"
    session.runner.scheduling_status = "UNSCHEDULABLE"
    initial_runner_version = session.runner.row_version

    repaired = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(
                    capability_code="AGENT_VERSION",
                    availability_status="CONFIGURED",
                    observed_version="0.1.0",
                ),
                RunnerCapabilityReportItem(
                    capability_code="PLAYWRIGHT_VERSION",
                    availability_status="CONFIGURED",
                    observed_version="1.62.0",
                ),
                RunnerCapabilityReportItem(
                    capability_code="FORMAL_EXECUTION",
                    availability_status="CONFIGURED",
                ),
            ]
        ),
        AuditContext(correlation_id="legacy-aggregate-repair", source_context="test"),
    )

    assert repaired.version_compatibility == "COMPATIBLE"
    assert repaired.scheduling_status == "IDLE"
    assert session.execution_slot is not None
    slot_id = session.execution_slot.execution_slot_id
    repaired_again = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="CONFIGURED"),
            ]
        ),
        AuditContext(correlation_id="legacy-aggregate-repair-repeat", source_context="test"),
    )
    assert repaired_again.version_compatibility == "COMPATIBLE"
    assert session.execution_slot.execution_slot_id == slot_id
    assert sum(isinstance(item, ExecutionSlot) for item in session.added) == 1
    assert session.capability.validation_status == "VALID"
    assert session.playwright_capability.validation_status == "VALID"
    assert session.runner.row_version == initial_runner_version


def test_version_report_change_fails_closed_until_revalidated() -> None:
    service, session = _runner_validation_service()
    session.capability.validation_status = "VALID"
    session.playwright_capability.validation_status = "VALID"
    session.runner.version_compatibility = "COMPATIBLE"
    session.runner.scheduling_status = "IDLE"
    context = AuditContext(correlation_id="compatibility-change", source_context="test")

    stable = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="CONFIGURED"),
            ]
        ),
        context,
    )
    assert stable.version_compatibility == "COMPATIBLE"
    assert session.execution_slot is not None
    slot_id = session.execution_slot.execution_slot_id
    assert session.execution_slot.lifecycle_status == "ACTIVE"

    changed = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(
                    capability_code="AGENT_VERSION",
                    availability_status="CONFIGURED",
                    observed_version="0.2.0",
                ),
                RunnerCapabilityReportItem(
                    capability_code="PLAYWRIGHT_VERSION",
                    availability_status="CONFIGURED",
                    observed_version="1.62.0",
                ),
                RunnerCapabilityReportItem(
                    capability_code="FORMAL_EXECUTION",
                    availability_status="CONFIGURED",
                ),
            ]
        ),
        context,
    )

    assert changed.version_compatibility == "UNKNOWN"
    assert changed.scheduling_status == "UNSCHEDULABLE"
    assert session.execution_slot is not None
    assert session.execution_slot.execution_slot_id == slot_id
    assert session.execution_slot.lifecycle_status == "DISABLED"
    assert session.capability.validation_status == "PENDING"

    restored_report = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(
                    capability_code="AGENT_VERSION",
                    availability_status="CONFIGURED",
                    observed_version="0.1.0",
                ),
                RunnerCapabilityReportItem(
                    capability_code="PLAYWRIGHT_VERSION",
                    availability_status="CONFIGURED",
                    observed_version="1.62.0",
                ),
                RunnerCapabilityReportItem(
                    capability_code="FORMAL_EXECUTION",
                    availability_status="CONFIGURED",
                ),
            ]
        ),
        context,
    )
    assert restored_report.version_compatibility == "UNKNOWN"
    assert restored_report.scheduling_status == "UNSCHEDULABLE"

    restored = service.validate_capability(
        "bearer",
        session.runner.runner_id,
        "AGENT_VERSION",
        ValidateRunnerCapabilityRequest(
            expected_capability_version=session.capability.row_version,
            evidence_summary="Runner Agent 0.1.0 was revalidated after version restoration.",
            reason="restore supported Runner Agent version",
        ),
        "revalidate-restored-agent-version",
        context,
    )
    assert restored.version_compatibility == "COMPATIBLE"
    assert restored.scheduling_status == "IDLE"
    assert session.execution_slot is not None
    assert session.execution_slot.execution_slot_id == slot_id
    assert session.execution_slot.lifecycle_status == "ACTIVE"


def test_formal_execution_capability_loss_disables_and_recovery_reuses_same_slot() -> None:
    service, session = _runner_validation_service()
    session.capability.validation_status = "VALID"
    session.playwright_capability.validation_status = "VALID"
    context = AuditContext(correlation_id="formal-slot-capability", source_context="test")

    initial = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="CONFIGURED"),
            ]
        ),
        context,
    )
    assert initial.version_compatibility == "COMPATIBLE"
    assert session.execution_slot is not None
    slot_id = session.execution_slot.execution_slot_id

    lost = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="NOT_CONFIGURED"),
            ]
        ),
        context,
    )
    assert lost.version_compatibility == "COMPATIBLE"
    assert session.execution_slot.lifecycle_status == "DISABLED"

    restored_report = service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="CONFIGURED"),
            ]
        ),
        context,
    )
    assert restored_report.version_compatibility == "COMPATIBLE"
    assert session.formal_capability.validation_status == "PENDING"
    assert session.execution_slot.lifecycle_status == "DISABLED"

    service.validate_capability(
        "bearer",
        session.runner.runner_id,
        "FORMAL_EXECUTION",
        ValidateRunnerCapabilityRequest(
            expected_capability_version=session.formal_capability.row_version,
            evidence_summary="Formal execution runtime is available for the single P0 slot.",
            reason="revalidate formal execution capacity",
        ),
        "revalidate-formal-execution",
        context,
    )
    assert session.execution_slot.execution_slot_id == slot_id
    assert session.execution_slot.lifecycle_status == "ACTIVE"
    assert sum(isinstance(item, ExecutionSlot) for item in session.added) == 1



def test_runner_disable_and_enable_reconcile_the_same_formal_execution_slot_identity() -> None:
    service, session = _runner_validation_service()
    session.capability.validation_status = "VALID"
    session.playwright_capability.validation_status = "VALID"
    context = AuditContext(correlation_id="slot-runner-lifecycle", source_context="test")

    service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="CONFIGURED"),
            ]
        ),
        context,
    )
    assert session.execution_slot is not None
    slot_id = session.execution_slot.execution_slot_id

    service.transition(
        "bearer",
        session.runner.runner_id,
        "disable",
        RunnerLifecycleRequest(expected_version=session.runner.row_version, reason="maintenance"),
        "disable-slot-owner",
        context,
    )
    assert session.execution_slot.execution_slot_id == slot_id
    assert session.execution_slot.lifecycle_status == "DISABLED"

    service.transition(
        "bearer",
        session.runner.runner_id,
        "enable",
        RunnerLifecycleRequest(expected_version=session.runner.row_version, reason="maintenance completed"),
        "enable-slot-owner",
        context,
    )
    assert session.execution_slot.execution_slot_id == slot_id
    assert session.execution_slot.lifecycle_status == "ACTIVE"
    assert sum(isinstance(item, ExecutionSlot) for item in session.added) == 1


def test_runner_archive_archives_existing_formal_execution_slot_without_replacing_identity() -> None:
    service, session = _runner_validation_service()
    session.capability.validation_status = "VALID"
    session.playwright_capability.validation_status = "VALID"
    context = AuditContext(correlation_id="slot-runner-archive", source_context="test")
    service.report_capabilities(
        session.runner.runner_id,
        session.agent_token,
        ReportRunnerCapabilitiesRequest(
            capabilities=[
                RunnerCapabilityReportItem(capability_code="AGENT_VERSION", availability_status="CONFIGURED", observed_version="0.1.0"),
                RunnerCapabilityReportItem(capability_code="PLAYWRIGHT_VERSION", availability_status="CONFIGURED", observed_version="1.62.0"),
                RunnerCapabilityReportItem(capability_code="FORMAL_EXECUTION", availability_status="CONFIGURED"),
            ]
        ),
        context,
    )
    assert session.execution_slot is not None
    slot_id = session.execution_slot.execution_slot_id
    service.transition(
        "bearer", session.runner.runner_id, "disable",
        RunnerLifecycleRequest(expected_version=session.runner.row_version, reason="retire runner"),
        "disable-before-archive", context,
    )
    service.transition(
        "bearer", session.runner.runner_id, "archive",
        RunnerLifecycleRequest(expected_version=session.runner.row_version, reason="retire runner"),
        "archive-slot-owner", context,
    )
    assert session.execution_slot.execution_slot_id == slot_id
    assert session.execution_slot.lifecycle_status == "ARCHIVED"
    assert sum(isinstance(item, ExecutionSlot) for item in session.added) == 1

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
