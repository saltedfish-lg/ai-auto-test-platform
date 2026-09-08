from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from platform_api.errors import PlatformError
from platform_api.execution_binding_schemas import BindingCommandRequest
from platform_api.execution_binding_service import (
    ExecutionBindingService,
    _command_idempotency_payload,
    _persistence_conflict,
)
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 9, 1, tzinfo=UTC).replace(tzinfo=None)


def _binding(**overrides: Any) -> SimpleNamespace:
    values = {
        "execution_binding_snapshot_id": "B" * 26,
        "execution_attempt_id": "A" * 26,
        "owner_execution_identity": "Q" * 26,
        "identity_lease_generation": 7,
        "runner_lease_generation": 11,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _lease(resource_type: str, generation: int, **overrides: Any) -> SimpleNamespace:
    values = {
        "resource_type": resource_type,
        "owner_type": (
            "FORMAL_ROOT_EXECUTION_TASK" if resource_type == "IDENTITY" else "EXECUTION_ATTEMPT"
        ),
        "owner_id": "Q" * 26 if resource_type == "IDENTITY" else "A" * 26,
        "status": "ACTIVE",
        "acquired_at": NOW,
        "expires_at": NOW + timedelta(seconds=120),
        "released_at": None,
        "fencing_generation": generation,
        "row_version": 1,
        "updated_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _command(**overrides: Any) -> BindingCommandRequest:
    values = {
        "owner_execution_identity": "Q" * 26,
        "expected_version": 1,
        "identity_lease_generation": 7,
        "runner_lease_generation": 11,
        "reason": "test command",
    }
    values.update(overrides)
    return BindingCommandRequest.model_validate(values)


def test_owner_and_both_fencing_generations_fail_closed() -> None:
    binding = _binding()
    identity = _lease("IDENTITY", 7)
    runner = _lease("RUNNER", 11)
    attempt = SimpleNamespace(
        execution_attempt_id="A" * 26,
        execution_binding_snapshot_id="B" * 26,
        run_task_id="Q" * 26,
    )

    with pytest.raises(PlatformError) as owner_error:
        ExecutionBindingService._assert_owner(
            binding,
            identity,
            runner,
            attempt,
            _command(owner_execution_identity="old-owner"),
        )
    assert owner_error.value.code == "RESOURCE_LEASE_FENCING_CONFLICT"

    with pytest.raises(PlatformError) as identity_owner_error:
        ExecutionBindingService._assert_owner(
            binding,
            _lease("IDENTITY", 7, owner_id="Z" * 26),
            runner,
            attempt,
            _command(),
        )
    assert identity_owner_error.value.code == "RESOURCE_LEASE_FENCING_CONFLICT"

    with pytest.raises(PlatformError) as identity_generation_error:
        ExecutionBindingService._assert_generations(
            binding, identity, runner, _command(identity_lease_generation=6)
        )
    assert identity_generation_error.value.code == "RESOURCE_LEASE_FENCING_CONFLICT"

    with pytest.raises(PlatformError) as runner_generation_error:
        ExecutionBindingService._assert_generations(
            binding, identity, runner, _command(runner_lease_generation=10)
        )
    assert runner_generation_error.value.code == "RESOURCE_LEASE_FENCING_CONFLICT"


def test_expired_active_lease_cannot_be_normally_released() -> None:
    identity = _lease("IDENTITY", 7, expires_at=NOW)
    runner = _lease("RUNNER", 11)

    with pytest.raises(PlatformError) as error:
        ExecutionBindingService._release_active_leases(identity, runner, NOW)
    assert error.value.code == "RESOURCE_LEASE_FENCING_CONFLICT"
    assert identity.status == "ACTIVE"
    assert runner.status == "ACTIVE"


def test_resource_release_and_stale_expiry_are_idempotent() -> None:
    identity = _lease("IDENTITY", 7)
    runner = _lease("RUNNER", 11)
    ExecutionBindingService._release_active_leases(identity, runner, NOW)
    identity_version = identity.row_version
    runner_version = runner.row_version

    ExecutionBindingService._release_lease(identity, NOW + timedelta(seconds=1))
    ExecutionBindingService._release_lease(runner, NOW + timedelta(seconds=1))
    assert (identity.status, runner.status) == ("RELEASED", "RELEASED")
    assert (identity.row_version, runner.row_version) == (identity_version, runner_version)

    stale = _lease("IDENTITY", 7)
    ExecutionBindingService._expire_lease(stale, NOW)
    stale_version = stale.row_version
    ExecutionBindingService._expire_lease(stale, NOW + timedelta(seconds=1))
    assert stale.status == "EXPIRED"
    assert stale.row_version == stale_version


@pytest.mark.parametrize("status", ["RELEASED", "EXPIRED"])
def test_terminal_binding_cannot_be_recovered(status: str) -> None:
    with pytest.raises(PlatformError) as error:
        ExecutionBindingService._assert_recoverable_status(_binding(status=status))
    assert error.value.code == "EXECUTION_BINDING_STATE_CONFLICT"


def test_command_idempotency_payload_is_scoped_to_the_path_binding() -> None:
    body = _command()
    assert _command_idempotency_payload("B" * 26, body) != _command_idempotency_payload(
        "C" * 26, body
    )


class _AcquireSession:
    def __init__(self, generation: SimpleNamespace | None) -> None:
        self.generation = generation
        self.added: list[object] = []

    def scalar(self, _query: object) -> SimpleNamespace | None:
        return self.generation

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None


def test_reacquire_increments_generation_but_new_identity_starts_at_one() -> None:
    existing = SimpleNamespace(current_generation=4, updated_at=NOW)
    session = _AcquireSession(existing)
    reacquired = ExecutionBindingService._acquire_lease(
        session,  # type: ignore[arg-type]
        project_id="P" * 26,
        resource_type="RUNNER",
        resource_identity="runner:FORMAL_EXECUTION_SLOT:slot-1",
        owner_type="EXECUTION_ATTEMPT",
        owner_id="A" * 26,
        ttl_seconds=120,
        now=NOW,
        correlation_id="correlation",
    )
    assert existing.current_generation == 5
    assert reacquired.fencing_generation == 5

    first_session = _AcquireSession(None)
    first = ExecutionBindingService._acquire_lease(
        first_session,  # type: ignore[arg-type]
        project_id="P" * 26,
        resource_type="IDENTITY",
        resource_identity="project:environment:identity",
        owner_type="FORMAL_ROOT_EXECUTION_TASK",
        owner_id="Q" * 26,
        ttl_seconds=600,
        now=NOW,
        correlation_id="correlation",
    )
    assert first.fencing_generation == 1


def test_generic_duplicate_is_not_misclassified_as_resource_lease_conflict() -> None:
    generic_duplicate = IntegrityError(
        "INSERT",
        {},
        Exception("Duplicate entry '1' for key 'uq_outbox_aggregate_sequence'"),
    )
    actual_lease_duplicate = IntegrityError(
        "INSERT",
        {},
        Exception("Duplicate entry '1' for key 'uq_atp_resource_lease_active'"),
    )

    assert _persistence_conflict(generic_duplicate).code == "EXECUTION_BINDING_PERSISTENCE_CONFLICT"
    assert _persistence_conflict(actual_lease_duplicate).code == "RESOURCE_LEASE_CONFLICT"
