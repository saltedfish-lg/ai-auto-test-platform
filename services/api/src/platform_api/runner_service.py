"""Transactional Runner enrollment, management, machine identity, and heartbeat service."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from base64 import urlsafe_b64encode
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticatedIdentity, AuthenticationService
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    IdempotencyRecord,
    OutboxEvent,
    Project,
    Runner,
    RunnerAgent,
    RunnerAudit,
    RunnerCapability,
    RunnerEnrollment,
)
from platform_api.runner_schemas import (
    CreateRunnerEnrollmentRequest,
    HeartbeatRunnerRequest,
    PageMeta,
    RegisterRunnerData,
    RegisterRunnerRequest,
    ReportRunnerCapabilitiesRequest,
    RotateRunnerAgentTokenData,
    RunnerCapabilityReportItem,
    RunnerCapabilityResource,
    RunnerEnrollmentIssuedResource,
    RunnerLifecycleRequest,
    RunnerListResponse,
    RunnerResource,
    UpdateRunnerRequest,
)
from platform_api.security import new_ulid, utc_now

_CAPABILITY_TYPES = {
    "BROWSER_CHROMIUM": "BROWSER",
    "BROWSER_CHROME": "BROWSER",
    "BROWSER_EDGE": "BROWSER",
    "MODE_HEADED": "SESSION",
    "MODE_HEADLESS": "SESSION",
    "TERMINAL_ADMIN_WEB": "TERMINAL",
    "TERMINAL_CLIENT_WEB": "TERMINAL",
    "TERMINAL_PDA_WEB": "TERMINAL",
    "SINGLE_TERMINAL": "FLOW",
    "CROSS_TERMINAL": "FLOW",
    "CAPTURE_SCREENSHOT": "ARTIFACT",
    "CAPTURE_VIDEO": "ARTIFACT",
    "CAPTURE_TRACE": "ARTIFACT",
    "NETWORK_RESPONSE_LISTEN": "NETWORK",
    "INTRANET_ACCESS": "NETWORK",
    "PROXY_ACCESS": "NETWORK",
    "FILE_TRANSFER": "IO",
    "MANUAL_RECORDING": "SESSION",
    "AI_EXPLORATION": "SESSION",
    "FORMAL_EXECUTION": "SESSION",
    "LOCAL_ARTIFACT_CACHE": "STORAGE",
    "PLAYWRIGHT_VERSION": "VERSION",
    "AGENT_VERSION": "VERSION",
    "CONTEXT_ISOLATION": "SECURITY",
}
_TRANSITIONS = {
    "enable": ({"REGISTERED", "DISABLED"}, "ACTIVE", "runner.enabled"),
    "disable": ({"REGISTERED", "ACTIVE"}, "DISABLED", "runner.disabled"),
    "archive": ({"DISABLED"}, "ARCHIVED", "runner.archived"),
}
_SECRET_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "authorization",
    "cookie",
)


class RunnerService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def require_machine_identity(self, runner_id: str, agent_token: str) -> None:
        """Authenticate the Runner Agent before it can receive a bound direct command."""
        with self._factory.begin() as db:
            runner, _agent = _authenticate_agent(db, runner_id, agent_token)
            if (
                runner.lifecycle_status != "ACTIVE"
                or runner.registration_status != "REGISTERED"
                or runner.enable_status != "ENABLED"
                or runner.project_binding_status != "BOUND"
            ):
                raise _machine_unauthenticated("Runner Agent is not eligible for execution.")

    def create_enrollment(
        self,
        bearer_token: str,
        body: CreateRunnerEnrollmentRequest,
        key: str,
        context: AuditContext,
    ) -> RunnerEnrollmentIssuedResource:
        raw_credential = _new_opaque_credential("enr")
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, bearer_token, "create_runner_enrollment", context
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    "create_runner_enrollment",
                    key,
                    _payload(body),
                )
                if replay:
                    raise _credential_already_issued()
                project = db.scalar(
                    select(Project).where(Project.project_id == body.project_id).with_for_update()
                )
                if project is None:
                    raise _not_found()
                self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "create_runner_enrollment",
                    ("RUNNER_BIND",),
                    body.project_id,
                    context,
                )
                if project.lifecycle_status != "ACTIVE":
                    raise _state_error("Only an ACTIVE Project can receive a Runner enrollment.")
                duplicate_runner = db.scalar(
                    select(Runner.runner_id).where(
                        Runner.project_id == body.project_id,
                        Runner.runner_code == body.runner_code,
                    )
                )
                duplicate_enrollment = db.scalar(
                    select(RunnerEnrollment.enrollment_id).where(
                        RunnerEnrollment.project_id == body.project_id,
                        RunnerEnrollment.runner_code == body.runner_code,
                        RunnerEnrollment.enrollment_status == "PENDING",
                    )
                )
                if duplicate_runner is not None or duplicate_enrollment is not None:
                    raise _identifier_conflict()
                now = utc_now()
                enrollment = RunnerEnrollment(
                    enrollment_id=new_ulid(),
                    project_id=body.project_id,
                    runner_code=body.runner_code,
                    display_name=body.display_name,
                    credential_hash=_secret_hash(raw_credential),
                    enrollment_status="PENDING",
                    consumed_runner_id=None,
                    consumed_at=None,
                    revoked_at=None,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    reason=body.reason,
                )
                db.add(enrollment)
                db.flush()
                self._audit(
                    db,
                    runner=None,
                    enrollment=enrollment,
                    actor_type="HUMAN",
                    actor_id=actor.user.user_id,
                    context=context,
                    action="CREATE_ENROLLMENT",
                    operation="create_runner_enrollment",
                    required_permission="RUNNER_BIND",
                    previous_status=None,
                    new_status="PENDING",
                    reason=body.reason,
                    before=None,
                    after={
                        "enrollment_id": enrollment.enrollment_id,
                        "project_id": enrollment.project_id,
                        "runner_code": enrollment.runner_code,
                        "enrollment_status": enrollment.enrollment_status,
                    },
                    credential_changed=True,
                )
                self._event(
                    db,
                    enrollment.enrollment_id,
                    enrollment.project_id,
                    "runner.enrollment_created",
                    context,
                    key,
                    {
                        "enrollment_id": enrollment.enrollment_id,
                        "runner_code": enrollment.runner_code,
                        "enrollment_status": "PENDING",
                    },
                )
                self._idempotency.complete(
                    record,
                    201,
                    {"enrollment_id": enrollment.enrollment_id, "credential_issued": True},
                )
                return RunnerEnrollmentIssuedResource(
                    enrollment_id=enrollment.enrollment_id,
                    project_id=enrollment.project_id,
                    runner_code=enrollment.runner_code,
                    display_name=enrollment.display_name,
                    enrollment_status="PENDING",
                    enrollment_credential=raw_credential,
                    row_version=enrollment.row_version,
                    created_at=enrollment.created_at,
                )
        except IntegrityError as error:
            raise _integrity_error(error) from None

    def register(
        self,
        body: RegisterRunnerRequest,
        key: str,
        context: AuditContext,
    ) -> RegisterRunnerData:
        _validate_metadata(body.runtime_metadata)
        for capability in body.capabilities:
            _validate_metadata(capability.observed_metadata)
        credential_hash = _secret_hash(body.enrollment_credential)
        principal = hashlib.sha256(credential_hash).hexdigest()[:26]
        raw_agent_token = _registration_agent_token(body.enrollment_credential, key)
        try:
            with self._factory.begin() as db:
                record, replay = self._idempotency.claim(
                    db, principal, "register_runner", key, _payload(body)
                )
                if replay:
                    return _replayed_registration(
                        db, record, credential_hash, raw_agent_token
                    )
                enrollment = db.scalar(
                    select(RunnerEnrollment)
                    .where(RunnerEnrollment.credential_hash == credential_hash)
                    .with_for_update()
                )
                if enrollment is None or enrollment.enrollment_status != "PENDING":
                    raise _machine_unauthenticated("Enrollment credential is invalid or consumed.")
                project = db.scalar(
                    select(Project)
                    .where(Project.project_id == enrollment.project_id)
                    .with_for_update()
                )
                if project is None or project.lifecycle_status != "ACTIVE":
                    raise _state_error("The enrollment Project is not ACTIVE.")
                duplicate = db.scalar(
                    select(Runner.runner_id).where(
                        Runner.project_id == enrollment.project_id,
                        Runner.runner_code == enrollment.runner_code,
                    )
                )
                if duplicate is not None:
                    raise _identifier_conflict()
                now = utc_now()
                runner = Runner(
                    runner_id=new_ulid(),
                    project_id=enrollment.project_id,
                    runner_code=enrollment.runner_code,
                    display_name=enrollment.display_name,
                    lifecycle_status="REGISTERED",
                    registration_status="REGISTERED",
                    connection_status="OFFLINE",
                    health_status="UNKNOWN",
                    enable_status="DISABLED",
                    project_binding_status="BOUND",
                    scheduling_status="UNSCHEDULABLE",
                    resource_status="AVAILABLE",
                    version_compatibility="UNKNOWN",
                    last_heartbeat_at=None,
                    registered_at=now,
                    runtime_metadata_json=body.runtime_metadata,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=enrollment.created_by,
                    updated_by=enrollment.created_by,
                    extension_json=None,
                )
                agent = RunnerAgent(
                    runner_agent_id=new_ulid(),
                    project_id=runner.project_id,
                    runner_id=runner.runner_id,
                    token_hash=_secret_hash(raw_agent_token),
                    token_status="ACTIVE",
                    token_version=1,
                    machine_fingerprint_hash=_secret_hash(body.machine_fingerprint),
                    agent_version=body.agent_version,
                    last_authenticated_at=None,
                    credential_rotated_at=None,
                    revoked_at=None,
                    lifecycle_status="ACTIVE",
                    display_name=None,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=enrollment.created_by,
                    updated_by=enrollment.created_by,
                    extension_json=None,
                )
                db.add(runner)
                db.flush()
                db.add(agent)
                self._apply_capability_snapshot(
                    db, runner, body.capabilities, now, actor_id=agent.runner_agent_id
                )
                enrollment.enrollment_status = "CONSUMED"
                enrollment.consumed_runner_id = runner.runner_id
                enrollment.consumed_at = now
                enrollment.updated_at = now
                enrollment.row_version += 1
                self._audit(
                    db,
                    runner=runner,
                    enrollment=enrollment,
                    actor_type="AGENT",
                    actor_id=agent.runner_agent_id,
                    context=context,
                    action="REGISTER",
                    operation="register_runner",
                    required_permission=None,
                    previous_status=None,
                    new_status="REGISTERED",
                    reason="project-scoped enrollment consumed",
                    before=None,
                    after=_projection(runner),
                    credential_changed=True,
                )
                self._event(
                    db,
                    runner.runner_id,
                    runner.project_id,
                    "runner.registered",
                    context,
                    key,
                    {
                        "runner_id": runner.runner_id,
                        "runner_code": runner.runner_code,
                        "lifecycle_status": runner.lifecycle_status,
                    },
                )
                self._idempotency.complete(
                    record,
                    201,
                    {"runner_id": runner.runner_id, "agent_token_issued": True},
                )
                db.flush()
                return RegisterRunnerData(
                    runner=_resource(db, runner),
                    agent_token=raw_agent_token,
                    token_version=agent.token_version,
                )
        except IntegrityError as error:
            raise _integrity_error(error) from None

    def list(
        self,
        bearer_token: str,
        project_id: str,
        page: int,
        page_size: int,
        lifecycle_status: str | None,
        health_status: str | None,
        capability_code: str | None,
        context: AuditContext,
    ) -> RunnerListResponse:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, bearer_token, "list_runner", context
            )
            project = db.scalar(select(Project).where(Project.project_id == project_id))
            if project is None:
                raise _not_found()
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "list_runner", ("RUNNER_REGISTER",), project_id, context
            )
            query = select(Runner).where(Runner.project_id == project_id)
            if lifecycle_status:
                query = query.where(Runner.lifecycle_status == lifecycle_status)
            if health_status:
                query = query.where(Runner.health_status == health_status)
            if capability_code:
                query = query.join(
                    RunnerCapability, RunnerCapability.runner_id == Runner.runner_id
                ).where(
                    RunnerCapability.capability_code == capability_code,
                    RunnerCapability.availability_status == "CONFIGURED",
                )
            total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
            runners = list(
                db.scalars(
                    query.order_by(Runner.runner_code)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                ).unique()
            )
            return RunnerListResponse(
                items=[_resource(db, runner) for runner in runners],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get(self, bearer_token: str, runner_id: str, context: AuditContext) -> RunnerResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, bearer_token, "get_runner", context
            )
            runner = db.scalar(select(Runner).where(Runner.runner_id == runner_id))
            if runner is None:
                raise _not_found()
            self._require_human_scope(
                db, actor, "get_runner", "RUNNER_REGISTER", runner.project_id, context
            )
            return _resource(db, runner)

    def update(
        self,
        bearer_token: str,
        runner_id: str,
        body: UpdateRunnerRequest,
        key: str,
        context: AuditContext,
    ) -> RunnerResource:
        return self._human_mutation(
            bearer_token, runner_id, body, key, context, "update_runner", None
        )

    def transition(
        self,
        bearer_token: str,
        runner_id: str,
        action: str,
        body: RunnerLifecycleRequest,
        key: str,
        context: AuditContext,
    ) -> RunnerResource:
        if action not in _TRANSITIONS:
            raise _state_error("Unsupported Runner lifecycle command.")
        return self._human_mutation(
            bearer_token, runner_id, body, key, context, f"{action}_runner", action
        )

    def rotate_token(
        self,
        bearer_token: str,
        runner_id: str,
        body: RunnerLifecycleRequest,
        key: str,
        context: AuditContext,
    ) -> RotateRunnerAgentTokenData:
        raw_token = _new_opaque_credential("rat")
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, bearer_token, "rotate_runner_agent_token", context
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    "rotate_runner_agent_token",
                    key,
                    _payload(body, runner_id),
                )
                if replay:
                    raise _credential_already_issued()
                runner = _locked_runner(db, runner_id)
                self._require_human_scope(
                    db,
                    actor,
                    "rotate_runner_agent_token",
                    "RUNNER_REGISTER",
                    runner.project_id,
                    context,
                )
                _check_version(runner.row_version, body.expected_version)
                if runner.lifecycle_status == "ARCHIVED":
                    raise _state_error("An archived Runner cannot rotate credentials.")
                agent = _locked_agent(db, runner_id)
                now = utc_now()
                before = _projection(runner)
                agent.token_hash = _secret_hash(raw_token)
                agent.token_status = "ACTIVE"
                agent.lifecycle_status = "ACTIVE"
                agent.token_version += 1
                agent.credential_rotated_at = now
                agent.revoked_at = None
                agent.row_version += 1
                agent.updated_at = now
                agent.updated_by = actor.user.user_id
                runner.row_version += 1
                runner.updated_at = now
                runner.updated_by = actor.user.user_id
                self._audit(
                    db,
                    runner=runner,
                    enrollment=None,
                    actor_type="HUMAN",
                    actor_id=actor.user.user_id,
                    context=context,
                    action="ROTATE_AGENT_TOKEN",
                    operation="rotate_runner_agent_token",
                    required_permission="RUNNER_REGISTER",
                    previous_status=str(before["lifecycle_status"]),
                    new_status=runner.lifecycle_status,
                    reason=body.reason,
                    before=before,
                    after=_projection(runner),
                    credential_changed=True,
                )
                self._event(
                    db,
                    runner.runner_id,
                    runner.project_id,
                    "runner.agent_token_rotated",
                    context,
                    key,
                    {"runner_id": runner.runner_id, "token_version": agent.token_version},
                )
                self._idempotency.complete(
                    record,
                    200,
                    {"runner_id": runner.runner_id, "agent_token_issued": True},
                )
                db.flush()
                return RotateRunnerAgentTokenData(
                    runner=_resource(db, runner),
                    agent_token=raw_token,
                    token_version=agent.token_version,
                )
        except IntegrityError as error:
            raise _integrity_error(error) from None

    def revoke_token(
        self,
        bearer_token: str,
        runner_id: str,
        body: RunnerLifecycleRequest,
        key: str,
        context: AuditContext,
    ) -> RunnerResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, bearer_token, "revoke_runner_agent_token", context
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    "revoke_runner_agent_token",
                    key,
                    _payload(body, runner_id),
                )
                if replay:
                    return _stored_runner(record)
                runner = _locked_runner(db, runner_id)
                self._require_human_scope(
                    db,
                    actor,
                    "revoke_runner_agent_token",
                    "RUNNER_REGISTER",
                    runner.project_id,
                    context,
                )
                _check_version(runner.row_version, body.expected_version)
                agent = _locked_agent(db, runner_id)
                if agent.token_status == "REVOKED":
                    raise _state_error("The Runner Agent token is already revoked.")
                before = _projection(runner)
                now = utc_now()
                agent.token_status = "REVOKED"
                agent.lifecycle_status = "REVOKED"
                agent.revoked_at = now
                agent.row_version += 1
                agent.updated_at = now
                agent.updated_by = actor.user.user_id
                runner.connection_status = "OFFLINE"
                runner.scheduling_status = "UNSCHEDULABLE"
                runner.row_version += 1
                runner.updated_at = now
                runner.updated_by = actor.user.user_id
                self._audit(
                    db,
                    runner=runner,
                    enrollment=None,
                    actor_type="HUMAN",
                    actor_id=actor.user.user_id,
                    context=context,
                    action="REVOKE_AGENT_TOKEN",
                    operation="revoke_runner_agent_token",
                    required_permission="RUNNER_REGISTER",
                    previous_status=str(before["lifecycle_status"]),
                    new_status=runner.lifecycle_status,
                    reason=body.reason,
                    before=before,
                    after=_projection(runner),
                    credential_changed=True,
                )
                self._event(
                    db,
                    runner.runner_id,
                    runner.project_id,
                    "runner.agent_token_revoked",
                    context,
                    key,
                    {"runner_id": runner.runner_id, "token_version": agent.token_version},
                )
                resource = _resource(db, runner)
                self._idempotency.complete(
                    record, 200, {"runner": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _integrity_error(error) from None

    def heartbeat(
        self,
        runner_id: str,
        agent_token: str,
        body: HeartbeatRunnerRequest,
        context: AuditContext,
    ) -> RunnerResource:
        _validate_metadata(body.runtime_metadata)
        for capability in body.capabilities or []:
            _validate_metadata(capability.observed_metadata)
        with self._factory.begin() as db:
            runner, agent = _authenticate_agent(db, runner_id, agent_token)
            if runner.lifecycle_status == "ARCHIVED":
                raise _state_error("An archived Runner cannot send heartbeat.")
            project = db.scalar(select(Project).where(Project.project_id == runner.project_id))
            if project is None:
                raise _not_found()
            now = utc_now()
            runner.connection_status = "ONLINE"
            runner.health_status = body.health_status
            runner.last_heartbeat_at = now
            runner.runtime_metadata_json = body.runtime_metadata
            runner.row_version += 1
            runner.updated_at = now
            runner.updated_by = agent.runner_agent_id
            agent.agent_version = body.agent_version
            agent.last_authenticated_at = now
            agent.row_version += 1
            agent.updated_at = now
            if body.capabilities is not None:
                changed = self._apply_capability_snapshot(
                    db, runner, body.capabilities, now, actor_id=agent.runner_agent_id
                )
                if changed:
                    self._audit_capability_change(db, runner, agent, context)
            if (
                runner.lifecycle_status != "ACTIVE"
                or runner.enable_status != "ENABLED"
                or project.lifecycle_status != "ACTIVE"
                or body.health_status not in {"HEALTHY", "DEGRADED"}
                or runner.registration_status != "REGISTERED"
            ):
                runner.scheduling_status = "UNSCHEDULABLE"
            db.flush()
            return _resource(db, runner)

    def report_capabilities(
        self,
        runner_id: str,
        agent_token: str,
        body: ReportRunnerCapabilitiesRequest,
        context: AuditContext,
    ) -> RunnerResource:
        for capability in body.capabilities:
            _validate_metadata(capability.observed_metadata)
        with self._factory.begin() as db:
            runner, agent = _authenticate_agent(db, runner_id, agent_token)
            if runner.lifecycle_status == "ARCHIVED":
                raise _state_error("An archived Runner cannot report capabilities.")
            changed = self._apply_capability_snapshot(
                db, runner, body.capabilities, utc_now(), actor_id=agent.runner_agent_id
            )
            if changed:
                runner.row_version += 1
                runner.updated_at = utc_now()
                runner.updated_by = agent.runner_agent_id
                self._audit_capability_change(db, runner, agent, context)
            db.flush()
            return _resource(db, runner)

    def _human_mutation(
        self,
        bearer_token: str,
        runner_id: str,
        body: UpdateRunnerRequest | RunnerLifecycleRequest,
        key: str,
        context: AuditContext,
        operation: str,
        action: str | None,
    ) -> RunnerResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, bearer_token, operation, context
                )
                record, replay = self._idempotency.claim(
                    db,
                    actor.user.user_id,
                    operation,
                    key,
                    _payload(body, runner_id),
                )
                if replay:
                    return _stored_runner(record)
                runner = _locked_runner(db, runner_id)
                self._require_human_scope(
                    db,
                    actor,
                    operation,
                    "RUNNER_REGISTER",
                    runner.project_id,
                    context,
                )
                _check_version(runner.row_version, body.expected_version)
                before = _projection(runner)
                previous = runner.lifecycle_status
                event_type = "runner.metadata_updated"
                if action is None:
                    if runner.lifecycle_status == "ARCHIVED":
                        raise _state_error("An archived Runner cannot be edited.")
                    assert isinstance(body, UpdateRunnerRequest)
                    runner.display_name = body.display_name
                else:
                    allowed, target, event_type = _TRANSITIONS[action]
                    if runner.lifecycle_status not in allowed:
                        raise _state_error(
                            f"Runner cannot execute {action} from {runner.lifecycle_status}."
                        )
                    if action == "enable":
                        project = db.scalar(
                            select(Project).where(Project.project_id == runner.project_id)
                        )
                        if project is None or project.lifecycle_status != "ACTIVE":
                            raise _state_error("Only an ACTIVE Project can enable a Runner.")
                    runner.lifecycle_status = target
                    runner.enable_status = "ENABLED" if target == "ACTIVE" else "DISABLED"
                    if target != "ACTIVE":
                        runner.scheduling_status = "UNSCHEDULABLE"
                runner.row_version += 1
                runner.updated_at = utc_now()
                runner.updated_by = actor.user.user_id
                self._audit(
                    db,
                    runner=runner,
                    enrollment=None,
                    actor_type="HUMAN",
                    actor_id=actor.user.user_id,
                    context=context,
                    action=(action or "UPDATE_METADATA").upper(),
                    operation=operation,
                    required_permission="RUNNER_REGISTER",
                    previous_status=previous,
                    new_status=runner.lifecycle_status,
                    reason=body.reason,
                    before=before,
                    after=_projection(runner),
                    credential_changed=False,
                )
                self._event(
                    db,
                    runner.runner_id,
                    runner.project_id,
                    event_type,
                    context,
                    key,
                    {
                        "runner_id": runner.runner_id,
                        "from_state": previous,
                        "to_state": runner.lifecycle_status,
                        "expected_version": body.expected_version,
                        "new_version": runner.row_version,
                    },
                )
                resource = _resource(db, runner)
                self._idempotency.complete(
                    record, 200, {"runner": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _integrity_error(error) from None

    def _require_human_scope(
        self,
        db: Session,
        actor: AuthenticatedIdentity,
        operation: str,
        permission: str,
        project_id: str,
        context: AuditContext,
    ) -> None:
        try:
            self._authentication.require_project_permissions_in_transaction(
                db, actor, operation, (permission,), project_id, context
            )
        except PlatformError as error:
            if error.status == 403:
                raise _not_found() from None
            raise

    @staticmethod
    def _apply_capability_snapshot(
        db: Session,
        runner: Runner,
        reports: Sequence[RunnerCapabilityReportItem],
        now: datetime,
        *,
        actor_id: str,
    ) -> bool:
        existing = {
            item.capability_code: item
            for item in db.scalars(
                select(RunnerCapability)
                .where(RunnerCapability.runner_id == runner.runner_id)
                .with_for_update()
            )
        }
        reported = {item.capability_code: item for item in reports}
        changed = False
        for code, existing_item in existing.items():
            if code not in reported and (
                existing_item.availability_status != "NOT_CONFIGURED"
                or existing_item.lifecycle_status != "DISABLED"
            ):
                existing_item.availability_status = "NOT_CONFIGURED"
                existing_item.lifecycle_status = "DISABLED"
                existing_item.validation_status = "PENDING"
                existing_item.reported_at = now
                existing_item.row_version += 1
                existing_item.updated_at = now
                existing_item.updated_by = actor_id
                changed = True
        for code, report in reported.items():
            capability = existing.get(code)
            lifecycle = "ACTIVE" if report.availability_status == "CONFIGURED" else "DISABLED"
            if capability is None:
                db.add(
                    RunnerCapability(
                        runner_capability_id=new_ulid(),
                        project_id=runner.project_id,
                        runner_id=runner.runner_id,
                        capability_code=code,
                        capability_type=_CAPABILITY_TYPES[code],
                        availability_status=report.availability_status,
                        validation_status="PENDING",
                        observed_version=report.observed_version,
                        observed_metadata_json=report.observed_metadata,
                        reported_at=now,
                        lifecycle_status=lifecycle,
                        display_name=None,
                        row_version=1,
                        created_at=now,
                        updated_at=now,
                        created_by=actor_id,
                        updated_by=actor_id,
                        extension_json=None,
                    )
                )
                changed = True
                continue
            current = (
                capability.availability_status,
                capability.observed_version,
                capability.observed_metadata_json,
                capability.lifecycle_status,
            )
            replacement = (
                report.availability_status,
                report.observed_version,
                report.observed_metadata,
                lifecycle,
            )
            if current != replacement:
                capability.availability_status = report.availability_status
                capability.observed_version = report.observed_version
                capability.observed_metadata_json = report.observed_metadata
                capability.lifecycle_status = lifecycle
                capability.validation_status = "PENDING"
                capability.row_version += 1
                capability.updated_at = now
                capability.updated_by = actor_id
                changed = True
            capability.reported_at = now
        return changed

    @staticmethod
    def _audit(
        db: Session,
        *,
        runner: Runner | None,
        enrollment: RunnerEnrollment | None,
        actor_type: str,
        actor_id: str,
        context: AuditContext,
        action: str,
        operation: str,
        required_permission: str | None,
        previous_status: str | None,
        new_status: str | None,
        reason: str | None,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
        credential_changed: bool,
    ) -> None:
        project_id = runner.project_id if runner is not None else enrollment.project_id  # type: ignore[union-attr]
        db.add(
            RunnerAudit(
                audit_id=new_ulid(),
                runner_id=runner.runner_id if runner is not None else None,
                enrollment_id=enrollment.enrollment_id if enrollment is not None else None,
                project_id=project_id,
                action=action,
                operation_id=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                required_permission=required_permission,
                previous_status=previous_status,
                new_status=new_status,
                result_code="SUCCESS",
                reason=reason,
                before_json=before,
                after_json=after,
                credential_changed=credential_changed,
                correlation_id=context.correlation_id,
                occurred_at=utc_now(),
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
            )
        )

    @classmethod
    def _audit_capability_change(
        cls,
        db: Session,
        runner: Runner,
        agent: RunnerAgent,
        context: AuditContext,
    ) -> None:
        cls._audit(
            db,
            runner=runner,
            enrollment=None,
            actor_type="AGENT",
            actor_id=agent.runner_agent_id,
            context=context,
            action="REPORT_CAPABILITIES",
            operation="report_runner_capabilities",
            required_permission=None,
            previous_status=runner.lifecycle_status,
            new_status=runner.lifecycle_status,
            reason="machine capability snapshot changed",
            before=None,
            after={"runner_id": runner.runner_id, "capabilities_changed": True},
            credential_changed=False,
        )

    @staticmethod
    def _event(
        db: Session,
        aggregate_id: str,
        project_id: str,
        event_type: str,
        context: AuditContext,
        causation_id: str,
        payload: dict[str, object],
    ) -> None:
        sequence = (
            int(
                db.scalar(
                    select(func.max(OutboxEvent.sequence)).where(
                        OutboxEvent.aggregate_id == aggregate_id
                    )
                )
                or 0
            )
            + 1
        )
        event_id = new_ulid()
        occurred_at = utc_now()
        db.add(
            OutboxEvent(
                event_id=event_id,
                aggregate_id=aggregate_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": occurred_at.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": aggregate_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": project_id,
                    "payload": payload,
                },
                occurred_at=occurred_at,
                published_at=None,
                attempt_count=0,
            )
        )


def _authenticate_agent(db: Session, runner_id: str, raw_token: str) -> tuple[Runner, RunnerAgent]:
    runner = db.scalar(select(Runner).where(Runner.runner_id == runner_id).with_for_update())
    agent = db.scalar(
        select(RunnerAgent).where(RunnerAgent.runner_id == runner_id).with_for_update()
    )
    supplied = _secret_hash(raw_token)
    if (
        runner is None
        or agent is None
        or agent.token_status != "ACTIVE"
        or agent.lifecycle_status != "ACTIVE"
        or not secrets.compare_digest(agent.token_hash, supplied)
    ):
        raise _machine_unauthenticated("Runner Agent authentication failed.")
    return runner, agent


def _locked_runner(db: Session, runner_id: str) -> Runner:
    runner = db.scalar(select(Runner).where(Runner.runner_id == runner_id).with_for_update())
    if runner is None:
        raise _not_found()
    return runner


def _locked_agent(db: Session, runner_id: str) -> RunnerAgent:
    agent = db.scalar(
        select(RunnerAgent).where(RunnerAgent.runner_id == runner_id).with_for_update()
    )
    if agent is None:
        raise _state_error("The Runner Agent identity is unavailable.")
    return agent


def _resource(db: Session, runner: Runner) -> RunnerResource:
    capabilities = list(
        db.scalars(
            select(RunnerCapability)
            .where(RunnerCapability.runner_id == runner.runner_id)
            .order_by(RunnerCapability.capability_code)
        )
    )
    return RunnerResource(
        runner_id=runner.runner_id,
        project_id=runner.project_id,
        runner_code=runner.runner_code,
        display_name=runner.display_name,
        lifecycle_status=runner.lifecycle_status,
        registration_status=runner.registration_status,
        connection_status=runner.connection_status,
        health_status=runner.health_status,
        enable_status=runner.enable_status,
        project_binding_status=runner.project_binding_status,
        scheduling_status=runner.scheduling_status,
        resource_status=runner.resource_status,
        version_compatibility=runner.version_compatibility,
        last_heartbeat_at=runner.last_heartbeat_at,
        registered_at=runner.registered_at,
        runtime_metadata=runner.runtime_metadata_json,
        capabilities=[
            RunnerCapabilityResource(
                runner_capability_id=item.runner_capability_id,
                capability_code=item.capability_code,
                capability_type=item.capability_type,
                availability_status=item.availability_status,
                validation_status=item.validation_status,
                observed_version=item.observed_version,
                observed_metadata=item.observed_metadata_json,
                lifecycle_status=item.lifecycle_status,
                reported_at=item.reported_at,
            )
            for item in capabilities
        ],
        row_version=runner.row_version,
        created_at=runner.created_at,
        updated_at=runner.updated_at,
    )


def _projection(runner: Runner) -> dict[str, object]:
    return {
        "runner_id": runner.runner_id,
        "project_id": runner.project_id,
        "runner_code": runner.runner_code,
        "display_name": runner.display_name,
        "lifecycle_status": runner.lifecycle_status,
        "registration_status": runner.registration_status,
        "connection_status": runner.connection_status,
        "health_status": runner.health_status,
        "enable_status": runner.enable_status,
        "project_binding_status": runner.project_binding_status,
        "scheduling_status": runner.scheduling_status,
        "resource_status": runner.resource_status,
        "version_compatibility": runner.version_compatibility,
        "last_heartbeat_at": runner.last_heartbeat_at.isoformat()
        if runner.last_heartbeat_at
        else None,
        "row_version": runner.row_version,
    }


def _payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    document = body.model_dump(mode="json")
    for key in ("enrollment_credential", "machine_fingerprint"):
        value = document.get(key)
        if isinstance(value, str):
            document[key] = hashlib.sha256(value.encode("utf-8")).hexdigest()
    if resource_id is not None:
        document["runner_id"] = resource_id
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stored_runner(record: IdempotencyRecord) -> RunnerResource:
    if not record.response_json or "runner" not in record.response_json:
        raise PlatformError(
            title="Runner idempotency state is unavailable",
            detail="The prior command did not persist a replayable non-secret projection.",
            status=409,
            code="RUNNER_IDEMPOTENCY_STATE_UNAVAILABLE",
        )
    return RunnerResource.model_validate(record.response_json["runner"])


def _secret_hash(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def _registration_agent_token(enrollment_credential: str, idempotency_key: str) -> str:
    """Reproduce only the first-delivery token when the same enrollment request is retried."""
    digest = hmac.new(
        enrollment_credential.encode("utf-8"),
        b"runner-agent-token-v1\x00" + idempotency_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return "rat_" + urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _replayed_registration(
    db: Session,
    record: IdempotencyRecord,
    credential_hash: bytes,
    raw_agent_token: str,
) -> RegisterRunnerData:
    runner_id = record.response_json.get("runner_id") if record.response_json else None
    if not isinstance(runner_id, str):
        raise _credential_already_issued()
    enrollment = db.scalar(
        select(RunnerEnrollment).where(
            RunnerEnrollment.credential_hash == credential_hash,
            RunnerEnrollment.enrollment_status == "CONSUMED",
            RunnerEnrollment.consumed_runner_id == runner_id,
        )
    )
    runner = db.scalar(select(Runner).where(Runner.runner_id == runner_id))
    agent = db.scalar(select(RunnerAgent).where(RunnerAgent.runner_id == runner_id))
    if (
        enrollment is None
        or runner is None
        or agent is None
        or not hmac.compare_digest(agent.token_hash, _secret_hash(raw_agent_token))
    ):
        raise _credential_already_issued()
    return RegisterRunnerData(
        runner=_resource(db, runner),
        agent_token=raw_agent_token,
        token_version=agent.token_version,
    )


def _new_opaque_credential(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(48)}"


def _validate_metadata(value: dict[str, object] | None) -> None:
    if value is None:
        return
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 16_384:
        raise PlatformError(
            title="Runner metadata is too large",
            detail="Runtime metadata must not exceed 16384 UTF-8 bytes.",
            status=422,
            code="RUNNER_METADATA_TOO_LARGE",
        )

    def walk(item: object) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                normalized = str(key).casefold()
                if any(fragment in normalized for fragment in _SECRET_KEY_FRAGMENTS):
                    raise PlatformError(
                        title="Runner metadata contains a forbidden key",
                        detail="Secrets and credentials are not accepted as runtime metadata.",
                        status=422,
                        code="RUNNER_METADATA_SECRET_FORBIDDEN",
                    )
                walk(nested)
        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(value)


def _check_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise PlatformError(
            title="Runner concurrency conflict",
            detail="The Runner changed after it was loaded.",
            status=409,
            code="RUNNER_CONCURRENCY_CONFLICT",
        )


def _not_found() -> PlatformError:
    return PlatformError(
        title="Runner not found",
        detail="The requested resource is unavailable in the authorized Project scope.",
        status=404,
        code="RUNNER_NOT_FOUND",
    )


def _state_error(detail: str) -> PlatformError:
    return PlatformError(
        title="Runner state conflict",
        detail=detail,
        status=409,
        code="RUNNER_STATE_CONFLICT",
    )


def _identifier_conflict() -> PlatformError:
    return PlatformError(
        title="Runner code conflict",
        detail="runner_code already has a Runner or pending enrollment in this Project.",
        status=409,
        code="RUNNER_CODE_CONFLICT",
    )


def _credential_already_issued() -> PlatformError:
    return PlatformError(
        title="Runner credential was already issued",
        detail="Opaque Runner credentials are returned once and cannot be replayed or recovered.",
        status=409,
        code="RUNNER_CREDENTIAL_ALREADY_ISSUED",
    )


def _machine_unauthenticated(detail: str) -> PlatformError:
    return PlatformError(
        title="Runner Agent authentication failed",
        detail=detail,
        status=401,
        code="RUNNER_AGENT_UNAUTHENTICATED",
    )


def _integrity_error(error: IntegrityError) -> PlatformError:
    message = str(error.orig).casefold()
    if "uq_atp_runner_business" in message or "duplicate" in message:
        return _identifier_conflict()
    return PlatformError(
        title="Runner persistence conflict",
        detail="The Runner command could not be committed.",
        status=409,
        code="RUNNER_PERSISTENCE_CONFLICT",
    )
