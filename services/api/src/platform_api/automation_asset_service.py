"""Login Strategy commands executed through the AutomationAsset aggregate boundary."""

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
    AutomationAssetListData,
    AutomationAssetResource,
    CreateAutomationAssetRequest,
    CreateLoginStrategyRequest,
    LifecycleCommandRequest,
    LoginStrategyListData,
    LoginStrategyResource,
    PageMeta,
    UpdateAutomationAssetRequest,
    UpdateLoginStrategyRequest,
)
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    AutomationAsset,
    IdempotencyRecord,
    LoginStrategy,
    LoginStrategyAudit,
    OutboxEvent,
    Project,
)
from platform_api.security import new_ulid, utc_now


class AutomationAssetService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency

    def create_automation_asset(
        self, token: str, body: CreateAutomationAssetRequest, key: str, context: AuditContext
    ) -> AutomationAssetResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "create_automation_asset", context
                )
                self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "create_automation_asset",
                    ("PROJECT_EDIT",),
                    body.project_id,
                    context,
                )
                record, replay = self._claim(
                    db, actor.user.user_id, "create_automation_asset", key, _payload(body)
                )
                if replay:
                    return _stored_asset(record.response_json)
                project = db.scalar(
                    select(Project)
                    .where(Project.project_id == body.project_id)
                    .with_for_update()
                )
                if project is None:
                    raise _project_not_found()
                if project.lifecycle_status != "ACTIVE":
                    raise _project_state_forbidden()
                now = utc_now()
                asset = AutomationAsset(
                    automation_asset_id=body.automation_asset_id or new_ulid(),
                    project_id=body.project_id,
                    lifecycle_status="CREATED",
                    display_name=body.display_name,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                db.add(asset)
                db.flush()
                resource = _asset_resource(asset)
                self._idempotency.complete(
                    record, 201, {"automation_asset": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _asset_integrity_error() from error

    def list_automation_assets(
        self,
        token: str,
        page: int,
        page_size: int,
        filter_value: str | None,
        context: AuditContext,
    ) -> AutomationAssetListData:
        filters = _parse_filter(filter_value, {"project_id", "lifecycle_status"})
        project_id = filters.get("project_id")
        if project_id is None:
            raise _scope_required("Automation Asset")
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_automation_asset", context
            )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "list_automation_asset", ("PROJECT_VIEW",), project_id, context
            )
            query = select(AutomationAsset).where(AutomationAsset.project_id == project_id)
            count = select(func.count(AutomationAsset.automation_asset_id)).where(
                AutomationAsset.project_id == project_id
            )
            if filters.get("lifecycle_status"):
                query = query.where(
                    AutomationAsset.lifecycle_status == filters["lifecycle_status"]
                )
                count = count.where(
                    AutomationAsset.lifecycle_status == filters["lifecycle_status"]
                )
            items = list(
                db.scalars(
                    query.order_by(AutomationAsset.updated_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return AutomationAssetListData(
                items=[_asset_resource(item) for item in items],
                page=PageMeta(page=page, page_size=page_size, total=int(db.scalar(count) or 0)),
            )

    def get_automation_asset(
        self, token: str, asset_id: str, context: AuditContext
    ) -> AutomationAssetResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_automation_asset", context
            )
            asset = db.get(AutomationAsset, asset_id)
            if asset is None:
                raise _asset_not_found()
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "get_automation_asset", ("PROJECT_VIEW",), asset.project_id, context
            )
            return _asset_resource(asset)

    def update_automation_asset(
        self,
        token: str,
        asset_id: str,
        body: UpdateAutomationAssetRequest,
        key: str,
        context: AuditContext,
    ) -> AutomationAssetResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "update_automation_asset", context
                )
                asset = db.scalar(
                    select(AutomationAsset)
                    .where(AutomationAsset.automation_asset_id == asset_id)
                    .with_for_update()
                )
                if asset is None:
                    raise _asset_not_found()
                self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "update_automation_asset",
                    ("PROJECT_EDIT",),
                    asset.project_id,
                    context,
                )
                record, replay = self._claim(
                    db, actor.user.user_id, "update_automation_asset", key, _payload(body, asset_id)
                )
                if replay:
                    return _stored_asset(record.response_json)
                _assert_asset_writable(asset)
                _check_version(asset.row_version, body.expected_version)
                asset.display_name = body.display_name
                asset.row_version += 1
                asset.updated_at = utc_now()
                asset.updated_by = actor.user.user_id
                resource = _asset_resource(asset)
                self._idempotency.complete(
                    record, 200, {"automation_asset": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _asset_integrity_error() from error

    def create_login_strategy(
        self, token: str, body: CreateLoginStrategyRequest, key: str, context: AuditContext
    ) -> LoginStrategyResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "create_login_strategy", context
                )
                self._authentication.require_project_permissions_in_transaction(
                    db, actor, "create_login_strategy", ("PROJECT_EDIT",), body.project_id, context
                )
                asset = self._lock_asset(db, body.automation_asset_id, body.project_id)
                record, replay = self._claim(
                    db, actor.user.user_id, "create_login_strategy", key, _payload(body)
                )
                if replay:
                    return _stored(record.response_json)
                _assert_asset_writable(asset)
                now = utc_now()
                strategy = LoginStrategy(
                    login_strategy_id=new_ulid(),
                    project_id=body.project_id,
                    automation_asset_id=asset.automation_asset_id,
                    local_storage_presets=[
                        item.model_dump(mode="json") for item in body.local_storage_presets
                    ],
                    refresh_after_local_storage=body.refresh_after_local_storage,
                    captcha_policy=body.captcha_policy,
                    captcha_request_header_name=body.captcha_request_header_name,
                    captcha_request_header_value=body.captcha_request_header_value,
                    captcha_response_header_name=body.captcha_response_header_name,
                    session_policy=body.session_policy,
                    lifecycle_status="CREATED",
                    display_name=body.display_name,
                    row_version=0,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                db.add(strategy)
                db.flush()
                self._audit(
                    db,
                    strategy,
                    actor.user.user_id,
                    context,
                    "LOGIN_STRATEGY_CREATED",
                    "create_login_strategy",
                    None,
                    None,
                    _strategy_projection(strategy),
                    body.reason,
                )
                resource = _strategy_resource(strategy)
                self._idempotency.complete(
                    record, 201, {"login_strategy": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _integrity_error() from error

    def list_login_strategies(
        self,
        token: str,
        page: int,
        page_size: int,
        filter_value: str | None,
        context: AuditContext,
    ) -> LoginStrategyListData:
        filters = _parse_filter(filter_value, {"project_id", "lifecycle_status"})
        project_id = filters.get("project_id")
        if project_id is None:
            raise _scope_required()
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_login_strategy", context
            )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "list_login_strategy", ("PROJECT_VIEW",), project_id, context
            )
            query = select(LoginStrategy).where(LoginStrategy.project_id == project_id)
            count = select(func.count(LoginStrategy.login_strategy_id)).where(
                LoginStrategy.project_id == project_id
            )
            if filters.get("lifecycle_status"):
                query = query.where(LoginStrategy.lifecycle_status == filters["lifecycle_status"])
                count = count.where(LoginStrategy.lifecycle_status == filters["lifecycle_status"])
            items = list(
                db.scalars(
                    query.order_by(LoginStrategy.updated_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return LoginStrategyListData(
                items=[_strategy_resource(item) for item in items],
                page=PageMeta(page=page, page_size=page_size, total=int(db.scalar(count) or 0)),
            )

    def get_login_strategy(
        self, token: str, strategy_id: str, context: AuditContext
    ) -> LoginStrategyResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_login_strategy", context
            )
            strategy = db.get(LoginStrategy, strategy_id)
            if strategy is None:
                raise _not_found()
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "get_login_strategy", ("PROJECT_VIEW",), strategy.project_id, context
            )
            return _strategy_resource(strategy)

    def update_login_strategy(
        self,
        token: str,
        strategy_id: str,
        body: UpdateLoginStrategyRequest,
        key: str,
        context: AuditContext,
    ) -> LoginStrategyResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "update_login_strategy", context
                )
                strategy = db.scalar(
                    select(LoginStrategy)
                    .where(LoginStrategy.login_strategy_id == strategy_id)
                    .with_for_update()
                )
                if strategy is None:
                    raise _not_found()
                asset = self._lock_asset(
                    db, strategy.automation_asset_id, strategy.project_id
                )
                self._authentication.require_project_permissions_in_transaction(
                    db,
                    actor,
                    "update_login_strategy",
                    ("PROJECT_EDIT",),
                    strategy.project_id,
                    context,
                )
                record, replay = self._claim(
                    db,
                    actor.user.user_id,
                    "update_login_strategy",
                    key,
                    _payload(body, strategy_id),
                )
                if replay:
                    return _stored(record.response_json)
                _assert_asset_writable(asset)
                _check_version(strategy.row_version, body.expected_version)
                if strategy.lifecycle_status not in {"CREATED", "DRAFT", "RECOVERED"}:
                    raise _state_error(
                        "Only CREATED, DRAFT, or RECOVERED strategies can be edited."
                    )
                previous_status = strategy.lifecycle_status
                before = _strategy_projection(strategy)
                fields = body.model_fields_set
                for name in (
                    "display_name",
                    "refresh_after_local_storage",
                    "captcha_policy",
                    "captcha_request_header_name",
                    "captcha_request_header_value",
                    "captcha_response_header_name",
                    "session_policy",
                ):
                    if name in fields:
                        setattr(strategy, name, getattr(body, name))
                if "local_storage_presets" in fields:
                    strategy.local_storage_presets = [
                        item.model_dump(mode="json")
                        for item in (body.local_storage_presets or [])
                    ]
                _validate_captcha(strategy)
                if previous_status == "CREATED":
                    strategy.lifecycle_status = "DRAFT"
                strategy.row_version += 1
                strategy.updated_at = utc_now()
                strategy.updated_by = actor.user.user_id
                after = _strategy_projection(strategy)
                self._audit(
                    db,
                    strategy,
                    actor.user.user_id,
                    context,
                    "LOGIN_STRATEGY_UPDATED",
                    "update_login_strategy",
                    previous_status,
                    before,
                    after,
                    body.reason,
                )
                if previous_status == "CREATED":
                    self._audit(
                        db,
                        strategy,
                        actor.user.user_id,
                        context,
                        "LOGIN_STRATEGY_DRAFT",
                        "update_login_strategy",
                        "CREATED",
                        before,
                        after,
                        body.reason,
                    )
                    self._event(
                        db,
                        strategy,
                        "login_strategy.draft",
                        actor.user.user_id,
                        context,
                        key,
                        "CREATED",
                        "DRAFT",
                        body.expected_version,
                        strategy.row_version,
                        {"changed_fields": sorted(fields - {"reason"})},
                    )
                resource = _strategy_resource(strategy)
                self._idempotency.complete(
                    record, 200, {"login_strategy": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _integrity_error() from error

    def activate_login_strategy(
        self,
        token: str,
        strategy_id: str,
        body: LifecycleCommandRequest,
        key: str,
        context: AuditContext,
    ) -> LoginStrategyResource:
        with self._factory.begin() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "activate_login_strategy", context
            )
            strategy = db.scalar(
                select(LoginStrategy)
                .where(LoginStrategy.login_strategy_id == strategy_id)
                .with_for_update()
            )
            if strategy is None:
                raise _not_found()
            asset = self._lock_asset(db, strategy.automation_asset_id, strategy.project_id)
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "activate_login_strategy",
                ("PROJECT_EDIT",),
                strategy.project_id,
                context,
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "activate_login_strategy",
                key,
                _payload(body, strategy_id),
            )
            if replay:
                return _stored(record.response_json)
            _assert_asset_writable(asset)
            _check_version(strategy.row_version, body.expected_version)
            if strategy.lifecycle_status not in {"DRAFT", "RECOVERED"}:
                raise _state_error("Only DRAFT or RECOVERED strategies can be activated.")
            _validate_captcha(strategy)
            previous_status = strategy.lifecycle_status
            before = _strategy_projection(strategy)
            strategy.lifecycle_status = "ACTIVE"
            strategy.row_version += 1
            strategy.updated_at = utc_now()
            strategy.updated_by = actor.user.user_id
            after = _strategy_projection(strategy)
            self._audit(
                db,
                strategy,
                actor.user.user_id,
                context,
                "LOGIN_STRATEGY_ACTIVE",
                "activate_login_strategy",
                previous_status,
                before,
                after,
                body.reason,
            )
            self._event(
                db,
                strategy,
                "login_strategy.active",
                actor.user.user_id,
                context,
                key,
                previous_status,
                "ACTIVE",
                body.expected_version,
                strategy.row_version,
                {"changed_fields": ["lifecycle_status"]},
            )
            resource = _strategy_resource(strategy)
            self._idempotency.complete(
                record, 200, {"login_strategy": resource.model_dump(mode="json")}
            )
            return resource

    @staticmethod
    def _lock_asset(db: Session, asset_id: str, project_id: str) -> AutomationAsset:
        asset = db.scalar(
            select(AutomationAsset)
            .where(
                AutomationAsset.automation_asset_id == asset_id,
                AutomationAsset.project_id == project_id,
            )
            .with_for_update()
        )
        if asset is None:
            raise PlatformError(
                title="Automation Asset not found",
                detail="The owning Automation Asset is unavailable in this project scope.",
                status=404,
                code="AUTOMATION_ASSET_NOT_FOUND",
            )
        return asset

    def _claim(
        self, db: Session, principal: str, operation: str, key: str, payload: bytes
    ) -> tuple[IdempotencyRecord, bool]:
        return self._idempotency.claim(db, principal, operation, key, payload)

    @staticmethod
    def _audit(
        db: Session,
        strategy: LoginStrategy,
        actor: str,
        context: AuditContext,
        action: str,
        operation: str,
        previous_status: str | None,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
        reason: str | None,
    ) -> None:
        db.add(
            LoginStrategyAudit(
                audit_id=new_ulid(),
                login_strategy_id=strategy.login_strategy_id,
                automation_asset_id=strategy.automation_asset_id,
                project_id=strategy.project_id,
                action=action,
                operation_id=operation,
                actor_user_id=actor,
                required_permission="PROJECT_EDIT",
                previous_status=previous_status,
                new_status=strategy.lifecycle_status,
                result_code="SUCCESS",
                reason=reason,
                before_json=before,
                after_json=after,
                correlation_id=context.correlation_id,
                occurred_at=utc_now(),
                source_context_hash=hashlib.sha256(
                    context.source_context.encode("utf-8")
                ).digest(),
            )
        )

    @staticmethod
    def _event(
        db: Session,
        strategy: LoginStrategy,
        event_type: str,
        actor: str,
        context: AuditContext,
        causation_id: str,
        from_state: str | None,
        to_state: str,
        expected_version: int,
        new_version: int,
        summary: dict[str, object],
    ) -> None:
        sequence = (
            int(
                db.scalar(
                    select(func.max(OutboxEvent.sequence)).where(
                        OutboxEvent.aggregate_id == strategy.login_strategy_id
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
                aggregate_id=strategy.login_strategy_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": occurred_at.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": strategy.login_strategy_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": strategy.project_id,
                    "payload": {
                        "login_strategy_id": strategy.login_strategy_id,
                        "project_id": strategy.project_id,
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


def _assert_asset_writable(asset: AutomationAsset) -> None:
    if asset.lifecycle_status in {"ARCHIVED", "LOGICALLY_DELETED"}:
        raise _state_error("The owning Automation Asset does not allow member changes.")


def _validate_captcha(strategy: LoginStrategy) -> None:
    headers = (
        strategy.captcha_request_header_name,
        strategy.captcha_request_header_value,
        strategy.captcha_response_header_name,
    )
    if strategy.captcha_policy == "NONE" and any(headers):
        raise _state_error("captcha headers require RESPONSE_HEADER policy")
    if strategy.captcha_policy == "RESPONSE_HEADER" and not all(headers):
        raise _state_error("RESPONSE_HEADER requires request name/value and response name")


def _strategy_resource(value: LoginStrategy) -> LoginStrategyResource:
    return LoginStrategyResource(
        login_strategy_id=value.login_strategy_id,
        project_id=value.project_id,
        automation_asset_id=value.automation_asset_id,
        display_name=value.display_name,
        local_storage_presets=value.local_storage_presets,
        refresh_after_local_storage=value.refresh_after_local_storage,
        captcha_policy=value.captcha_policy,
        captcha_request_header_name=value.captcha_request_header_name,
        captcha_request_header_value=value.captcha_request_header_value,
        captcha_response_header_name=value.captcha_response_header_name,
        session_policy=value.session_policy,
        lifecycle_status=value.lifecycle_status,
        row_version=value.row_version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _strategy_projection(value: LoginStrategy) -> dict[str, object]:
    return {
        "login_strategy_id": value.login_strategy_id,
        "automation_asset_id": value.automation_asset_id,
        "project_id": value.project_id,
        "display_name": value.display_name,
        "lifecycle_status": value.lifecycle_status,
        "row_version": value.row_version,
        "local_storage_preset_count": len(value.local_storage_presets),
        "refresh_after_local_storage": value.refresh_after_local_storage,
        "captcha_policy": value.captcha_policy,
        "captcha_headers_configured": all(
            (
                value.captcha_request_header_name,
                value.captcha_request_header_value,
                value.captcha_response_header_name,
            )
        ),
        "session_policy_configured": value.session_policy is not None,
    }


def _asset_resource(value: AutomationAsset) -> AutomationAssetResource:
    return AutomationAssetResource(
        automation_asset_id=value.automation_asset_id,
        project_id=value.project_id,
        display_name=value.display_name,
        lifecycle_status=value.lifecycle_status,
        row_version=value.row_version,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def _payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    value = body.model_dump(mode="json", exclude_none=False)
    if resource_id is not None:
        value["resource_id"] = resource_id
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stored(value: dict[str, object] | None) -> LoginStrategyResource:
    if not isinstance(value, dict) or not isinstance(value.get("login_strategy"), dict):
        raise PlatformError(
            title="Idempotency replay failed",
            detail="The stored response is unavailable.",
            status=409,
            code="IDEMPOTENCY_RESPONSE_UNAVAILABLE",
        )
    return LoginStrategyResource.model_validate(value["login_strategy"])


def _stored_asset(value: dict[str, object] | None) -> AutomationAssetResource:
    if not isinstance(value, dict) or not isinstance(value.get("automation_asset"), dict):
        raise PlatformError(
            title="Idempotency replay failed",
            detail="The stored response is unavailable.",
            status=409,
            code="IDEMPOTENCY_RESPONSE_UNAVAILABLE",
        )
    return AutomationAssetResource.model_validate(value["automation_asset"])


def _parse_filter(value: str | None, allowed: set[str]) -> dict[str, str]:
    if not value:
        return {}
    result: dict[str, str] = {}
    for item in value.split(";"):
        key, separator, field_value = item.partition("=")
        if not separator or key not in allowed or not field_value:
            raise PlatformError(
                title="Invalid Login Strategy filter",
                detail="Use declared semicolon-separated key=value filters.",
                status=400,
                code="LOGIN_STRATEGY_FILTER_INVALID",
            )
        result[key] = field_value
    return result


def _check_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise PlatformError(
            title="Concurrent modification",
            detail="The aggregate version no longer matches expected_version.",
            status=409,
            code="ROW_VERSION_CONFLICT",
        )


def _not_found() -> PlatformError:
    return PlatformError(
        title="Login Strategy not found",
        detail="The strategy does not exist.",
        status=404,
        code="LOGIN_STRATEGY_NOT_FOUND",
    )


def _scope_required(resource: str = "Login Strategy") -> PlatformError:
    return PlatformError(
        title="Project scope required",
        detail=f"{resource} listing requires project_id.",
        status=400,
        code="PROJECT_SCOPE_REQUIRED",
    )


def _state_error(detail: str) -> PlatformError:
    return PlatformError(
        title="Login Strategy state conflict",
        detail=detail,
        status=409,
        code="LOGIN_STRATEGY_STATE_CONFLICT",
    )


def _integrity_error() -> PlatformError:
    return PlatformError(
        title="Login Strategy conflict",
        detail="The Login Strategy violates an aggregate integrity constraint.",
        status=409,
        code="LOGIN_STRATEGY_CONFLICT",
    )


def _asset_not_found() -> PlatformError:
    return PlatformError(
        title="Automation Asset not found",
        detail="The Automation Asset does not exist.",
        status=404,
        code="AUTOMATION_ASSET_NOT_FOUND",
    )


def _project_not_found() -> PlatformError:
    return PlatformError(
        title="Project not found",
        detail="The owning Project does not exist.",
        status=404,
        code="PROJECT_NOT_FOUND",
    )


def _project_state_forbidden() -> PlatformError:
    return PlatformError(
        title="Project state conflict",
        detail="Automation Asset creation requires an ACTIVE Project.",
        status=409,
        code="PROJECT_STATE_CONFLICT",
    )


def _asset_integrity_error() -> PlatformError:
    return PlatformError(
        title="Automation Asset conflict",
        detail="The Automation Asset violates an integrity constraint.",
        status=409,
        code="AUTOMATION_ASSET_CONFLICT",
    )
