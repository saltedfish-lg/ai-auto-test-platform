#!/usr/bin/env python3
"""Verify a completed real-runner AI Exploration from persisted production-path evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from tools.environment import get_env, load_project_environment  # noqa: E402

ROOT = _BOOTSTRAP_ROOT
API_SRC = ROOT / "services" / "api" / "src"
COMMON_SRC = ROOT / "packages" / "platform-common" / "src"
OBSERVABILITY_SRC = ROOT / "packages" / "observability" / "src"
for import_root in (API_SRC, COMMON_SRC, OBSERVABILITY_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from platform_api.database import create_database_engine, create_session_factory  # noqa: E402
from platform_api.runner_readiness import (  # noqa: E402
    runner_accept_new_execution_blockers,
    resolve_version_compatibility,
)
from platform_api.models import (  # noqa: E402
    AICall,
    AIExplorationAudit,
    AIExplorationSession,
    AIExplorationStep,
    AccountMappingRevision,
    CredentialRevision,
    ExecutionAttempt,
    ExecutionBindingSnapshot,
    ExecutionOwnerAudit,
    ExecutionSlot,
    LoginStrategy,
    ModelConfiguration,
    OutboxEvent,
    Project,
    ProjectRuntimePolicyRevision,
    ResourceLease,
    RunTask,
    Runner,
    RunnerAgent,
    RunnerCapability,
    TerminalAccessRevision,
    TestAccount,
)

GATE_ID = "AI_EXPLORATION_REAL_RUNNER_ACCEPTANCE"
DATABASE_URL_ENV = "ATP_DATABASE_URL"
_REQUIRED_CAPABILITIES = {
    "AI_EXPLORATION",
    "BROWSER_CHROMIUM",
    "FORMAL_EXECUTION",
    "MODE_HEADLESS",
    "CONTEXT_ISOLATION",
}
_BLOCKED_KEY_TERMS = {
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "captcha",
    "localstorage",
    "local_storage",
    "html",
    "dom",
    "chain_of_thought",
    "reasoning",
}


def _normalize_key(value: object) -> str:
    return "".join(c for c in str(value).lower() if c.isalnum() or c == "_")


def _unsafe_document_path(value: object, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalize_key(key)
            if any(term in normalized for term in _BLOCKED_KEY_TERMS):
                return f"{path}.{key}"
            found = _unsafe_document_path(item, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _unsafe_document_path(item, f"{path}[{index}]")
            if found:
                return found
    return None


def _bounded_observation(value: object) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("current_url"), str):
        return False
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return len(raw.encode("utf-8")) <= 65536 and _unsafe_document_path(value) is None


def _validated_capability_codes(snapshot: object) -> set[str]:
    """Read only capabilities frozen as configured, validated and active at bind time."""
    if not isinstance(snapshot, list):
        return set()
    return {
        str(item.get("capability_code"))
        for item in snapshot
        if isinstance(item, dict)
        and isinstance(item.get("capability_code"), str)
        and item.get("availability_status") == "CONFIGURED"
        and item.get("validation_status") == "VALID"
        and item.get("lifecycle_status") == "ACTIVE"
    }


def _successful_owner_lifecycle_evidence(rows: list[ExecutionOwnerAudit]) -> bool:
    """Require the canonical LC-035/LC-036 success path without skipped lifecycle edges."""

    edges: dict[str, set[tuple[str | None, str | None]]] = {
        "RUN_TASK": set(),
        "EXECUTION_ATTEMPT": set(),
    }
    for row in rows:
        if row.aggregate_type in edges:
            edges[row.aggregate_type].add((row.previous_status, row.new_status))
    run_task_edges = {
        ("CREATED", "SNAPSHOTTED"),
        ("SNAPSHOTTED", "VALIDATING"),
        ("VALIDATING", "WAITING_RESOURCE"),
        ("WAITING_RESOURCE", "DISPATCHING"),
        ("DISPATCHING", "PREPARING"),
        ("PREPARING", "RUNNING"),
        ("RUNNING", "COMPLETED"),
    }
    attempt_edges = {
        ("CREATED", "PREPARING"),
        ("PREPARING", "RUNNING"),
        ("RUNNING", "PASSED"),
        ("PASSED", "COMPLETED"),
    }
    return run_task_edges.issubset(edges["RUN_TASK"]) and attempt_edges.issubset(
        edges["EXECUTION_ATTEMPT"]
    )


def _event_types(rows: list[OutboxEvent]) -> set[str]:
    return {row.event_type for row in rows}




def _successful_step_call_evidence(
    steps: list[AIExplorationStep],
    step_calls: dict[str, AICall],
    *,
    ai_task_id: str,
    project_id: str,
) -> bool:
    """Each Browser Loop decision has its own successful AICall under the frozen AI task."""
    if not steps:
        return False
    for step in steps:
        call = step_calls.get(step.ai_call_id)
        if (
            call is None
            or step.model_call_identity != step.ai_call_id
            or call.ai_task_id != ai_task_id
            or call.project_id != project_id
            or call.lifecycle_status != "SUCCEEDED"
            or not isinstance(call.extension_json, dict)
            or not call.extension_json.get("provider_request_id")
        ):
            return False
    return True



def _login_succeeded(steps: list[AIExplorationStep]) -> bool:
    """Require a redacted observable login-success marker from the real Runner runtime."""
    for step in steps:
        observation = step.observation_json if isinstance(step.observation_json, dict) else {}
        marker = observation.get("login_state_marker")
        if not isinstance(marker, dict):
            continue
        if (
            marker.get("status") == "SUCCEEDED"
            and marker.get("login_submitted") is True
            and marker.get("signal") in {"AUTHENTICATED_URL", "LOGIN_FORM_DISAPPEARED"}
        ):
            return True
    return False

def _successful_step_evidence(steps: list[AIExplorationStep]) -> bool:
    """Require executed steps followed by the accepted terminal goal-completion proposal."""
    if not steps:
        return False
    for step in steps[:-1]:
        if step.completed_at is None or step.status != "SUCCEEDED":
            return False
    final = steps[-1]
    if final.completed_at is None:
        return False
    action = final.action_json if isinstance(final.action_json, dict) else {}
    result = final.action_result_json if isinstance(final.action_result_json, dict) else {}
    return (
        action.get("type") == "goal_completed"
        and final.status == "COMPLETION_PROPOSED"
        and result.get("status") == "COMPLETION_ACCEPTED"
    )


def _current_version_capabilities_ready(capabilities: list[RunnerCapability]) -> bool:
    """Require current validated version capabilities to resolve to COMPATIBLE."""
    return resolve_version_compatibility(capabilities) == "COMPATIBLE"


def verify_session(factory, session_id: str) -> dict[str, Any]:
    with factory() as db:
        session = db.get(AIExplorationSession, session_id)
        if session is None:
            return _failed("SESSION_NOT_FOUND")
        attempt = db.get(ExecutionAttempt, session.execution_attempt_id) if session.execution_attempt_id else None
        binding = (
            db.get(ExecutionBindingSnapshot, session.execution_binding_snapshot_id)
            if session.execution_binding_snapshot_id
            else None
        )
        run_task = db.get(RunTask, attempt.run_task_id) if attempt and attempt.run_task_id else None
        runner = db.get(Runner, binding.runner_id) if binding else None
        project = db.get(Project, binding.project_id) if binding else None
        runner_agent = (
            db.scalar(select(RunnerAgent).where(RunnerAgent.runner_id == binding.runner_id))
            if binding
            else None
        )
        current_runner_capabilities = (
            list(
                db.scalars(
                    select(RunnerCapability).where(
                        RunnerCapability.runner_id == binding.runner_id
                    )
                )
            )
            if binding
            else []
        )
        terminal = db.get(TerminalAccessRevision, binding.terminal_access_revision_id) if binding else None
        strategy = db.get(LoginStrategy, binding.login_strategy_id) if binding else None
        account = db.get(TestAccount, binding.test_account_id) if binding else None
        credential = db.get(CredentialRevision, binding.credential_revision_id) if binding else None
        mapping = db.get(AccountMappingRevision, binding.account_mapping_revision_id) if binding else None
        policy = db.get(ProjectRuntimePolicyRevision, binding.runtime_policy_revision_id) if binding else None
        model = db.get(ModelConfiguration, session.resolved_model_config_id)
        ai_call = db.get(AICall, session.ai_call_id)
        identity_lease = db.get(ResourceLease, binding.identity_lease_id) if binding else None
        runner_lease = db.get(ResourceLease, binding.runner_lease_id) if binding else None
        execution_slots = (
            list(
                db.scalars(
                    select(ExecutionSlot).where(
                        ExecutionSlot.project_id == binding.project_id,
                        ExecutionSlot.runner_id == binding.runner_id,
                    )
                )
            )
            if binding
            else []
        )
        formal_slot = next(
            (slot for slot in execution_slots if slot.slot_no == "0"),
            None,
        )
        steps = list(
            db.scalars(
                select(AIExplorationStep)
                .where(AIExplorationStep.session_id == session_id)
                .order_by(AIExplorationStep.sequence)
            )
        )
        step_call_ids = {step.ai_call_id for step in steps if step.ai_call_id}
        step_calls = {
            call.ai_call_id: call
            for call in db.scalars(select(AICall).where(AICall.ai_call_id.in_(step_call_ids)))
        } if step_call_ids else {}
        ai_audits = list(
            db.scalars(select(AIExplorationAudit).where(AIExplorationAudit.session_id == session_id))
        )
        owner_audits = [] if run_task is None else list(
            db.scalars(
                select(ExecutionOwnerAudit).where(
                    ExecutionOwnerAudit.aggregate_id.in_(
                        [run_task.run_task_id, attempt.execution_attempt_id]
                    )
                )
            )
        )
        outbox_ids = [session_id]
        if run_task is not None:
            outbox_ids.append(run_task.run_task_id)
        if attempt is not None:
            outbox_ids.append(attempt.execution_attempt_id)
        outbox = list(
            db.scalars(select(OutboxEvent).where(OutboxEvent.aggregate_id.in_(outbox_ids)))
        )

        checks: dict[str, bool] = {}
        checks["session_succeeded"] = session.lifecycle_status == "SUCCEEDED"
        checks["execution_owner_links"] = bool(
            attempt
            and binding
            and run_task
            and session.execution_attempt_id == attempt.execution_attempt_id
            and session.execution_binding_snapshot_id == binding.execution_binding_snapshot_id
            and binding.execution_attempt_id == attempt.execution_attempt_id
            and binding.owner_execution_identity == run_task.run_task_id
            and attempt.run_task_id == run_task.run_task_id
            and attempt.runner_id == binding.runner_id
            and attempt.project_id == session.project_id == binding.project_id == run_task.project_id
        )
        checks["frozen_business_facts"] = bool(
            binding
            and terminal
            and strategy
            and account
            and credential
            and mapping
            and policy
            and terminal.environment_terminal_access_revision_id == binding.terminal_access_revision_id
            and terminal.project_id == binding.project_id
            and terminal.environment_id == binding.environment_id
            and terminal.business_terminal_id == binding.business_terminal_id
            and terminal.lifecycle_status == "PUBLISHED"
            and terminal.login_strategy_id == binding.login_strategy_id
            and strategy.login_strategy_id == binding.login_strategy_id
            and strategy.project_id == binding.project_id
            and strategy.lifecycle_status == "ACTIVE"
            and account.test_account_id == binding.test_account_id
            and account.project_id == binding.project_id
            and account.environment_id == binding.environment_id
            and account.lifecycle_status == "ACTIVE"
            and credential.credential_revision_id == binding.credential_revision_id
            and credential.test_account_id == binding.test_account_id
            and credential.project_id == binding.project_id
            and credential.lifecycle_status == "PUBLISHED"
            and mapping.account_mapping_revision_id == binding.account_mapping_revision_id
            and mapping.test_account_id == binding.test_account_id
            and mapping.project_id == binding.project_id
            and mapping.environment_id == binding.environment_id
            and mapping.business_terminal_id == binding.business_terminal_id
            and mapping.lifecycle_status == "PUBLISHED"
            and policy.runtime_policy_revision_id == binding.runtime_policy_revision_id
            and policy.project_id == binding.project_id
            and policy.lifecycle_status == "PUBLISHED"
        )
        codes = _validated_capability_codes(binding.runner_capability_snapshot if binding else None)
        checks["bound_real_runner"] = bool(
            binding
            and runner
            and runner.runner_id == binding.runner_id
            and runner.project_id == binding.project_id
            and runner.lifecycle_status == "ACTIVE"
            and runner.registration_status == "REGISTERED"
            and runner.connection_status == "ONLINE"
            and runner.health_status == "HEALTHY"
            and runner.enable_status == "ENABLED"
            and runner.project_binding_status == "BOUND"
            and runner.version_compatibility == "COMPATIBLE"
            and runner.last_heartbeat_at is not None
            and binding.runner_heartbeat_at is not None
            and _REQUIRED_CAPABILITIES.issubset(codes)
        )
        checks["current_version_capabilities"] = bool(
            binding
            and runner
            and _current_version_capabilities_ready(current_runner_capabilities)
        )
        checks["formal_execution_slot"] = bool(
            binding
            and len(execution_slots) == 1
            and formal_slot is not None
            and formal_slot.project_id == binding.project_id
            and formal_slot.runner_id == binding.runner_id
            and formal_slot.slot_no == "0"
            and formal_slot.lifecycle_status == "ACTIVE"
            and binding.runner_lease_id
            and runner_lease
            and runner_lease.resource_identity
            == f"{binding.runner_id}:FORMAL_EXECUTION_SLOT:{formal_slot.execution_slot_id}"
        )
        checks["runner_accepts_new_execution"] = bool(
            runner
            and project
            and not runner_accept_new_execution_blockers(
                runner, project_lifecycle_status=project.lifecycle_status
            )
        )
        checks["machine_auth"] = bool(
            binding
            and runner_agent
            and runner_agent.runner_id == binding.runner_id
            and runner_agent.project_id == binding.project_id
            and runner_agent.token_status == "ACTIVE"
            and runner_agent.lifecycle_status == "ACTIVE"
            and runner_agent.last_authenticated_at is not None
        )
        checks["model_snapshot"] = bool(
            model
            and ai_call
            and session.resolved_model_config_id == model.model_config_id
            and session.resolved_provider_code == model.provider_code
            and session.resolved_model_name == model.model_name
            and ai_call.ai_task_id == session.ai_task_id
            and ai_call.project_id == session.project_id
            and ai_call.lifecycle_status == "SUCCEEDED"
            and bool(session.plan)
        )
        checks["ordered_step_evidence"] = bool(
            steps
            and [step.sequence for step in steps] == list(range(1, len(steps) + 1))
            and all(step.execution_attempt_id == session.execution_attempt_id for step in steps)
            and _successful_step_call_evidence(
                steps,
                step_calls,
                ai_task_id=session.ai_task_id,
                project_id=session.project_id,
            )
            and _successful_step_evidence(steps)
            and binding is not None
            and all(step.identity_lease_generation == binding.identity_lease_generation for step in steps)
            and all(step.runner_lease_generation == binding.runner_lease_generation for step in steps)
        )
        checks["minimal_observation"] = bool(steps) and all(
            _bounded_observation(step.observation_json) for step in steps
        )
        checks["login_success"] = _login_succeeded(steps)
        unsafe_paths = [
            path
            for step in steps
            for value in (step.observation_json, step.action_json, step.action_result_json)
            if (path := _unsafe_document_path(value)) is not None
        ]
        checks["secret_boundary"] = not unsafe_paths
        checks["release"] = bool(
            binding
            and identity_lease
            and runner_lease
            and binding.status == "RELEASED"
            and binding.released_at is not None
            and identity_lease.status == "RELEASED"
            and runner_lease.status == "RELEASED"
        )
        checks["owner_terminal_state"] = bool(
            attempt
            and run_task
            and attempt.execution_status == "SUCCEEDED"
            and attempt.finalization_status == "COMPLETED"
            and attempt.lifecycle_status == "COMPLETED"
            and run_task.lifecycle_status == "COMPLETED"
            and run_task.task_state == "COMPLETED"
            and run_task.final_result == "PASSED"
        )
        owner_actions = {row.action for row in owner_audits}
        events = _event_types(outbox)
        ai_audit_actions = {row.action for row in ai_audits}
        checks["browser_cleanup"] = (
            "BROWSER_CLEANUP_SUCCEEDED" in ai_audit_actions
            and "BROWSER_CLEANUP_FAILED" not in ai_audit_actions
        )
        checks["owner_lifecycle_path"] = _successful_owner_lifecycle_evidence(owner_audits)
        checks["audit_outbox"] = bool(
            {"BROWSER_STARTED", "BROWSER_SUCCEEDED"}.issubset(ai_audit_actions)
            and {
                "RUN_TASK_CREATED",
                "RUN_TASK_SNAPSHOTTED",
                "RUN_TASK_VALIDATING",
                "RUN_TASK_WAITING_RESOURCE",
                "RUN_TASK_DISPATCHING",
                "RUN_TASK_PREPARING",
                "RUN_TASK_RUNNING",
                "RUN_TASK_COMPLETED",
                "EXECUTION_ATTEMPT_CREATED",
                "EXECUTION_ATTEMPT_PREPARING",
                "EXECUTION_ATTEMPT_RUNNING",
                "EXECUTION_ATTEMPT_PASSED",
                "EXECUTION_ATTEMPT_COMPLETED",
            }.issubset(owner_actions)
            and {
                "run_task.created",
                "run_task.snapshotted",
                "run_task.validating",
                "run_task.waiting_resource",
                "run_task.dispatching",
                "run_task.preparing",
                "run_task.running",
                "run_task.completed",
                "execution_attempt.created",
                "execution_attempt.preparing",
                "execution_attempt.running",
                "execution_attempt.passed",
                "execution_attempt.completed",
                "ai_exploration.browser_started",
                "ai_exploration.succeeded",
            }.issubset(events)
        )

        passed = all(checks.values())
        result: dict[str, Any] = {
            "result_schema_version": 1,
            "gate": GATE_ID,
            "gate_id": GATE_ID,
            "status": "PASS" if passed else "FAIL",
            "result": "PASS" if passed else "FAIL",
            GATE_ID: "PASS" if passed else "FAIL",
            "contains_secrets": False,
            "session_id": session.session_id,
            "ai_exploration_session_id": session.session_id,
            "project_id": session.project_id,
            "environment_id": None if binding is None else binding.environment_id,
            "business_terminal_id": None if binding is None else binding.business_terminal_id,
            "terminal_access_revision_id": None if binding is None else binding.terminal_access_revision_id,
            "login_strategy_id": None if binding is None else binding.login_strategy_id,
            "test_account_id": None if binding is None else binding.test_account_id,
            "credential_revision_id": None if binding is None else binding.credential_revision_id,
            "runner_id": None if binding is None else binding.runner_id,
            "execution_slot_count": len(execution_slots),
            "execution_slot_id": None if formal_slot is None else formal_slot.execution_slot_id,
            "execution_slot_no": None if formal_slot is None else formal_slot.slot_no,
            "execution_slot_lifecycle": None if formal_slot is None else formal_slot.lifecycle_status,
            "runner_version_compatibility": None if runner is None else runner.version_compatibility,
            "runner_scheduling_status": None if runner is None else runner.scheduling_status,
            "runner_resource_status": None if runner is None else runner.resource_status,
            "version_capabilities_valid": checks["current_version_capabilities"],
            "runtime_policy_revision_id": None if binding is None else binding.runtime_policy_revision_id,
            "execution_attempt_id": session.execution_attempt_id,
            "execution_binding_snapshot_id": session.execution_binding_snapshot_id,
            "run_task_id": None if run_task is None else run_task.run_task_id,
            "model_snapshot_id": session.resolved_model_config_id,
            "model_config_id": session.resolved_model_config_id,
            "provider_code": session.resolved_provider_code,
            "model_name": session.resolved_model_name,
            "ordered_step_count": len(steps),
            "login_success": checks["login_success"],
            "minimal_observation": checks["minimal_observation"],
            "secret_boundary": "PASS" if checks["secret_boundary"] else "FAIL",
            "binding_released": bool(binding and binding.status == "RELEASED"),
            "identity_lease_released": bool(identity_lease and identity_lease.status == "RELEASED"),
            "runner_lease_released": bool(runner_lease and runner_lease.status == "RELEASED"),
            "cleanup": "PASS" if checks["browser_cleanup"] else "FAIL",
            "checks": {key: "PASS" if value else "FAIL" for key, value in checks.items()},
            "unsafe_persisted_paths": unsafe_paths,
        }
        if not passed:
            result["failed_checks"] = [key for key, value in checks.items() if not value]
        return result


def _failed(code: str) -> dict[str, Any]:
    return {
        "result_schema_version": 1,
        "gate": GATE_ID,
        "gate_id": GATE_ID,
        "status": "FAIL",
        "result": "FAIL",
        "contains_secrets": False,
        "error_code": code,
    }


def main() -> int:
    load_project_environment(root=ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True, help="Completed AI Exploration session id")
    parser.add_argument("--output", type=Path, help="Optional JSON result path")
    args = parser.parse_args()
    database_url = get_env(DATABASE_URL_ENV, root=ROOT)
    if not database_url:
        payload = _failed(f"{DATABASE_URL_ENV}_MISSING")
    else:
        try:
            engine = create_database_engine(database_url)
            factory = create_session_factory(engine)
            payload = verify_session(factory, args.session_id)
            engine.dispose()
        except Exception as exc:  # keep diagnostics secret-free
            payload = _failed(type(exc).__name__)
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
