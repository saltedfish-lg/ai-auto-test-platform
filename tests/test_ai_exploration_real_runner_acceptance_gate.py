from __future__ import annotations

from tools.gates.ai_exploration_real_runner_acceptance import (
    _bounded_observation,
    _current_version_capabilities_ready,
    _login_succeeded,
    _validated_capability_codes,
    _successful_owner_lifecycle_evidence,
    _successful_step_call_evidence,
    _successful_step_evidence,
    _unsafe_document_path,
)


def test_real_runner_acceptance_secret_boundary_rejects_sensitive_keys() -> None:
    assert _unsafe_document_path({"current_url": "https://example.test", "password": "x"}) == "$.password"
    assert _unsafe_document_path({"nested": [{"authorization": "x"}]}) == "$.nested[0].authorization"
    assert _unsafe_document_path({"current_url": "https://example.test", "title": "Dashboard"}) is None


def test_real_runner_acceptance_requires_bounded_minimal_observation() -> None:
    assert _bounded_observation(
        {
            "current_url": "https://example.test/dashboard",
            "title": "Dashboard",
            "visible_text": "Welcome",
            "interactive_elements": [{"role": "button", "name": "Search"}],
        }
    )
    assert not _bounded_observation({"title": "missing url"})
    assert not _bounded_observation({"current_url": "https://example.test", "dom": "<html/>"})



class _LoginStep:
    def __init__(self, observation: object) -> None:
        self.observation_json = observation


def test_real_runner_acceptance_requires_observable_login_success_marker() -> None:
    assert _login_succeeded(
        [
            _LoginStep(
                {
                    "current_url": "https://example.test/dashboard",
                    "login_state_marker": {
                        "status": "SUCCEEDED",
                        "signal": "AUTHENTICATED_URL",
                        "login_submitted": True,
                    },
                }
            )
        ]
    )
    assert not _login_succeeded(
        [
            _LoginStep(
                {
                    "current_url": "https://example.test/login",
                    "login_state_marker": {
                        "status": "NOT_OBSERVED",
                        "signal": "LOGIN_FORM_NOT_PRESENT",
                        "login_submitted": False,
                    },
                }
            )
        ]
    )
    assert not _login_succeeded(
        [
            _LoginStep(
                {
                    "current_url": "https://example.test/dashboard",
                    "login_state_marker": {
                        "status": "SUCCEEDED",
                        "signal": "UNTRUSTED_SLEEP",
                        "login_submitted": True,
                    },
                }
            )
        ]
    )

def test_real_runner_acceptance_requires_validated_capabilities_from_frozen_snapshot() -> None:
    assert _validated_capability_codes(
        [
            {
                "capability_code": "AI_EXPLORATION",
                "availability_status": "CONFIGURED",
                "validation_status": "VALID",
                "lifecycle_status": "ACTIVE",
            },
            {
                "capability_code": "BROWSER_CHROMIUM",
                "availability_status": "CONFIGURED",
                "validation_status": "PENDING",
                "lifecycle_status": "ACTIVE",
            },
            "ignored",
        ]
    ) == {"AI_EXPLORATION"}


class _Step:
    def __init__(self, *, status: str, action: object, result: object, completed: bool = True) -> None:
        self.status = status
        self.action_json = action
        self.action_result_json = result
        self.completed_at = "2026-09-07T00:00:00Z" if completed else None


def test_real_runner_acceptance_accepts_terminal_goal_completion_evidence() -> None:
    assert _successful_step_evidence(
        [
            _Step(status="SUCCEEDED", action={"type": "Click"}, result={"status": "SUCCEEDED"}),
            _Step(
                status="COMPLETION_PROPOSED",
                action={"type": "goal_completed"},
                result={"status": "COMPLETION_ACCEPTED"},
            ),
        ]
    )
    assert not _successful_step_evidence(
        [
            _Step(
                status="COMPLETION_PROPOSED",
                action={"type": "goal_completed"},
                result={"status": "COMPLETION_REJECTED"},
            )
        ]
    )
    assert not _successful_step_evidence(
        [_Step(status="SUCCEEDED", action={"type": "Click"}, result={"status": "SUCCEEDED"})]
    )


class _Call:
    def __init__(
        self,
        *,
        ai_task_id: str = "task-1",
        project_id: str = "project-1",
        lifecycle_status: str = "SUCCEEDED",
        provider_request_id: str | None = "provider-1",
    ) -> None:
        self.ai_task_id = ai_task_id
        self.project_id = project_id
        self.lifecycle_status = lifecycle_status
        self.extension_json = (
            {"provider_request_id": provider_request_id} if provider_request_id is not None else {}
        )


