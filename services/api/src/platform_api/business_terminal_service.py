"""Transactional Business Terminal, Login Strategy, and access-revision service."""

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
from platform_api.business_terminal_schemas import (
    BusinessTerminalListData,
    BusinessTerminalResource,
    CreateBusinessTerminalRequest,
    CreateTerminalAccessRevisionRequest,
    LifecycleCommandRequest,
    PageMeta,
    PublishTerminalAccessRevisionRequest,
    TerminalAccessRevisionListData,
    TerminalAccessRevisionResource,
    UpdateBusinessTerminalRequest,
    UpdateTerminalAccessRevisionRequest,
)
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    BusinessTerminal,
    BusinessTerminalAudit,
    Environment,
    ExecutionBindingSnapshot,
    IdempotencyRecord,
    LoginStrategy,
    OutboxEvent,
    TerminalAccessRevision,
)
from platform_api.security import new_ulid, utc_now

_TERMINAL_TRANSITIONS = {
    "validate": ({"CONFIGURING"}, "VALIDATING", "business_terminal.validating"),
    "reconfigure": ({"VALIDATING"}, "CONFIGURING", "business_terminal.configuring"),
    "activate": ({"VALIDATING", "RECOVERING"}, "ACTIVE", "business_terminal.active"),
    "mark-unreachable": ({"ACTIVE"}, "UNREACHABLE", "business_terminal.unreachable"),
    "recover": ({"UNREACHABLE", "DISABLED"}, "RECOVERING", "business_terminal.recovering"),
    "disable": ({"ACTIVE"}, "DISABLED", "business_terminal.disabled"),
    "archive": ({"DISABLED"}, "ARCHIVED", "business_terminal.archived"),
}


