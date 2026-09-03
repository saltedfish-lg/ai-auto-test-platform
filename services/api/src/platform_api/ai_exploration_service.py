"""Transactional planning plus fenced, bound-direct AI Browser Loop orchestration."""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from platform_api.ai_exploration_schemas import (
    AIExplorationBrowserAction,
    AIExplorationSessionResource,
    AIExplorationStepResource,
    CancelAIExplorationSessionRequest,
    CreateAIExplorationRequest,
    ExplorationPlan,
    StartAIExplorationSessionRequest,
)
from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticatedIdentity, AuthenticationService
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.model_configuration_service import (
    AI_EXPLORATION,
    ModelConfigurationService,
    ResolvedModelConfiguration,
)
from platform_api.model_gateway import GatewayInvocationResult
from platform_api.models import (
    AccountMappingRevision,
    AICall,
    AIExplorationAudit,
    AIExplorationSession,
    AIExplorationStep,
    AITask,
    CredentialRevision,
    Environment,
    ExecutionAttempt,
    ExecutionBindingSnapshot,
    IdempotencyRecord,
    LoginStrategy,
    OutboxEvent,
    Project,
    ProjectRuntimePolicyRevision,
    ResourceLease,
    Runner,
    TerminalAccessRevision,
    TestAccount,
    TestAccountSecret,
)
from platform_api.secret_store import SecretProtector, SecretStoreError, UnavailableSecretProtector
from platform_api.security import new_ulid, utc_now

AI_TASK_CREATE = "AI_TASK_CREATE"
CREATE_AI_EXPLORATION_SESSION = "create_ai_exploration_session"
START_AI_EXPLORATION_SESSION = "start_ai_exploration_session"
CANCEL_AI_EXPLORATION_SESSION = "cancel_ai_exploration_session"
GET_AI_EXPLORATION_SESSION = "get_ai_exploration_session"
LIST_AI_EXPLORATION_STEPS = "list_ai_exploration_steps"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED"}


@dataclass(frozen=True, slots=True)
class BrowserStoragePreset:
    key: str
    value: str = field(repr=False)
    set_before_login: bool = True


@dataclass(frozen=True, slots=True)
class BrowserLoginMaterial:
    account_identifier: str
    secret_value: str = field(repr=False)
    login_url: str | None = None
    local_storage_presets: tuple[BrowserStoragePreset, ...] = ()
    refresh_after_local_storage: bool = False
    captcha_policy: str = "NONE"
    captcha_request_header_name: str | None = None
    captcha_request_header_value: str | None = field(default=None, repr=False)
    captcha_response_header_name: str | None = None


@dataclass(frozen=True, slots=True)
class BoundBrowserCommand:
    runner_id: str
    execution_attempt_id: str
    execution_binding_snapshot_id: str
    identity_lease_generation: int
    runner_lease_generation: int
    target_url: str
    allowed_origins: tuple[str, ...]
    authentication_redirect_origins: tuple[str, ...]
    action_timeout_seconds: int
    login_material: BrowserLoginMaterial = field(repr=False)


@dataclass(frozen=True, slots=True)
class BrowserObservation:
    browser_session_id: str
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class BrowserActionResult:
    result: dict[str, object]
    observation: BrowserObservation


class BoundRunnerBrowserRuntime(Protocol):
    def start(self, command: BoundBrowserCommand) -> BrowserObservation: ...

    def observe(
        self, command: BoundBrowserCommand, browser_session_id: str
    ) -> BrowserObservation: ...

    def execute(
        self,
        command: BoundBrowserCommand,
        browser_session_id: str,
        action: AIExplorationBrowserAction,
    ) -> BrowserActionResult: ...

    def owns(self, command: BoundBrowserCommand, browser_session_id: str) -> bool: ...

    def close(self, command: BoundBrowserCommand, browser_session_id: str) -> None: ...

    def cancel(
        self, command: BoundBrowserCommand, browser_session_id: str | None
    ) -> None: ...


class UnavailableBoundRunnerBrowserRuntime:
    def start(self, command: BoundBrowserCommand) -> BrowserObservation:
        del command
        raise PlatformError(
            title="Bound Runner unavailable",
            detail="The bound Runner browser command channel is unavailable.",
            status=503,
            code="AI_EXPLORATION_RUNNER_UNAVAILABLE",
        )

    def execute(
        self,
        command: BoundBrowserCommand,
        browser_session_id: str,
        action: AIExplorationBrowserAction,
    ) -> BrowserActionResult:
        del command, browser_session_id, action
        raise RuntimeError("bound Runner browser runtime is unavailable")

    def observe(self, command: BoundBrowserCommand, browser_session_id: str) -> BrowserObservation:
        del command, browser_session_id
        raise RuntimeError("bound Runner browser runtime is unavailable")

    def owns(self, command: BoundBrowserCommand, browser_session_id: str) -> bool:
        del command, browser_session_id
        return False

    def close(self, command: BoundBrowserCommand, browser_session_id: str) -> None:
        del command, browser_session_id

    def cancel(self, command: BoundBrowserCommand, browser_session_id: str | None) -> None:
        del command, browser_session_id
        raise RuntimeError("bound Runner browser runtime is unavailable")


@dataclass(frozen=True, slots=True)
class ExplorationContext:
    project_id: str
    objective: str
    target_url: str
    source_case_id: str | None


class ExplorationContextProvider(Protocol):
    def build(self, request: CreateAIExplorationRequest) -> ExplorationContext: ...


class RequestExplorationContextProvider:
    """Foundation context boundary that can be extended without changing the session."""

    def build(self, request: CreateAIExplorationRequest) -> ExplorationContext:
        return ExplorationContext(
            project_id=request.project_id,
            objective=request.objective,
            target_url=str(request.target_url),
            source_case_id=request.source_case_id,
        )