class _CallStep:
    def __init__(self, ai_call_id: str) -> None:
        self.ai_call_id = ai_call_id
        self.model_call_identity = ai_call_id


def test_real_runner_acceptance_uses_distinct_successful_browser_ai_calls() -> None:
    steps = [_CallStep("call-1"), _CallStep("call-2")]
    calls = {"call-1": _Call(), "call-2": _Call(provider_request_id="provider-2")}
    assert _successful_step_call_evidence(
        steps, calls, ai_task_id="task-1", project_id="project-1"
    )
    assert not _successful_step_call_evidence(
        steps, {"call-1": _Call()}, ai_task_id="task-1", project_id="project-1"
    )
    assert not _successful_step_call_evidence(
        steps,
        {"call-1": _Call(), "call-2": _Call(lifecycle_status="FAILED")},
        ai_task_id="task-1",
        project_id="project-1",
    )
    assert not _successful_step_call_evidence(
        steps,
        {"call-1": _Call(), "call-2": _Call(provider_request_id=None)},
        ai_task_id="task-1",
        project_id="project-1",
    )


class _OwnerAudit:
    def __init__(self, aggregate_type: str, previous_status: str | None, new_status: str) -> None:
        self.aggregate_type = aggregate_type
        self.previous_status = previous_status
        self.new_status = new_status


def test_real_runner_acceptance_requires_unskipped_owner_lifecycle_paths() -> None:
    rows = [
        _OwnerAudit("RUN_TASK", None, "CREATED"),
        _OwnerAudit("RUN_TASK", "CREATED", "SNAPSHOTTED"),
        _OwnerAudit("RUN_TASK", "SNAPSHOTTED", "VALIDATING"),
        _OwnerAudit("RUN_TASK", "VALIDATING", "WAITING_RESOURCE"),
        _OwnerAudit("RUN_TASK", "WAITING_RESOURCE", "DISPATCHING"),
        _OwnerAudit("RUN_TASK", "DISPATCHING", "PREPARING"),
        _OwnerAudit("RUN_TASK", "PREPARING", "RUNNING"),
        _OwnerAudit("RUN_TASK", "RUNNING", "COMPLETED"),
        _OwnerAudit("EXECUTION_ATTEMPT", None, "CREATED"),
        _OwnerAudit("EXECUTION_ATTEMPT", "CREATED", "PREPARING"),
        _OwnerAudit("EXECUTION_ATTEMPT", "PREPARING", "RUNNING"),
        _OwnerAudit("EXECUTION_ATTEMPT", "RUNNING", "PASSED"),
        _OwnerAudit("EXECUTION_ATTEMPT", "PASSED", "COMPLETED"),
    ]
    assert _successful_owner_lifecycle_evidence(rows)
    assert not _successful_owner_lifecycle_evidence(
        [row for row in rows if not (row.aggregate_type == "RUN_TASK" and row.new_status == "VALIDATING")]
    )


class _VersionCapability:
    def __init__(
        self,
        code: str,
        version: str,
        *,
        validation: str = "VALID",
        availability: str = "CONFIGURED",
        lifecycle: str = "ACTIVE",
    ) -> None:
        self.capability_code = code
        self.observed_version = version
        self.validation_status = validation
        self.availability_status = availability
        self.lifecycle_status = lifecycle


def test_real_runner_acceptance_requires_current_formal_version_compatibility() -> None:
    compatible = [
        _VersionCapability("AGENT_VERSION", "0.1.0"),
        _VersionCapability("PLAYWRIGHT_VERSION", "1.62.0"),
    ]
    assert _current_version_capabilities_ready(compatible)
    assert not _current_version_capabilities_ready(
        [
            _VersionCapability("AGENT_VERSION", "0.1.0", validation="PENDING"),
            _VersionCapability("PLAYWRIGHT_VERSION", "1.62.0"),
        ]
    )
    assert not _current_version_capabilities_ready(
        [
            _VersionCapability("AGENT_VERSION", "0.2.0"),
            _VersionCapability("PLAYWRIGHT_VERSION", "1.62.0"),
        ]
    )


def test_project_acceptance_no_longer_precreates_execution_slot_with_sql() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "tools/gates/project_acceptance_runtime.py").read_text(encoding="utf-8")
    assert "INSERT INTO atp_execution_slot" not in source
    assert "reconcile_formal_execution_slot" in source


def test_real_runner_gate_requires_the_stable_p0_formal_execution_slot() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "tools/gates/ai_exploration_real_runner_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert 'checks["formal_execution_slot"]' in source
    assert 'formal_slot.slot_no == "0"' in source
    assert "FORMAL_EXECUTION_SLOT" in source
