"""Deterministic preflight, immutable binding snapshots, and fenced resource leases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticatedIdentity, AuthenticationService
from platform_api.errors import PlatformError
from platform_api.execution_binding_schemas import (
    BindingCommandRequest,
    CreateRuntimePolicyRevisionRequest,
    ExecutionBindingInput,
    ExecutionBindingSnapshotListResponse,
    ExecutionBindingSnapshotResource,
    PageMeta,
    PreflightCheck,
    PreflightResult,
    RecoverBindingRequest,
    ResourceLeaseResource,
    RuntimePolicyRevisionListResponse,
    RuntimePolicyRevisionResource,
    RuntimePolicySnapshot,
)
from platform_api.execution_owner_transitions import (
    prepare_execution_attempt,
    prepare_run_task,
)
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    AccountMappingRevision,
    BusinessTerminal,
    CredentialRevision,
    Environment,
    ExecutionAttempt,
    ExecutionBindingAudit,
    ExecutionBindingSnapshot,
    ExecutionSlot,
    LoginStrategy,
    OutboxEvent,
    Project,
    ProjectRuntimePolicyAudit,
    ProjectRuntimePolicyRevision,
    ResourceLease,
    ResourceLeaseGeneration,
    Role,
    Runner,
    RunnerCapability,
    RunTask,
    TerminalAccessRevision,
    TestAccount,
    UserRoleBinding,
)
from platform_api.runner_readiness import runner_can_continue_bound_execution
from platform_api.security import new_ulid

IDENTITY_LEASE_TTL_SECONDS = 600
IDENTITY_LEASE_RENEW_SECONDS = 120
RUNNER_LEASE_TTL_SECONDS = 120
RUNNER_LEASE_RENEW_SECONDS = 30

_TERMINAL_CAPABILITIES = {
    "MANAGEMENT": "TERMINAL_ADMIN_WEB",
    "CLIENT": "TERMINAL_CLIENT_WEB",
    "PDA": "TERMINAL_PDA_WEB",
}
_BROWSER_CAPABILITIES = {
    "CHROMIUM": "BROWSER_CHROMIUM",
    "CHROME": "BROWSER_CHROME",
    "EDGE": "BROWSER_EDGE",
}
_ARTIFACT_CAPABILITIES = {
    "SCREENSHOT": "CAPTURE_SCREENSHOT",
    "VIDEO": "CAPTURE_VIDEO",
    "TRACE": "CAPTURE_TRACE",
}
_NETWORK_CAPABILITIES = {
    "INTRANET": "INTRANET_ACCESS",
    "PROXY": "PROXY_ACCESS",
}


@dataclass(frozen=True, slots=True)
class _ResolvedPreflight:
    result: PreflightResult
    project: Project
    environment: Environment
    terminal: BusinessTerminal
    terminal_revision: TerminalAccessRevision
    login_strategy: LoginStrategy
    account: TestAccount
    credential: CredentialRevision
    mapping: AccountMappingRevision
    runner: Runner
    policy: ProjectRuntimePolicyRevision
    attempt: ExecutionAttempt
    capability_snapshot: list[dict[str, object]]
    identity_resource: str
    runner_resource: str


class _PreflightRejected(Exception):
    def __init__(self, result: PreflightResult) -> None:
        super().__init__("execution binding preflight rejected")
        self.result = result


class ExecutionBindingService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def preflight(
        self,
        bearer_token: str,
        body: ExecutionBindingInput,
        context: AuditContext,
    ) -> PreflightResult:
        with self._factory.begin() as db:
            actor = self._authenticate(
                db,
                bearer_token,
                "preflight_execution_binding_snapshot",
                body.project_id,
                context,
                "PROJECT_EDIT",
            )
            del actor
            try:
                return self._resolve_preflight(db, body, lock=False, check_leases=True).result
            except _PreflightRejected as rejected:
                return rejected.result

    def create(
        self,
        bearer_token: str,
        body: ExecutionBindingInput,
        key: str,
        context: AuditContext,
    ) -> ExecutionBindingSnapshotResource:
        try:
            with self._factory.begin() as db:
                actor = self._authenticate(
                    db,
                    bearer_token,
                    "create_execution_binding_snapshot",
                    body.project_id,
                    context,
                    "PROJECT_EDIT",
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    "create_execution_binding_snapshot",
                    key,
                    body.model_dump_json().encode("utf-8"),
                )
                if replay:
                    binding_id = str(
                        (record.response_json or {}).get("execution_binding_snapshot_id", "")
                    )
                    binding = self._binding(db, binding_id)
                    return self._resource(db, binding)

                try:
                    resolved = self._resolve_preflight(db, body, lock=True, check_leases=True)
                except _PreflightRejected as rejected:
                    raise _preflight_failed(rejected.result) from None
                now = _server_now(db)
                root_execution_task_id = resolved.attempt.run_task_id
                assert root_execution_task_id is not None
                identity_lease = self._acquire_lease(
                    db,
                    project_id=body.project_id,
                    resource_type="IDENTITY",
                    resource_identity=resolved.identity_resource,
                    owner_type="FORMAL_ROOT_EXECUTION_TASK",
                    owner_id=root_execution_task_id,
                    ttl_seconds=IDENTITY_LEASE_TTL_SECONDS,
                    now=now,
                    correlation_id=context.correlation_id,
                )
                runner_lease = self._acquire_lease(
                    db,
                    project_id=body.project_id,
                    resource_type="RUNNER",
                    resource_identity=resolved.runner_resource,
                    owner_type="EXECUTION_ATTEMPT",
                    owner_id=body.execution_attempt_id,
                    ttl_seconds=RUNNER_LEASE_TTL_SECONDS,
                    now=now,
                    correlation_id=context.correlation_id,
                )
                binding = ExecutionBindingSnapshot(
                    execution_binding_snapshot_id=new_ulid(),
                    execution_attempt_id=body.execution_attempt_id,
                    project_id=body.project_id,
                    environment_id=body.environment_id,
                    business_terminal_id=body.business_terminal_id,
                    terminal_access_revision_id=resolved.terminal_revision.environment_terminal_access_revision_id,
                    login_strategy_id=resolved.login_strategy.login_strategy_id,
                    login_strategy_row_version=resolved.login_strategy.row_version,
                    test_account_id=body.test_account_id,
                    credential_revision_id=resolved.credential.credential_revision_id,
                    account_mapping_revision_id=resolved.mapping.account_mapping_revision_id,
                    runner_id=body.runner_id,
                    runner_row_version=resolved.runner.row_version,
                    runner_heartbeat_at=resolved.runner.last_heartbeat_at,
                    runner_capability_snapshot=resolved.capability_snapshot,
                    runtime_policy_revision_id=body.runtime_policy_revision_id,
                    identity_lease_id=identity_lease.resource_lease_id,
                    identity_lease_generation=identity_lease.fencing_generation,
                    runner_lease_id=runner_lease.resource_lease_id,
                    runner_lease_generation=runner_lease.fencing_generation,
                    owner_execution_identity=body.owner_execution_identity,
                    correlation_id=context.correlation_id,
                    status="READY",
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    released_at=None,
                    expired_at=None,
                    created_by=actor.user.user_id,
                )
                db.add(binding)
                db.flush()
                resolved.attempt.execution_binding_snapshot_id = (
                    binding.execution_binding_snapshot_id
                )
                run_task = db.get(RunTask, root_execution_task_id)
                if run_task is None:
                    raise RuntimeError("ExecutionBinding RunTask disappeared")
                owner_summary = {
                    "execution_binding_snapshot_id": binding.execution_binding_snapshot_id,
                    "runner_id": binding.runner_id,
                }
                # The direct binding path performs snapshot/preflight/resource acquisition
                # synchronously.  Project those actual facts through every canonical
                # LC-035/LC-036 preparation edge; no Scheduler/Queue is introduced.
                prepare_run_task(
                    db,
                    run_task,
                    actor_user_id=actor.user.user_id,
                    operation_id="create_execution_binding_snapshot",
                    context=context,
                    now=now,
                    change_summary=owner_summary,
                )
                prepare_execution_attempt(
                    db,
                    resolved.attempt,
                    actor_user_id=actor.user.user_id,
                    operation_id="create_execution_binding_snapshot",
                    context=context,
                    now=now,
                    change_summary=owner_summary,
                )
                self._audit(
                    db,
                    binding,
                    actor.user.user_id,
                    "HUMAN",
                    "CREATE",
                    None,
                    "READY",
                    "SUCCESS",
                    "preflight and atomic lease acquisition passed",
                    context,
                    now,
                )
                self._event(
                    db,
                    binding,
                    "execution_binding_snapshot.ready",
                    "create_execution_binding_snapshot",
                    context,
                    now,
                )
                self._idempotency.complete(
                    record,
                    201,
                    {"execution_binding_snapshot_id": binding.execution_binding_snapshot_id},
                )
                db.flush()
                return self._resource(db, binding)
        except IntegrityError as error:
            raise _persistence_conflict(error) from None

    def list(
        self,
        bearer_token: str,
        project_id: str,
        page: int,
        page_size: int,
        status: str | None,
        context: AuditContext,
    ) -> ExecutionBindingSnapshotListResponse:
        with self._factory.begin() as db:
            self._authenticate(
                db,
                bearer_token,
                "list_execution_binding_snapshots",
                project_id,
                context,
                "PROJECT_VIEW",
            )
            query = select(ExecutionBindingSnapshot).where(
                ExecutionBindingSnapshot.project_id == project_id
            )
            if status:
                query = query.where(ExecutionBindingSnapshot.status == status)
            total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
            items = list(
                db.scalars(
                    query.order_by(ExecutionBindingSnapshot.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return ExecutionBindingSnapshotListResponse(
                items=[self._resource(db, item) for item in items],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get(
        self, bearer_token: str, binding_id: str, context: AuditContext
    ) -> ExecutionBindingSnapshotResource:
        with self._factory.begin() as db:
            binding = self._binding(db, binding_id)
            self._authenticate(
                db,
                bearer_token,
                "get_execution_binding_snapshot",
                binding.project_id,
                context,
                "PROJECT_VIEW",
            )
            return self._resource(db, binding)

    def command(
        self,
        bearer_token: str,
        binding_id: str,
        action: str,
        body: BindingCommandRequest | RecoverBindingRequest,
        key: str,
        context: AuditContext,
    ) -> ExecutionBindingSnapshotResource:
        operation = {
            "consume": "consume_execution_binding_snapshot",
            "renew": "renew_execution_binding_snapshot_leases",
            "release": "release_execution_binding_snapshot",
            "recover": "recover_execution_binding_snapshot",
        }.get(action)
        if operation is None:
            raise _state_conflict("Unsupported binding command.")
        try:
            with self._factory.begin() as db:
                binding = db.scalar(
                    select(ExecutionBindingSnapshot)
                    .where(ExecutionBindingSnapshot.execution_binding_snapshot_id == binding_id)
                    .with_for_update()
                )
                if binding is None:
                    raise _not_found()
                actor = self._authenticate(
                    db, bearer_token, operation, binding.project_id, context, "PROJECT_EDIT"
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    operation,
                    key,
                    _command_idempotency_payload(binding_id, body),
                )
                if replay:
                    return self._resource(db, binding)
                now = _server_now(db)
                identity = self._locked_lease(db, binding.identity_lease_id)
                runner = self._locked_lease(db, binding.runner_lease_id)
                attempt = db.scalar(
                    select(ExecutionAttempt)
                    .where(ExecutionAttempt.execution_attempt_id == binding.execution_attempt_id)
                    .with_for_update()
                )
                self._assert_owner(binding, identity, runner, attempt, body)
                self._assert_generations(binding, identity, runner, body)
                previous = binding.status

                if action == "consume":
                    self._assert_version(binding, body.expected_version)
                    self._assert_active_leases(identity, runner, now)
                    if binding.status != "READY":
                        raise _state_conflict("Only a READY binding can be consumed.")
                    binding.status = "IN_USE"
                elif action == "renew":
                    self._assert_version(binding, body.expected_version)
                    self._assert_active_leases(identity, runner, now)
                    if binding.status not in {"READY", "IN_USE"}:
                        raise _state_conflict("Only READY or IN_USE bindings can renew leases.")
                    identity.expires_at = now + timedelta(seconds=IDENTITY_LEASE_TTL_SECONDS)
                    runner.expires_at = now + timedelta(seconds=RUNNER_LEASE_TTL_SECONDS)
                    identity.row_version += 1
                    runner.row_version += 1
                    identity.updated_at = now
                    runner.updated_at = now
                elif action == "release":
                    if binding.status == "RELEASED":
                        self._idempotency.complete(
                            record, 200, {"execution_binding_snapshot_id": binding_id}
                        )
                        return self._resource(db, binding)
                    self._assert_version(binding, body.expected_version)
                    if binding.status not in {"READY", "IN_USE"}:
                        raise _state_conflict("Only READY or IN_USE bindings can be released.")
                    self._release_active_leases(identity, runner, now)
                    binding.status = "RELEASED"
                    binding.released_at = now
                else:
                    if not isinstance(body, RecoverBindingRequest):
                        raise _state_conflict("Recovery evidence is required.")
                    self._assert_recoverable_status(binding)
                    self._assert_version(binding, body.expected_version)
                    self._require_recovery_role(db, actor, now)
                    current_runner = db.scalar(
                        select(Runner)
                        .where(Runner.runner_id == binding.runner_id)
                        .with_for_update()
                    )
                    stale = identity.expires_at <= now or runner.expires_at <= now
                    stale = (
                        stale
                        or current_runner is None
                        or current_runner.connection_status != "ONLINE"
                    )
                    stale = (
                        stale
                        or attempt is None
                        or attempt.execution_status
                        in {"ABORTED", "BROKEN", "CANCELLED", "FAILED", "SUCCEEDED"}
                    )
                    if not stale:
                        raise _state_conflict(
                            "Recovery requires expired leases, an unavailable Runner, "
                            "or a terminal execution attempt."
                        )
                    self._expire_lease(identity, now)
                    self._expire_lease(runner, now)
                    binding.status = "EXPIRED"
                    binding.expired_at = now

                binding.row_version += 1
                binding.updated_at = now
                self._audit(
                    db,
                    binding,
                    actor.user.user_id,
                    "HUMAN",
                    action.upper(),
                    previous,
                    binding.status,
                    "SUCCESS",
                    body.reason,
                    context,
                    now,
                )
                event_type = {
                    "consume": "execution_binding_snapshot.in_use",
                    "renew": "execution_binding_snapshot.leases_renewed",
                    "release": "execution_binding_snapshot.released",
                    "recover": "execution_binding_snapshot.expired",
                }[action]
                self._event(db, binding, event_type, operation, context, now)
                self._idempotency.complete(
                    record, 200, {"execution_binding_snapshot_id": binding_id}
                )
                db.flush()
                return self._resource(db, binding)
        except IntegrityError as error:
            raise _persistence_conflict(error) from None

    def list_runtime_policies(
        self, bearer_token: str, project_id: str, context: AuditContext
    ) -> RuntimePolicyRevisionListResponse:
        with self._factory.begin() as db:
            self._authenticate(
                db,
                bearer_token,
                "list_project_runtime_policy_revisions",
                project_id,
                context,
                "PROJECT_VIEW",
            )
            policies = list(
                db.scalars(
                    select(ProjectRuntimePolicyRevision)
                    .where(
                        ProjectRuntimePolicyRevision.project_id == project_id,
                        ProjectRuntimePolicyRevision.lifecycle_status == "PUBLISHED",
                    )
                    .order_by(ProjectRuntimePolicyRevision.revision_no.desc())
                )
            )
            return RuntimePolicyRevisionListResponse(
                items=[_policy_resource(item) for item in policies]
            )

    def create_runtime_policy(
        self,
        bearer_token: str,
        body: CreateRuntimePolicyRevisionRequest,
        key: str,
        context: AuditContext,
    ) -> RuntimePolicyRevisionResource:
        operation = "create_project_runtime_policy_revision"
        try:
            with self._factory.begin() as db:
                actor = self._authenticate(
                    db,
                    bearer_token,
                    operation,
                    body.project_id,
                    context,
                    "PROJECT_EDIT",
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    operation,
                    key,
                    body.model_dump_json().encode("utf-8"),
                )
                if replay:
                    policy_id = str(
                        (record.response_json or {}).get("runtime_policy_revision_id", "")
                    )
                    policy = db.get(ProjectRuntimePolicyRevision, policy_id)
                    if policy is None:
                        raise _policy_not_found()
                    return _policy_resource(policy)

                project = db.scalar(
                    select(Project).where(Project.project_id == body.project_id).with_for_update()
                )
                if project is None:
                    raise _policy_not_found()
                if project.lifecycle_status != "ACTIVE":
                    raise _state_conflict(
                        "Only an ACTIVE Project can receive a RuntimePolicy Revision."
                    )
                revision_no = (
                    int(
                        db.scalar(
                            select(func.max(ProjectRuntimePolicyRevision.revision_no)).where(
                                ProjectRuntimePolicyRevision.project_id == body.project_id
                            )
                        )
                        or 0
                    )
                    + 1
                )
                now = _server_now(db)
                policy = ProjectRuntimePolicyRevision(
                    runtime_policy_revision_id=new_ulid(),
                    project_id=body.project_id,
                    revision_no=revision_no,
                    browser_runtime=body.browser_runtime,
                    artifact_policy=body.artifact_policy,
                    timeout_seconds=body.timeout_seconds,
                    max_steps=body.max_steps,
                    total_exploration_timeout_seconds=body.total_exploration_timeout_seconds,
                    model_transient_retry_per_step=body.model_transient_retry_per_step,
                    allowed_origins=[str(item).rstrip("/") for item in body.allowed_origins],
                    authentication_redirect_origins=[
                        str(item).rstrip("/") for item in body.authentication_redirect_origins
                    ],
                    retry_mode=body.retry_mode,
                    network_requirement=body.network_requirement,
                    serial_execution_policy=body.serial_execution_policy,
                    lifecycle_status="PUBLISHED",
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                )
                db.add(policy)
                db.flush()
                snapshot = _policy_resource(policy).model_dump(mode="json")
                db.add(
                    ProjectRuntimePolicyAudit(
                        audit_id=new_ulid(),
                        runtime_policy_revision_id=policy.runtime_policy_revision_id,
                        project_id=policy.project_id,
                        action="CREATE_AND_PUBLISH",
                        actor_user_id=actor.user.user_id,
                        required_permission="PROJECT_EDIT",
                        previous_status=None,
                        new_status="PUBLISHED",
                        result_code="SUCCESS",
                        reason=body.reason,
                        policy_snapshot_json=snapshot,
                        correlation_id=context.correlation_id,
                        occurred_at=now,
                        source_context_hash=hashlib.sha256(
                            context.source_context.encode("utf-8")
                        ).digest(),
                    )
                )
                self._runtime_policy_event(db, policy, actor.user.user_id, key, context, now)
                self._idempotency.complete(
                    record,
                    201,
                    {"runtime_policy_revision_id": policy.runtime_policy_revision_id},
                )
                return _policy_resource(policy)
        except IntegrityError as error:
            raise _persistence_conflict(error) from None

    def _authenticate(
        self,
        db: Session,
        token: str,
        operation: str,
        project_id: str,
        context: AuditContext,
        permission: str,
    ) -> AuthenticatedIdentity:
        actor = self._authentication.authenticate_access_in_transaction(
            db, token, operation, context
        )
        self._authentication.require_project_permissions_in_transaction(
            db, actor, operation, (permission,), project_id, context
        )
        return actor

    def _resolve_preflight(
        self, db: Session, body: ExecutionBindingInput, *, lock: bool, check_leases: bool
    ) -> _ResolvedPreflight:
        checks: list[PreflightCheck] = []

        def query_suffix(query: Any) -> Any:
            return query.with_for_update() if lock else query

        project = db.scalar(
            query_suffix(select(Project).where(Project.project_id == body.project_id))
        )
        _check(
            checks,
            "PROJECT",
            project is not None and project.lifecycle_status == "ACTIVE",
            "Project must exist and be ACTIVE.",
        )
        environment = db.scalar(
            query_suffix(
                select(Environment).where(
                    Environment.environment_id == body.environment_id,
                    Environment.project_id == body.project_id,
                )
            )
        )
        _check(
            checks,
            "ENVIRONMENT",
            environment is not None
            and environment.lifecycle_status == "ACTIVE"
            and environment.enablement_state == "ENABLED",
            "Environment must belong to the Project and be ACTIVE and ENABLED.",
        )
        terminal = db.scalar(
            query_suffix(
                select(BusinessTerminal).where(
                    BusinessTerminal.business_terminal_id == body.business_terminal_id,
                    BusinessTerminal.project_id == body.project_id,
                    BusinessTerminal.environment_id == body.environment_id,
                )
            )
        )
        _check(
            checks,
            "BUSINESS_TERMINAL",
            terminal is not None
            and terminal.lifecycle_status == "ACTIVE"
            and terminal.current_published_revision_id is not None,
            "Business Terminal must be ACTIVE with a current published revision.",
        )
        revision = (
            None
            if terminal is None or terminal.current_published_revision_id is None
            else db.scalar(
                query_suffix(
                    select(TerminalAccessRevision).where(
                        TerminalAccessRevision.environment_terminal_access_revision_id
                        == terminal.current_published_revision_id,
                        TerminalAccessRevision.business_terminal_id == body.business_terminal_id,
                        TerminalAccessRevision.lifecycle_status == "PUBLISHED",
                    )
                )
            )
        )
        _check(
            checks,
            "TERMINAL_ACCESS_REVISION",
            revision is not None,
            "The current Terminal Access Revision must be PUBLISHED.",
        )
        strategy = (
            None
            if revision is None or revision.login_strategy_id is None
            else db.scalar(
                query_suffix(
                    select(LoginStrategy).where(
                        LoginStrategy.login_strategy_id == revision.login_strategy_id,
                        LoginStrategy.project_id == body.project_id,
                        LoginStrategy.lifecycle_status == "ACTIVE",
                    )
                )
            )
        )
        _check(
            checks,
            "LOGIN_STRATEGY",
            strategy is not None,
            "A current ACTIVE Login Strategy is required.",
        )
        account = db.scalar(
            query_suffix(
                select(TestAccount).where(
                    TestAccount.test_account_id == body.test_account_id,
                    TestAccount.project_id == body.project_id,
                    TestAccount.environment_id == body.environment_id,
                )
            )
        )
        _check(
            checks,
            "TEST_ACCOUNT",
            account is not None
            and account.lifecycle_status == "ACTIVE"
            and account.credential_state == "VALID",
            "Test Account must be ACTIVE with a VALID credential state.",
        )
        mapping = db.scalar(
            query_suffix(
                select(AccountMappingRevision)
                .where(
                    AccountMappingRevision.test_account_id == body.test_account_id,
                    AccountMappingRevision.project_id == body.project_id,
                    AccountMappingRevision.environment_id == body.environment_id,
                    AccountMappingRevision.business_terminal_id == body.business_terminal_id,
                    AccountMappingRevision.lifecycle_status == "PUBLISHED",
                )
                .order_by(AccountMappingRevision.created_at.desc())
            )
        )
        _check(
            checks,
            "ACCOUNT_MAPPING",
            mapping is not None,
            "A PUBLISHED Test Account mapping to the Business Terminal is required.",
        )
        credential = db.scalar(
            query_suffix(
                select(CredentialRevision)
                .where(
                    CredentialRevision.test_account_id == body.test_account_id,
                    CredentialRevision.project_id == body.project_id,
                    CredentialRevision.lifecycle_status == "PUBLISHED",
                )
                .order_by(CredentialRevision.revision_no.desc())
            )
        )
        _check(
            checks,
            "CREDENTIAL_REVISION",
            credential is not None,
            "A PUBLISHED Credential Revision is required.",
        )
        attempt = db.scalar(
            query_suffix(
                select(ExecutionAttempt).where(
                    ExecutionAttempt.execution_attempt_id == body.execution_attempt_id,
                    ExecutionAttempt.project_id == body.project_id,
                    ExecutionAttempt.runner_id == body.runner_id,
                )
            )
        )
        _check(
            checks,
            "EXECUTION_ATTEMPT",
            attempt is not None
            and attempt.run_task_id is not None
            and attempt.execution_binding_snapshot_id is None
            and body.owner_execution_identity == attempt.run_task_id
            and attempt.execution_status in {"PRESTART_BLOCKED", "READY"}
            and attempt.lifecycle_status in {"CREATED", "PREPARING"},
            "Execution Attempt must own the Project, Runner, root RunTask identity, "
            "and no Binding.",
        )
        runner = db.scalar(
            query_suffix(
                select(Runner).where(
                    Runner.runner_id == body.runner_id, Runner.project_id == body.project_id
                )
            )
        )
        runner_ready = (
            runner is not None
            and runner_can_continue_bound_execution(
                runner,
                project_lifecycle_status=project.lifecycle_status if project else None,
            )
            and runner.resource_status in {"AVAILABLE", "PARTIALLY_OCCUPIED"}
        )
        _check(
            checks,
            "RUNNER",
            runner_ready,
            "Runner must be ACTIVE, enabled, bound, online, healthy, compatible, and heartbeating.",
        )
        runner_resource = None
        if body.runner_resource_type == "FORMAL_EXECUTION_SLOT":
            runner_resource = db.scalar(
                query_suffix(
                    select(ExecutionSlot).where(
                        ExecutionSlot.execution_slot_id == body.runner_resource_identity,
                        ExecutionSlot.project_id == body.project_id,
                        ExecutionSlot.runner_id == body.runner_id,
                        ExecutionSlot.lifecycle_status == "ACTIVE",
                    )
                )
            )
        else:
            runner_resource = db.scalar(
                query_suffix(
                    select(RunnerCapability).where(
                        RunnerCapability.runner_capability_id == body.runner_resource_identity,
                        RunnerCapability.project_id == body.project_id,
                        RunnerCapability.runner_id == body.runner_id,
                        RunnerCapability.capability_type == "SESSION",
                        RunnerCapability.availability_status == "CONFIGURED",
                        RunnerCapability.validation_status == "VALID",
                        RunnerCapability.lifecycle_status == "ACTIVE",
                    )
                )
            )
        _check(
            checks,
            "RUNNER_RESOURCE_IDENTITY",
            runner_resource is not None,
            "Runner resource identity must be an ACTIVE slot or validated session capability.",
        )
        policy = db.scalar(
            query_suffix(
                select(ProjectRuntimePolicyRevision).where(
                    ProjectRuntimePolicyRevision.runtime_policy_revision_id
                    == body.runtime_policy_revision_id,
                    ProjectRuntimePolicyRevision.project_id == body.project_id,
                    ProjectRuntimePolicyRevision.lifecycle_status == "PUBLISHED",
                )
            )
        )
        _check(
            checks,
            "RUNTIME_POLICY",
            policy is not None and policy.serial_execution_policy == "SINGLE_PROCESS_UNIFIED_RETRY",
            "A PUBLISHED Project RuntimePolicy Revision with serial execution is required.",
        )

        required = set(body.required_capabilities)
        required.add("FORMAL_EXECUTION")
        if terminal is not None and terminal.terminal_type in _TERMINAL_CAPABILITIES:
            required.add(_TERMINAL_CAPABILITIES[terminal.terminal_type])
        if policy is not None:
            if policy.browser_runtime in _BROWSER_CAPABILITIES:
                required.add(_BROWSER_CAPABILITIES[policy.browser_runtime])
            if policy.artifact_policy in _ARTIFACT_CAPABILITIES:
                required.add(_ARTIFACT_CAPABILITIES[policy.artifact_policy])
            if policy.network_requirement in _NETWORK_CAPABILITIES:
                required.add(_NETWORK_CAPABILITIES[policy.network_requirement])
        capabilities = (
            []
            if runner is None
            else list(
                db.scalars(
                    select(RunnerCapability).where(
                        RunnerCapability.runner_id == body.runner_id,
                        RunnerCapability.capability_code.in_(required),
                        RunnerCapability.availability_status == "CONFIGURED",
                        RunnerCapability.validation_status == "VALID",
                        RunnerCapability.lifecycle_status == "ACTIVE",
                    )
                )
            )
        )
        codes = {item.capability_code for item in capabilities}
        _check(
            checks,
            "RUNNER_CAPABILITIES",
            required.issubset(codes),
            f"Runner is missing required capabilities: {sorted(required - codes)}",
        )

        sso_key = "" if account is None else (account.sso_identity_id or account.test_account_id)
        sso_digest = hashlib.sha256(sso_key.encode("utf-8")).hexdigest()
        identity_resource = f"{body.project_id}:{body.environment_id}:{sso_digest}"
        runner_resource = (
            f"{body.runner_id}:{body.runner_resource_type}:{body.runner_resource_identity}"
        )
        if check_leases:
            now = _server_now(db)
            identity_available = self._lease_available(db, "IDENTITY", identity_resource, now)
            runner_available = self._lease_available(db, "RUNNER", runner_resource, now)
            _check(
                checks,
                "IDENTITY_LEASE",
                identity_available,
                "The normalized identity already has an active or unrecovered lease.",
            )
            _check(
                checks,
                "RUNNER_LEASE",
                runner_available,
                "The selected Runner resource identity already has an active or unrecovered lease.",
            )

        result = PreflightResult(
            ready=all(item.status == "PASS" for item in checks),
            checks=checks,
            terminal_access_revision_id=None
            if revision is None
            else revision.environment_terminal_access_revision_id,
            login_strategy_id=None if strategy is None else strategy.login_strategy_id,
            login_strategy_row_version=None if strategy is None else strategy.row_version,
            credential_revision_id=None
            if credential is None
            else credential.credential_revision_id,
            account_mapping_revision_id=None
            if mapping is None
            else mapping.account_mapping_revision_id,
            sso_identity_key=None
            if not sso_key
            else hashlib.sha256(sso_key.encode("utf-8")).hexdigest(),
            runner_capability_codes=sorted(codes),
        )
        if not result.ready:
            raise _PreflightRejected(result)
        assert (
            project is not None
            and environment is not None
            and terminal is not None
            and revision is not None
            and strategy is not None
            and account is not None
            and credential is not None
            and mapping is not None
            and runner is not None
            and policy is not None
            and attempt is not None
        )
        snapshot = [
            {
                "capability_code": item.capability_code,
                "capability_type": item.capability_type,
                "availability_status": item.availability_status,
                "validation_status": item.validation_status,
                "lifecycle_status": item.lifecycle_status,
                "observed_version": item.observed_version,
                "reported_at": item.reported_at.replace(tzinfo=UTC).isoformat(),
            }
            for item in sorted(capabilities, key=lambda value: value.capability_code)
        ]
        return _ResolvedPreflight(
            result,
            project,
            environment,
            terminal,
            revision,
            strategy,
            account,
            credential,
            mapping,
            runner,
            policy,
            attempt,
            snapshot,
            identity_resource,
            runner_resource,
        )

    @staticmethod
    def _lease_available(db: Session, resource_type: str, identity: str, now: datetime) -> bool:
        del now
        digest = _resource_hash(resource_type, identity)
        existing = db.scalar(
            select(ResourceLease.resource_lease_id).where(
                ResourceLease.resource_type == resource_type,
                ResourceLease.resource_identity_hash == digest,
                ResourceLease.status == "ACTIVE",
            )
        )
        return existing is None

    @staticmethod
    def _acquire_lease(
        db: Session,
        *,
        project_id: str,
        resource_type: str,
        resource_identity: str,
        owner_type: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime,
        correlation_id: str,
    ) -> ResourceLease:
        digest = _resource_hash(resource_type, resource_identity)
        generation = db.scalar(
            select(ResourceLeaseGeneration)
            .where(
                ResourceLeaseGeneration.resource_type == resource_type,
                ResourceLeaseGeneration.resource_identity_hash == digest,
            )
            .with_for_update()
        )
        if generation is None:
            generation = ResourceLeaseGeneration(
                resource_type=resource_type,
                resource_identity_hash=digest,
                current_generation=1,
                updated_at=now,
            )
            db.add(generation)
            next_generation = 1
        else:
            generation.current_generation += 1
            generation.updated_at = now
            next_generation = generation.current_generation
        lease = ResourceLease(
            resource_lease_id=new_ulid(),
            project_id=project_id,
            resource_type=resource_type,
            resource_identity=resource_identity,
            resource_identity_hash=digest,
            owner_type=owner_type,
            owner_id=owner_id,
            status="ACTIVE",
            acquired_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            released_at=None,
            fencing_generation=next_generation,
            correlation_id=correlation_id,
            row_version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(lease)
        db.flush()
        return lease

    @staticmethod
    def _binding(db: Session, binding_id: str) -> ExecutionBindingSnapshot:
        binding = db.scalar(
            select(ExecutionBindingSnapshot).where(
                ExecutionBindingSnapshot.execution_binding_snapshot_id == binding_id
            )
        )
        if binding is None:
            raise _not_found()
        return binding

    @staticmethod
    def _locked_lease(db: Session, lease_id: str) -> ResourceLease:
        lease = db.scalar(
            select(ResourceLease)
            .where(ResourceLease.resource_lease_id == lease_id)
            .with_for_update()
        )
        if lease is None:
            raise _fencing_conflict()
        return lease

    @staticmethod
    def _assert_generations(
        binding: ExecutionBindingSnapshot,
        identity: ResourceLease,
        runner: ResourceLease,
        body: BindingCommandRequest,
    ) -> None:
        if (
            body.identity_lease_generation != binding.identity_lease_generation
            or body.runner_lease_generation != binding.runner_lease_generation
            or identity.fencing_generation != binding.identity_lease_generation
            or runner.fencing_generation != binding.runner_lease_generation
        ):
            raise _fencing_conflict()

    @staticmethod
    def _assert_owner(
        binding: ExecutionBindingSnapshot,
        identity: ResourceLease,
        runner: ResourceLease,
        attempt: ExecutionAttempt | None,
        body: BindingCommandRequest,
    ) -> None:
        if (
            attempt is None
            or attempt.run_task_id is None
            or attempt.execution_binding_snapshot_id != binding.execution_binding_snapshot_id
            or body.owner_execution_identity != binding.owner_execution_identity
            or binding.owner_execution_identity != attempt.run_task_id
        ):
            raise _fencing_conflict()
        if (
            identity.owner_type != "FORMAL_ROOT_EXECUTION_TASK"
            or identity.owner_id != attempt.run_task_id
        ):
            raise _fencing_conflict()
        if (
            runner.owner_type != "EXECUTION_ATTEMPT"
            or runner.owner_id != binding.execution_attempt_id
        ):
            raise _fencing_conflict()

    @staticmethod
    def _assert_recoverable_status(binding: ExecutionBindingSnapshot) -> None:
        if binding.status not in {"READY", "IN_USE"}:
            raise _state_conflict("Only READY or IN_USE bindings can be recovered.")

    @staticmethod
    def _assert_version(binding: ExecutionBindingSnapshot, expected: int) -> None:
        if binding.row_version != expected:
            raise _concurrency_conflict()

    @staticmethod
    def _assert_active_leases(
        identity: ResourceLease, runner: ResourceLease, now: datetime
    ) -> None:
        if (
            identity.status != "ACTIVE"
            or runner.status != "ACTIVE"
            or identity.expires_at <= now
            or runner.expires_at <= now
        ):
            raise _fencing_conflict()

    @staticmethod
    def _release_lease(lease: ResourceLease, now: datetime) -> None:
        if lease.status == "RELEASED":
            return
        if lease.status != "ACTIVE":
            raise _fencing_conflict()
        lease.status = "RELEASED"
        lease.released_at = now
        lease.updated_at = now
        lease.row_version += 1

    @classmethod
    def _release_active_leases(
        cls, identity: ResourceLease, runner: ResourceLease, now: datetime
    ) -> None:
        cls._assert_active_leases(identity, runner, now)
        cls._release_lease(identity, now)
        cls._release_lease(runner, now)

    @staticmethod
    def _expire_lease(lease: ResourceLease, now: datetime) -> None:
        if lease.status == "ACTIVE":
            lease.status = "EXPIRED"
            lease.released_at = now
            lease.updated_at = now
            lease.row_version += 1

    @staticmethod
    def _require_recovery_role(db: Session, actor: AuthenticatedIdentity, now: datetime) -> None:
        roles = set(
            db.scalars(
                select(Role.role_code)
                .join(UserRoleBinding, UserRoleBinding.role_id == Role.role_id)
                .where(
                    UserRoleBinding.user_id == actor.user.user_id,
                    Role.lifecycle_status == "ACTIVE",
                    UserRoleBinding.valid_from <= now,
                    or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                )
            )
        )
        if not roles.intersection({"ROLE-SUPER-ADMIN", "ROLE-PLATFORM-ADMIN"}):
            raise PlatformError(
                title="Recovery is forbidden",
                detail="Only a platform recovery administrator may recover a stale binding.",
                status=403,
                code="EXECUTION_BINDING_RECOVERY_FORBIDDEN",
            )

    @staticmethod
    def _audit(
        db: Session,
        binding: ExecutionBindingSnapshot,
        actor_id: str,
        actor_type: str,
        action: str,
        previous: str | None,
        new: str | None,
        result: str,
        reason: str,
        context: AuditContext,
        now: datetime,
    ) -> None:
        db.add(
            ExecutionBindingAudit(
                audit_id=new_ulid(),
                execution_binding_snapshot_id=binding.execution_binding_snapshot_id,
                project_id=binding.project_id,
                execution_attempt_id=binding.execution_attempt_id,
                action=action,
                actor_type=actor_type,
                actor_id=actor_id,
                previous_status=previous,
                new_status=new,
                result_code=result,
                reason=reason,
                lease_generations_json={
                    "identity": binding.identity_lease_generation,
                    "runner": binding.runner_lease_generation,
                },
                correlation_id=context.correlation_id,
                occurred_at=now,
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
            )
        )

    @staticmethod
    def _event(
        db: Session,
        binding: ExecutionBindingSnapshot,
        event_type: str,
        causation_id: str,
        context: AuditContext,
        now: datetime,
    ) -> None:
        sequence = (
            int(
                db.scalar(
                    select(func.max(OutboxEvent.sequence)).where(
                        OutboxEvent.aggregate_id == binding.execution_binding_snapshot_id
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
                aggregate_id=binding.execution_binding_snapshot_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": now.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": binding.execution_binding_snapshot_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": binding.project_id,
                    "payload": {
                        "execution_binding_snapshot_id": binding.execution_binding_snapshot_id,
                        "execution_attempt_id": binding.execution_attempt_id,
                        "status": binding.status,
                        "identity_lease_generation": binding.identity_lease_generation,
                        "runner_lease_generation": binding.runner_lease_generation,
                    },
                },
                occurred_at=now,
                published_at=None,
                attempt_count=0,
            )
        )

    @staticmethod
    def _runtime_policy_event(
        db: Session,
        policy: ProjectRuntimePolicyRevision,
        actor_id: str,
        causation_id: str,
        context: AuditContext,
        now: datetime,
    ) -> None:
        event_id = new_ulid()
        db.add(
            OutboxEvent(
                event_id=event_id,
                aggregate_id=policy.runtime_policy_revision_id,
                sequence=1,
                event_type="project_runtime_policy_revision.published",
                payload_json={
                    "event_id": event_id,
                    "event_type": "project_runtime_policy_revision.published",
                    "event_version": "1.0.0",
                    "occurred_at": now.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": policy.runtime_policy_revision_id,
                    "sequence": 1,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": policy.project_id,
                    "payload": {
                        "runtime_policy_revision_id": policy.runtime_policy_revision_id,
                        "project_id": policy.project_id,
                        "revision_no": policy.revision_no,
                        "from_state": None,
                        "to_state": "PUBLISHED",
                        "expected_version": 0,
                        "new_version": 1,
                        "changed_by": actor_id,
                        "change_summary": {
                            "browser_runtime": policy.browser_runtime,
                            "artifact_policy": policy.artifact_policy,
                            "network_requirement": policy.network_requirement,
                        },
                    },
                },
                occurred_at=now,
                published_at=None,
                attempt_count=0,
            )
        )

    @staticmethod
    def _resource(
        db: Session, binding: ExecutionBindingSnapshot
    ) -> ExecutionBindingSnapshotResource:
        identity = db.get(ResourceLease, binding.identity_lease_id)
        runner = db.get(ResourceLease, binding.runner_lease_id)
        policy = db.get(ProjectRuntimePolicyRevision, binding.runtime_policy_revision_id)
        if identity is None or runner is None or policy is None:
            raise _state_conflict("The binding snapshot references unavailable immutable facts.")
        return ExecutionBindingSnapshotResource(
            execution_binding_snapshot_id=binding.execution_binding_snapshot_id,
            execution_attempt_id=binding.execution_attempt_id,
            project_id=binding.project_id,
            environment_id=binding.environment_id,
            business_terminal_id=binding.business_terminal_id,
            terminal_access_revision_id=binding.terminal_access_revision_id,
            login_strategy_id=binding.login_strategy_id,
            login_strategy_row_version=binding.login_strategy_row_version,
            test_account_id=binding.test_account_id,
            credential_revision_id=binding.credential_revision_id,
            account_mapping_revision_id=binding.account_mapping_revision_id,
            runner_id=binding.runner_id,
            runner_row_version=binding.runner_row_version,
            runner_heartbeat_at=binding.runner_heartbeat_at,
            runner_capabilities=binding.runner_capability_snapshot,
            runtime_policy=RuntimePolicySnapshot(
                runtime_policy_revision_id=policy.runtime_policy_revision_id,
                revision_no=policy.revision_no,
                browser_runtime=policy.browser_runtime,
                artifact_policy=policy.artifact_policy,
                timeout_seconds=policy.timeout_seconds,
                max_steps=policy.max_steps,
                total_exploration_timeout_seconds=policy.total_exploration_timeout_seconds,
                model_transient_retry_per_step=policy.model_transient_retry_per_step,
                allowed_origins=policy.allowed_origins,
                authentication_redirect_origins=policy.authentication_redirect_origins,
                retry_mode=policy.retry_mode,
                network_requirement=policy.network_requirement,
                serial_execution_policy=policy.serial_execution_policy,
            ),
            identity_lease=_lease_resource(identity),
            runner_lease=_lease_resource(runner),
            owner_execution_identity=binding.owner_execution_identity,
            correlation_id=binding.correlation_id,
            status=binding.status,
            row_version=binding.row_version,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
            released_at=binding.released_at,
            expired_at=binding.expired_at,
        )


def _check(checks: list[PreflightCheck], code: str, passed: bool, detail: str) -> None:
    checks.append(
        PreflightCheck(
            code=code, status="PASS" if passed else "FAIL", detail="Ready." if passed else detail
        )
    )


def _server_now(db: Session) -> datetime:
    value = db.scalar(select(func.utc_timestamp(6)))
    if not isinstance(value, datetime):
        raise PlatformError(
            title="Database time unavailable",
            detail="MySQL server time is required for lease decisions.",
            status=503,
            code="EXECUTION_BINDING_TIME_UNAVAILABLE",
        )
    return value


def _resource_hash(resource_type: str, identity: str) -> bytes:
    encoded_type = resource_type.encode("utf-8")
    encoded_identity = identity.encode("utf-8")
    return hashlib.sha256(
        len(encoded_type).to_bytes(4, "big")
        + encoded_type
        + len(encoded_identity).to_bytes(4, "big")
        + encoded_identity
    ).digest()


def _command_idempotency_payload(
    binding_id: str, body: BindingCommandRequest | RecoverBindingRequest
) -> bytes:
    return json.dumps(
        {"binding_id": binding_id, "body": body.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _lease_resource(lease: ResourceLease) -> ResourceLeaseResource:
    return ResourceLeaseResource(
        resource_lease_id=lease.resource_lease_id,
        resource_type=lease.resource_type,
        resource_identity=lease.resource_identity,
        owner_type=lease.owner_type,
        owner_id=lease.owner_id,
        status=lease.status,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
        released_at=lease.released_at,
        fencing_generation=lease.fencing_generation,
        row_version=lease.row_version,
    )


def _policy_resource(policy: ProjectRuntimePolicyRevision) -> RuntimePolicyRevisionResource:
    return RuntimePolicyRevisionResource(
        runtime_policy_revision_id=policy.runtime_policy_revision_id,
        project_id=policy.project_id,
        revision_no=policy.revision_no,
        browser_runtime=policy.browser_runtime,
        artifact_policy=policy.artifact_policy,
        timeout_seconds=policy.timeout_seconds,
        max_steps=policy.max_steps,
        total_exploration_timeout_seconds=policy.total_exploration_timeout_seconds,
        model_transient_retry_per_step=policy.model_transient_retry_per_step,
        allowed_origins=policy.allowed_origins,
        authentication_redirect_origins=policy.authentication_redirect_origins,
        retry_mode=policy.retry_mode,
        network_requirement=policy.network_requirement,
        serial_execution_policy=policy.serial_execution_policy,
        lifecycle_status=policy.lifecycle_status,
        row_version=policy.row_version,
    )


def _preflight_failed(result: PreflightResult) -> PlatformError:
    failures = [item.code for item in result.checks if item.status == "FAIL"]
    return PlatformError(
        title="Execution binding preflight failed",
        detail=f"Preflight failed: {', '.join(failures)}",
        status=409,
        code="EXECUTION_BINDING_PREFLIGHT_FAILED",
    )


def _not_found() -> PlatformError:
    return PlatformError(
        title="Execution binding not found",
        detail="The requested binding is unavailable in the authorized Project scope.",
        status=404,
        code="EXECUTION_BINDING_NOT_FOUND",
    )


def _policy_not_found() -> PlatformError:
    return PlatformError(
        title="RuntimePolicy Revision not found",
        detail="The requested Project or RuntimePolicy Revision is unavailable in scope.",
        status=404,
        code="RUNTIME_POLICY_REVISION_NOT_FOUND",
    )


def _state_conflict(detail: str) -> PlatformError:
    return PlatformError(
        title="Execution binding state conflict",
        detail=detail,
        status=409,
        code="EXECUTION_BINDING_STATE_CONFLICT",
    )


def _fencing_conflict() -> PlatformError:
    return PlatformError(
        title="Lease fencing conflict",
        detail="The lease owner, status, expiry, or fencing generation is no longer current.",
        status=409,
        code="RESOURCE_LEASE_FENCING_CONFLICT",
    )


def _concurrency_conflict() -> PlatformError:
    return PlatformError(
        title="Execution binding concurrency conflict",
        detail="expected_version does not match the current binding version.",
        status=409,
        code="EXECUTION_BINDING_CONCURRENCY_CONFLICT",
    )


def _persistence_conflict(error: IntegrityError) -> PlatformError:
    message = str(error.orig).casefold()
    if "uq_atp_resource_lease_active" in message or "uq_atp_execution_binding_attempt" in message:
        return PlatformError(
            title="Resource lease conflict",
            detail="The execution attempt or resource identity is already bound.",
            status=409,
            code="RESOURCE_LEASE_CONFLICT",
        )
    return PlatformError(
        title="Execution binding persistence conflict",
        detail="The command could not be committed atomically.",
        status=409,
        code="EXECUTION_BINDING_PERSISTENCE_CONFLICT",
    )
