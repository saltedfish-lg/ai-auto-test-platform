"""Transactional Environment service bound to realtime Project permissions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticationService
from platform_api.environment_schemas import (
    CreateEnvironmentRequest,
    EnvironmentListData,
    EnvironmentResource,
    LifecycleCommandRequest,
    PageMeta,
    UpdateEnvironmentRequest,
)
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    Environment,
    EnvironmentAudit,
    IdempotencyRecord,
    OutboxEvent,
    Project,
)
from platform_api.security import new_ulid, utc_now

_ENVIRONMENT_TRANSITIONS: dict[str, tuple[frozenset[str], str, str]] = {
    "validate": (frozenset({"CONFIGURING"}), "VALIDATING", "environment.validating"),
    "reconfigure": (frozenset({"VALIDATING"}), "CONFIGURING", "environment.configuring"),
    "activate": (
        frozenset({"VALIDATING", "RECOVERING"}),
        "ACTIVE",
        "environment.active",
    ),
}


class EnvironmentService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def create_environment(
        self,
        token: str,
        body: CreateEnvironmentRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> EnvironmentResource:
        assert body.project_id is not None and body.environment_code is not None
        actor_user_id: str | None = None
        scope_decision: str | None = None
        project_exists = False
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "create_environment", audit_context
                )
                actor_user_id = actor.user.user_id
                scope = self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "create_environment",
                    ("PROJECT_EDIT",),
                    body.project_id,
                    audit_context,
                )
                scope_decision = scope
                record, replay = self._claim(
                    db,
                    actor.user.user_id,
                    "create_environment",
                    idempotency_key,
                    _canonical_payload(body),
                )
                if replay:
                    return _stored_environment(record.response_json)
                project = db.scalar(
                    select(Project).where(Project.project_id == body.project_id).with_for_update()
                )
                if project is None:
                    raise _not_found("The target project does not exist.")
                project_exists = True
                if project.lifecycle_status != "ACTIVE":
                    raise _state_forbidden("Environment creation requires an ACTIVE project.")
                if {"enablement_state", "accessibility_state"} & body.model_fields_set:
                    raise PlatformError(
                        title="Environment creation state is server managed",
                        detail=(
                            "enablement_state and accessibility_state cannot be supplied "
                            "at creation."
                        ),
                        status=400,
                        code="ENVIRONMENT_CREATE_STATE_MANAGED",
                    )
                duplicate = db.scalar(
                    select(Environment.environment_id).where(
                        Environment.project_id == body.project_id,
                        Environment.environment_code == body.environment_code,
                    )
                )
                if duplicate is not None:
                    raise _code_conflict()
                now = utc_now()
                environment = Environment(
                    environment_id=new_ulid(),
                    project_id=body.project_id,
                    environment_code=body.environment_code,
                    lifecycle_status="CREATED",
                    enablement_state="ENABLED",
                    accessibility_state="UNKNOWN",
                    display_name=body.display_name,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                db.add(environment)
                db.flush()
                environment.lifecycle_status = "CONFIGURING"
                environment.row_version = 1
                environment.updated_at = utc_now()
                after = _projection(environment)
                self._append_audit(
                    db,
                    environment,
                    audit_context,
                    actor.user.user_id,
                    scope,
                    action="ENVIRONMENT_CREATED",
                    operation_id="create_environment",
                    previous_status="CREATED",
                    before=None,
                    after=after,
                    reason=body.reason,
                )
                self._append_event(
                    db,
                    environment,
                    "environment.configuring",
                    actor.user.user_id,
                    context=audit_context,
                    causation_id=idempotency_key,
                    previous_status="CREATED",
                    expected_version=0,
                    change_summary={"lifecycle_path": ["CREATED", "CONFIGURING"]},
                )
                resource = _resource(environment)
                self._idempotency.complete(
                    record, 201, {"environment": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            failure = _environment_integrity_error(error)
            if actor_user_id is not None and scope_decision is not None and project_exists:
                self._append_failed_audit(
                    audit_context,
                    action="ENVIRONMENT_CREATED",
                    operation_id="create_environment",
                    environment_id=None,
                    project_id=body.project_id,
                    environment_code=body.environment_code,
                    actor_user_id=actor_user_id,
                    required_permission="PROJECT_EDIT",
                    scope_decision=scope_decision,
                    previous_status=None,
                    result_code=failure.code,
                    reason=body.reason,
                )
            raise failure from error
        except PlatformError as error:
            if (
                actor_user_id is not None
                and scope_decision is not None
                and project_exists
                and error.code
                in {
                    "ENVIRONMENT_CODE_CONFLICT",
                    "ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE",
                    "ENVIRONMENT_CREATE_STATE_MANAGED",
                    "ENVIRONMENT_NOT_FOUND",
                }
            ):
                self._append_failed_audit(
                    audit_context,
                    action="ENVIRONMENT_CREATED",
                    operation_id="create_environment",
                    environment_id=None,
                    project_id=body.project_id,
                    environment_code=body.environment_code,
                    actor_user_id=actor_user_id,
                    required_permission="PROJECT_EDIT",
                    scope_decision=scope_decision,
                    previous_status=None,
                    result_code=error.code,
                    reason=body.reason,
                )
            raise

    def list_environments(
        self,
        token: str,
        page: int,
        page_size: int,
        sort: str | None,
        filter_value: str | None,
        audit_context: AuditContext,
    ) -> EnvironmentListData:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_environment", audit_context
            )
            filters = _parse_filter(filter_value)
            project_id = filters.pop("project_id", None)
            if project_id is None:
                raise PlatformError(
                    title="Project scope is required",
                    detail="Environment list requests must include filter=project_id=<id>.",
                    status=400,
                    code="ENVIRONMENT_PROJECT_SCOPE_REQUIRED",
                )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "list_environment", ("PROJECT_VIEW",), project_id, audit_context
            )
            query = select(Environment).where(Environment.project_id == project_id)
            count = select(func.count(Environment.environment_id)).where(
                Environment.project_id == project_id
            )
            for key, column in {
                "lifecycle_status": Environment.lifecycle_status,
                "enablement_state": Environment.enablement_state,
                "accessibility_state": Environment.accessibility_state,
            }.items():
                value = filters.get(key)
                if value is not None:
                    query = query.where(column == value)
                    count = count.where(column == value)
            ordering = (
                Environment.environment_code.asc()
                if sort == "environment_code"
                else Environment.updated_at.desc()
            )
            items = list(
                db.scalars(
                    query.order_by(ordering, Environment.environment_id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return EnvironmentListData(
                items=[_resource(item) for item in items],
                page=PageMeta(page=page, page_size=page_size, total=int(db.scalar(count) or 0)),
            )

    def get_environment(
        self, token: str, environment_id: str, audit_context: AuditContext
    ) -> EnvironmentResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_environment", audit_context
            )
            environment = db.get(Environment, environment_id)
            if environment is None or environment.project_id is None:
                raise _not_found("The environment does not exist.")
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "get_environment",
                ("PROJECT_VIEW",),
                environment.project_id,
                audit_context,
            )
            return _resource(environment)

    def update_environment(
        self,
        token: str,
        environment_id: str,
        body: UpdateEnvironmentRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> EnvironmentResource:
        failure_evidence: dict[str, object] = {}
        try:
            return self._update_environment_transaction(
                token,
                environment_id,
                body,
                idempotency_key,
                audit_context,
                failure_evidence,
            )
        except PlatformError as error:
            if failure_evidence and error.code in {
                "ENVIRONMENT_CONCURRENCY_CONFLICT",
                "ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE",
                "ENVIRONMENT_UPDATE_NO_EFFECT",
                "ENVIRONMENT_STATE_NULL_INVALID",
            }:
                self._append_failed_audit(
                    audit_context,
                    action="ENVIRONMENT_UPDATED",
                    operation_id="update_environment",
                    result_code=error.code,
                    reason=body.reason,
                    **failure_evidence,
                )
            raise

    def _update_environment_transaction(
        self,
        token: str,
        environment_id: str,
        body: UpdateEnvironmentRequest,
        idempotency_key: str,
        audit_context: AuditContext,
        failure_evidence: dict[str, object],
    ) -> EnvironmentResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "update_environment", audit_context
            )
            project_id = db.scalar(
                select(Environment.project_id).where(Environment.environment_id == environment_id)
            )
            if project_id is None:
                raise _not_found("The environment does not exist.")
            scope = self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "update_environment",
                ("PROJECT_EDIT",),
                project_id,
                audit_context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "update_environment",
                idempotency_key,
                _canonical_payload(body, environment_id),
            )
            if replay:
                return _stored_environment(record.response_json)
            environment = db.scalar(
                select(Environment)
                .where(
                    Environment.environment_id == environment_id,
                    Environment.project_id == project_id,
                )
                .with_for_update()
            )
            if environment is None or environment.environment_code is None:
                raise _not_found("The environment does not exist.")
            failure_evidence.update(
                environment_id=environment.environment_id,
                project_id=project_id,
                environment_code=environment.environment_code,
                actor_user_id=actor.user.user_id,
                required_permission="PROJECT_EDIT",
                scope_decision=scope,
                previous_status=environment.lifecycle_status,
            )
            immutable = {"project_id", "environment_code"} & body.model_fields_set
            if immutable:
                raise PlatformError(
                    title="Environment identity is immutable",
                    detail="project_id and environment_code cannot be changed after creation.",
                    status=400,
                    code="ENVIRONMENT_IDENTITY_IMMUTABLE",
                )
            mutable = {
                "display_name",
                "enablement_state",
                "accessibility_state",
            } & body.model_fields_set
            if not mutable:
                raise PlatformError(
                    title="No environment update supplied",
                    detail="At least one mutable environment field must be supplied.",
                    status=400,
                    code="ENVIRONMENT_UPDATE_EMPTY",
                )
            for state_field in ("enablement_state", "accessibility_state"):
                if state_field in body.model_fields_set and getattr(body, state_field) is None:
                    raise PlatformError(
                        title="Environment state cannot be null",
                        detail=f"{state_field} may be omitted but cannot be null.",
                        status=400,
                        code="ENVIRONMENT_STATE_NULL_INVALID",
                    )
            if environment.row_version != body.expected_version:
                raise PlatformError(
                    title="Environment concurrency conflict",
                    detail="The expected environment version no longer matches.",
                    status=409,
                    code="ENVIRONMENT_CONCURRENCY_CONFLICT",
                )
            if environment.lifecycle_status == "ARCHIVED":
                raise _state_forbidden("An ARCHIVED environment is read-only.")
            before = _projection(environment)
            previous_status = environment.lifecycle_status
            if not any(
                field in mutable and getattr(body, field) != getattr(environment, field)
                for field in ("display_name", "enablement_state", "accessibility_state")
            ):
                raise PlatformError(
                    title="Environment update has no effect",
                    detail="The supplied values already match the current environment.",
                    status=409,
                    code="ENVIRONMENT_UPDATE_NO_EFFECT",
                )
            transition_event: str | None = None
            audit_action = "ENVIRONMENT_UPDATED"
            if "display_name" in mutable:
                environment.display_name = body.display_name
            transition_event, transition_action = _apply_state_changes(environment, body)
            if transition_action is not None:
                audit_action = transition_action
            environment.row_version += 1
            environment.updated_at = utc_now()
            environment.updated_by = actor.user.user_id
            after = _projection(environment)
            self._append_audit(
                db,
                environment,
                audit_context,
                actor.user.user_id,
                scope,
                action=audit_action,
                operation_id="update_environment",
                previous_status=previous_status,
                before=before,
                after=after,
                reason=body.reason,
            )
            if transition_event is not None:
                self._append_event(
                    db,
                    environment,
                    transition_event,
                    actor.user.user_id,
                    context=audit_context,
                    causation_id=idempotency_key,
                    previous_status=previous_status,
                    expected_version=body.expected_version,
                    change_summary={"changed_fields": sorted(mutable)},
                )
            resource = _resource(environment)
            self._idempotency.complete(
                record, 200, {"environment": resource.model_dump(mode="json")}
            )
            return resource

    def transition_environment(
        self,
        token: str,
        environment_id: str,
        action: str,
        body: LifecycleCommandRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> EnvironmentResource:
        transition = _ENVIRONMENT_TRANSITIONS.get(action)
        if transition is None:
            raise _state_forbidden("Unknown environment lifecycle command.")
        failure_evidence: dict[str, object] = {}
        try:
            return self._transition_environment_transaction(
                token,
                environment_id,
                action,
                body,
                idempotency_key,
                audit_context,
                failure_evidence,
            )
        except PlatformError as error:
            if failure_evidence and error.code in {
                "ENVIRONMENT_CONCURRENCY_CONFLICT",
                "ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE",
            }:
                self._append_failed_audit(
                    audit_context,
                    action=f"ENVIRONMENT_{transition[1]}",
                    operation_id=f"{action}_environment",
                    result_code=error.code,
                    reason=body.reason,
                    **failure_evidence,
                )
            raise

    def _transition_environment_transaction(
        self,
        token: str,
        environment_id: str,
        action: str,
        body: LifecycleCommandRequest,
        idempotency_key: str,
        audit_context: AuditContext,
        failure_evidence: dict[str, object],
    ) -> EnvironmentResource:
        allowed, target, event_type = _ENVIRONMENT_TRANSITIONS[action]
        operation_id = f"{action}_environment"
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, operation_id, audit_context
            )
            project_id = db.scalar(
                select(Environment.project_id).where(Environment.environment_id == environment_id)
            )
            if project_id is None:
                raise _not_found("The environment does not exist.")
            scope = self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                operation_id,
                ("PROJECT_EDIT",),
                project_id,
                audit_context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                operation_id,
                idempotency_key,
                _canonical_payload(body, environment_id),
            )
            if replay:
                return _stored_environment(record.response_json)
            environment = db.scalar(
                select(Environment)
                .where(
                    Environment.environment_id == environment_id,
                    Environment.project_id == project_id,
                )
                .with_for_update()
            )
            if environment is None or environment.environment_code is None:
                raise _not_found("The environment does not exist.")
            failure_evidence.update(
                environment_id=environment.environment_id,
                project_id=project_id,
                environment_code=environment.environment_code,
                actor_user_id=actor.user.user_id,
                required_permission="PROJECT_EDIT",
                scope_decision=scope,
                previous_status=environment.lifecycle_status,
            )
            if environment.row_version != body.expected_version:
                raise PlatformError(
                    title="Environment concurrency conflict",
                    detail="The expected environment version no longer matches.",
                    status=409,
                    code="ENVIRONMENT_CONCURRENCY_CONFLICT",
                )
            if environment.lifecycle_status not in allowed:
                raise _state_forbidden(
                    f"{action} is not allowed from {environment.lifecycle_status}."
                )
            previous_status = environment.lifecycle_status
            before = _projection(environment)
            environment.lifecycle_status = target
            environment.row_version += 1
            environment.updated_at = utc_now()
            environment.updated_by = actor.user.user_id
            after = _projection(environment)
            self._append_audit(
                db,
                environment,
                audit_context,
                actor.user.user_id,
                scope,
                action=f"ENVIRONMENT_{target}",
                operation_id=operation_id,
                previous_status=previous_status,
                before=before,
                after=after,
                reason=body.reason,
            )
            self._append_event(
                db,
                environment,
                event_type,
                actor.user.user_id,
                context=audit_context,
                causation_id=idempotency_key,
                previous_status=previous_status,
                expected_version=body.expected_version,
                change_summary={"reason_supplied": True},
            )
            resource = _resource(environment)
            self._idempotency.complete(
                record, 200, {"environment": resource.model_dump(mode="json")}
            )
            return resource

    def _claim(
        self,
        db: Session,
        principal_id: str,
        operation_id: str,
        idempotency_key: str,
        payload: bytes,
    ) -> tuple[IdempotencyRecord, bool]:
        return self._idempotency.claim(db, principal_id, operation_id, idempotency_key, payload)

    @staticmethod
    def _append_event(
        db: Session,
        environment: Environment,
        event_type: str,
        actor_user_id: str,
        *,
        context: AuditContext,
        causation_id: str,
        previous_status: str | None,
        expected_version: int,
        change_summary: dict[str, object],
    ) -> None:
        sequence = (
            int(
                db.scalar(
                    select(func.max(OutboxEvent.sequence)).where(
                        OutboxEvent.aggregate_id == environment.environment_id
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
                aggregate_id=environment.environment_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": occurred_at.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": environment.environment_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": environment.project_id,
                    "payload": {
                        "environment_id": environment.environment_id,
                        "project_id": environment.project_id,
                        "from_state": previous_status,
                        "to_state": environment.lifecycle_status,
                        "expected_version": expected_version,
                        "new_version": environment.row_version,
                        "changed_by": actor_user_id,
                        "change_summary": change_summary,
                    },
                },
                occurred_at=occurred_at,
                published_at=None,
                attempt_count=0,
            )
        )

    @staticmethod
    def _append_audit(
        db: Session,
        environment: Environment,
        context: AuditContext,
        actor_user_id: str,
        scope_decision: str,
        *,
        action: str,
        operation_id: str,
        previous_status: str | None,
        before: dict[str, object] | None,
        after: dict[str, object],
        reason: str | None,
    ) -> None:
        assert environment.project_id is not None and environment.environment_code is not None
        db.add(
            EnvironmentAudit(
                audit_id=new_ulid(),
                environment_id=environment.environment_id,
                project_id=environment.project_id,
                environment_code=environment.environment_code,
                action=action,
                operation_id=operation_id,
                actor_user_id=actor_user_id,
                required_permission="PROJECT_EDIT",
                scope_decision=scope_decision,
                previous_status=previous_status,
                new_status=environment.lifecycle_status,
                result_code="SUCCESS",
                reason=reason,
                before_json=before,
                after_json=after,
                correlation_id=context.correlation_id,
                occurred_at=utc_now(),
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
            )
        )

    def _append_failed_audit(
        self,
        context: AuditContext,
        *,
        action: str,
        operation_id: str,
        environment_id: str | None,
        project_id: str,
        environment_code: str,
        actor_user_id: str,
        required_permission: str,
        scope_decision: str,
        previous_status: str | None,
        result_code: str,
        reason: str | None,
    ) -> None:
        """Persist command failure evidence after the business transaction rolls back."""
        with self._factory.begin() as db:
            db.add(
                EnvironmentAudit(
                    audit_id=new_ulid(),
                    environment_id=environment_id,
                    project_id=project_id,
                    environment_code=environment_code,
                    action=action,
                    operation_id=operation_id,
                    actor_user_id=actor_user_id,
                    required_permission=required_permission,
                    scope_decision=scope_decision,
                    previous_status=previous_status,
                    new_status=None,
                    result_code=result_code,
                    reason=reason,
                    before_json=None,
                    after_json=None,
                    correlation_id=context.correlation_id,
                    occurred_at=utc_now(),
                    source_context_hash=hashlib.sha256(
                        context.source_context.encode("utf-8")
                    ).digest(),
                )
            )


def _resource(environment: Environment) -> EnvironmentResource:
    if environment.project_id is None or environment.environment_code is None:
        raise RuntimeError("environment business identity is incomplete")
    return EnvironmentResource(
        environment_id=environment.environment_id,
        display_name=environment.display_name,
        row_version=environment.row_version,
        created_at=environment.created_at,
        updated_at=environment.updated_at,
        project_id=environment.project_id,
        environment_code=environment.environment_code,
        lifecycle_status=environment.lifecycle_status,
        enablement_state=environment.enablement_state,
        accessibility_state=environment.accessibility_state,
    )


def _projection(environment: Environment) -> dict[str, object]:
    return _resource(environment).model_dump(mode="json", exclude={"created_at", "updated_at"})


def _canonical_payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    value = body.model_dump(mode="json", exclude_none=False)
    if resource_id is not None:
        value["resource_id"] = resource_id
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _stored_environment(value: dict[str, object] | None) -> EnvironmentResource:
    if not isinstance(value, dict) or not isinstance(value.get("environment"), dict):
        raise RuntimeError("environment idempotency projection is invalid")
    return EnvironmentResource.model_validate(value["environment"])


def _parse_filter(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    result: dict[str, str] = {}
    for part in value.split(";"):
        key, separator, item = part.partition("=")
        if (
            not separator
            or key
            not in {"project_id", "lifecycle_status", "enablement_state", "accessibility_state"}
            or not item
        ):
            raise PlatformError(
                title="Environment filter is invalid",
                detail="Use semicolon-separated key=value environment filters.",
                status=400,
                code="ENVIRONMENT_FILTER_INVALID",
            )
        result[key] = item
    return result


def _apply_state_changes(
    environment: Environment, body: UpdateEnvironmentRequest
) -> tuple[str | None, str | None]:
    transition_event: str | None = None
    audit_action: str | None = None
    if body.accessibility_state is not None:
        environment.accessibility_state = body.accessibility_state
        if environment.lifecycle_status == "ACTIVE" and body.accessibility_state == "UNREACHABLE":
            environment.lifecycle_status = "UNREACHABLE"
            transition_event = "environment.unreachable"
            audit_action = "ENVIRONMENT_UNREACHABLE"
        elif (
            environment.lifecycle_status == "UNREACHABLE"
            and body.accessibility_state == "REACHABLE"
        ):
            environment.lifecycle_status = "RECOVERING"
            transition_event = "environment.recovering"
            audit_action = "ENVIRONMENT_RECOVERING"
    if body.enablement_state == "DISABLED":
        if environment.lifecycle_status != "ACTIVE":
            raise _state_forbidden("Only ACTIVE environments can be disabled.")
        environment.enablement_state = "DISABLED"
        environment.lifecycle_status = "DISABLED"
        transition_event = "environment.disabled"
        audit_action = "ENVIRONMENT_DISABLED"
    elif body.enablement_state == "ENABLED":
        if environment.lifecycle_status != "DISABLED":
            if environment.enablement_state != "ENABLED":
                raise _state_forbidden("Only DISABLED environments can be recovered.")
        else:
            environment.lifecycle_status = "RECOVERING"
            environment.enablement_state = "ENABLED"
            transition_event = "environment.recovering"
            audit_action = "ENVIRONMENT_RECOVERING"
    return transition_event, audit_action


def _not_found(detail: str) -> PlatformError:
    return PlatformError(
        title="Environment not found", detail=detail, status=404, code="ENVIRONMENT_NOT_FOUND"
    )


def _code_conflict() -> PlatformError:
    return PlatformError(
        title="Environment code conflict",
        detail="environment_code must be unique within the target project.",
        status=409,
        code="ENVIRONMENT_CODE_CONFLICT",
    )


def _environment_integrity_error(error: IntegrityError) -> PlatformError:
    original_args = list(getattr(error.orig, "args", ()))
    vendor_code = original_args[0] if original_args else None
    vendor_message = str(original_args[1]) if len(original_args) > 1 else ""
    if vendor_code == 1062 and "uq_atp_environment_business" in vendor_message:
        return _code_conflict()
    return PlatformError(
        title="Internal server error",
        detail="The environment command could not be completed.",
        status=500,
        code="INTERNAL_ERROR",
    )


def _state_forbidden(detail: str) -> PlatformError:
    return PlatformError(
        title="Environment operation is forbidden for its state",
        detail=detail,
        status=409,
        code="ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE",
    )