class BusinessTerminalService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def create_terminal(
        self, token: str, body: CreateBusinessTerminalRequest, key: str, context: AuditContext
    ) -> BusinessTerminalResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "create_business_terminal", context
                )
                environment = db.scalar(
                    select(Environment)
                    .where(Environment.environment_id == body.environment_id)
                    .with_for_update()
                )
                if environment is None or environment.project_id is None:
                    raise _not_found()
                self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "create_business_terminal",
                    ("BUSINESS_TERMINAL_CREATE",),
                    environment.project_id,
                    context,
                )
                if environment.lifecycle_status not in {
                    "CONFIGURING",
                    "VALIDATING",
                    "ACTIVE",
                    "RECOVERING",
                }:
                    raise _state_error(
                        "The target environment does not allow terminal creation "
                        "in its current state."
                    )
                record, replay = self._claim(
                    db,
                    actor.user.user_id,
                    "create_business_terminal",
                    key,
                    _payload(body),
                )
                if replay:
                    return _stored(
                        record.response_json, "business_terminal", BusinessTerminalResource
                    )
                duplicate = db.scalar(
                    select(BusinessTerminal.business_terminal_id).where(
                        BusinessTerminal.project_id == environment.project_id,
                        BusinessTerminal.terminal_code == body.terminal_code,
                    )
                )
                if duplicate is not None:
                    raise _code_conflict()
                now = utc_now()
                terminal = BusinessTerminal(
                    business_terminal_id=new_ulid(),
                    project_id=environment.project_id,
                    environment_id=environment.environment_id,
                    terminal_code=body.terminal_code,
                    terminal_type=body.terminal_type,
                    current_published_revision_id=None,
                    lifecycle_status="CREATED",
                    display_name=body.display_name,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                db.add(terminal)
                db.flush()
                terminal.lifecycle_status = "CONFIGURING"
                terminal.row_version = 1
                terminal.updated_at = utc_now()
                self._audit(
                    db,
                    terminal,
                    actor.user.user_id,
                    context,
                    "BUSINESS_TERMINAL_CREATED",
                    "create_business_terminal",
                    "CREATED",
                    None,
                    _terminal_projection(terminal),
                    body.reason,
                    "BUSINESS_TERMINAL_CREATE",
                )
                self._event(
                    db,
                    terminal.business_terminal_id,
                    terminal.project_id,
                    "business_terminal.configuring",
                    actor.user.user_id,
                    context,
                    key,
                    "CREATED",
                    "CONFIGURING",
                    0,
                    1,
                    {"lifecycle_path": ["CREATED", "CONFIGURING"]},
                )
                resource = _terminal_resource(terminal)
                self._idempotency.complete(
                    record, 201, {"business_terminal": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _integrity_error(error) from error

    def list_terminals(
        self,
        token: str,
        page: int,
        page_size: int,
        filter_value: str | None,
        context: AuditContext,
    ) -> BusinessTerminalListData:
        filters = _parse_filter(
            filter_value, {"project_id", "environment_id", "terminal_type", "lifecycle_status"}
        )
        project_id = filters.get("project_id")
        if project_id is None:
            raise _scope_required("Business Terminal")
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_business_terminal", context
            )
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "list_business_terminal",
                ("BUSINESS_TERMINAL_VIEW",),
                project_id,
                context,
            )
            query = select(BusinessTerminal).where(BusinessTerminal.project_id == project_id)
            count = select(func.count(BusinessTerminal.business_terminal_id)).where(
                BusinessTerminal.project_id == project_id
            )
            for key, column in {
                "environment_id": BusinessTerminal.environment_id,
                "terminal_type": BusinessTerminal.terminal_type,
                "lifecycle_status": BusinessTerminal.lifecycle_status,
            }.items():
                if filters.get(key):
                    query = query.where(column == filters[key])
                    count = count.where(column == filters[key])
            items = list(
                db.scalars(
                    query.order_by(BusinessTerminal.terminal_code)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return BusinessTerminalListData(
                items=[_terminal_resource(item) for item in items],
                page=PageMeta(page=page, page_size=page_size, total=int(db.scalar(count) or 0)),
            )

    def get_terminal(
        self, token: str, terminal_id: str, context: AuditContext
    ) -> BusinessTerminalResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_business_terminal", context
            )
            terminal = db.get(BusinessTerminal, terminal_id)
            if terminal is None:
                raise _not_found()
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "get_business_terminal",
                ("BUSINESS_TERMINAL_VIEW",),
                terminal.project_id,
                context,
            )
            return _terminal_resource(terminal)

    def update_terminal(
        self,
        token: str,
        terminal_id: str,
        body: UpdateBusinessTerminalRequest,
        key: str,
        context: AuditContext,
    ) -> BusinessTerminalResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "update_business_terminal", context
            )
            terminal = db.scalar(
                select(BusinessTerminal)
                .where(BusinessTerminal.business_terminal_id == terminal_id)
                .with_for_update()
            )
            if terminal is None:
                raise _not_found()
            environment = db.scalar(
                select(Environment)
                .where(Environment.environment_id == terminal.environment_id)
                .with_for_update()
            )
            _assert_environment_member_change(environment, terminal)
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "update_business_terminal",
                ("BUSINESS_TERMINAL_EDIT",),
                terminal.project_id,
                context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "update_business_terminal",
                key,
                _payload(body, terminal_id),
            )
            if replay:
                return _stored(record.response_json, "business_terminal", BusinessTerminalResource)
            _check_version(terminal.row_version, body.expected_version)
            if terminal.lifecycle_status == "ARCHIVED":
                raise _state_error("Archived terminals are immutable.")
            if body.display_name == terminal.display_name:
                raise PlatformError(
                    title="No terminal changes",
                    detail="The update has no effect.",
                    status=409,
                    code="BUSINESS_TERMINAL_UPDATE_NO_EFFECT",
                )
            before = _terminal_projection(terminal)
            terminal.display_name = body.display_name
            terminal.row_version += 1
            terminal.updated_at = utc_now()
            terminal.updated_by = actor.user.user_id
            self._audit(
                db,
                terminal,
                actor.user.user_id,
                context,
                "BUSINESS_TERMINAL_UPDATED",
                "update_business_terminal",
                terminal.lifecycle_status,
                before,
                _terminal_projection(terminal),
                body.reason,
                "BUSINESS_TERMINAL_EDIT",
            )
            resource = _terminal_resource(terminal)
            self._idempotency.complete(
                record, 200, {"business_terminal": resource.model_dump(mode="json")}
            )
            return resource

    def transition_terminal(
        self,
        token: str,
        terminal_id: str,
        action: str,
        body: LifecycleCommandRequest,
        key: str,
        context: AuditContext,
    ) -> BusinessTerminalResource:
        if action not in _TERMINAL_TRANSITIONS:
            raise _state_error("Unknown terminal lifecycle command.")
        allowed, target, event_type = _TERMINAL_TRANSITIONS[action]
        permission = (
            "BUSINESS_TERMINAL_ARCHIVE" if action == "archive" else "BUSINESS_TERMINAL_EDIT"
        )
        operation_id = f"{action.replace('-', '_')}_business_terminal"
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, operation_id, context
            )
            terminal = db.scalar(
                select(BusinessTerminal)
                .where(BusinessTerminal.business_terminal_id == terminal_id)
                .with_for_update()
            )
            if terminal is None:
                raise _not_found()
            environment = db.scalar(
                select(Environment)
                .where(Environment.environment_id == terminal.environment_id)
                .with_for_update()
            )
            _assert_environment_member_change(
                environment, terminal, require_active=action == "activate"
            )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, operation_id, (permission,), terminal.project_id, context
            )
            record, replay = self._claim(
                db, actor.user.user_id, operation_id, key, _payload(body, terminal_id)
            )
            if replay:
                return _stored(record.response_json, "business_terminal", BusinessTerminalResource)
            _check_version(terminal.row_version, body.expected_version)
            if terminal.lifecycle_status not in allowed:
                raise _state_error(f"{action} is not allowed from {terminal.lifecycle_status}.")
            if action == "activate" and terminal.current_published_revision_id is None:
                raise _state_error("Activation requires a published terminal access revision.")
            previous = terminal.lifecycle_status
            before = _terminal_projection(terminal)
            terminal.lifecycle_status = target
            terminal.row_version += 1
            terminal.updated_at = utc_now()
            terminal.updated_by = actor.user.user_id
            self._audit(
                db,
                terminal,
                actor.user.user_id,
                context,
                f"BUSINESS_TERMINAL_{target}",
                operation_id,
                previous,
                before,
                _terminal_projection(terminal),
                body.reason,
                permission,
            )
            self._event(
                db,
                terminal.business_terminal_id,
                terminal.project_id,
                event_type,
                actor.user.user_id,
                context,
                key,
                previous,
                target,
                body.expected_version,
                terminal.row_version,
                {"reason_supplied": True},
            )
            resource = _terminal_resource(terminal)
            self._idempotency.complete(
                record, 200, {"business_terminal": resource.model_dump(mode="json")}
            )
            return resource

    def create_revision(
        self,
        token: str,
        body: CreateTerminalAccessRevisionRequest,
        key: str,
        context: AuditContext,
    ) -> TerminalAccessRevisionResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "create_environment_terminal_access_revision", context
            )
            terminal = db.scalar(
                select(BusinessTerminal)
                .where(BusinessTerminal.business_terminal_id == body.business_terminal_id)
                .with_for_update()
            )
            if terminal is None:
                raise _not_found()
            environment = db.scalar(
                select(Environment)
                .where(Environment.environment_id == terminal.environment_id)
                .with_for_update()
            )
            _assert_environment_member_change(environment, terminal)
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "create_environment_terminal_access_revision",
                ("BUSINESS_TERMINAL_EDIT",),
                terminal.project_id,
                context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "create_environment_terminal_access_revision",
                key,
                _payload(body),
            )
            if replay:
                return _stored(
                    record.response_json, "terminal_access_revision", TerminalAccessRevisionResource
                )
            if terminal.lifecycle_status == "ARCHIVED":
                raise _state_error("Archived terminals cannot receive new revisions.")
            if body.login_strategy_id:
                _require_active_login_strategy(
                    db, body.login_strategy_id, terminal.project_id, "Creating"
                )
            revision_no = (
                int(
                    db.scalar(
                        select(func.max(TerminalAccessRevision.revision_no)).where(
                            TerminalAccessRevision.business_terminal_id
                            == terminal.business_terminal_id
                        )
                    )
                    or 0
                )
                + 1
            )
            now = utc_now()
            revision = TerminalAccessRevision(
                environment_terminal_access_revision_id=new_ulid(),
                project_id=terminal.project_id,
                environment_id=terminal.environment_id,
                business_terminal_id=terminal.business_terminal_id,
                revision_no=revision_no,
                entry_url=body.entry_url,
                login_url=body.login_url,
                login_strategy_id=body.login_strategy_id,
                login_prerequisites=body.login_prerequisites,
                network_requirements=body.network_requirements,
                lifecycle_status="DRAFT",
                published_at=None,
                display_name=body.display_name,
                row_version=1,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json=None,
            )
            db.add(revision)
            db.flush()
            self._audit(
                db,
                terminal,
                actor.user.user_id,
                context,
                "TERMINAL_ACCESS_REVISION_CREATED",
                "create_environment_terminal_access_revision",
                None,
                None,
                {
                    "revision_id": revision.environment_terminal_access_revision_id,
                    "revision_no": revision.revision_no,
                    "status": "DRAFT",
                },
                body.reason,
                "BUSINESS_TERMINAL_EDIT",
                new_status="DRAFT",
            )
            self._event(
                db,
                revision.environment_terminal_access_revision_id,
                terminal.project_id,
                "environment_terminal_access_revision.draft",
                actor.user.user_id,
                context,
                key,
                None,
                "DRAFT",
                0,
                1,
                {
                    "revision_id": revision.environment_terminal_access_revision_id,
                    "revision_no": revision.revision_no,
                },
                identity_field="environment_terminal_access_revision_id",
            )
            resource = _revision_resource(revision)
            self._idempotency.complete(
                record, 201, {"terminal_access_revision": resource.model_dump(mode="json")}
            )
            return resource

    def list_revisions(
        self,
        token: str,
        page: int,
        page_size: int,
        filter_value: str | None,
        context: AuditContext,
    ) -> TerminalAccessRevisionListData:
        filters = _parse_filter(filter_value, {"business_terminal_id", "lifecycle_status"})
        terminal_id = filters.get("business_terminal_id")
        if terminal_id is None:
            raise _scope_required("Terminal Access Revision")
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_environment_terminal_access_revision", context
            )
            terminal = db.get(BusinessTerminal, terminal_id)
            if terminal is None:
                raise _not_found()
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "list_environment_terminal_access_revision",
                ("BUSINESS_TERMINAL_VIEW",),
                terminal.project_id,
                context,
            )
            query = select(TerminalAccessRevision).where(
                TerminalAccessRevision.business_terminal_id == terminal_id
            )
            count = select(
                func.count(TerminalAccessRevision.environment_terminal_access_revision_id)
            ).where(TerminalAccessRevision.business_terminal_id == terminal_id)
            if filters.get("lifecycle_status"):
                query = query.where(
                    TerminalAccessRevision.lifecycle_status == filters["lifecycle_status"]
                )
                count = count.where(
                    TerminalAccessRevision.lifecycle_status == filters["lifecycle_status"]
                )
            items = list(
                db.scalars(
                    query.order_by(TerminalAccessRevision.revision_no.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return TerminalAccessRevisionListData(
                items=[_revision_resource(item) for item in items],
                page=PageMeta(page=page, page_size=page_size, total=int(db.scalar(count) or 0)),
            )

    def get_revision(
        self, token: str, revision_id: str, context: AuditContext
    ) -> TerminalAccessRevisionResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_environment_terminal_access_revision", context
            )
            revision = db.get(TerminalAccessRevision, revision_id)
            if revision is None:
                raise _revision_not_found()
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "get_environment_terminal_access_revision",
                ("BUSINESS_TERMINAL_VIEW",),
                revision.project_id,
                context,
            )
            return _revision_resource(revision)

    def update_revision(
        self,
        token: str,
        revision_id: str,
        body: UpdateTerminalAccessRevisionRequest,
        key: str,
        context: AuditContext,
    ) -> TerminalAccessRevisionResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "update_environment_terminal_access_revision", context
            )
            revision = db.scalar(
                select(TerminalAccessRevision)
                .where(
                    TerminalAccessRevision.environment_terminal_access_revision_id == revision_id
                )
                .with_for_update()
            )
            if revision is None:
                raise _revision_not_found()
            terminal = db.scalar(
                select(BusinessTerminal)
                .where(BusinessTerminal.business_terminal_id == revision.business_terminal_id)
                .with_for_update()
            )
            if terminal is None:
                raise _not_found()
            environment = db.scalar(
                select(Environment)
                .where(Environment.environment_id == terminal.environment_id)
                .with_for_update()
            )
            _assert_environment_member_change(environment, terminal)
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "update_environment_terminal_access_revision",
                ("BUSINESS_TERMINAL_EDIT",),
                terminal.project_id,
                context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "update_environment_terminal_access_revision",
                key,
                _payload(body, revision_id),
            )
            if replay:
                return _stored(
                    record.response_json, "terminal_access_revision", TerminalAccessRevisionResource
                )
            _check_version(revision.row_version, body.expected_version)
            _assert_revision_draft_mutable(revision, "edited")
            fields = body.model_fields_set - {"expected_version", "reason"}
            if "login_strategy_id" in fields and body.login_strategy_id is not None:
                _require_active_login_strategy(
                    db, body.login_strategy_id, terminal.project_id, "Updating"
                )
            before = _revision_projection(revision)
            for name in (
                "entry_url",
                "login_url",
                "login_strategy_id",
                "login_prerequisites",
                "network_requirements",
                "display_name",
            ):
                if name in fields:
                    setattr(revision, name, getattr(body, name))
            revision.row_version += 1
            revision.updated_at = utc_now()
            revision.updated_by = actor.user.user_id
            after = _revision_projection(revision)
            self._audit(
                db,
                terminal,
                actor.user.user_id,
                context,
                "TERMINAL_ACCESS_REVISION_UPDATED",
                "update_environment_terminal_access_revision",
                "DRAFT",
                before,
                after,
                body.reason,
                "BUSINESS_TERMINAL_EDIT",
                new_status="DRAFT",
            )
            self._event(
                db,
                revision_id,
                terminal.project_id,
                "environment_terminal_access_revision.updated",
                actor.user.user_id,
                context,
                key,
                "DRAFT",
                "DRAFT",
                body.expected_version,
                revision.row_version,
                {"revision_no": revision.revision_no, "changed_fields": sorted(fields)},
                identity_field="environment_terminal_access_revision_id",
            )
            resource = _revision_resource(revision)
            self._idempotency.complete(
                record, 200, {"terminal_access_revision": resource.model_dump(mode="json")}
            )
            return resource

    def abandon_revision(
        self,
        token: str,
        revision_id: str,
        body: LifecycleCommandRequest,
        key: str,
        context: AuditContext,
    ) -> TerminalAccessRevisionResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "abandon_environment_terminal_access_revision", context
                )
                record, replay = self._claim(
                    db,
                    actor.user.user_id,
                    "abandon_environment_terminal_access_revision",
                    key,
                    _payload(body, revision_id),
                )
                if replay:
                    return _stored(
                        record.response_json,
                        "terminal_access_revision",
                        TerminalAccessRevisionResource,
                    )
                revision = db.scalar(
                    select(TerminalAccessRevision)
                    .where(
                        TerminalAccessRevision.environment_terminal_access_revision_id
                        == revision_id
                    )
                    .with_for_update()
                )
                if revision is None:
                    raise _revision_not_found()
                terminal = db.scalar(
                    select(BusinessTerminal)
                    .where(BusinessTerminal.business_terminal_id == revision.business_terminal_id)
                    .with_for_update()
                )
                if terminal is None:
                    raise _not_found()
                environment = db.scalar(
                    select(Environment)
                    .where(Environment.environment_id == terminal.environment_id)
                    .with_for_update()
                )
                _assert_environment_member_change(environment, terminal)
                self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "abandon_environment_terminal_access_revision",
                    ("BUSINESS_TERMINAL_EDIT",),
                    terminal.project_id,
                    context,
                )
                _check_version(revision.row_version, body.expected_version)
                _assert_revision_draft_mutable(revision, "abandoned")
                if terminal.current_published_revision_id == revision_id or db.scalar(
                    select(ExecutionBindingSnapshot.execution_binding_snapshot_id).where(
                        ExecutionBindingSnapshot.terminal_access_revision_id == revision_id
                    )
                ):
                    raise _revision_reference_conflict()
                resource = _revision_resource(revision)
                self._audit(
                    db,
                    terminal,
                    actor.user.user_id,
                    context,
                    "TERMINAL_ACCESS_REVISION_ABANDONED",
                    "abandon_environment_terminal_access_revision",
                    "DRAFT",
                    _revision_projection(revision),
                    {"revision_id": revision_id, "command_result": "ABANDONED"},
                    body.reason,
                    "BUSINESS_TERMINAL_EDIT",
                    new_status="ABANDONED",
                )
                self._event(
                    db,
                    revision_id,
                    terminal.project_id,
                    "environment_terminal_access_revision.abandoned",
                    actor.user.user_id,
                    context,
                    key,
                    "DRAFT",
                    "ABANDONED",
                    body.expected_version,
                    body.expected_version,
                    {"revision_no": revision.revision_no, "physical_delete": True},
                    identity_field="environment_terminal_access_revision_id",
                )
                db.delete(revision)
                db.flush()
                self._idempotency.complete(
                    record, 200, {"terminal_access_revision": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _revision_reference_conflict() from error

    def validate_revision(
        self,
        token: str,
        revision_id: str,
        body: LifecycleCommandRequest,
        key: str,
        context: AuditContext,
    ) -> TerminalAccessRevisionResource:
        return self._transition_revision(
            token, revision_id, body, key, context, "DRAFT", "VALIDATING", "validate"
        )

    def return_revision_to_draft(
        self,
        token: str,
        revision_id: str,
        body: LifecycleCommandRequest,
        key: str,
        context: AuditContext,
    ) -> TerminalAccessRevisionResource:
        return self._transition_revision(
            token,
            revision_id,
            body,
            key,
            context,
            "VALIDATING",
            "DRAFT",
            "return_to_draft",
        )

    def publish_revision(
        self,
        token: str,
        revision_id: str,
        body: PublishTerminalAccessRevisionRequest,
        key: str,
        context: AuditContext,
    ) -> TerminalAccessRevisionResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "publish_environment_terminal_access_revision", context
            )
            revision = db.scalar(
                select(TerminalAccessRevision)
                .where(
                    TerminalAccessRevision.environment_terminal_access_revision_id == revision_id
                )
                .with_for_update()
            )
            if revision is None:
                raise _revision_not_found()
            terminal = db.scalar(
                select(BusinessTerminal)
                .where(BusinessTerminal.business_terminal_id == revision.business_terminal_id)
                .with_for_update()
            )
            if terminal is None:
                raise _not_found()
            environment = db.scalar(
                select(Environment)
                .where(Environment.environment_id == terminal.environment_id)
                .with_for_update()
            )
            _assert_environment_member_change(environment, terminal)
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "publish_environment_terminal_access_revision",
                ("BUSINESS_TERMINAL_EDIT",),
                terminal.project_id,
                context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "publish_environment_terminal_access_revision",
                key,
                _payload(body, revision_id),
            )
            if replay:
                return _stored(
                    record.response_json, "terminal_access_revision", TerminalAccessRevisionResource
                )
            _check_version(revision.row_version, body.expected_version)
            _check_version(terminal.row_version, body.expected_terminal_version)
            if revision.lifecycle_status != "VALIDATING":
                raise _revision_state_error("Only VALIDATING revisions can be published.")
            if revision.login_strategy_id:
                _require_active_login_strategy(
                    db, revision.login_strategy_id, terminal.project_id, "Publishing"
                )
            previous_pointer = terminal.current_published_revision_id
            if previous_pointer:
                previous = db.scalar(
                    select(TerminalAccessRevision)
                    .where(
                        TerminalAccessRevision.environment_terminal_access_revision_id
                        == previous_pointer
                    )
                    .with_for_update()
                )
                if previous is not None and previous.lifecycle_status == "PUBLISHED":
                    previous_expected_version = previous.row_version
                    previous_before = _revision_projection(previous)
                    previous.lifecycle_status = "SUPERSEDED"
                    previous.row_version += 1
                    previous.updated_at = utc_now()
                    previous.updated_by = actor.user.user_id
                    previous_after = _revision_projection(previous)
                    self._audit(
                        db,
                        terminal,
                        actor.user.user_id,
                        context,
                        "TERMINAL_ACCESS_REVISION_SUPERSEDED",
                        "publish_environment_terminal_access_revision",
                        "PUBLISHED",
                        previous_before,
                        previous_after,
                        body.reason,
                        "BUSINESS_TERMINAL_EDIT",
                        new_status="SUPERSEDED",
                    )
                    self._event(
                        db,
                        previous.environment_terminal_access_revision_id,
                        terminal.project_id,
                        "environment_terminal_access_revision.superseded",
                        actor.user.user_id,
                        context,
                        key,
                        "PUBLISHED",
                        "SUPERSEDED",
                        previous_expected_version,
                        previous.row_version,
                        {
                            "revision_id": previous.environment_terminal_access_revision_id,
                            "revision_no": previous.revision_no,
                            "superseded_by_revision_id": revision_id,
                        },
                        identity_field="environment_terminal_access_revision_id",
                    )
            revision.lifecycle_status = "PUBLISHED"
            revision.published_at = utc_now()
            revision.row_version += 1
            revision.updated_at = utc_now()
            revision.updated_by = actor.user.user_id
            before = _terminal_projection(terminal)
            terminal.current_published_revision_id = revision_id
            terminal.row_version += 1
            terminal.updated_at = utc_now()
            terminal.updated_by = actor.user.user_id
            self._audit(
                db,
                terminal,
                actor.user.user_id,
                context,
                "TERMINAL_ACCESS_REVISION_PUBLISHED",
                "publish_environment_terminal_access_revision",
                "VALIDATING",
                before,
                _terminal_projection(terminal),
                body.reason,
                "BUSINESS_TERMINAL_EDIT",
                new_status="PUBLISHED",
            )
            self._event(
                db,
                revision.environment_terminal_access_revision_id,
                terminal.project_id,
                "environment_terminal_access_revision.published",
                actor.user.user_id,
                context,
                key,
                "VALIDATING",
                "PUBLISHED",
                body.expected_version,
                revision.row_version,
                {
                    "revision_id": revision_id,
                    "revision_no": revision.revision_no,
                    "previous_revision_id": previous_pointer,
                },
                identity_field="environment_terminal_access_revision_id",
            )
            resource = _revision_resource(revision)
            self._idempotency.complete(
                record, 200, {"terminal_access_revision": resource.model_dump(mode="json")}
            )
            return resource

    def _transition_revision(
        self,
        token: str,
        revision_id: str,
        body: LifecycleCommandRequest,
        key: str,
        context: AuditContext,
        source: str,
        target: str,
        action: str,
    ) -> TerminalAccessRevisionResource:
        operation_id = f"{action}_environment_terminal_access_revision"
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, operation_id, context
            )
            revision = db.scalar(
                select(TerminalAccessRevision)
                .where(
                    TerminalAccessRevision.environment_terminal_access_revision_id == revision_id
                )
                .with_for_update()
            )
            if revision is None:
                raise _revision_not_found()
            terminal = db.get(BusinessTerminal, revision.business_terminal_id)
            if terminal is None:
                raise _not_found()
            environment = db.scalar(
                select(Environment)
                .where(Environment.environment_id == terminal.environment_id)
                .with_for_update()
            )
            _assert_environment_member_change(environment, terminal)
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                operation_id,
                ("BUSINESS_TERMINAL_EDIT",),
                terminal.project_id,
                context,
            )
            record, replay = self._claim(
                db, actor.user.user_id, operation_id, key, _payload(body, revision_id)
            )
            if replay:
                return _stored(
                    record.response_json, "terminal_access_revision", TerminalAccessRevisionResource
                )
            _check_version(revision.row_version, body.expected_version)
            if revision.lifecycle_status != source:
                raise _revision_state_error(
                    f"{action} is not allowed from {revision.lifecycle_status}."
                )
            if action == "validate" and revision.login_strategy_id:
                _require_active_login_strategy(
                    db, revision.login_strategy_id, terminal.project_id, "Validating"
                )
            revision.lifecycle_status = target
            revision.row_version += 1
            revision.updated_at = utc_now()
            revision.updated_by = actor.user.user_id
            self._audit(
                db,
                terminal,
                actor.user.user_id,
                context,
                f"TERMINAL_ACCESS_REVISION_{target}",
                operation_id,
                source,
                {"revision_id": revision_id, "status": source},
                {"revision_id": revision_id, "status": target},
                body.reason,
                "BUSINESS_TERMINAL_EDIT",
                new_status=target,
            )
            self._event(
                db,
                revision.environment_terminal_access_revision_id,
                terminal.project_id,
                f"environment_terminal_access_revision.{target.lower()}",
                actor.user.user_id,
                context,
                key,
                source,
                target,
                body.expected_version,
                revision.row_version,
                {"revision_id": revision_id, "revision_no": revision.revision_no},
                identity_field="environment_terminal_access_revision_id",
            )
            resource = _revision_resource(revision)
            self._idempotency.complete(
                record, 200, {"terminal_access_revision": resource.model_dump(mode="json")}
            )
            return resource

    def _claim(
        self, db: Session, principal: str, operation: str, key: str, payload: bytes
    ) -> tuple[IdempotencyRecord, bool]:
        return self._idempotency.claim(db, principal, operation, key, payload)

    @staticmethod
    def _audit(
        db: Session,
        terminal: BusinessTerminal,
        actor: str,
        context: AuditContext,
        action: str,
        operation: str,
        previous_status: str | None,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
        reason: str | None,
        permission: str,
        *,
        new_status: str | None = None,
    ) -> None:
        db.add(
            BusinessTerminalAudit(
                audit_id=new_ulid(),
                business_terminal_id=terminal.business_terminal_id,
                environment_id=terminal.environment_id,
                project_id=terminal.project_id,
                action=action,
                operation_id=operation,
                actor_user_id=actor,
                required_permission=permission,
                previous_status=previous_status,
                new_status=new_status if new_status is not None else terminal.lifecycle_status,
                result_code="SUCCESS",
                reason=reason,
                before_json=before,
                after_json=after,
                correlation_id=context.correlation_id,
                occurred_at=utc_now(),
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
            )
        )

    @staticmethod
    def _event(
        db: Session,
        aggregate_id: str,
        project_id: str,
        event_type: str,
        actor: str,
        context: AuditContext,
        causation_id: str,
        from_state: str | None,
        to_state: str,
        expected_version: int,
        new_version: int,
        summary: dict[str, object],
        *,
        identity_field: str = "business_terminal_id",
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
                    "payload": {
                        identity_field: aggregate_id,
                        "project_id": project_id,
                        "from_state": from_state,
                        "to_state": to_state,
                        "expected_version": expected_version,
                        "new_version": new_version,
                        "changed_by": actor,
                        "change_summary": summary,
                    },
                },
                occurred_at=occurred_at,
                published_at=None,
                attempt_count=0,
            )
        )


