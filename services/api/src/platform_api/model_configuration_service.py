"""Transactional platform AI model configuration service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, timedelta

from pydantic import BaseModel, SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticatedIdentity, AuthenticationService
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.model_configuration_schemas import (
    CapabilityDefaultResource,
    ClearCapabilityDefaultModelRequest,
    ClearCapabilityDefaultResult,
    CreateModelConfigRequest,
    ModelConfigLifecycleRequest,
    ModelConfigListData,
    ModelConfigResource,
    ModelConnectionTestResult,
    PageMeta,
    SetCapabilityDefaultModelRequest,
    TestModelConfigConnectionRequest,
    UpdateModelConfigRequest,
)
from platform_api.model_gateway import GatewayInvocationResult, ModelGateway
from platform_api.models import (
    IdempotencyRecord,
    ModelCapabilityDefault,
    ModelConfiguration,
    ModelConfigurationAudit,
    ModelConfigurationSecret,
    OutboxEvent,
)
from platform_api.secret_store import SecretProtector, SecretStoreError
from platform_api.security import new_ulid, utc_now

MANAGE_PERMISSION = "MODEL_CONFIGURATION_MANAGE"
REVIEW_PERMISSION = "MODEL_VERSION_REVIEW"
AI_EXPLORATION = "AI_EXPLORATION"
ACTIVE = "ACTIVE"


@dataclass(frozen=True, slots=True)
class ResolvedModelConfiguration:
    """Internal runtime projection carrying only an opaque credential reference."""

    model_config_id: str
    provider_code: str
    model_name: str
    request_timeout_seconds: int
    secret_reference: str
    display_name: str | None = None


class ModelConfigurationService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
        secret_protector: SecretProtector,
        gateway: ModelGateway,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency
        self._secret_protector = secret_protector
        self._gateway = gateway

    def list_model_configs(
        self,
        token: str,
        page: int,
        page_size: int,
        audit_context: AuditContext,
    ) -> ModelConfigListData:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_model_config", audit_context
            )
            self._authentication.require_platform_permissions_in_transaction(
                db, actor, "list_model_config", (MANAGE_PERMISSION,), audit_context
            )
            total = int(db.scalar(select(func.count(ModelConfiguration.model_config_id))) or 0)
            rows = list(
                db.scalars(
                    select(ModelConfiguration)
                    .order_by(
                        ModelConfiguration.updated_at.desc(),
                        ModelConfiguration.model_config_id,
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return ModelConfigListData(
                items=[self._resource(db, row) for row in rows],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get_model_config(
        self, token: str, model_config_id: str, audit_context: AuditContext
    ) -> ModelConfigResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_model_config", audit_context
            )
            self._authentication.require_platform_permissions_in_transaction(
                db, actor, "get_model_config", (MANAGE_PERMISSION,), audit_context
            )
            row = db.get(ModelConfiguration, model_config_id)
            if row is None:
                raise _not_found()
            return self._resource(db, row)

    def list_model_config_reviews(
        self,
        token: str,
        page: int,
        page_size: int,
        audit_context: AuditContext,
    ) -> ModelConfigListData:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_model_config_reviews", audit_context
            )
            self._authentication.require_platform_permissions_in_transaction(
                db, actor, "list_model_config_reviews", (REVIEW_PERMISSION,), audit_context
            )
            criterion = ModelConfiguration.lifecycle_status.in_(("VALIDATING", "RECOVERING"))
            total = int(
                db.scalar(select(func.count(ModelConfiguration.model_config_id)).where(criterion))
                or 0
            )
            rows = list(
                db.scalars(
                    select(ModelConfiguration)
                    .where(criterion)
                    .order_by(ModelConfiguration.updated_at, ModelConfiguration.model_config_id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return ModelConfigListData(
                items=[self._resource(db, row) for row in rows],
                page=PageMeta(page=page, page_size=page_size, total=total),
            )

    def get_model_config_review(
        self, token: str, model_config_id: str, audit_context: AuditContext
    ) -> ModelConfigResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_model_config_review", audit_context
            )
            self._authentication.require_platform_permissions_in_transaction(
                db, actor, "get_model_config_review", (REVIEW_PERMISSION,), audit_context
            )
            row = db.get(ModelConfiguration, model_config_id)
            if row is None or row.lifecycle_status not in {"VALIDATING", "RECOVERING"}:
                raise _not_found()
            return self._resource(db, row)

    def create_model_config(
        self,
        token: str,
        body: CreateModelConfigRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> ModelConfigResource:
        actor_user_id: str | None = None
        model_config_id: str | None = None
        try:
            with self._factory.begin() as db:
                actor = self._authorize(
                    db, token, "create_model_config", MANAGE_PERMISSION, audit_context
                )
                actor_user_id = actor.user.user_id
                record, replay = self._claim_idempotency(
                    db,
                    actor_user_id,
                    "create_model_config",
                    idempotency_key,
                    _canonical_payload(body),
                )
                if replay:
                    return _stored_model_config(record.response_json)
                if (
                    db.scalar(
                        select(ModelConfiguration.model_config_id).where(
                            ModelConfiguration.config_code == body.config_code
                        )
                    )
                    is not None
                ):
                    raise _code_conflict()

                now = utc_now()
                model_config_id = new_ulid()
                encrypted = self._encrypt_secret(
                    model_config_id, body.secret_value.get_secret_value()
                )
                row = ModelConfiguration(
                    model_config_id=model_config_id,
                    config_code=body.config_code,
                    provider_code=body.provider_code,
                    model_name=body.model_name,
                    request_timeout_seconds=body.request_timeout_seconds,
                    lifecycle_status="CONFIGURING",
                    display_name=body.display_name,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                    extension_json=None,
                )
                db.add(row)
                db.add(
                    ModelConfigurationSecret(
                        model_config_id=model_config_id,
                        encrypted_secret=encrypted.ciphertext,
                        key_id=encrypted.key_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._append_audit(
                    db,
                    row,
                    audit_context,
                    operation_id="create_model_config",
                    action="MODEL_CONFIG_CREATED",
                    actor_user_id=actor_user_id,
                    required_permission=MANAGE_PERMISSION,
                    previous_status="CREATED",
                    new_status="CONFIGURING",
                    reason=body.reason,
                    details={
                        "provider_code": body.provider_code,
                        "initial_status": "CREATED",
                    },
                )
                self._append_event(
                    db,
                    row,
                    "model_config.configuring",
                    actor_user_id=actor_user_id,
                    context=audit_context,
                    causation_id=idempotency_key,
                    previous_status="CREATED",
                    expected_version=0,
                    change_summary={"operation_id": "create_model_config"},
                )
                resource = self._resource(db, row, secret_configured=True)
                self._idempotency.complete(
                    record, 201, {"model_config": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _model_config_integrity_error(error) from error

    def update_model_config(
        self,
        token: str,
        model_config_id: str,
        body: UpdateModelConfigRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> ModelConfigResource:
        mutable_fields = {
            "display_name",
            "provider_code",
            "model_name",
            "secret_value",
            "request_timeout_seconds",
        }
        supplied_mutable_fields = body.model_fields_set & mutable_fields
        changed_fields = sorted(
            field_name
            for field_name in supplied_mutable_fields
            if field_name == "display_name" or getattr(body, field_name) is not None
        )
        if not changed_fields:
            raise PlatformError(
                title="No model configuration update supplied",
                detail="At least one mutable model configuration field must be supplied.",
                status=400,
                code="MODEL_CONFIG_UPDATE_EMPTY",
            )
        with self._factory.begin() as db:
            actor = self._authorize(
                db, token, "update_model_config", MANAGE_PERMISSION, audit_context
            )
            record, replay = self._claim_idempotency(
                db,
                actor.user.user_id,
                "update_model_config",
                idempotency_key,
                _canonical_payload(body, model_config_id),
            )
            if replay:
                return _stored_model_config(record.response_json)
            row = self._locked(db, model_config_id)
            self._require_version(row, body.expected_version)
            previous_status = row.lifecycle_status
            if previous_status == "ARCHIVED":
                raise _state_forbidden(
                    "ARCHIVED model configurations are terminal and cannot be edited."
                )
            sensitive_fields = {
                "provider_code",
                "model_name",
                "secret_value",
                "request_timeout_seconds",
            }
            if set(changed_fields) & sensitive_fields and row.lifecycle_status != "CONFIGURING":
                raise _state_forbidden(
                    "Provider, model, timeout and credential fields can only be edited while "
                    "CONFIGURING."
                )
            if "display_name" in body.model_fields_set:
                row.display_name = body.display_name
            if body.provider_code is not None:
                row.provider_code = body.provider_code
            if body.model_name is not None:
                row.model_name = body.model_name
            if body.request_timeout_seconds is not None:
                row.request_timeout_seconds = body.request_timeout_seconds
            if body.secret_value is not None:
                encrypted = self._encrypt_secret(
                    row.model_config_id, body.secret_value.get_secret_value()
                )
                secret_row = db.get(ModelConfigurationSecret, row.model_config_id)
                if secret_row is None:
                    secret_row = ModelConfigurationSecret(
                        model_config_id=row.model_config_id,
                        encrypted_secret=encrypted.ciphertext,
                        key_id=encrypted.key_id,
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    db.add(secret_row)
                else:
                    secret_row.encrypted_secret = encrypted.ciphertext
                    secret_row.key_id = encrypted.key_id
                    secret_row.updated_at = utc_now()
            row.row_version += 1
            row.updated_at = utc_now()
            row.updated_by = actor.user.user_id
            self._append_audit(
                db,
                row,
                audit_context,
                operation_id="update_model_config",
                action="MODEL_CONFIG_UPDATED",
                actor_user_id=actor.user.user_id,
                required_permission=MANAGE_PERMISSION,
                previous_status=previous_status,
                new_status=row.lifecycle_status,
                reason=body.reason,
                details={"changed_fields": changed_fields},
            )
            if body.secret_value is not None:
                self._append_audit(
                    db,
                    row,
                    audit_context,
                    operation_id="update_model_config",
                    action="MODEL_CONFIG_SECRET_UPDATED",
                    actor_user_id=actor.user.user_id,
                    required_permission=MANAGE_PERMISSION,
                    previous_status=previous_status,
                    new_status=row.lifecycle_status,
                    reason=body.reason,
                    details={"secret_reference_rotated": True},
                )
            resource = self._resource(
                db,
                row,
                secret_configured=True if body.secret_value is not None else None,
            )
            self._idempotency.complete(
                record, 200, {"model_config": resource.model_dump(mode="json")}
            )
            return resource

    def transition_model_config(
        self,
        token: str,
        model_config_id: str,
        body: ModelConfigLifecycleRequest,
        idempotency_key: str,
        audit_context: AuditContext,
        *,
        action: str,
    ) -> ModelConfigResource:
        transitions = {
            "submit_review": (
                "submit_model_config_review",
                MANAGE_PERMISSION,
                ("CONFIGURING",),
                "VALIDATING",
                "MODEL_CONFIG_REVIEW_SUBMITTED",
                "model_config.validating",
            ),
            "return_to_configuring": (
                "return_model_config_to_configuring",
                REVIEW_PERMISSION,
                ("VALIDATING",),
                "CONFIGURING",
                "MODEL_CONFIG_RETURNED_TO_CONFIGURING",
                "model_config.configuring",
            ),
            "activate": (
                "activate_model_config",
                REVIEW_PERMISSION,
                ("VALIDATING", "RECOVERING"),
                "ACTIVE",
                "MODEL_CONFIG_ACTIVATED",
                "model_config.active",
            ),
            "disable": (
                "disable_model_config",
                MANAGE_PERMISSION,
                ("ACTIVE",),
                "DISABLED",
                "MODEL_CONFIG_DISABLED",
                "model_config.disabled",
            ),
            "recover": (
                "recover_model_config",
                MANAGE_PERMISSION,
                ("DISABLED", "UNAVAILABLE"),
                "RECOVERING",
                "MODEL_CONFIG_RECOVERY_STARTED",
                "model_config.recovering",
            ),
            "archive": (
                "archive_model_config",
                MANAGE_PERMISSION,
                ("DISABLED",),
                "ARCHIVED",
                "MODEL_CONFIG_ARCHIVED",
                "model_config.archived",
            ),
        }
        try:
            operation_id, permission, expected_states, target_state, audit_action, event_type = (
                transitions[action]
            )
        except KeyError as error:
            raise ValueError("unsupported model configuration transition") from error
        with self._factory.begin() as db:
            actor = self._authorize(db, token, operation_id, permission, audit_context)
            record, replay = self._claim_idempotency(
                db,
                actor.user.user_id,
                operation_id,
                idempotency_key,
                _canonical_payload(body, model_config_id),
            )
            if replay:
                return _stored_model_config(record.response_json)
            row = self._locked(db, model_config_id)
            self._require_version(row, body.expected_version)
            if row.lifecycle_status not in expected_states:
                raise _state_forbidden(
                    "The transition requires lifecycle status " + " or ".join(expected_states) + "."
                )
            review_audit_details: dict[str, object] | None = None
            if action == "activate" and row.lifecycle_status == "VALIDATING":
                submitting_actor_id = db.scalar(
                    select(ModelConfigurationAudit.actor_user_id)
                    .where(
                        ModelConfigurationAudit.model_config_id == row.model_config_id,
                        ModelConfigurationAudit.action == "MODEL_CONFIG_REVIEW_SUBMITTED",
                    )
                    .order_by(
                        ModelConfigurationAudit.occurred_at.desc(),
                        ModelConfigurationAudit.audit_id.desc(),
                    )
                    .limit(1)
                )
                if submitting_actor_id is None:
                    raise PlatformError(
                        title="Model review submission evidence missing",
                        detail=(
                            "The validating model configuration has no immutable review "
                            "submission evidence."
                        ),
                        status=409,
                        code="MODEL_CONFIG_REVIEW_SUBMISSION_EVIDENCE_MISSING",
                    )
                self_approval = submitting_actor_id == actor.user.user_id
                is_super_admin = self_approval and (
                    self._authentication.user_has_active_platform_role_in_transaction(
                        db,
                        actor.user.user_id,
                        "ROLE-SUPER-ADMIN",
                    )
                )
                if self_approval and not is_super_admin:
                    raise PlatformError(
                        title="Independent model review required",
                        detail=(
                            "The submitting operator cannot activate the same model configuration."
                        ),
                        status=403,
                        code="MODEL_CONFIG_SELF_REVIEW_FORBIDDEN",
                    )
                review_audit_details = {
                    "actor_user_id": actor.user.user_id,
                    "submitter_user_id": submitting_actor_id,
                    "reviewer_user_id": actor.user.user_id,
                    "self_approval": self_approval,
                }
                if is_super_admin:
                    review_audit_details["operator_role"] = "SUPER_ADMIN"
            if action == "disable":
                default_binding = db.get(ModelCapabilityDefault, AI_EXPLORATION)
                if (
                    default_binding is not None
                    and default_binding.model_config_id == row.model_config_id
                ):
                    raise PlatformError(
                        title="Default model cannot be disabled",
                        detail="Switch or clear the AI_EXPLORATION default before disabling it.",
                        status=409,
                        code="MODEL_CONFIG_DEFAULT_DISABLE_CONFLICT",
                    )
            previous_status = row.lifecycle_status
            row.lifecycle_status = target_state
            row.row_version += 1
            row.updated_at = utc_now()
            row.updated_by = actor.user.user_id
            self._append_audit(
                db,
                row,
                audit_context,
                operation_id=operation_id,
                action=audit_action,
                actor_user_id=actor.user.user_id,
                required_permission=permission,
                previous_status=previous_status,
                new_status=target_state,
                reason=body.reason,
                details=review_audit_details,
            )
            self._append_event(
                db,
                row,
                event_type,
                actor_user_id=actor.user.user_id,
                context=audit_context,
                causation_id=idempotency_key,
                previous_status=previous_status,
                expected_version=body.expected_version,
                change_summary={
                    "operation_id": operation_id,
                    "reason": body.reason,
                },
            )
            resource = self._resource(db, row)
            self._idempotency.complete(
                record, 200, {"model_config": resource.model_dump(mode="json")}
            )
            return resource

    def test_connection(
        self,
        token: str,
        model_config_id: str,
        body: TestModelConfigConnectionRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> ModelConnectionTestResult:
        record: IdempotencyRecord
        with self._factory.begin() as db:
            actor = self._authorize(
                db, token, "test_model_config_connection", MANAGE_PERMISSION, audit_context
            )
            record, replay = self._claim_idempotency(
                db,
                actor.user.user_id,
                "test_model_config_connection",
                idempotency_key,
                _canonical_payload(body, model_config_id),
            )
            if replay:
                return _stored_connection_result(record.response_json)
            row = self._locked(db, model_config_id)
            tested_version = row.row_version
            tested_provider_code = row.provider_code
            tested_model_name = row.model_name
            tested_timeout_seconds = row.request_timeout_seconds
            # The terminal response is retained for 24 hours by complete().  While the
            # remote call is in progress, use a bounded recovery window so a process
            # crash cannot strand this diagnostic idempotency key for a full day.
            record.expires_at = utc_now() + timedelta(seconds=tested_timeout_seconds + 30)
            attempt_expires_at = record.expires_at
            idempotency_record_key = record.idempotency_key
            attempt_request_hash = record.request_hash
            secret_row = db.get(ModelConfigurationSecret, model_config_id)
            provider_secret = None if secret_row is None else self._decrypt_secret(row, secret_row)

        # PRN-004: remote provider I/O must never hold a database transaction or row lock.
        if provider_secret is None:
            gateway_result = None
        else:
            gateway_result = self._gateway.test_connection(
                provider_code=tested_provider_code,
                model_name=tested_model_name,
                provider_secret=provider_secret,
                timeout_seconds=tested_timeout_seconds,
            )

        with self._factory.begin() as db:
            attached_record = db.scalar(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == idempotency_record_key)
                .with_for_update()
            )
            if attached_record is None:
                raise _connection_test_attempt_stale()
            if (
                attached_record.expires_at != attempt_expires_at
                or attached_record.request_hash != attempt_request_hash
                or attached_record.response_status is not None
                or attached_record.completed_at is not None
            ):
                raise _connection_test_attempt_stale()
            # Idempotency is the global command lock and must always precede the
            # aggregate lock.  This matches claim() and prevents a reclaimed attempt
            # from deadlocking with an older provider call during finalization.
            row = self._locked(db, model_config_id)
            configuration_changed = (
                row.row_version != tested_version
                or row.provider_code != tested_provider_code
                or row.model_name != tested_model_name
                or row.request_timeout_seconds != tested_timeout_seconds
            )
            if configuration_changed:
                result = self._connection_result(
                    row,
                    status="INVALID_CONFIGURATION",
                    latency_ms=0,
                    message="The model configuration changed while the connection test ran.",
                )
            elif gateway_result is None:
                result = self._connection_result(
                    row,
                    status="INVALID_CONFIGURATION",
                    latency_ms=0,
                    message="The model credential is not configured.",
                )
            else:
                result = self._connection_result(
                    row,
                    status=gateway_result.status,
                    latency_ms=gateway_result.latency_ms,
                    message=gateway_result.message,
                )
            self._append_audit(
                db,
                row,
                audit_context,
                operation_id="test_model_config_connection",
                action="MODEL_CONFIG_CONNECTION_TESTED",
                actor_user_id=actor.user.user_id,
                required_permission=MANAGE_PERMISSION,
                previous_status=row.lifecycle_status,
                new_status=row.lifecycle_status,
                result_code=result.status,
                reason=body.reason,
                details={
                    "provider_code": tested_provider_code,
                    "tested_version": tested_version,
                    "configuration_changed": configuration_changed,
                    "latency_ms": result.latency_ms,
                },
            )
            self._idempotency.complete(
                attached_record,
                200,
                {"connection_result": result.model_dump(mode="json")},
            )
            return result

    def set_capability_default(
        self,
        token: str,
        capability_code: str,
        body: SetCapabilityDefaultModelRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> CapabilityDefaultResource:
        self._require_capability(capability_code)
        with self._factory.begin() as db:
            actor = self._authorize(
                db, token, "set_capability_default_model", MANAGE_PERMISSION, audit_context
            )
            record, replay = self._claim_idempotency(
                db,
                actor.user.user_id,
                "set_capability_default_model",
                idempotency_key,
                _canonical_payload(body, capability_code),
            )
            if replay:
                return _stored_capability_default(record.response_json)
            now = utc_now()
            existing_capability = db.scalar(
                select(ModelCapabilityDefault.capability_code).where(
                    ModelCapabilityDefault.capability_code == capability_code
                )
            )
            binding = (
                db.scalar(
                    select(ModelCapabilityDefault)
                    .where(ModelCapabilityDefault.capability_code == capability_code)
                    .with_for_update()
                )
                if existing_capability is not None
                else None
            )
            previous_model_config_id = binding.model_config_id if binding is not None else None
            model = self._locked(db, body.model_config_id)
            if model.lifecycle_status != ACTIVE:
                raise PlatformError(
                    title="Default model must be active",
                    detail="Only an ACTIVE model configuration can be the effective default.",
                    status=409,
                    code="MODEL_CAPABILITY_DEFAULT_MODEL_NOT_ACTIVE",
                )
            if binding is None:
                if body.expected_version is not None:
                    raise _capability_concurrency_conflict()
                binding = ModelCapabilityDefault(
                    capability_code=capability_code,
                    model_config_id=model.model_config_id,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                )
                try:
                    # The unique capability key is the atomic first-writer competition
                    # point.  A savepoint keeps the outer command transaction usable so
                    # a concurrent first binding maps to the formal 409 instead of 500.
                    with db.begin_nested():
                        db.add(binding)
                        db.flush()
                except IntegrityError as error:
                    raise _capability_concurrency_conflict() from error
            else:
                if body.expected_version is None or binding.row_version != body.expected_version:
                    raise _capability_concurrency_conflict()
                binding.model_config_id = model.model_config_id
                binding.row_version += 1
                binding.updated_at = now
                binding.updated_by = actor.user.user_id
            if (
                previous_model_config_id is not None
                and previous_model_config_id != model.model_config_id
            ):
                previous_model = self._locked(db, previous_model_config_id)
                self._append_audit(
                    db,
                    previous_model,
                    audit_context,
                    operation_id="set_capability_default_model",
                    action="CAPABILITY_DEFAULT_CLEARED",
                    actor_user_id=actor.user.user_id,
                    required_permission=MANAGE_PERMISSION,
                    previous_status=previous_model.lifecycle_status,
                    new_status=previous_model.lifecycle_status,
                    reason=body.reason,
                    details={
                        "capability_code": capability_code,
                        "replacement_model_config_id": model.model_config_id,
                    },
                )
            self._append_audit(
                db,
                model,
                audit_context,
                operation_id="set_capability_default_model",
                action="CAPABILITY_DEFAULT_SET",
                actor_user_id=actor.user.user_id,
                required_permission=MANAGE_PERMISSION,
                previous_status=model.lifecycle_status,
                new_status=model.lifecycle_status,
                reason=body.reason,
                details={
                    "capability_code": capability_code,
                    "previous_model_config_id": previous_model_config_id,
                },
            )
            resource = self._capability_resource(binding)
            self._idempotency.complete(
                record, 200, {"capability_default": resource.model_dump(mode="json")}
            )
            return resource

    def clear_capability_default(
        self,
        token: str,
        capability_code: str,
        body: ClearCapabilityDefaultModelRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> ClearCapabilityDefaultResult:
        self._require_capability(capability_code)
        with self._factory.begin() as db:
            actor = self._authorize(
                db, token, "clear_capability_default_model", MANAGE_PERMISSION, audit_context
            )
            record, replay = self._claim_idempotency(
                db,
                actor.user.user_id,
                "clear_capability_default_model",
                idempotency_key,
                _canonical_payload(body, capability_code),
            )
            if replay:
                return ClearCapabilityDefaultResult(capability_code=AI_EXPLORATION, cleared=True)
            binding = db.scalar(
                select(ModelCapabilityDefault)
                .where(ModelCapabilityDefault.capability_code == capability_code)
                .with_for_update()
            )
            if binding is None:
                raise PlatformError(
                    title="Capability default not found",
                    detail="The capability does not have an effective default model.",
                    status=404,
                    code="MODEL_CAPABILITY_DEFAULT_NOT_FOUND",
                )
            if binding.row_version != body.expected_version:
                raise _capability_concurrency_conflict()
            model = self._locked(db, binding.model_config_id)
            db.delete(binding)
            self._append_audit(
                db,
                model,
                audit_context,
                operation_id="clear_capability_default_model",
                action="CAPABILITY_DEFAULT_CLEARED",
                actor_user_id=actor.user.user_id,
                required_permission=MANAGE_PERMISSION,
                previous_status=model.lifecycle_status,
                new_status=model.lifecycle_status,
                reason=body.reason,
                details={"capability_code": capability_code},
            )
            result = ClearCapabilityDefaultResult(capability_code=AI_EXPLORATION, cleared=True)
            self._idempotency.complete(
                record, 200, {"clear_result": result.model_dump(mode="json")}
            )
            return result

    def resolve_default(self, capability_code: str) -> ResolvedModelConfiguration:
        """Resolve exactly one ACTIVE platform binding; never use a fallback model."""
        with self._factory() as db:
            return self.resolve_default_in_transaction(db, capability_code)

    def resolve_default_in_transaction(
        self,
        db: Session,
        capability_code: str,
    ) -> ResolvedModelConfiguration:
        """Resolve a capability default inside the caller's transaction."""
        self._require_capability(capability_code)
        row = db.execute(
            select(ModelConfiguration, ModelConfigurationSecret)
            .join(
                ModelCapabilityDefault,
                ModelCapabilityDefault.model_config_id == ModelConfiguration.model_config_id,
            )
            .join(
                ModelConfigurationSecret,
                ModelConfigurationSecret.model_config_id == ModelConfiguration.model_config_id,
            )
            .where(
                ModelCapabilityDefault.capability_code == capability_code,
                ModelConfiguration.lifecycle_status == ACTIVE,
            )
        ).one_or_none()
        if row is None:
            raise PlatformError(
                title="Capability default unavailable",
                detail="No ACTIVE default model is bound for the requested capability.",
                status=503,
                code="MODEL_CAPABILITY_DEFAULT_UNAVAILABLE",
            )
        model, _secret = row
        return ResolvedModelConfiguration(
            model_config_id=model.model_config_id,
            provider_code=model.provider_code,
            model_name=model.model_name,
            request_timeout_seconds=model.request_timeout_seconds,
            secret_reference=f"model-config-secret:{model.model_config_id}",
            display_name=model.display_name,
        )

    def invoke(
        self,
        resolved: ResolvedModelConfiguration,
        messages: list[dict[str, str]],
    ) -> GatewayInvocationResult:
        """Invoke the exact resolved snapshot; capability changes never retarget a session."""
        with self._factory() as db:
            row = db.execute(
                select(ModelConfiguration, ModelConfigurationSecret)
                .join(
                    ModelConfigurationSecret,
                    ModelConfigurationSecret.model_config_id == ModelConfiguration.model_config_id,
                )
                .where(ModelConfiguration.model_config_id == resolved.model_config_id)
            ).one_or_none()
            if row is None:
                raise PlatformError(
                    title="Resolved model unavailable",
                    detail="The resolved model configuration can no longer be invoked.",
                    status=503,
                    code="MODEL_RUNTIME_CONFIGURATION_UNAVAILABLE",
                )
            model, secret = row
            if (
                model.provider_code != resolved.provider_code
                or model.model_name != resolved.model_name
            ):
                raise PlatformError(
                    title="Resolved model snapshot mismatch",
                    detail="The resolved model configuration no longer matches its snapshot.",
                    status=503,
                    code="MODEL_RUNTIME_CONFIGURATION_UNAVAILABLE",
                )
            provider_secret = self._decrypt_secret(model, secret)
        return self._gateway.invoke(
            provider_code=resolved.provider_code,
            model_name=resolved.model_name,
            provider_secret=provider_secret,
            timeout_seconds=resolved.request_timeout_seconds,
            messages=messages,
        )

    def _authorize(
        self,
        db: Session,
        token: str,
        operation_id: str,
        permission: str,
        audit_context: AuditContext,
    ) -> AuthenticatedIdentity:
        actor = self._authentication.authenticate_access_in_transaction(
            db, token, operation_id, audit_context
        )
        self._authentication.require_platform_permissions_in_transaction(
            db, actor, operation_id, (permission,), audit_context
        )
        return actor

    @staticmethod
    def _locked(db: Session, model_config_id: str) -> ModelConfiguration:
        row = db.scalar(
            select(ModelConfiguration)
            .where(ModelConfiguration.model_config_id == model_config_id)
            .with_for_update()
        )
        if row is None:
            raise _not_found()
        return row

    @staticmethod
    def _require_version(row: ModelConfiguration, expected_version: int) -> None:
        if row.row_version != expected_version:
            raise PlatformError(
                title="Model configuration concurrency conflict",
                detail="The expected model configuration version no longer matches.",
                status=409,
                code="MODEL_CONFIG_CONCURRENCY_CONFLICT",
            )

    @staticmethod
    def _require_capability(capability_code: str) -> None:
        if capability_code != AI_EXPLORATION:
            raise PlatformError(
                title="Unsupported model capability",
                detail="Only AI_EXPLORATION has a platform model binding.",
                status=404,
                code="MODEL_CAPABILITY_NOT_FOUND",
            )

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
                db, principal_id, operation_id, idempotency_key, canonical_request
            )
        except PlatformError as error:
            code = {
                "AUTH_CONCURRENCY_CONFLICT": "MODEL_CONFIG_IDEMPOTENCY_REQUEST_INCOMPLETE",
                "AUTH_IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST": (
                    "MODEL_CONFIG_IDEMPOTENCY_KEY_CONFLICT"
                ),
            }.get(error.code)
            if code is None:
                raise
            raise PlatformError(
                title="Model configuration idempotency conflict",
                detail=error.detail,
                status=error.status,
                code=code,
            ) from error

    def _encrypt_secret(self, model_config_id: str, secret_value: str):
        try:
            return self._secret_protector.encrypt(model_config_id, secret_value)
        except SecretStoreError as error:
            raise _secret_store_unavailable() from error

    def _decrypt_secret(self, model: ModelConfiguration, secret: ModelConfigurationSecret) -> str:
        try:
            return self._secret_protector.decrypt(
                model.model_config_id, secret.encrypted_secret, secret.key_id
            )
        except SecretStoreError as error:
            raise _secret_store_unavailable() from error

    @staticmethod
    def _connection_result(
        row: ModelConfiguration,
        *,
        status: str,
        latency_ms: int,
        message: str,
    ) -> ModelConnectionTestResult:
        error_code = None if status == "SUCCESS" else f"MODEL_CONNECTION_{status}"
        return ModelConnectionTestResult(
            status=status,
            provider_code=row.provider_code,
            model_name=row.model_name,
            latency_ms=latency_ms,
            error_code=error_code,
            message=message,
        )

    @staticmethod
    def _resource(
        db: Session,
        row: ModelConfiguration,
        *,
        secret_configured: bool | None = None,
    ) -> ModelConfigResource:
        if secret_configured is None:
            secret_configured = (
                db.scalar(
                    select(ModelConfigurationSecret.model_config_id).where(
                        ModelConfigurationSecret.model_config_id == row.model_config_id
                    )
                )
                is not None
            )
        default_version = db.scalar(
            select(ModelCapabilityDefault.row_version).where(
                ModelCapabilityDefault.capability_code == AI_EXPLORATION,
                ModelCapabilityDefault.model_config_id == row.model_config_id,
            )
        )
        return ModelConfigResource(
            model_config_id=row.model_config_id,
            config_code=row.config_code,
            display_name=row.display_name,
            provider_code=row.provider_code,
            model_name=row.model_name,
            request_timeout_seconds=row.request_timeout_seconds,
            lifecycle_status=row.lifecycle_status,
            secret_configured=secret_configured,
            is_ai_exploration_default=default_version is not None,
            ai_exploration_default_version=(
                int(default_version) if default_version is not None else None
            ),
            row_version=row.row_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _capability_resource(row: ModelCapabilityDefault) -> CapabilityDefaultResource:
        return CapabilityDefaultResource(
            capability_code=row.capability_code,
            model_config_id=row.model_config_id,
            row_version=row.row_version,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _next_event_sequence(db: Session, model_config_id: str) -> int:
        current = db.scalar(
            select(func.max(OutboxEvent.sequence)).where(
                OutboxEvent.aggregate_id == model_config_id
            )
        )
        return int(current or 0) + 1

    @classmethod
    def _append_event(
        cls,
        db: Session,
        row: ModelConfiguration,
        event_type: str,
        *,
        actor_user_id: str,
        context: AuditContext,
        causation_id: str,
        previous_status: str | None,
        expected_version: int,
        change_summary: dict[str, object],
    ) -> None:
        event_id = new_ulid()
        sequence = cls._next_event_sequence(db, row.model_config_id)
        occurred_at = utc_now()
        db.add(
            OutboxEvent(
                event_id=event_id,
                aggregate_id=row.model_config_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": occurred_at.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": row.model_config_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": None,
                    "payload": {
                        "model_config_id": row.model_config_id,
                        "project_id": None,
                        "from_state": previous_status,
                        "to_state": row.lifecycle_status,
                        "expected_version": expected_version,
                        "new_version": row.row_version,
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
        row: ModelConfiguration,
        context: AuditContext,
        *,
        operation_id: str,
        action: str,
        actor_user_id: str,
        required_permission: str,
        previous_status: str | None,
        new_status: str | None,
        reason: str | None,
        details: dict[str, object] | None,
        result_code: str = "SUCCESS",
    ) -> None:
        db.add(
            ModelConfigurationAudit(
                audit_id=new_ulid(),
                model_config_id=row.model_config_id,
                config_code=row.config_code,
                operation_id=operation_id,
                action=action,
                actor_user_id=actor_user_id,
                required_permission=required_permission,
                previous_status=previous_status,
                new_status=new_status,
                result_code=result_code,
                reason=reason,
                correlation_id=context.correlation_id,
                occurred_at=utc_now(),
                source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
                details_json=details,
            )
        )


def _canonical_payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    value: dict[str, object] = body.model_dump(mode="python", exclude_none=False)
    secret_value = value.pop("secret_value", None)
    if isinstance(secret_value, SecretStr):
        # Distinguish credential rotations without placing the credential in the
        # idempotency payload. The coordinator applies its own keyed HMAC before storage.
        value["secret_value_sha256"] = hashlib.sha256(
            secret_value.get_secret_value().encode()
        ).hexdigest()
    if resource_id is not None:
        value["resource_id"] = resource_id
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _stored_model_config(value: dict[str, object] | None) -> ModelConfigResource:
    if not isinstance(value, dict) or not isinstance(value.get("model_config"), dict):
        raise RuntimeError("terminal model configuration projection is invalid")
    return ModelConfigResource.model_validate(value["model_config"])


def _stored_capability_default(value: dict[str, object] | None) -> CapabilityDefaultResource:
    if not isinstance(value, dict) or not isinstance(value.get("capability_default"), dict):
        raise RuntimeError("terminal capability default projection is invalid")
    return CapabilityDefaultResource.model_validate(value["capability_default"])


def _stored_connection_result(value: dict[str, object] | None) -> ModelConnectionTestResult:
    if not isinstance(value, dict) or not isinstance(value.get("connection_result"), dict):
        raise RuntimeError("terminal model connection result is invalid")
    return ModelConnectionTestResult.model_validate(value["connection_result"])


def _not_found() -> PlatformError:
    return PlatformError(
        title="Model configuration not found",
        detail="The model configuration does not exist.",
        status=404,
        code="MODEL_CONFIG_NOT_FOUND",
    )


def _code_conflict() -> PlatformError:
    return PlatformError(
        title="Model configuration code conflict",
        detail="The config_code is already in use.",
        status=409,
        code="MODEL_CONFIG_CODE_CONFLICT",
    )


def _model_config_integrity_error(error: IntegrityError) -> PlatformError:
    args = list(getattr(error.orig, "args", ()))
    vendor_code = args[0] if args else None
    vendor_message = str(args[1]) if len(args) > 1 else ""
    if vendor_code == 1062 and "uq_atp_model_config_business" in vendor_message:
        return _code_conflict()
    return PlatformError(
        title="Internal server error",
        detail="The model configuration command could not be completed.",
        status=500,
        code="INTERNAL_ERROR",
    )


def _state_forbidden(detail: str) -> PlatformError:
    return PlatformError(
        title="Operation forbidden for model configuration state",
        detail=detail,
        status=409,
        code="MODEL_CONFIG_OPERATION_FORBIDDEN_FOR_STATE",
    )


def _connection_test_attempt_stale() -> PlatformError:
    return PlatformError(
        title="Model connection test attempt is stale",
        detail=("A newer attempt owns this idempotency key; the stale result was not persisted."),
        status=409,
        code="MODEL_CONFIG_CONNECTION_TEST_ATTEMPT_STALE",
    )


def _capability_concurrency_conflict() -> PlatformError:
    return PlatformError(
        title="Capability default concurrency conflict",
        detail="The expected capability binding version no longer matches.",
        status=409,
        code="MODEL_CAPABILITY_DEFAULT_CONCURRENCY_CONFLICT",
    )


def _secret_store_unavailable() -> PlatformError:
    return PlatformError(
        title="Model secret store unavailable",
        detail="The model credential cannot be processed by this deployment.",
        status=503,
        code="MODEL_SECRET_STORE_UNAVAILABLE",
    )
