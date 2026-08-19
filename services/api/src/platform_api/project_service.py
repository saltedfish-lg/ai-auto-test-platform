"""Transactional service for the Project aggregate foundation."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticationService
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    IdempotencyRecord,
    OutboxEvent,
    PlatformUser,
    Project,
    ProjectAudit,
    ProjectMember,
    Role,
)
from platform_api.project_schemas import (
    CreateProjectRequest,
    PageMeta,
    ProjectListData,
    ProjectOwnerResource,
    ProjectResource,
    ProjectStateCommandRequest,
    UpdateProjectRequest,
)
from platform_api.security import new_ulid, utc_now

ACTIVE = "ACTIVE"
OWNER_ROLE_CODE = "ROLE-PROJECT-OWNER-DUTY"


class ProjectService:
    """Own Project writes, membership initialization, evidence and event publication."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def create_project(
        self,
        token: str,
        body: CreateProjectRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> ProjectResource:
        """Atomically initialize CREATED→CONFIGURING→VALIDATING→ACTIVE."""
        actor_user_id: str | None = None
        project_id: str | None = None
        owner_user_id = body.owner_user_id
        audited_participant_user_id: str | None = None
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "create_project", audit_context
                )
                actor_user_id = actor.user.user_id
                self._authentication.require_platform_permissions_in_transaction(
                    db, actor, "create_project", ("PROJECT_CREATE",), audit_context
                )
                record, replay = self._claim_idempotency(
                    db,
                    actor.user.user_id,
                    "create_project",
                    idempotency_key,
                    _canonical_payload(body),
                )
                if replay:
                    return _stored_project(record.response_json)

                owner_user_id = body.owner_user_id or actor.user.user_id
                if (
                    db.scalar(
                        select(Project.project_id).where(Project.project_code == body.project_code)
                    )
                    is not None
                ):
                    raise _project_code_conflict()

                owner = db.scalar(
                    select(PlatformUser)
                    .where(PlatformUser.user_id == owner_user_id)
                    .with_for_update()
                )
                if owner is None:
                    raise _owner_ineligible(
                        "The designated owner does not exist or is unavailable."
                    )
                audited_participant_user_id = owner_user_id
                if owner.lifecycle_status != ACTIVE:
                    raise _owner_ineligible("The designated owner is not an ACTIVE user.")
                if not self._authentication.user_has_permission_qualification_in_transaction(
                    db, owner_user_id, "PROJECT_OWNER_ELIGIBLE"
                ):
                    raise _owner_ineligible(
                        "The designated owner does not have PROJECT_OWNER_ELIGIBLE."
                    )
                owner_role = db.scalar(
                    select(Role)
                    .where(
                        Role.role_code == OWNER_ROLE_CODE,
                        Role.lifecycle_status == ACTIVE,
                    )
                    .with_for_update()
                )
                if owner_role is None:
                    raise _configuration_error("The Project Owner duty role is unavailable.")

                now = utc_now()
                project = Project(
                    project_id=new_ulid(),
                    project_code=body.project_code,
                    lifecycle_status="CREATED",
                    display_name=body.display_name,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                project_id = project.project_id
                db.add(project)
                db.flush()

                # Intermediate states are real writes inside the one local transaction,
                # but never become externally visible if any later validation fails.
                project.lifecycle_status = "CONFIGURING"
                project.row_version += 1
                db.flush()
                project.lifecycle_status = "VALIDATING"
                project.row_version += 1
                db.flush()

                member = ProjectMember(
                    project_member_id=new_ulid(),
                    project_id=project.project_id,
                    user_id=owner_user_id,
                    role_id=owner_role.role_id,
                    lifecycle_status=ACTIVE,
                    display_name=owner.display_name,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                db.add(member)
                db.flush()
                project.lifecycle_status = ACTIVE
                project.row_version += 1
                project.updated_at = utc_now()
                db.flush()

                self._append_audit(
                    db,
                    project,
                    audit_context,
                    action="PROJECT_CREATED",
                    operation_id="create_project",
                    actor_user_id=actor.user.user_id,
                    participant_user_id=audited_participant_user_id,
                    required_permission="PROJECT_CREATE",
                    scope_decision="NOT_APPLICABLE",
                    previous_status="CREATED",
                    new_status=ACTIVE,
                    reason=body.reason,
                )
                self._append_event(
                    db,
                    project,
                    "project.created",
                    sequence=1,
                    actor_user_id=actor.user.user_id,
                    payload={
                        "project_code": project.project_code,
                        "owner_user_id": owner_user_id,
                        "lifecycle_path": [
                            "CREATED",
                            "CONFIGURING",
                            "VALIDATING",
                            "ACTIVE",
                        ],
                    },
                )
                self._append_event(
                    db,
                    project,
                    "project.active",
                    sequence=2,
                    actor_user_id=actor.user.user_id,
                    payload={"source": "ATOMIC_INITIALIZATION"},
                )
                resource = self._project_resource(db, project)
                self._idempotency.complete(
                    record, 201, {"project": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            failure = _project_integrity_error(error)
            if actor_user_id is not None:
                self._append_failed_audit(
                    audit_context,
                    action="PROJECT_CREATED",
                    operation_id="create_project",
                    actor_user_id=actor_user_id,
                    participant_user_id=audited_participant_user_id,
                    project_id=project_id,
                    project_code=body.project_code,
                    required_permission="PROJECT_CREATE",
                    scope_decision="NOT_APPLICABLE",
                    previous_status=None,
                    result_code=failure.code,
                    reason=body.reason,
                )
            raise failure from error
        except PlatformError as error:
            if actor_user_id is not None and error.code in {
                "PROJECT_CODE_CONFLICT",
                "PROJECT_OWNER_NOT_ELIGIBLE",
            }:
                self._append_failed_audit(
                    audit_context,
                    action="PROJECT_CREATED",
                    operation_id="create_project",
                    actor_user_id=actor_user_id,
                    participant_user_id=audited_participant_user_id,
                    project_id=project_id,
                    project_code=body.project_code,
                    required_permission="PROJECT_CREATE",
                    scope_decision="NOT_APPLICABLE",
                    previous_status=None,
                    result_code=error.code,
                    reason=body.reason,
                )
            raise

    def list_projects(
        self,
        token: str,
        page: int,
        page_size: int,
        audit_context: AuditContext,
    ) -> ProjectListData:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_project", audit_context
            )
            permitted_ids = self._authentication.authorized_project_ids_in_transaction(
                db, actor, "PROJECT_VIEW"
            )
            query = select(Project).where(Project.lifecycle_status != "LOGICALLY_DELETED")
            count_query = select(func.count(Project.project_id)).where(
                Project.lifecycle_status != "LOGICALLY_DELETED"
            )
            if permitted_ids is not None:
                if not permitted_ids:
                    return ProjectListData(
                        items=[], page=PageMeta(page=page, page_size=page_size, total=0)
                    )
                query = query.where(Project.project_id.in_(permitted_ids))
                count_query = count_query.where(Project.project_id.in_(permitted_ids))
            total = int(db.scalar(count_query) or 0)
            projects = list(
                db.scalars(
                    query.order_by(Project.updated_at.desc(), Project.project_id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return ProjectListData(
                items=[self._project_resource(db, project) for project in projects],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get_project(
        self,
        token: str,
        project_id: str,
        audit_context: AuditContext,
    ) -> ProjectResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_project", audit_context
            )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "get_project", ("PROJECT_VIEW",), project_id, audit_context
            )
            project = db.get(Project, project_id)
            if project is None or project.lifecycle_status == "LOGICALLY_DELETED":
                raise _not_found("The project does not exist.")
            return self._project_resource(db, project)

    def update_project(
        self,
        token: str,
        project_id: str,
        body: UpdateProjectRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> ProjectResource:
        if "display_name" not in body.model_fields_set:
            raise PlatformError(
                title="No project update supplied",
                detail="At least one mutable project field must be supplied.",
                status=400,
                code="PROJECT_UPDATE_EMPTY",
            )
        actor_user_id: str | None = None
        project_code: str | None = None
        previous_status: str | None = None
        scope_decision: str | None = None
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "update_project", audit_context
                )
                actor_user_id = actor.user.user_id
                scope_decision = self._authentication.require_project_permissions_in_transaction(
                    db, actor, "update_project", ("PROJECT_EDIT",), project_id, audit_context
                )
                record, replay = self._claim_idempotency(
                    db,
                    actor.user.user_id,
                    "update_project",
                    idempotency_key,
                    _canonical_payload(body, project_id),
                )
                if replay:
                    return _stored_project(record.response_json)
                project = self._locked_project(db, project_id)
                project_code = project.project_code
                previous_status = project.lifecycle_status
                self._require_version(project, body.expected_version)
                if project.lifecycle_status != ACTIVE:
                    raise _state_forbidden("Only an ACTIVE project can be edited.")
                project.display_name = body.display_name
                project.row_version += 1
                project.updated_at = utc_now()
                project.updated_by = actor.user.user_id
                self._append_audit(
                    db,
                    project,
                    audit_context,
                    action="PROJECT_UPDATED",
                    operation_id="update_project",
                    actor_user_id=actor.user.user_id,
                    participant_user_id=None,
                    required_permission="PROJECT_EDIT",
                    scope_decision=scope_decision,
                    previous_status=ACTIVE,
                    new_status=ACTIVE,
                    reason=body.reason,
                )
                self._append_event(
                    db,
                    project,
                    "project.updated",
                    sequence=self._next_event_sequence(db, project.project_id),
                    actor_user_id=actor.user.user_id,
                    payload={"changed_fields": ["display_name"]},
                )
                resource = self._project_resource(db, project)
                self._idempotency.complete(
                    record, 200, {"project": resource.model_dump(mode="json")}
                )
                return resource
        except PlatformError as error:
            if (
                actor_user_id is not None
                and project_code is not None
                and error.code
                in {"PROJECT_CONCURRENCY_CONFLICT", "PROJECT_OPERATION_FORBIDDEN_FOR_STATE"}
            ):
                self._append_failed_audit(
                    audit_context,
                    action="PROJECT_UPDATED",
                    operation_id="update_project",
                    actor_user_id=actor_user_id,
                    participant_user_id=None,
                    project_id=project_id,
                    project_code=project_code,
                    required_permission="PROJECT_EDIT",
                    scope_decision=scope_decision or "ALLOWED",
                    previous_status=previous_status,
                    result_code=error.code,
                    reason=body.reason,
                )
            raise

    def transition_project(
        self,
        token: str,
        project_id: str,
        body: ProjectStateCommandRequest,
        idempotency_key: str,
        audit_context: AuditContext,
        *,
        action: str,
    ) -> ProjectResource:
        transitions = {
            "disable": (
                "disable_project",
                "PROJECT_EDIT",
                ACTIVE,
                "DISABLED",
                ("project.disabled",),
            ),
            "recover": (
                "recover_project",
                "PROJECT_EDIT",
                "DISABLED",
                ACTIVE,
                ("project.recovering", "project.active"),
            ),
            "archive": (
                "archive_project",
                "PROJECT_ARCHIVE",
                "DISABLED",
                "ARCHIVED",
                ("project.archived",),
            ),
        }
        try:
            operation_id, permission, expected_state, final_state, event_types = transitions[action]
        except KeyError as error:
            raise ValueError("unsupported project transition") from error
        audit_action = {
            "disable": "PROJECT_DISABLED",
            "recover": "PROJECT_RECOVERED",
            "archive": "PROJECT_ARCHIVED",
        }[action]
        actor_user_id: str | None = None
        project_code: str | None = None
        previous_status: str | None = None
        scope_decision: str | None = None
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, operation_id, audit_context
                )
                actor_user_id = actor.user.user_id
                scope_decision = self._authentication.require_project_permissions_in_transaction(
                    db, actor, operation_id, (permission,), project_id, audit_context
                )
                record, replay = self._claim_idempotency(
                    db,
                    actor.user.user_id,
                    operation_id,
                    idempotency_key,
                    _canonical_payload(body, project_id),
                )
                if replay:
                    return _stored_project(record.response_json)
                project = self._locked_project(db, project_id)
                project_code = project.project_code
                previous_status = project.lifecycle_status
                self._require_version(project, body.expected_version)
                if project.lifecycle_status != expected_state:
                    raise _state_forbidden(
                        f"Project transition {expected_state} to {final_state} is required."
                    )
                lifecycle_path = [expected_state]
                if action == "recover":
                    project.lifecycle_status = "RECOVERING"
                    project.row_version += 1
                    project.updated_at = utc_now()
                    project.updated_by = actor.user.user_id
                    db.flush()
                    lifecycle_path.append("RECOVERING")
                project.lifecycle_status = final_state
                project.row_version += 1
                project.updated_at = utc_now()
                project.updated_by = actor.user.user_id
                lifecycle_path.append(final_state)
                self._append_audit(
                    db,
                    project,
                    audit_context,
                    action=audit_action,
                    operation_id=operation_id,
                    actor_user_id=actor.user.user_id,
                    participant_user_id=None,
                    required_permission=permission,
                    scope_decision=scope_decision,
                    previous_status=expected_state,
                    new_status=final_state,
                    reason=body.reason,
                )
                first_sequence = self._next_event_sequence(db, project.project_id)
                for offset, event_type in enumerate(event_types):
                    event_status = (
                        "RECOVERING" if event_type == "project.recovering" else final_state
                    )
                    self._append_event(
                        db,
                        project,
                        event_type,
                        sequence=first_sequence + offset,
                        actor_user_id=actor.user.user_id,
                        payload={
                            "action": action,
                            "lifecycle_path": lifecycle_path,
                            "event_status": event_status,
                        },
                    )
                resource = self._project_resource(db, project)
                self._idempotency.complete(
                    record, 200, {"project": resource.model_dump(mode="json")}
                )
                return resource
        except PlatformError as error:
            if (
                actor_user_id is not None
                and project_code is not None
                and error.code
                in {"PROJECT_CONCURRENCY_CONFLICT", "PROJECT_OPERATION_FORBIDDEN_FOR_STATE"}
            ):
                self._append_failed_audit(
                    audit_context,
                    action=audit_action,
                    operation_id=operation_id,
                    actor_user_id=actor_user_id,
                    participant_user_id=None,
                    project_id=project_id,
                    project_code=project_code,
                    required_permission=permission,
                    scope_decision=scope_decision or "ALLOWED",
                    previous_status=previous_status,
                    result_code=error.code,
                    reason=body.reason,
                )
            raise

    @staticmethod
    def _locked_project(db: Session, project_id: str) -> Project:
        project = db.scalar(
            select(Project).where(Project.project_id == project_id).with_for_update()
        )
        if project is None:
            raise _not_found("The project does not exist.")
        return project

    @staticmethod
    def _require_version(project: Project, expected_version: int) -> None:
        if project.row_version != expected_version:
            raise PlatformError(
                title="Project concurrency conflict",
                detail="The expected project version no longer matches.",
                status=409,
                code="PROJECT_CONCURRENCY_CONFLICT",
            )

    @staticmethod
    def _next_event_sequence(db: Session, project_id: str) -> int:
        current = db.scalar(
            select(func.max(OutboxEvent.sequence)).where(OutboxEvent.aggregate_id == project_id)
        )
        return int(current or 0) + 1

    def _claim_idempotency(
        self,
        db: Session,
        principal_id: str,
        operation_id: str,
        idempotency_key: str,
        canonical_request: bytes,
    ) -> tuple[IdempotencyRecord, bool]:
        try:
            return self._idempotency.claim(
                db,
                principal_id,
                operation_id,
                idempotency_key,
                canonical_request,
            )
        except PlatformError as error:
            codes = {
                "AUTH_CONCURRENCY_CONFLICT": "PROJECT_IDEMPOTENCY_REQUEST_INCOMPLETE",
                "AUTH_IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST": (
                    "PROJECT_IDEMPOTENCY_KEY_CONFLICT"
                ),
            }
            code = codes.get(error.code)
            if code is None:
                raise
            raise PlatformError(
                title="Project idempotency conflict",
                detail=error.detail,
                status=error.status,
                code=code,
            ) from error

    @staticmethod
    def _append_event(
        db: Session,
        project: Project,
        event_type: str,
        *,
        sequence: int,
        actor_user_id: str,
        payload: dict[str, object],
    ) -> None:
        db.add(
            OutboxEvent(
                event_id=new_ulid(),
                aggregate_id=project.project_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "project_id": project.project_id,
                    "row_version": project.row_version,
                    "lifecycle_status": project.lifecycle_status,
                    "actor_user_id": actor_user_id,
                    **payload,
                },
                occurred_at=utc_now(),
                published_at=None,
                attempt_count=0,
            )
        )

    @staticmethod
    def _append_audit(
        db: Session,
        project: Project,
        context: AuditContext,
        *,
        action: str,
        operation_id: str,
        actor_user_id: str,
        participant_user_id: str | None,
        required_permission: str,
        scope_decision: str,
        previous_status: str | None,
        new_status: str,
        reason: str | None,
    ) -> None:
        db.add(
            ProjectAudit(
                audit_id=new_ulid(),
                project_id=project.project_id,
                project_code=project.project_code,
                action=action,
                operation_id=operation_id,
                actor_user_id=actor_user_id,
                participant_user_id=participant_user_id,
                required_permission=required_permission,
                scope_decision=scope_decision,
                previous_status=previous_status,
                new_status=new_status,
                result_code="SUCCESS",
                reason=reason,
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
        actor_user_id: str,
        participant_user_id: str | None,
        project_id: str | None,
        project_code: str,
        required_permission: str,
        scope_decision: str,
        previous_status: str | None,
        result_code: str,
        reason: str | None,
    ) -> None:
        """Persist failure evidence only after the command transaction has rolled back."""
        with self._factory.begin() as db:
            db.add(
                ProjectAudit(
                    audit_id=new_ulid(),
                    project_id=project_id,
                    project_code=project_code,
                    action=action,
                    operation_id=operation_id,
                    actor_user_id=actor_user_id,
                    participant_user_id=participant_user_id,
                    required_permission=required_permission,
                    scope_decision=scope_decision,
                    previous_status=previous_status,
                    new_status=None,
                    result_code=result_code,
                    reason=reason,
                    correlation_id=context.correlation_id,
                    occurred_at=utc_now(),
                    source_context_hash=hashlib.sha256(
                        context.source_context.encode("utf-8")
                    ).digest(),
                )
            )

    @staticmethod
    def _project_resource(db: Session, project: Project) -> ProjectResource:
        owner_rows = list(
            db.execute(
                select(PlatformUser.user_id, PlatformUser.display_name)
                .select_from(ProjectMember)
                .join(PlatformUser, PlatformUser.user_id == ProjectMember.user_id)
                .join(Role, Role.role_id == ProjectMember.role_id)
                .where(
                    ProjectMember.project_id == project.project_id,
                    ProjectMember.lifecycle_status == ACTIVE,
                    PlatformUser.lifecycle_status == ACTIVE,
                    Role.lifecycle_status == ACTIVE,
                    Role.role_code == OWNER_ROLE_CODE,
                )
                .order_by(ProjectMember.created_at, ProjectMember.project_member_id)
            )
        )
        if not owner_rows:
            raise RuntimeError("project aggregate has no active owner")
        return ProjectResource(
            project_id=project.project_id,
            display_name=project.display_name,
            row_version=project.row_version,
            created_at=project.created_at,
            updated_at=project.updated_at,
            project_code=project.project_code,
            lifecycle_status=project.lifecycle_status,
            owners=[
                ProjectOwnerResource(
                    user_id=user_id,
                    display_name=display_name,
                    membership_status=ACTIVE,
                )
                for user_id, display_name in owner_rows
            ],
        )


def _canonical_payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    value: dict[str, object] = body.model_dump(mode="json", exclude_none=False)
    if resource_id is not None:
        value["resource_id"] = resource_id
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _stored_project(value: dict[str, object] | None) -> ProjectResource:
    if not isinstance(value, dict) or not isinstance(value.get("project"), dict):
        raise RuntimeError("terminal idempotency project projection is invalid")
    return ProjectResource.model_validate(value["project"])


def _not_found(detail: str) -> PlatformError:
    return PlatformError(
        title="Project resource not found",
        detail=detail,
        status=404,
        code="PROJECT_NOT_FOUND",
    )


def _owner_ineligible(detail: str) -> PlatformError:
    return PlatformError(
        title="Project owner is not eligible",
        detail=detail,
        status=403,
        code="PROJECT_OWNER_NOT_ELIGIBLE",
    )


def _project_code_conflict() -> PlatformError:
    return PlatformError(
        title="Project code conflict",
        detail="The project_code is already in use.",
        status=409,
        code="PROJECT_CODE_CONFLICT",
    )


def _project_integrity_error(error: IntegrityError) -> PlatformError:
    """Only the canonical project-code unique key maps to a domain conflict."""
    original_args = list(getattr(error.orig, "args", ()))
    vendor_code = original_args[0] if original_args else None
    vendor_message = str(original_args[1]) if len(original_args) > 1 else ""
    if vendor_code == 1062 and "uq_atp_project_business" in vendor_message:
        return _project_code_conflict()
    return PlatformError(
        title="Internal server error",
        detail="The project command could not be completed.",
        status=500,
        code="INTERNAL_ERROR",
    )


def _state_forbidden(detail: str) -> PlatformError:
    return PlatformError(
        title="Operation forbidden for project state",
        detail=detail,
        status=403,
        code="PROJECT_OPERATION_FORBIDDEN_FOR_STATE",
    )


def _configuration_error(detail: str) -> PlatformError:
    return PlatformError(
        title="Project configuration unavailable",
        detail=detail,
        status=503,
        code="PROJECT_CONFIGURATION_UNAVAILABLE",
    )
