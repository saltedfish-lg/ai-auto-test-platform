"""Transactional AI exploration planning foundation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from platform_api.ai_exploration_schemas import (
    AIExplorationSessionResource,
    CreateAIExplorationRequest,
    ExplorationPlan,
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
    AICall,
    AIExplorationAudit,
    AIExplorationSession,
    AITask,
    IdempotencyRecord,
    Project,
)
from platform_api.security import new_ulid, utc_now

AI_TASK_CREATE = "AI_TASK_CREATE"
CREATE_AI_EXPLORATION_SESSION = "create_ai_exploration_session"


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
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency
        self._model_configurations = model_configurations
        self._context_provider = context_provider or RequestExplorationContextProvider()

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
            now = utc_now()
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
                extension_json=None,
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
            row.plan = plan.model_dump(mode="json")
            row.updated_at = utc_now()
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
        now = utc_now()
        if row is None or row.lifecycle_status != "PLANNING" or row.planning_deadline_at > now:
            return False
        row.lifecycle_status = "FAILED"
        row.plan = None
        row.failure_code = "AI_EXPLORATION_PLANNING_INTERRUPTED"
        row.failure_message = self._failure_message(row.failure_code)
        row.updated_at = now
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
        actor = self._authentication.authenticate_access_in_transaction(
            db, token, CREATE_AI_EXPLORATION_SESSION, audit_context
        )
        permission_decision = self._authentication.require_project_permissions_in_transaction(
            db,
            actor,
            CREATE_AI_EXPLORATION_SESSION,
            (AI_TASK_CREATE,),
            project_id,
            audit_context,
        )
        return actor, permission_decision

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
                    "Do not generate selectors, code, or claim that browser actions ran."
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
    ) -> None:
        db.add(
            AIExplorationAudit(
                audit_id=new_ulid(),
                session_id=row.session_id,
                ai_task_id=row.ai_task_id,
                ai_call_id=row.ai_call_id,
                operation_id=CREATE_AI_EXPLORATION_SESSION,
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
            project_id=row.project_id,
            source_case_id=row.source_case_id,
            objective=row.objective,
            target_url=row.target_url,
            lifecycle_status=row.lifecycle_status,
            resolved_model_config_id=row.resolved_model_config_id,
            resolved_model_display_name=row.resolved_model_display_name,
            resolved_provider_code=row.resolved_provider_code,
            resolved_model_name=row.resolved_model_name,
            plan=row.plan,
            failure_code=row.failure_code,
            failure_message=row.failure_message,
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
        }[code]


def _stored_session(value: dict[str, object] | None) -> AIExplorationSessionResource:
    if not isinstance(value, dict) or not isinstance(value.get("ai_exploration"), dict):
        raise RuntimeError("terminal AI exploration projection is invalid")
    return AIExplorationSessionResource.model_validate(value["ai_exploration"])