def _terminal_resource(value: BusinessTerminal) -> BusinessTerminalResource:
    return BusinessTerminalResource(
        business_terminal_id=value.business_terminal_id,
        project_id=value.project_id,
        environment_id=value.environment_id,
        terminal_code=value.terminal_code,
        display_name=value.display_name,
        terminal_type=value.terminal_type,
        current_published_revision_id=value.current_published_revision_id,
        lifecycle_status=value.lifecycle_status,
        row_version=value.row_version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _terminal_projection(value: BusinessTerminal) -> dict[str, object]:
    return _terminal_resource(value).model_dump(mode="json", exclude={"created_at", "updated_at"})


def _revision_projection(value: TerminalAccessRevision) -> dict[str, object]:
    return {
        "environment_terminal_access_revision_id": (
            value.environment_terminal_access_revision_id
        ),
        "business_terminal_id": value.business_terminal_id,
        "project_id": value.project_id,
        "environment_id": value.environment_id,
        "revision_no": value.revision_no,
        "login_strategy_id": value.login_strategy_id,
        "lifecycle_status": value.lifecycle_status,
        "published_at": value.published_at.isoformat() if value.published_at else None,
        "row_version": value.row_version,
    }


def _revision_resource(value: TerminalAccessRevision) -> TerminalAccessRevisionResource:
    return TerminalAccessRevisionResource(
        environment_terminal_access_revision_id=value.environment_terminal_access_revision_id,
        project_id=value.project_id,
        environment_id=value.environment_id,
        business_terminal_id=value.business_terminal_id,
        revision_no=value.revision_no,
        entry_url=value.entry_url,
        login_url=value.login_url,
        login_strategy_id=value.login_strategy_id,
        login_prerequisites=value.login_prerequisites,
        network_requirements=value.network_requirements,
        display_name=value.display_name,
        lifecycle_status=value.lifecycle_status,
        published_at=value.published_at,
        row_version=value.row_version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    value = body.model_dump(mode="json", exclude_none=False)
    if resource_id:
        value["resource_id"] = resource_id
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _stored[ResourceModel: BaseModel](
    value: dict[str, object] | None,
    key: str,
    model: type[ResourceModel],
) -> ResourceModel:
    if not isinstance(value, dict) or not isinstance(value.get(key), dict):
        raise RuntimeError("terminal idempotency projection is invalid")
    return model.model_validate(value[key])


def _parse_filter(value: str | None, allowed: set[str]) -> dict[str, str]:
    if not value:
        return {}
    result: dict[str, str] = {}
    for item in value.split(";"):
        key, separator, field_value = item.partition("=")
        if not separator or key not in allowed or not field_value:
            raise PlatformError(
                title="Terminal filter is invalid",
                detail="Use declared semicolon-separated key=value filters.",
                status=400,
                code="BUSINESS_TERMINAL_FILTER_INVALID",
            )
        result[key] = field_value
    return result


def _check_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise PlatformError(
            title="Concurrent terminal update",
            detail="The resource changed; refresh and retry.",
            status=409,
            code="BUSINESS_TERMINAL_CONCURRENCY_CONFLICT",
        )


def _assert_environment_member_change(
    environment: Environment | None,
    terminal: BusinessTerminal,
    *,
    require_active: bool = False,
) -> None:
    if (
        environment is None
        or environment.project_id != terminal.project_id
        or environment.environment_id != terminal.environment_id
    ):
        raise _state_error("The owning Environment aggregate is unavailable or out of scope.")
    if require_active and environment.lifecycle_status != "ACTIVE":
        raise _state_error("The owning Environment must be ACTIVE for this command.")
    if environment.lifecycle_status in {"ARCHIVED", "LOGICALLY_DELETED"}:
        raise _state_error("The owning Environment does not allow member changes.")


def _not_found() -> PlatformError:
    return PlatformError(
        title="Business Terminal not found",
        detail="The Business Terminal is unavailable in this scope.",
        status=404,
        code="BUSINESS_TERMINAL_NOT_FOUND",
    )


def _revision_not_found() -> PlatformError:
    return PlatformError(
        title="Terminal Access Revision not found",
        detail="The revision is unavailable in this scope.",
        status=404,
        code="TERMINAL_ACCESS_REVISION_NOT_FOUND",
    )


def _scope_required(resource: str) -> PlatformError:
    return PlatformError(
        title="Project scope is required",
        detail=f"{resource} list requests require an explicit owner filter.",
        status=400,
        code="BUSINESS_TERMINAL_PROJECT_SCOPE_REQUIRED",
    )


def _state_error(detail: str) -> PlatformError:
    return PlatformError(
        title="Business Terminal operation is forbidden for its state",
        detail=detail,
        status=409,
        code="BUSINESS_TERMINAL_OPERATION_FORBIDDEN_FOR_STATE",
    )


def _revision_state_error(detail: str) -> PlatformError:
    return PlatformError(
        title="Terminal Access Revision operation is forbidden for its state",
        detail=detail,
        status=409,
        code="TERMINAL_ACCESS_REVISION_OPERATION_FORBIDDEN_FOR_STATE",
    )


def _assert_revision_draft_mutable(revision: TerminalAccessRevision, action: str) -> None:
    if revision.lifecycle_status != "DRAFT" or revision.published_at is not None:
        raise _revision_state_error(
            f"Only never-published DRAFT revisions can be {action}."
        )


def _revision_reference_conflict() -> PlatformError:
    return PlatformError(
        title="Terminal Access Revision is referenced",
        detail="A referenced or published Terminal Access Revision cannot be abandoned.",
        status=409,
        code="TERMINAL_ACCESS_REVISION_REFERENCE_CONFLICT",
    )


def _require_active_login_strategy(
    db: Session, strategy_id: str, project_id: str, action: str
) -> LoginStrategy:
    strategy = db.get(LoginStrategy, strategy_id)
    if (
        strategy is None
        or strategy.project_id != project_id
        or strategy.lifecycle_status != "ACTIVE"
    ):
        raise _revision_state_error(
            f"{action} requires an ACTIVE in-scope Login Strategy."
        )
    return strategy


def _code_conflict() -> PlatformError:
    return PlatformError(
        title="Business Terminal code conflict",
        detail="terminal_code must be unique within the target project.",
        status=409,
        code="BUSINESS_TERMINAL_CODE_CONFLICT",
    )


def _integrity_error(error: IntegrityError) -> PlatformError:
    args = list(getattr(error.orig, "args", ()))
    message = str(args[1]) if len(args) > 1 else ""
    if args and args[0] == 1062 and "uq_atp_business_terminal_business" in message:
        return _code_conflict()
    return PlatformError(
        title="Internal server error",
        detail="The Business Terminal command could not be completed.",
        status=500,
        code="INTERNAL_ERROR",
    )