class AIExplorationService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
        model_configurations: ModelConfigurationService,
        context_provider: ExplorationContextProvider | None = None,
        browser_runtime: BoundRunnerBrowserRuntime | None = None,
        secret_protector: SecretProtector | None = None,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency
        self._model_configurations = model_configurations
        self._context_provider = context_provider or RequestExplorationContextProvider()
        self._browser_runtime = browser_runtime or UnavailableBoundRunnerBrowserRuntime()
        self._secret_protector = secret_protector or UnavailableSecretProtector()

    def create(
        self,
        token: str,
        body: CreateAIExplorationRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> AIExplorationSessionResource:
        context = self._context_provider.build(body)
        try:
            session_id, storage_key, resolved, replayed = self._create_planning_session(
                token,
                context,
                body,
                idempotency_key,
                audit_context,
            )
        except PlatformError as error:
            if error.code == "MODEL_CAPABILITY_DEFAULT_UNAVAILABLE":
                raise PlatformError(
                    title="AI exploration model not configured",
                    detail="No ACTIVE default model is configured for AI exploration.",
                    status=503,
                    code="AI_EXPLORATION_MODEL_NOT_CONFIGURED",
                ) from error
            raise
        if replayed is not None:
            return replayed
        if resolved is None:
            raise RuntimeError("new AI exploration session has no resolved model")

        result: GatewayInvocationResult | None = None
        try:
            result = self._model_configurations.invoke(
                resolved,
                self._planning_messages(context),
            )
            if result.status != "SUCCESS":
                code = (
                    "AI_EXPLORATION_MODEL_RESPONSE_INVALID"
                    if result.status == "INVALID_RESPONSE"
                    else "AI_EXPLORATION_MODEL_UNAVAILABLE"
                )
                return self._fail(
                    session_id,
                    storage_key,
                    audit_context,
                    code,
                    self._failure_message(code),
                    result.provider_request_id,
                )
            try:
                plan = ExplorationPlan.model_validate_json(result.content or "")
            except ValidationError:
                return self._fail(
                    session_id,
                    storage_key,
                    audit_context,
                    "AI_EXPLORATION_MODEL_RESPONSE_INVALID",
                    self._failure_message("AI_EXPLORATION_MODEL_RESPONSE_INVALID"),
                    result.provider_request_id,
                )
            return self._ready(
                session_id,
                storage_key,
                audit_context,
                plan,
                result.provider_request_id,
            )
        except PlatformError:
            return self._fail(
                session_id,
                storage_key,
                audit_context,
                "AI_EXPLORATION_MODEL_UNAVAILABLE",
                self._failure_message("AI_EXPLORATION_MODEL_UNAVAILABLE"),
                result.provider_request_id if result is not None else None,
            )
        except Exception:
            return self._fail(
                session_id,
                storage_key,
                audit_context,
                "AI_EXPLORATION_PLANNING_FAILED",
                self._failure_message("AI_EXPLORATION_PLANNING_FAILED"),
                result.provider_request_id if result is not None else None,
            )

    def get(
        self, token: str, session_id: str, audit_context: AuditContext
    ) -> AIExplorationSessionResource:
        with self._factory.begin() as db:
            row = db.get(AIExplorationSession, session_id)
            if row is None:
                raise self._not_found()
            self._authorize(db, token, GET_AI_EXPLORATION_SESSION, row.project_id, audit_context)
            return self._resource(row)

    def list_steps(
        self, token: str, session_id: str, audit_context: AuditContext
    ) -> list[AIExplorationStepResource]:
        with self._factory.begin() as db:
            row = db.get(AIExplorationSession, session_id)
            if row is None:
                raise self._not_found()
            self._authorize(db, token, LIST_AI_EXPLORATION_STEPS, row.project_id, audit_context)
            steps = list(
                db.scalars(
                    select(AIExplorationStep)
                    .where(AIExplorationStep.session_id == session_id)
                    .order_by(AIExplorationStep.sequence)
                )
            )
            return [self._step_resource(step) for step in steps]

    def start(
        self,
        token: str,
        session_id: str,
        body: StartAIExplorationSessionRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> tuple[AIExplorationSessionResource, bool]:
        """Atomically bind exactly one Attempt and fence the session into RUNNING."""
        with self._factory.begin() as db:
            row = db.scalar(
                select(AIExplorationSession)
                .where(AIExplorationSession.session_id == session_id)
                .with_for_update()
            )
            if row is None:
                raise self._not_found()
            actor, _ = self._authorize(
                db, token, START_AI_EXPLORATION_SESSION, row.project_id, audit_context
            )
            record, replayed = self._idempotency.claim(
                db,
                actor.user.user_id,
                START_AI_EXPLORATION_SESSION,
                idempotency_key,
                json.dumps(
                    {"session_id": session_id, **body.model_dump(mode="json")},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
            if replayed:
                return _stored_session(record.response_json), False
            if row.lifecycle_status != "READY":
                raise self._conflict("Only a READY AI exploration session can be started.")
            if row.row_version != body.expected_row_version:
                raise self._concurrency_conflict()
            attempt, binding, identity_lease, runner_lease, policy, terminal = (
                self._validate_start_preflight(db, row, body.execution_attempt_id)
            )
            frozen_model = self._frozen_model_snapshot(db, row)
            self._model_configurations.resolve_snapshot_in_transaction(
                db,
                row.resolved_model_config_id,
                row.resolved_provider_code,
                row.resolved_model_name,
                int(cast(int, frozen_model["request_timeout_seconds"])),
                str(frozen_model["display_name"]),
            )
            now = _server_now(db)
            row.execution_attempt_id = attempt.execution_attempt_id
            row.execution_binding_snapshot_id = binding.execution_binding_snapshot_id
            row.browser_session_id = None
            row.current_observation_id = None
            row.current_step_sequence = 0
            row.max_steps = policy.max_steps
            row.total_timeout_seconds = policy.total_exploration_timeout_seconds
            row.model_transient_retry_per_step = policy.model_transient_retry_per_step
            row.started_at = now
            row.total_deadline_at = now + timedelta(
                seconds=policy.total_exploration_timeout_seconds
            )
            row.terminal_at = None
            row.cancel_requested_at = None
            row.failure_code = None
            row.failure_message = None
            row.lifecycle_status = "RUNNING"
            row.row_version += 1
            row.updated_at = now
            binding.status = "IN_USE"
            binding.row_version += 1
            binding.updated_at = now
            attempt.execution_status = "RUNNING"
            attempt.lifecycle_status = "RUNNING"
            attempt.row_version += 1
            task = db.get(AITask, row.ai_task_id)
            if task is None:
                raise RuntimeError("AI exploration task disappeared")
            task.status = "RUNNING"
            task.row_version += 1
            task.updated_at = now
            task.updated_by = actor.user.user_id
            self._append_audit(
                db,
                row,
                audit_context,
                action="BROWSER_STARTED",
                previous_status="READY",
                new_status="RUNNING",
                result_code="SUCCESS",
                operation_id=START_AI_EXPLORATION_SESSION,
            )
            self._append_event(db, row, "ai_exploration.browser_started", audit_context, now)
            resource = self._resource(row)
            self._idempotency.complete(
                record, 202, {"ai_exploration": resource.model_dump(mode="json")}
            )
            # Force access while the locked rows are known current; the Runner command is
            # reconstructed again by run() and never trusts caller-supplied runtime inputs.
            _ = identity_lease, runner_lease, terminal
            return resource, True

    def run(self, session_id: str, audit_context: AuditContext) -> None:
        """Execute one Browser Loop after Start has committed; safe for a background worker."""
        command: BoundBrowserCommand | None = None
        browser_session_id: str | None = None
        try:
            command, resolved = self._load_runtime_snapshot(session_id)
            observation = self._safe_observation(self._browser_runtime.start(command), command)
            browser_session_id = observation.browser_session_id
            observation_id, state_version = self._accept_initial_observation(
                session_id, command, observation
            )
            while True:
                prepared = self._prepare_step(
                    session_id,
                    command,
                    observation_id,
                    observation.data,
                    state_version,
                )
                if prepared is None:
                    return
                step_id, model_call_identity, expected_version, plan, retry_limit = prepared
                result = self._decide_with_retry(
                    resolved,
                    plan,
                    observation.data,
                    retry_limit,
                )
                if result is None:
                    self._fail_running(
                        session_id,
                        command,
                        audit_context,
                        "AI_EXPLORATION_MODEL_CALL_FAILED",
                        step_id=step_id,
                    )
                    return
                try:
                    action = AIExplorationBrowserAction.model_validate_json(result.content or "")
                except ValidationError:
                    self._fail_running(
                        session_id,
                        command,
                        audit_context,
                        "AI_EXPLORATION_MODEL_RESPONSE_INVALID",
                        step_id=step_id,
                    )
                    return
                accepted_version = self._accept_action(
                    session_id,
                    command,
                    step_id,
                    observation_id,
                    expected_version,
                    action,
                    result.provider_request_id or model_call_identity,
                )
                if accepted_version is None:
                    return
                if action.type == "goal_completed":
                    if not self._browser_runtime.owns(command, browser_session_id):
                        raise self._fencing_conflict()
                    completed, state_version = self._complete_running(
                        session_id,
                        command,
                        step_id,
                        observation_id,
                        accepted_version,
                        audit_context,
                    )
                    if completed:
                        return
                    observation = self._safe_observation(
                        self._browser_runtime.observe(command, browser_session_id), command
                    )
                    observation_id, state_version = self._accept_reobservation(
                        session_id,
                        command,
                        observation,
                        state_version,
                    )
                    continue
                try:
                    action_result = self._browser_runtime.execute(
                        command, browser_session_id, action
                    )
                    observation = self._safe_observation(action_result.observation, command)
                    observation_id, state_version = self._finish_step(
                        session_id,
                        command,
                        step_id,
                        accepted_version,
                        action_result.result,
                        observation,
                    )
                except PlatformError as error:
                    if error.code in {"AI_EXPLORATION_TIMEOUT", "AI_EXPLORATION_LEASE_LOST"}:
                        raise
                    observation = self._safe_observation(
                        self._browser_runtime.observe(command, browser_session_id), command
                    )
                    observation_id, state_version = self._finish_failed_action(
                        session_id,
                        command,
                        step_id,
                        accepted_version,
                        observation,
                        type(error).__name__,
                    )
                except Exception as error:
                    observation = self._safe_observation(
                        self._browser_runtime.observe(command, browser_session_id), command
                    )
                    observation_id, state_version = self._finish_failed_action(
                        session_id,
                        command,
                        step_id,
                        accepted_version,
                        observation,
                        type(error).__name__,
                    )
        except PlatformError as error:
            if command is not None:
                self._fail_running(
                    session_id,
                    command,
                    audit_context,
                    error.code
                    if error.code.startswith("AI_EXPLORATION_")
                    else "AI_EXPLORATION_RUNNER_UNAVAILABLE",
                )
            else:
                self._fail_before_runtime(
                    session_id,
                    audit_context,
                    error.code
                    if error.code
                    in {
                        "AI_EXPLORATION_LEASE_LOST",
                        "AI_EXPLORATION_RUNNER_UNAVAILABLE",
                    }
                    else "AI_EXPLORATION_RUNNER_UNAVAILABLE",
                )
        except Exception:
            if command is not None:
                self._fail_running(
                    session_id,
                    command,
                    audit_context,
                    "AI_EXPLORATION_RUNNER_UNAVAILABLE",
                )
            else:
                self._fail_before_runtime(
                    session_id,
                    audit_context,
                    "AI_EXPLORATION_RUNNER_UNAVAILABLE",
                )
        finally:
            if command is not None and browser_session_id is not None:
                with suppress(Exception):
                    self._browser_runtime.close(command, browser_session_id)

    def cancel(
        self,
        token: str,
        session_id: str,
        body: CancelAIExplorationSessionRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> tuple[AIExplorationSessionResource, BoundBrowserCommand | None, str | None]:
        """Fence terminal state first; the caller closes the Runner after commit."""
        with self._factory.begin() as db:
            row = db.scalar(
                select(AIExplorationSession)
                .where(AIExplorationSession.session_id == session_id)
                .with_for_update()
            )
            if row is None:
                raise self._not_found()
            actor, _ = self._authorize(
                db, token, CANCEL_AI_EXPLORATION_SESSION, row.project_id, audit_context
            )
            record, replayed = self._idempotency.claim(
                db,
                actor.user.user_id,
                CANCEL_AI_EXPLORATION_SESSION,
                idempotency_key,
                json.dumps(
                    {"session_id": session_id, **body.model_dump(mode="json")},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
            if replayed:
                resource = _stored_session(record.response_json)
                if row.lifecycle_status == "CANCELLED" and self._execution_is_active(db, row):
                    return resource, self._command_from_locked_rows(db, row), row.browser_session_id
                return resource, None, None
            if row.lifecycle_status in TERMINAL_STATUSES:
                if row.lifecycle_status != "CANCELLED":
                    raise self._conflict("A completed exploration cannot be cancelled.")
                resource = self._resource(row)
                self._idempotency.complete(
                    record, 200, {"ai_exploration": resource.model_dump(mode="json")}
                )
                return resource, None, None
            if row.lifecycle_status != "RUNNING":
                raise self._conflict("Only a RUNNING exploration can be cancelled.")
            if row.row_version != body.expected_row_version:
                raise self._concurrency_conflict()
            command = self._command_from_locked_rows(db, row)
            browser_session_id = row.browser_session_id
            now = _server_now(db)
            row.lifecycle_status = "CANCELLED"
            row.cancel_requested_at = now
            row.terminal_at = now
            row.updated_at = now
            row.row_version += 1
            db.execute(
                update(AIExplorationStep)
                .where(
                    AIExplorationStep.session_id == session_id,
                    AIExplorationStep.status.in_(("DECIDING", "EXECUTING", "COMPLETION_PROPOSED")),
                )
                .values(status="DISCARDED", completed_at=now, failure_code="CANCELLED")
            )
            resource = self._resource(row)
            self._idempotency.complete(
                record, 200, {"ai_exploration": resource.model_dump(mode="json")}
            )
            return resource, command, browser_session_id

    def close_cancelled_runtime(
        self, command: BoundBrowserCommand | None, browser_session_id: str | None
    ) -> None:
        if command is not None:
            self._browser_runtime.cancel(command, browser_session_id)

    def finalize_cancel(
        self,
        session_id: str,
        command: BoundBrowserCommand | None,
        audit_context: AuditContext,
    ) -> None:
        """Release ownership and publish cancellation only after Browser termination."""
        if command is None:
            return
        with self._factory.begin() as db:
            row = db.scalar(
                select(AIExplorationSession)
                .where(AIExplorationSession.session_id == session_id)
                .with_for_update()
            )
            if row is None or row.lifecycle_status != "CANCELLED":
                return
            if not self._execution_is_active(db, row):
                return
            current = self._command_from_locked_rows(db, row)
            if current != command:
                raise self._fencing_conflict()
            now = _server_now(db)
            self._release_execution(db, row, "CANCELLED", now)
            self._append_audit(
                db,
                row,
                audit_context,
                action="CANCEL_REQUESTED",
                previous_status="RUNNING",
                new_status="CANCELLED",
                result_code="SUCCESS",
                operation_id=CANCEL_AI_EXPLORATION_SESSION,
            )
            self._append_audit(
                db,
                row,
                audit_context,
                action="BROWSER_CANCELLED",
                previous_status="RUNNING",
                new_status="CANCELLED",
                result_code="SUCCESS",
                operation_id=CANCEL_AI_EXPLORATION_SESSION,
            )
            self._append_event(db, row, "ai_exploration.cancelled", audit_context, now)

    def _validate_start_preflight(
        self, db: Session, row: AIExplorationSession, execution_attempt_id: str
    ) -> tuple[
        ExecutionAttempt,
        ExecutionBindingSnapshot,
        ResourceLease,
        ResourceLease,
        ProjectRuntimePolicyRevision,
        TerminalAccessRevision,
    ]:
        attempt_hint = db.scalar(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.execution_attempt_id == execution_attempt_id)
        )
        if (
            attempt_hint is None
            or attempt_hint.project_id != row.project_id
            or attempt_hint.run_task_id is None
            or attempt_hint.execution_binding_snapshot_id is None
        ):
            raise self._preflight_failed("ExecutionAttempt is not startable by this Session.")
        binding = db.scalar(
            select(ExecutionBindingSnapshot)
            .where(
                ExecutionBindingSnapshot.execution_binding_snapshot_id
                == attempt_hint.execution_binding_snapshot_id
            )
            .with_for_update()
        )
        if binding is None:
            raise self._preflight_failed("ExecutionBindingSnapshot is not a READY owner match.")
        identity = self._locked_lease(db, binding.identity_lease_id)
        runner_lease = self._locked_lease(db, binding.runner_lease_id)
        attempt = db.scalar(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.execution_attempt_id == execution_attempt_id)
            .with_for_update()
        )
        if (
            attempt is None
            or attempt.project_id != row.project_id
            or attempt.run_task_id is None
            or attempt.execution_binding_snapshot_id != binding.execution_binding_snapshot_id
            or attempt.execution_status not in {"PRESTART_BLOCKED", "READY"}
            or attempt.lifecycle_status not in {"CREATED", "PREPARING"}
            or binding.execution_attempt_id != attempt.execution_attempt_id
            or binding.project_id != row.project_id
            or binding.runner_id != attempt.runner_id
            or binding.owner_execution_identity != attempt.run_task_id
            or binding.status != "READY"
        ):
            raise self._preflight_failed("ExecutionBindingSnapshot is not a READY owner match.")
        now = _server_now(db)
        if (
            identity.status != "ACTIVE"
            or runner_lease.status != "ACTIVE"
            or identity.expires_at <= now
            or runner_lease.expires_at <= now
            or identity.fencing_generation != binding.identity_lease_generation
            or runner_lease.fencing_generation != binding.runner_lease_generation
            or identity.owner_type != "FORMAL_ROOT_EXECUTION_TASK"
            or identity.owner_id != attempt.run_task_id
            or runner_lease.owner_type != "EXECUTION_ATTEMPT"
            or runner_lease.owner_id != attempt.execution_attempt_id
        ):
            raise self._preflight_failed("Execution leases or fencing generations are stale.")
        policy = db.get(ProjectRuntimePolicyRevision, binding.runtime_policy_revision_id)
        if (
            policy is None
            or policy.project_id != row.project_id
            or policy.lifecycle_status != "PUBLISHED"
            or policy.max_steps <= 0
            or policy.total_exploration_timeout_seconds <= 0
            or policy.model_transient_retry_per_step < 0
        ):
            raise self._preflight_failed("The frozen RuntimePolicy is not consumable.")
        terminal = db.get(TerminalAccessRevision, binding.terminal_access_revision_id)
        strategy = db.get(LoginStrategy, binding.login_strategy_id)
        account = db.get(TestAccount, binding.test_account_id)
        credential = db.get(CredentialRevision, binding.credential_revision_id)
        mapping = db.get(AccountMappingRevision, binding.account_mapping_revision_id)
        environment = db.get(Environment, binding.environment_id)
        if (
            environment is None
            or environment.project_id != row.project_id
            or environment.lifecycle_status != "ACTIVE"
            or terminal is None
            or terminal.lifecycle_status != "PUBLISHED"
            or terminal.project_id != row.project_id
            or strategy is None
            or strategy.lifecycle_status != "ACTIVE"
            or strategy.row_version != binding.login_strategy_row_version
            or account is None
            or account.lifecycle_status != "ACTIVE"
            or credential is None
            or credential.lifecycle_status != "PUBLISHED"
            or mapping is None
            or mapping.lifecycle_status != "PUBLISHED"
        ):
            raise self._preflight_failed("The frozen terminal/login/account facts are stale.")
        runner = db.get(Runner, binding.runner_id)
        if (
            runner is None
            or runner.project_id != row.project_id
            or runner.lifecycle_status != "ACTIVE"
            or runner.registration_status != "REGISTERED"
            or runner.connection_status != "ONLINE"
            or runner.health_status != "HEALTHY"
            or runner.enable_status != "ENABLED"
            or runner.project_binding_status != "BOUND"
            or runner.version_compatibility != "COMPATIBLE"
            or not binding.runner_capability_snapshot
        ):
            raise self._preflight_failed("The bound Runner is unavailable or incompatible.")
        allowed = {
            origin
            for raw in [*policy.allowed_origins, *policy.authentication_redirect_origins]
            if (origin := self._origin(raw)) is not None
        }
        if self._origin(terminal.entry_url) not in allowed:
            raise self._preflight_failed("Terminal entry origin is denied by RuntimePolicy.")
        return attempt, binding, identity, runner_lease, policy, terminal

    def _load_runtime_snapshot(
        self, session_id: str
    ) -> tuple[BoundBrowserCommand, ResolvedModelConfiguration]:
        with self._factory.begin() as db:
            row = db.scalar(
                select(AIExplorationSession)
                .where(AIExplorationSession.session_id == session_id)
                .with_for_update()
            )
            if row is None or row.lifecycle_status != "RUNNING":
                raise self._conflict("The exploration is no longer running.")
            command = self._command_from_locked_rows(db, row)
            frozen_model = self._frozen_model_snapshot(db, row)
            resolved = self._model_configurations.resolve_snapshot_in_transaction(
                db,
                row.resolved_model_config_id,
                row.resolved_provider_code,
                row.resolved_model_name,
                int(cast(int, frozen_model["request_timeout_seconds"])),
                str(frozen_model["display_name"]),
            )
            return command, resolved

    def _command_from_locked_rows(
        self, db: Session, row: AIExplorationSession
    ) -> BoundBrowserCommand:
        if row.execution_attempt_id is None or row.execution_binding_snapshot_id is None:
            raise self._fencing_conflict()
        binding = db.scalar(
            select(ExecutionBindingSnapshot)
            .where(
                ExecutionBindingSnapshot.execution_binding_snapshot_id
                == row.execution_binding_snapshot_id
            )
            .with_for_update()
        )
        if binding is None:
            raise self._fencing_conflict()
        identity = self._locked_lease(db, binding.identity_lease_id)
        runner_lease = self._locked_lease(db, binding.runner_lease_id)
        attempt = db.scalar(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.execution_attempt_id == row.execution_attempt_id)
            .with_for_update()
        )
        if (
            attempt is None
            or binding.execution_attempt_id != attempt.execution_attempt_id
            or binding.runner_id != attempt.runner_id
            or binding.owner_execution_identity != attempt.run_task_id
            or binding.status != "IN_USE"
        ):
            raise self._fencing_conflict()
        now = _server_now(db)
        if (
            identity.status != "ACTIVE"
            or runner_lease.status != "ACTIVE"
            or identity.expires_at <= now
            or runner_lease.expires_at <= now
            or identity.fencing_generation != binding.identity_lease_generation
            or runner_lease.fencing_generation != binding.runner_lease_generation
        ):
            raise self._fencing_conflict()
        policy = db.get(ProjectRuntimePolicyRevision, binding.runtime_policy_revision_id)
        terminal = db.get(TerminalAccessRevision, binding.terminal_access_revision_id)
        strategy = db.get(LoginStrategy, binding.login_strategy_id)
        account = db.get(TestAccount, binding.test_account_id)
        secret = db.get(TestAccountSecret, binding.credential_revision_id)
        if (
            policy is None
            or terminal is None
            or terminal.lifecycle_status != "PUBLISHED"
            or strategy is None
            or strategy.lifecycle_status != "ACTIVE"
            or strategy.row_version != binding.login_strategy_row_version
            or account is None
            or account.lifecycle_status != "ACTIVE"
            or secret is None
        ):
            raise self._fencing_conflict()
        try:
            secret_value = self._secret_protector.decrypt_scoped(
                "test-account-credential",
                binding.credential_revision_id,
                secret.encrypted_secret,
                secret.key_id,
            )
        except SecretStoreError as error:
            raise PlatformError(
                title="Bound credential unavailable",
                detail=(
                    "The frozen CredentialRevision could not be resolved in the trusted runtime."
                ),
                status=503,
                code="AI_EXPLORATION_RUNNER_UNAVAILABLE",
            ) from error
        allowed = tuple(
            dict.fromkeys(
                origin
                for raw in policy.allowed_origins
                if (origin := self._origin(raw)) is not None
            )
        )
        redirects = tuple(
            dict.fromkeys(
                origin
                for raw in policy.authentication_redirect_origins
                if (origin := self._origin(raw)) is not None
            )
        )
        if self._origin(terminal.entry_url) not in {*allowed, *redirects}:
            raise self._fencing_conflict()
        return BoundBrowserCommand(
            runner_id=binding.runner_id,
            execution_attempt_id=attempt.execution_attempt_id,
            execution_binding_snapshot_id=binding.execution_binding_snapshot_id,
            identity_lease_generation=binding.identity_lease_generation,
            runner_lease_generation=binding.runner_lease_generation,
            target_url=terminal.entry_url,
            allowed_origins=allowed,
            authentication_redirect_origins=redirects,
            action_timeout_seconds=policy.timeout_seconds,
            login_material=BrowserLoginMaterial(
                account_identifier=account.account_identifier,
                secret_value=secret_value,
                login_url=terminal.login_url,
                local_storage_presets=tuple(
                    BrowserStoragePreset(
                        key=str(item["key"]),
                        value=str(item["value"]),
                        set_before_login=bool(item.get("set_before_login", True)),
                    )
                    for item in strategy.local_storage_presets
                    if isinstance(item, dict) and "key" in item and "value" in item
                ),
                refresh_after_local_storage=strategy.refresh_after_local_storage,
                captcha_policy=strategy.captcha_policy,
                captcha_request_header_name=strategy.captcha_request_header_name,
                captcha_request_header_value=strategy.captcha_request_header_value,
                captcha_response_header_name=strategy.captcha_response_header_name,
            ),
        )

    def _accept_initial_observation(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        observation: BrowserObservation,
    ) -> tuple[str, int]:
        self._sanitize_observation(observation.data, command)
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            if row.total_deadline_at is None or row.total_deadline_at <= _server_now(db):
                raise self._timeout_error()
            if row.browser_session_id is not None:
                raise self._fencing_conflict()
            observation_id = new_ulid()
            row.browser_session_id = observation.browser_session_id[:191]
            row.current_observation_id = observation_id
            row.row_version += 1
            row.updated_at = utc_now()
            # The observation is persisted with the first Step; Session stores only identity.
            return observation_id, row.row_version

    def _accept_reobservation(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        observation: BrowserObservation,
        expected_version: int,
    ) -> tuple[str, int]:
        document = self._sanitize_observation(observation.data, command)
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            if (
                row.row_version != expected_version
                or row.browser_session_id != observation.browser_session_id
            ):
                raise self._fencing_conflict()
            if row.total_deadline_at is None or row.total_deadline_at <= _server_now(db):
                raise self._timeout_error()
            observation_id = new_ulid()
            row.current_observation_id = observation_id
            row.row_version += 1
            row.updated_at = _server_now(db)
            _ = document
            return observation_id, row.row_version

    def _prepare_step(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        observation_id: str,
        observation: dict[str, object],
        state_version: int,
    ) -> tuple[str, str, int, dict[str, object], int] | None:
        document = self._sanitize_observation(observation, command)
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            if row.row_version != state_version or row.current_observation_id != observation_id:
                return None
            now = _server_now(db)
            if row.total_deadline_at is None or row.total_deadline_at <= now:
                raise PlatformError(
                    title="AI exploration timed out",
                    detail="The frozen total exploration deadline has elapsed.",
                    status=409,
                    code="AI_EXPLORATION_TIMEOUT",
                )
            if row.max_steps is None or row.current_step_sequence >= row.max_steps:
                raise PlatformError(
                    title="AI exploration step limit reached",
                    detail="The frozen maximum Browser Loop step count was reached.",
                    status=409,
                    code="AI_EXPLORATION_MAX_STEPS",
                )
            sequence = row.current_step_sequence + 1
            step_id = new_ulid()
            ai_call_id = new_ulid()
            db.add(
                AICall(
                    ai_call_id=ai_call_id,
                    project_id=row.project_id,
                    ai_task_id=row.ai_task_id,
                    prompt_revision_id=None,
                    lifecycle_status="RUNNING",
                    display_name=f"AI exploration browser decision {sequence}",
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=row.created_by,
                    updated_by=row.created_by,
                    extension_json=None,
                )
            )
            db.add(
                AIExplorationStep(
                    ai_exploration_step_id=step_id,
                    session_id=row.session_id,
                    execution_attempt_id=command.execution_attempt_id,
                    ai_call_id=ai_call_id,
                    sequence=sequence,
                    model_call_identity=ai_call_id,
                    observation_identity=observation_id,
                    action_identity=new_ulid(),
                    status="DECIDING",
                    observation_json=document,
                    action_json=None,
                    action_result_json=None,
                    sanitized_reason=None,
                    failure_code=None,
                    state_version=row.row_version,
                    identity_lease_generation=command.identity_lease_generation,
                    runner_lease_generation=command.runner_lease_generation,
                    started_at=now,
                    completed_at=None,
                    created_at=now,
                )
            )
            row.current_step_sequence = sequence
            row.row_version += 1
            row.updated_at = now
            return (
                step_id,
                ai_call_id,
                row.row_version,
                dict(row.plan or {}),
                int(row.model_transient_retry_per_step or 0),
            )

    def _decide_with_retry(
        self,
        resolved: ResolvedModelConfiguration,
        plan: dict[str, object],
        observation: dict[str, object],
        retry_limit: int,
    ) -> GatewayInvocationResult | None:
        messages = self._browser_messages(plan, observation)
        for attempt in range(retry_limit + 1):
            try:
                result = self._model_configurations.invoke(resolved, messages)
            except PlatformError:
                result = None
            if result is not None and result.status == "SUCCESS":
                return result
            transient = result is None or result.status in {
                "TIMEOUT",
                "RATE_LIMITED",
                "PROVIDER_ERROR",
            }
            if not transient or attempt >= retry_limit:
                return None
        return None

    def _accept_action(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        step_id: str,
        observation_id: str,
        expected_version: int,
        action: AIExplorationBrowserAction,
        provider_request_id: str,
    ) -> int | None:
        if action.type == "Navigate":
            self._require_allowed_url(str(action.url), command)
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            if row.total_deadline_at is None or row.total_deadline_at <= _server_now(db):
                raise self._timeout_error()
            if row.row_version != expected_version or row.current_observation_id != observation_id:
                self._discard_step(db, step_id, "STALE_PROVIDER_RESPONSE")
                return None
            step = db.scalar(
                select(AIExplorationStep)
                .where(AIExplorationStep.ai_exploration_step_id == step_id)
                .with_for_update()
            )
            if step is None or step.status != "DECIDING":
                return None
            now = _server_now(db)
            step.action_json = action.model_dump(mode="json")
            step.sanitized_reason = (action.reason or "")[:1000] or None
            step.status = "COMPLETION_PROPOSED" if action.type == "goal_completed" else "EXECUTING"
            step.completed_at = now if action.type == "goal_completed" else None
            call = db.get(AICall, step.ai_call_id)
            if call is not None:
                call.lifecycle_status = "SUCCEEDED"
                call.row_version += 1
                call.updated_at = now
                call.extension_json = {"provider_request_id": provider_request_id[:191]}
            row.row_version += 1
            row.updated_at = now
            return row.row_version

    def _finish_step(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        step_id: str,
        expected_version: int,
        action_result: dict[str, object],
        observation: BrowserObservation,
    ) -> tuple[str, int]:
        self._sanitize_observation(observation.data, command)
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            if row.total_deadline_at is None or row.total_deadline_at <= _server_now(db):
                raise self._timeout_error()
            if (
                row.row_version != expected_version
                or row.browser_session_id != observation.browser_session_id
            ):
                self._discard_step(db, step_id, "STALE_BROWSER_RESPONSE")
                raise self._fencing_conflict()
            step = db.scalar(
                select(AIExplorationStep)
                .where(AIExplorationStep.ai_exploration_step_id == step_id)
                .with_for_update()
            )
            if step is None or step.status != "EXECUTING":
                raise self._fencing_conflict()
            now = _server_now(db)
            observation_id = new_ulid()
            step.status = "SUCCEEDED"
            step.action_result_json = cast(
                dict[str, Any], self._sanitize_document(action_result, command=command)
            )
            step.completed_at = now
            row.current_observation_id = observation_id
            row.row_version += 1
            row.updated_at = now
            return observation_id, row.row_version

    def _finish_failed_action(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        step_id: str,
        expected_version: int,
        observation: BrowserObservation,
        error_type: str,
    ) -> tuple[str, int]:
        self._sanitize_observation(observation.data, command)
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            if row.total_deadline_at is None or row.total_deadline_at <= _server_now(db):
                raise self._timeout_error()
            if (
                row.row_version != expected_version
                or row.browser_session_id != observation.browser_session_id
            ):
                self._discard_step(db, step_id, "STALE_BROWSER_RESPONSE")
                raise self._fencing_conflict()
            step = db.scalar(
                select(AIExplorationStep)
                .where(AIExplorationStep.ai_exploration_step_id == step_id)
                .with_for_update()
            )
            if step is None or step.status != "EXECUTING":
                raise self._fencing_conflict()
            now = _server_now(db)
            observation_id = new_ulid()
            step.status = "FAILED"
            step.failure_code = "AI_EXPLORATION_ACTION_FAILED"
            step.action_result_json = {
                "status": "FAILED",
                "error_type": "".join(c for c in error_type if c.isalnum() or c == "_")[:64],
                "reobserved": True,
            }
            step.completed_at = now
            row.current_observation_id = observation_id
            row.row_version += 1
            row.updated_at = now
            return observation_id, row.row_version

    def _complete_running(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        step_id: str,
        observation_id: str,
        expected_version: int,
        audit_context: AuditContext,
    ) -> tuple[bool, int]:
        with self._factory.begin() as db:
            row = self._locked_running(db, session_id, command)
            now = _server_now(db)
            if row.total_deadline_at is None or row.total_deadline_at <= now:
                raise self._timeout_error()
            if (
                row.row_version != expected_version
                or row.current_observation_id != observation_id
                or not row.plan
                or row.browser_session_id is None
            ):
                self._discard_step(db, step_id, "STALE_COMPLETION_PROPOSAL")
                return False, row.row_version
            step = db.scalar(
                select(AIExplorationStep)
                .where(AIExplorationStep.ai_exploration_step_id == step_id)
                .with_for_update()
            )
            if (
                step is None
                or step.status != "COMPLETION_PROPOSED"
                or step.session_id != row.session_id
                or step.execution_attempt_id != command.execution_attempt_id
                or step.observation_identity != observation_id
                or step.identity_lease_generation != command.identity_lease_generation
                or step.runner_lease_generation != command.runner_lease_generation
            ):
                return False, row.row_version
            pending = db.scalar(
                select(func.count())
                .select_from(AIExplorationStep)
                .where(
                    AIExplorationStep.session_id == session_id,
                    AIExplorationStep.ai_exploration_step_id != step_id,
                    AIExplorationStep.status.in_(("DECIDING", "EXECUTING", "COMPLETION_PROPOSED")),
                )
            )
            if pending:
                self._discard_step(db, step_id, "PENDING_ACTION_EXISTS")
                return False, row.row_version
            grounded = self._completion_grounded(row, step)
            if not grounded:
                step.status = "FAILED"
                step.failure_code = "COMPLETION_EVIDENCE_INSUFFICIENT"
                step.action_result_json = {"status": "COMPLETION_REJECTED"}
                step.completed_at = now
                row.row_version += 1
                row.updated_at = step.completed_at
                return False, row.row_version
            step.status = "COMPLETION_PROPOSED"
            step.action_result_json = {"status": "COMPLETION_ACCEPTED"}
            step.completed_at = now
            previous = row.lifecycle_status
            row.lifecycle_status = "SUCCEEDED"
            row.terminal_at = now
            row.updated_at = now
            row.row_version += 1
            self._release_execution(db, row, "SUCCEEDED", now)
            self._append_audit(
                db,
                row,
                audit_context,
                action="BROWSER_SUCCEEDED",
                previous_status=previous,
                new_status="SUCCEEDED",
                result_code="SUCCESS",
                operation_id=START_AI_EXPLORATION_SESSION,
            )
            self._append_event(db, row, "ai_exploration.succeeded", audit_context, now)
            return True, row.row_version

    def _fail_running(
        self,
        session_id: str,
        command: BoundBrowserCommand,
        audit_context: AuditContext,
        code: str,
        *,
        step_id: str | None = None,
    ) -> None:
        with self._factory.begin() as db:
            row = db.scalar(
                select(AIExplorationSession)
                .where(AIExplorationSession.session_id == session_id)
                .with_for_update()
            )
            if row is None or row.lifecycle_status != "RUNNING":
                return
            if (
                row.execution_attempt_id != command.execution_attempt_id
                or row.execution_binding_snapshot_id != command.execution_binding_snapshot_id
            ):
                return
            now = _server_now(db)
            previous = row.lifecycle_status
            row.lifecycle_status = "FAILED"
            row.failure_code = code
            row.failure_message = self._failure_message(code)
            row.terminal_at = now
            row.updated_at = now
            row.row_version += 1
            if step_id is not None:
                step = db.get(AIExplorationStep, step_id)
                if step is not None and step.status in {"DECIDING", "EXECUTING"}:
                    step.status = "FAILED"
                    step.failure_code = code
                    step.completed_at = now
                    call = db.get(AICall, step.ai_call_id)
                    if call is not None:
                        call.lifecycle_status = "FAILED"
                        call.row_version += 1
                        call.updated_at = now
            self._release_execution(db, row, "FAILED", now)
            action = "LEASE_LOST" if code == "AI_EXPLORATION_LEASE_LOST" else "BROWSER_FAILED"
            self._append_audit(
                db,
                row,
                audit_context,
                action=action,
                previous_status=previous,
                new_status="FAILED",
                result_code=code,
                operation_id=START_AI_EXPLORATION_SESSION,
            )
            self._append_event(db, row, "ai_exploration.failed", audit_context, now)

    def _fail_before_runtime(
        self,
        session_id: str,
        audit_context: AuditContext,
        code: str,
    ) -> None:
        """Close a RUNNING Session when frozen command resolution fails before dispatch."""

        with self._factory.begin() as db:
            row = db.scalar(
                select(AIExplorationSession)
                .where(AIExplorationSession.session_id == session_id)
                .with_for_update()
            )
            if row is None or row.lifecycle_status != "RUNNING":
                return
            now = utc_now()
            row.lifecycle_status = "FAILED"
            row.failure_code = code
            row.failure_message = self._failure_message(code)
            row.terminal_at = now
            row.updated_at = now
            row.row_version += 1
            self._release_execution(db, row, "FAILED", now)
            self._append_audit(
                db,
                row,
                audit_context,
                action=("LEASE_LOST" if code == "AI_EXPLORATION_LEASE_LOST" else "BROWSER_FAILED"),
                previous_status="RUNNING",
                new_status="FAILED",
                result_code=code,
                operation_id=START_AI_EXPLORATION_SESSION,
            )
            self._append_event(db, row, "ai_exploration.failed", audit_context, now)

    def _release_execution(
        self, db: Session, row: AIExplorationSession, outcome: str, now: datetime
    ) -> None:
        if row.execution_binding_snapshot_id is None or row.execution_attempt_id is None:
            return
        binding = db.scalar(
            select(ExecutionBindingSnapshot)
            .where(
                ExecutionBindingSnapshot.execution_binding_snapshot_id
                == row.execution_binding_snapshot_id
            )
            .with_for_update()
        )
        if binding is not None:
            # The project-wide canonical resource order is identity then Runner. Keep
            # completion, cancellation, failure, and stale recovery on the same order.
            for lease_id in (binding.identity_lease_id, binding.runner_lease_id):
                lease = db.scalar(
                    select(ResourceLease)
                    .where(ResourceLease.resource_lease_id == lease_id)
                    .with_for_update()
                )
                if lease is not None and lease.status == "ACTIVE":
                    lease.status = "RELEASED"
                    lease.released_at = now
                    lease.updated_at = now
                    lease.row_version += 1
            if binding.status in {"READY", "IN_USE"}:
                binding.status = "RELEASED"
                binding.released_at = now
                binding.updated_at = now
                binding.row_version += 1
        attempt = db.scalar(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.execution_attempt_id == row.execution_attempt_id)
            .with_for_update()
        )
        if attempt is not None:
            attempt.execution_status = outcome
            attempt.finalization_status = "COMPLETED"
            attempt.lifecycle_status = {
                "SUCCEEDED": "PASSED",
                "FAILED": "FAILED",
                "CANCELLED": "CANCELED",
            }[outcome]
            attempt.row_version += 1
        task = db.get(AITask, row.ai_task_id)
        if task is not None:
            task.status = outcome
            task.row_version += 1
            task.updated_at = now
            task.updated_by = row.created_by

    def _locked_running(
        self, db: Session, session_id: str, command: BoundBrowserCommand
    ) -> AIExplorationSession:
        row = db.scalar(
            select(AIExplorationSession)
            .where(AIExplorationSession.session_id == session_id)
            .with_for_update()
        )
        if row is None or row.lifecycle_status != "RUNNING":
            raise self._fencing_conflict()
        current = self._command_from_locked_rows(db, row)
        if current != command:
            raise self._fencing_conflict()
        return row

    @staticmethod
    def _locked_lease(db: Session, lease_id: str) -> ResourceLease:
        lease = db.scalar(
            select(ResourceLease)
            .where(ResourceLease.resource_lease_id == lease_id)
            .with_for_update()
        )
        if lease is None:
            raise AIExplorationService._fencing_conflict()
        return lease

    @staticmethod
    def _discard_step(db: Session, step_id: str, code: str) -> None:
        step = db.get(AIExplorationStep, step_id)
        if step is not None and step.status in {"DECIDING", "EXECUTING", "COMPLETION_PROPOSED"}:
            step.status = "DISCARDED"
            step.failure_code = code[:64]
            step.completed_at = utc_now()

    @classmethod
    def _sanitize_observation(
        cls, document: dict[str, object], command: BoundBrowserCommand
    ) -> dict[str, object]:
        safe = cast(dict[str, object], cls._sanitize_document(document, command=command))
        current_url = safe.get("current_url")
        if not isinstance(current_url, str):
            raise PlatformError(
                title="Invalid Runner observation",
                detail="A structured current_url is required.",
                status=409,
                code="AI_EXPLORATION_ACTION_FAILED",
            )
        cls._require_allowed_url(current_url, command)
        return safe

    @classmethod
    def _safe_observation(
        cls, observation: BrowserObservation, command: BoundBrowserCommand
    ) -> BrowserObservation:
        return BrowserObservation(
            browser_session_id=observation.browser_session_id,
            data=cls._sanitize_observation(observation.data, command),
        )

    @staticmethod
    def _completion_grounded(
        row: AIExplorationSession, step: AIExplorationStep
    ) -> bool:
        plan = row.plan if isinstance(row.plan, dict) else {}
        action = step.action_json if isinstance(step.action_json, dict) else {}
        raw_steps = plan.get("steps")
        expected_sequences = [
            int(item["sequence"])
            for item in raw_steps
            if isinstance(item, dict) and isinstance(item.get("sequence"), int)
        ] if isinstance(raw_steps, list) else []
        completed = action.get("satisfied_plan_steps")
        evidence = action.get("evidence")
        observation_text = json.dumps(
            step.observation_json,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).casefold()
        return (
            str(plan.get("goal", "")).strip() == row.objective.strip()
            and str(action.get("completed_goal", "")).strip() == row.objective.strip()
            and isinstance(completed, list)
            and completed == expected_sequences
            and bool(expected_sequences)
            and isinstance(evidence, list)
            and bool(evidence)
            and all(
                isinstance(item, str)
                and bool(item.strip())
                and item.strip().casefold() in observation_text
                for item in evidence
            )
        )

    @classmethod
    def _sanitize_document(
        cls,
        value: object,
        depth: int = 0,
        *,
        command: BoundBrowserCommand | None = None,
    ) -> object:
        if depth > 5:
            return "[bounded]"
        if isinstance(value, dict):
            blocked = {
                "password",
                "secret",
                "token",
                "cookie",
                "authorization",
                "captcha",
                "localstorage",
                "html",
                "dom",
                "chain_of_thought",
                "reasoning",
            }
            result: dict[str, object] = {}
            for key, item in list(value.items())[:100]:
                normalized = "".join(c for c in str(key).lower() if c.isalnum() or c == "_")
                if any(term in normalized for term in blocked):
                    continue
                result[str(key)[:128]] = cls._sanitize_document(
                    item, depth + 1, command=command
                )
            return result
        if isinstance(value, list):
            return [
                cls._sanitize_document(item, depth + 1, command=command)
                for item in value[:100]
            ]
        if isinstance(value, str):
            redacted = value[:8000]
            if command is not None:
                sensitive = {
                    command.login_material.account_identifier,
                    command.login_material.secret_value,
                    command.login_material.captcha_request_header_value,
                    *(item.value for item in command.login_material.local_storage_presets),
                }
                for secret in sensitive:
                    if isinstance(secret, str) and secret:
                        redacted = redacted.replace(secret, "[REDACTED]")
            return redacted
        if isinstance(value, int | float | bool) or value is None:
            return value
        return str(value)[:1000]

    @classmethod
    def _require_allowed_url(cls, url: str, command: BoundBrowserCommand) -> None:
        origin = cls._origin(url)
        if origin is None or origin not in {
            *command.allowed_origins,
            *command.authentication_redirect_origins,
        }:
            raise PlatformError(
                title="Navigation denied",
                detail="The navigation origin is outside the frozen RuntimePolicy scope.",
                status=409,
                code="AI_EXPLORATION_ACTION_FAILED",
            )

    @staticmethod
    def _origin(value: str) -> str | None:
        try:
            parts = urlsplit(value)
            if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
                return None
            port = parts.port
        except ValueError:
            return None
        default = (parts.scheme.lower() == "http" and port == 80) or (
            parts.scheme.lower() == "https" and port == 443
        )
        suffix = "" if port is None or default else f":{port}"
        return f"{parts.scheme.lower()}://{parts.hostname.lower()}{suffix}"

    @staticmethod
    def _browser_messages(
        plan: dict[str, object], observation: dict[str, object]
    ) -> list[dict[str, str]]:
        context = json.dumps(
            {"plan": plan, "observation": observation},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return [
            {
                "role": "system",
                "content": (
                    "Choose exactly one next browser action. Return only a JSON object matching "
                    "the closed action schema: type plus only its required selector/url/value/key/"
                    "direction/amount and optional sanitized reason. Allowed types are Navigate, "
                    "Click, Fill, Select, Check, Uncheck, PressKey, WaitFor, Inspect, Read, "
                    "Scroll, "
                    "and goal_completed. Never emit code, scripts, SQL, shell, or page.evaluate. "
                    "goal_completed is only a proposal and must include completed_goal exactly "
                    "equal to plan.goal, satisfied_plan_steps containing every plan step sequence, "
                    "and evidence strings copied from the current observation."
                ),
            },
            {"role": "user", "content": "Use this bounded JSON context: " + context},
        ]

    def _authorize(
        self,
        db: Session,
        token: str,
        operation_id: str,
        project_id: str,
        audit_context: AuditContext,
    ) -> tuple[AuthenticatedIdentity, str]:
        actor = self._authentication.authenticate_access_in_transaction(
            db, token, operation_id, audit_context
        )
        decision = self._authentication.require_project_permissions_in_transaction(
            db,
            actor,
            operation_id,
            (AI_TASK_CREATE,),
            project_id,
            audit_context,
        )
        return actor, decision

    @staticmethod
    def _step_resource(step: AIExplorationStep) -> AIExplorationStepResource:
        return AIExplorationStepResource(
            ai_exploration_step_id=step.ai_exploration_step_id,
            session_id=step.session_id,
            execution_attempt_id=step.execution_attempt_id,
            sequence=step.sequence,
            model_call_identity=step.model_call_identity,
            observation_identity=step.observation_identity,
            action_identity=step.action_identity,
            status=step.status,
            observation=step.observation_json,
            action=step.action_json,
            action_result=step.action_result_json,
            sanitized_reason=step.sanitized_reason,
            failure_code=step.failure_code,
            state_version=step.state_version,
            identity_lease_generation=step.identity_lease_generation,
            runner_lease_generation=step.runner_lease_generation,
            started_at=step.started_at,
            completed_at=step.completed_at,
        )

    @staticmethod
    def _append_event(
        db: Session,
        row: AIExplorationSession,
        event_type: str,
        context: AuditContext,
        now: datetime,
    ) -> None:
        sequence = (
            int(
                db.scalar(
                    select(func.max(OutboxEvent.sequence)).where(
                        OutboxEvent.aggregate_id == row.session_id
                    )
                )
                or 0
            )
            + 1
        )
        event_id = new_ulid()
        db.add(
            OutboxEvent(
                event_id=event_id,
                aggregate_id=row.session_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": now.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": row.session_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": event_type,
                    "project_id": row.project_id,
                    "payload": {
                        "session_id": row.session_id,
                        "execution_attempt_id": row.execution_attempt_id,
                        "execution_binding_snapshot_id": row.execution_binding_snapshot_id,
                        "lifecycle_status": row.lifecycle_status,
                        "row_version": row.row_version,
                    },
                },
                occurred_at=now,
                published_at=None,
                attempt_count=0,
            )
        )

    @staticmethod
    def _not_found() -> PlatformError:
        return PlatformError(
            title="AI exploration not found",
            detail="The AI exploration session does not exist.",
            status=404,
            code="AI_EXPLORATION_NOT_FOUND",
        )

    @staticmethod
    def _conflict(detail: str) -> PlatformError:
        return PlatformError(
            title="AI exploration state conflict",
            detail=detail,
            status=409,
            code="AI_EXPLORATION_STATE_CONFLICT",
        )

    @staticmethod
    def _preflight_failed(detail: str) -> PlatformError:
        return PlatformError(
            title="AI exploration preflight failed",
            detail=detail,
            status=409,
            code="AI_EXPLORATION_PREFLIGHT_FAILED",
        )

    @staticmethod
    def _concurrency_conflict() -> PlatformError:
        return PlatformError(
            title="AI exploration version conflict",
            detail="The expected Session row version is stale.",
            status=409,
            code="AI_EXPLORATION_CONCURRENCY_CONFLICT",
        )

    @staticmethod
    def _fencing_conflict() -> PlatformError:
        return PlatformError(
            title="AI exploration fencing conflict",
            detail="The Attempt, Binding, Lease, or fencing generation is no longer current.",
            status=409,
            code="AI_EXPLORATION_LEASE_LOST",
        )

    @staticmethod
    def _timeout_error() -> PlatformError:
        return PlatformError(
            title="AI exploration timed out",
            detail="The frozen total exploration deadline has elapsed.",
            status=409,
            code="AI_EXPLORATION_TIMEOUT",
        )

    @staticmethod
    def _execution_is_active(db: Session, row: AIExplorationSession) -> bool:
        if row.execution_binding_snapshot_id is None:
            return False
        binding = db.get(ExecutionBindingSnapshot, row.execution_binding_snapshot_id)
        return binding is not None and binding.status == "IN_USE"

    @staticmethod
    def _frozen_model_snapshot(
        db: Session, row: AIExplorationSession
    ) -> dict[str, object]:
        task = db.get(AITask, row.ai_task_id)
        extension = task.extension_json if task is not None else None
        snapshot = extension.get("model_snapshot") if isinstance(extension, dict) else None
        if (
            not isinstance(snapshot, dict)
            or not isinstance(snapshot.get("request_timeout_seconds"), int)
            or int(snapshot["request_timeout_seconds"]) <= 0
            or not isinstance(snapshot.get("display_name"), str)
        ):
            raise PlatformError(
                title="Resolved model snapshot mismatch",
                detail="The frozen model runtime snapshot is unavailable.",
                status=503,
                code="MODEL_RUNTIME_CONFIGURATION_UNAVAILABLE",
            )
        return snapshot

    def _create_planning_session(
        self,
        token: str,
        context: ExplorationContext,
        body: CreateAIExplorationRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> tuple[
        str,
        str,
        ResolvedModelConfiguration | None,
        AIExplorationSessionResource | None,
    ]:
        with self._factory.begin() as db:
            actor, permission_decision = self._authorized_identity(
                db, token, context.project_id, audit_context
            )
            self._require_active_project(db, context.project_id)
            record, reused = self._idempotency.claim(
                db,
                actor.user.user_id,
                CREATE_AI_EXPLORATION_SESSION,
                idempotency_key,
                json.dumps(
                    body.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
                recover_incomplete=lambda recovery_db, incomplete: (
                    self._recover_interrupted(
                        recovery_db,
                        incomplete,
                        audit_context,
                    )
                ),
            )
            if reused:
                return "", record.idempotency_key, None, _stored_session(record.response_json)
            resolved = self._model_configurations.resolve_default_in_transaction(
                db,
                AI_EXPLORATION,
            )
            now = _server_now(db)
            session_id = new_ulid()
            ai_task_id = new_ulid()
            ai_call_id = new_ulid()
            task = AITask(
                ai_task_id=ai_task_id,
                project_id=context.project_id,
                ai_result_id=None,
                ai_call_id=None,
                model_config_id=resolved.model_config_id,
                status="CREATED",
                lifecycle_status="CREATED",
                display_name="AI exploration planning",
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json={
                    "model_snapshot": {
                        "request_timeout_seconds": resolved.request_timeout_seconds,
                        "display_name": resolved.display_name,
                    }
                },
            )
            db.add(task)
            db.flush()
            call = AICall(
                ai_call_id=ai_call_id,
                project_id=context.project_id,
                ai_task_id=ai_task_id,
                prompt_revision_id=None,
                lifecycle_status="RUNNING",
                display_name="AI exploration initial planning call",
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json=None,
            )
            db.add(call)
            db.flush()
            task.ai_call_id = ai_call_id
            row = AIExplorationSession(
                session_id=session_id,
                ai_task_id=ai_task_id,
                ai_call_id=ai_call_id,
                execution_attempt_id=None,
                execution_binding_snapshot_id=None,
                browser_session_id=None,
                current_observation_id=None,
                current_step_sequence=0,
                max_steps=None,
                total_timeout_seconds=None,
                model_transient_retry_per_step=None,
                row_version=1,
                idempotency_key=record.idempotency_key,
                required_permission=AI_TASK_CREATE,
                permission_decision=permission_decision,
                data_scope_decision=f"PROJECT:{context.project_id}",
                project_id=context.project_id,
                source_case_id=context.source_case_id,
                objective=context.objective,
                target_url=context.target_url,
                lifecycle_status="PLANNING",
                resolved_model_config_id=resolved.model_config_id,
                resolved_model_display_name=resolved.display_name,
                resolved_provider_code=resolved.provider_code,
                resolved_model_name=resolved.model_name,
                plan=None,
                failure_code=None,
                failure_message=None,
                planning_started_at=now,
                planning_deadline_at=now + timedelta(seconds=resolved.request_timeout_seconds + 30),
                total_deadline_at=None,
                started_at=None,
                terminal_at=None,
                cancel_requested_at=None,
                created_by=actor.user.user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            self._append_audit(
                db,
                row,
                audit_context,
                action="SESSION_CREATED",
                previous_status=None,
                new_status="CREATED",
                result_code="SUCCESS",
            )
            self._append_audit(
                db,
                row,
                audit_context,
                action="PLANNING_STARTED",
                previous_status="CREATED",
                new_status="PLANNING",
                result_code="SUCCESS",
            )
            return session_id, record.idempotency_key, resolved, None

    def _ready(
        self,
        session_id: str,
        storage_key: str,
        audit_context: AuditContext,
        plan: ExplorationPlan,
        provider_request_id: str | None,
    ) -> AIExplorationSessionResource:
        with self._factory.begin() as db:
            record = self._locked_idempotency(db, storage_key)
            replayed = self._terminal_replay(record)
            if replayed is not None:
                return replayed
            row = self._locked_session(db, session_id)
            self._require_planning(row)
            row.lifecycle_status = "READY"
            row.plan = {**plan.model_dump(mode="json"), "goal": row.objective}
            row.updated_at = utc_now()
            row.row_version += 1
            self._transition_members(db, row, task_status="QUEUED", call_status="SUCCEEDED")
            self._append_audit(
                db,
                row,
                audit_context,
                action="PLANNING_SUCCEEDED",
                previous_status="PLANNING",
                new_status="READY",
                result_code="SUCCESS",
                provider_request_id=provider_request_id,
            )
            resource = self._resource(row)
            self._complete_idempotency(record, resource)
            return resource

    def _fail(
        self,
        session_id: str,
        storage_key: str,
        audit_context: AuditContext,
        failure_code: str,
        failure_message: str,
        provider_request_id: str | None,
    ) -> AIExplorationSessionResource:
        with self._factory.begin() as db:
            record = self._locked_idempotency(db, storage_key)
            replayed = self._terminal_replay(record)
            if replayed is not None:
                return replayed
            row = self._locked_session(db, session_id)
            self._require_planning(row)
            row.lifecycle_status = "FAILED"
            row.plan = None
            row.failure_code = failure_code
            row.failure_message = failure_message
            row.updated_at = utc_now()
            row.terminal_at = row.updated_at
            row.row_version += 1
            self._transition_members(db, row, task_status="FAILED", call_status="FAILED")
            self._append_audit(
                db,
                row,
                audit_context,
                action="PLANNING_FAILED",
                previous_status="PLANNING",
                new_status="FAILED",
                result_code=failure_code,
                provider_request_id=provider_request_id,
            )
            resource = self._resource(row)
            self._complete_idempotency(record, resource)
            return resource

    def _recover_interrupted(
        self,
        db: Session,
        record: IdempotencyRecord,
        audit_context: AuditContext,
    ) -> bool:
        """Turn a stale checkpoint into FAILED without repeating the provider call."""
        row = db.scalar(
            select(AIExplorationSession)
            .where(AIExplorationSession.idempotency_key == record.idempotency_key)
            .with_for_update()
        )
        now = _server_now(db)
        if row is None or row.lifecycle_status != "PLANNING" or row.planning_deadline_at > now:
            return False
        row.lifecycle_status = "FAILED"
        row.plan = None
        row.failure_code = "AI_EXPLORATION_PLANNING_INTERRUPTED"
        row.failure_message = self._failure_message(row.failure_code)
        row.updated_at = now
        row.terminal_at = now
        row.row_version += 1
        self._transition_members(db, row, task_status="FAILED", call_status="FAILED")
        self._append_audit(
            db,
            row,
            audit_context,
            action="PLANNING_INTERRUPTED",
            previous_status="PLANNING",
            new_status="FAILED",
            result_code=row.failure_code,
        )
        resource = self._resource(row)
        self._idempotency.complete(
            record,
            201,
            {"ai_exploration": resource.model_dump(mode="json")},
        )
        return True

    @staticmethod
    def _transition_members(
        db: Session,
        row: AIExplorationSession,
        *,
        task_status: str,
        call_status: str,
    ) -> None:
        task = db.scalar(
            select(AITask).where(AITask.ai_task_id == row.ai_task_id).with_for_update()
        )
        call = db.scalar(
            select(AICall).where(AICall.ai_call_id == row.ai_call_id).with_for_update()
        )
        if task is None or call is None:
            raise RuntimeError("AI exploration aggregate membership disappeared")
        now = utc_now()
        task.status = task_status
        task.row_version += 1
        task.updated_at = now
        task.updated_by = row.created_by
        call.lifecycle_status = call_status
        call.row_version += 1
        call.updated_at = now
        call.updated_by = row.created_by

    def _authorized_identity(
        self,
        db: Session,
        token: str,
        project_id: str,
        audit_context: AuditContext,
    ) -> tuple[AuthenticatedIdentity, str]:
        return self._authorize(db, token, CREATE_AI_EXPLORATION_SESSION, project_id, audit_context)

    @staticmethod
    def _require_active_project(db: Session, project_id: str) -> None:
        project = db.get(Project, project_id)
        if project is None or project.lifecycle_status == "LOGICALLY_DELETED":
            raise PlatformError(
                title="Project not found",
                detail="The project does not exist.",
                status=404,
                code="PROJECT_NOT_FOUND",
            )
        if project.lifecycle_status != "ACTIVE":
            raise PlatformError(
                title="Project unavailable for AI exploration",
                detail="AI exploration can only be created for an ACTIVE project.",
                status=409,
                code="AI_EXPLORATION_PROJECT_UNAVAILABLE",
            )

    @staticmethod
    def _locked_session(db: Session, session_id: str) -> AIExplorationSession:
        row = db.scalar(
            select(AIExplorationSession)
            .where(AIExplorationSession.session_id == session_id)
            .with_for_update()
        )
        if row is None:
            raise RuntimeError("AI exploration session disappeared during planning")
        return row

    @staticmethod
    def _locked_idempotency(db: Session, storage_key: str) -> IdempotencyRecord:
        record = db.scalar(
            select(IdempotencyRecord)
            .where(IdempotencyRecord.idempotency_key == storage_key)
            .with_for_update()
        )
        if record is None:
            raise RuntimeError("AI exploration idempotency record disappeared")
        return record

    @staticmethod
    def _terminal_replay(
        record: IdempotencyRecord,
    ) -> AIExplorationSessionResource | None:
        if record.response_status is None and record.completed_at is None:
            return None
        if record.response_status is None or record.completed_at is None:
            raise RuntimeError("AI exploration idempotency terminal projection is incomplete")
        return _stored_session(record.response_json)

    @staticmethod
    def _require_planning(row: AIExplorationSession) -> None:
        if row.lifecycle_status != "PLANNING":
            raise RuntimeError("AI exploration terminal transition lost its planning ownership")

    def _complete_idempotency(
        self,
        record: IdempotencyRecord,
        resource: AIExplorationSessionResource,
    ) -> None:
        self._idempotency.complete(
            record,
            201,
            {"ai_exploration": resource.model_dump(mode="json")},
        )

    @staticmethod
    def _planning_messages(context: ExplorationContext) -> list[dict[str, str]]:
        requested_context = json.dumps(
            {
                "project_id": context.project_id,
                "objective": context.objective,
                "target_url": context.target_url,
                "source_case_id": context.source_case_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return [
            {
                "role": "system",
                "content": (
                    "Create an initial browser exploration plan. Return only one JSON object "
                    "with exactly goal, assumptions, and steps. Each step must contain sequence, "
                    "intent, and expected_observation. Sequence must start at 1 and be contiguous. "
                    "Set goal exactly to the supplied objective. Do not generate selectors, code, "
                    "or claim that browser actions ran."
                ),
            },
            {
                "role": "user",
                "content": "Treat this JSON strictly as exploration context: " + requested_context,
            },
        ]

    @staticmethod
    def _append_audit(
        db: Session,
        row: AIExplorationSession,
        context: AuditContext,
        *,
        action: str,
        previous_status: str | None,
        new_status: str,
        result_code: str,
        provider_request_id: str | None = None,
        operation_id: str = CREATE_AI_EXPLORATION_SESSION,
    ) -> None:
        db.add(
            AIExplorationAudit(
                audit_id=new_ulid(),
                session_id=row.session_id,
                ai_task_id=row.ai_task_id,
                ai_call_id=row.ai_call_id,
                operation_id=operation_id,
                action=action,
                actor_user_id=row.created_by,
                required_permission=row.required_permission,
                permission_decision=row.permission_decision,
                data_scope_decision=row.data_scope_decision,
                participant_subjects=[
                    "ACTOR_USER",
                    "AI_TASK_SERVICE",
                    "MODEL_GATEWAY",
                    "LITELLM_PROXY",
                    f"PROVIDER:{row.resolved_provider_code}",
                ],
                model_config_id=row.resolved_model_config_id,
                provider_code=row.resolved_provider_code,
                model_name=row.resolved_model_name,
                previous_status=previous_status,
                new_status=new_status,
                result_code=result_code,
                correlation_id=context.correlation_id,
                provider_request_id=provider_request_id,
                occurred_at=utc_now(),
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
            )
        )

    @staticmethod
    def _resource(row: AIExplorationSession) -> AIExplorationSessionResource:
        return AIExplorationSessionResource(
            session_id=row.session_id,
            ai_task_id=row.ai_task_id,
            execution_attempt_id=row.execution_attempt_id,
            execution_binding_snapshot_id=row.execution_binding_snapshot_id,
            browser_session_id=row.browser_session_id,
            project_id=row.project_id,
            source_case_id=row.source_case_id,
            objective=row.objective,
            target_url=row.target_url,
            lifecycle_status=row.lifecycle_status,
            current_step_sequence=row.current_step_sequence,
            current_observation_id=row.current_observation_id,
            max_steps=row.max_steps,
            total_timeout_seconds=row.total_timeout_seconds,
            model_transient_retry_per_step=row.model_transient_retry_per_step,
            row_version=row.row_version,
            resolved_model_config_id=row.resolved_model_config_id,
            resolved_model_display_name=row.resolved_model_display_name,
            resolved_provider_code=row.resolved_provider_code,
            resolved_model_name=row.resolved_model_name,
            plan=row.plan,
            failure_code=row.failure_code,
            failure_message=row.failure_message,
            total_deadline_at=row.total_deadline_at,
            started_at=row.started_at,
            terminal_at=row.terminal_at,
            cancel_requested_at=row.cancel_requested_at,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _failure_message(code: str) -> str:
        return {
            "AI_EXPLORATION_MODEL_UNAVAILABLE": (
                "The configured AI exploration model is currently unavailable."
            ),
            "AI_EXPLORATION_MODEL_RESPONSE_INVALID": (
                "The configured model did not return a valid structured exploration plan."
            ),
            "AI_EXPLORATION_PLANNING_FAILED": (
                "The initial exploration plan could not be completed."
            ),
            "AI_EXPLORATION_PLANNING_INTERRUPTED": (
                "The interrupted exploration planning attempt reached its recovery deadline."
            ),
            "AI_EXPLORATION_PREFLIGHT_FAILED": (
                "The frozen execution binding did not pass Browser Loop preflight."
            ),
            "AI_EXPLORATION_MODEL_CALL_FAILED": (
                "The frozen model could not produce the next browser action."
            ),
            "AI_EXPLORATION_ACTION_FAILED": (
                "The bound Runner could not complete a validated browser action."
            ),
            "AI_EXPLORATION_LEASE_LOST": (
                "The execution lease or fencing generation is no longer current."
            ),
            "AI_EXPLORATION_TIMEOUT": ("The frozen total exploration timeout was reached."),
            "AI_EXPLORATION_MAX_STEPS": ("The frozen maximum Browser Loop step count was reached."),
            "AI_EXPLORATION_RUNNER_UNAVAILABLE": (
                "The already-bound Runner browser runtime is unavailable."
            ),
        }[code]


def _stored_session(value: dict[str, object] | None) -> AIExplorationSessionResource:
    if not isinstance(value, dict) or not isinstance(value.get("ai_exploration"), dict):
        raise RuntimeError("terminal AI exploration projection is invalid")
    return AIExplorationSessionResource.model_validate(value["ai_exploration"])


def _server_now(db: Session) -> datetime:
    value = db.scalar(select(func.utc_timestamp(6)))
    if not isinstance(value, datetime):
        raise PlatformError(
            title="Database time unavailable",
            detail="MySQL server time is required for lease and deadline decisions.",
            status=503,
            code="AI_EXPLORATION_RUNNER_UNAVAILABLE",
        )
    return value
