"""Transactional Test Account, credential revision, and terminal mapping service."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext
from platform_api.auth_service import AuthenticationService
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    AccountMappingRevision,
    BusinessTerminal,
    CredentialRevision,
    Environment,
    IdempotencyRecord,
    OutboxEvent,
    TestAccount,
    TestAccountAudit,
    TestAccountSecret,
)
from platform_api.secret_store import SecretProtector, SecretStoreError
from platform_api.security import new_ulid, utc_now
from platform_api.test_account_schemas import (
    CreateTestAccountRequest,
    PageMeta,
    RotateTestAccountSecretRequest,
    TestAccountLifecycleRequest,
    TestAccountListData,
    TestAccountResource,
    TestAccountTerminalResource,
    UpdateTestAccountRequest,
)

_TRANSITIONS = {
    "validate": ({"CONFIGURING"}, "VALIDATING", "test_account.validating"),
    "reconfigure": ({"VALIDATING"}, "CONFIGURING", "test_account.configuring"),
    "activate": ({"VALIDATING", "RECOVERING"}, "ACTIVE", "test_account.active"),
    "mark-credential-expired": (
        {"ACTIVE"},
        "CREDENTIAL_EXPIRED",
        "test_account.credential_expired",
    ),
    "recover": (
        {"CREDENTIAL_EXPIRED", "DISABLED"},
        "RECOVERING",
        "test_account.recovering",
    ),
    "disable": ({"ACTIVE"}, "DISABLED", "test_account.disabled"),
    "archive": ({"DISABLED"}, "ARCHIVED", "test_account.archived"),
}


class TestAccountService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        authentication: AuthenticationService,
        idempotency: IdempotencyCoordinator,
        secrets: SecretProtector,
    ) -> None:
        self._factory = factory
        self._authentication = authentication
        self._idempotency = idempotency
        self._secrets = secrets

    def create(
        self,
        token: str,
        body: CreateTestAccountRequest,
        key: str,
        context: AuditContext,
    ) -> TestAccountResource:
        try:
            with self._factory.begin() as db:
                actor = self._authentication.authenticate_access_in_transaction(
                    db, token, "create_test_account", context
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
                    "create_test_account",
                    ("PROJECT_EDIT",),
                    environment.project_id,
                    context,
                )
                if environment.lifecycle_status not in {
                    "CONFIGURING",
                    "VALIDATING",
                    "ACTIVE",
                    "RECOVERING",
                }:
                    raise _state_error("The environment does not allow Test Account creation.")
                terminals = list(
                    db.scalars(
                        select(BusinessTerminal)
                        .where(BusinessTerminal.business_terminal_id.in_(body.business_terminal_ids))
                        .order_by(BusinessTerminal.business_terminal_id)
                        .with_for_update()
                    )
                )
                if len(terminals) != len(body.business_terminal_ids):
                    raise _not_found()
                if any(
                    terminal.project_id != environment.project_id
                    or terminal.environment_id != environment.environment_id
                    for terminal in terminals
                ):
                    raise _scope_error()
                if any(terminal.lifecycle_status == "ARCHIVED" for terminal in terminals):
                    raise _state_error("Archived Business Terminals cannot receive accounts.")
                record, replay = self._claim(
                    db,
                    actor.user.user_id,
                    "create_test_account",
                    key,
                    _payload(body),
                )
                if replay:
                    return _stored(record.response_json)
                duplicate = db.scalar(
                    select(TestAccount.test_account_id).where(
                        TestAccount.project_id == environment.project_id,
                        TestAccount.environment_id == environment.environment_id,
                        TestAccount.account_identifier == body.account_identifier,
                    )
                )
                if duplicate is not None:
                    raise _identifier_conflict()
                account_id = new_ulid()
                credential_id = new_ulid()
                encrypted = self._encrypt(credential_id, body.secret_value)
                now = utc_now()
                account = TestAccount(
                    test_account_id=account_id,
                    project_id=environment.project_id,
                    environment_id=environment.environment_id,
                    account_identifier=body.account_identifier,
                    sso_identity_id=None,
                    login_qualification_id=None,
                    lifecycle_status="CONFIGURING",
                    credential_state="VALID",
                    display_name=body.display_name,
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                credential = CredentialRevision(
                    credential_revision_id=credential_id,
                    test_account_id=account_id,
                    project_id=environment.project_id,
                    revision_no=1,
                    secret_ref=f"test-account-secret:{credential_id}",
                    published_at=now,
                    superseded_by_revision_id=None,
                    lifecycle_status="PUBLISHED",
                    display_name="Initial credential",
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=actor.user.user_id,
                    updated_by=actor.user.user_id,
                    extension_json=None,
                )
                # These mappers intentionally have no relationship properties. Flush the
                # aggregate root and credential parent explicitly before their FK children.
                db.add(account)
                db.flush()
                db.add(credential)
                db.flush()
                db.add(
                    TestAccountSecret(
                        credential_revision_id=credential_id,
                        encrypted_secret=encrypted.ciphertext,
                        key_id=encrypted.key_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
                for terminal in terminals:
                    db.add(
                        AccountMappingRevision(
                            account_mapping_revision_id=new_ulid(),
                            project_id=environment.project_id,
                            test_account_id=account_id,
                            environment_id=environment.environment_id,
                            business_terminal_id=terminal.business_terminal_id,
                            lifecycle_status="PUBLISHED",
                            display_name=terminal.display_name,
                            row_version=1,
                            created_at=now,
                            updated_at=now,
                            created_by=actor.user.user_id,
                            updated_by=actor.user.user_id,
                            extension_json=None,
                        )
                    )
                db.flush()
                terminal_ids = sorted(item.business_terminal_id for item in terminals)
                self._audit(
                    db,
                    account,
                    terminal_ids,
                    actor.user.user_id,
                    context,
                    "TEST_ACCOUNT_CREATED",
                    "create_test_account",
                    "CREATED",
                    None,
                    _projection(account, terminal_ids, 1),
                    body.reason,
                    credential_changed=True,
                )
                self._event(
                    db,
                    account,
                    "test_account.configuring",
                    actor.user.user_id,
                    context,
                    key,
                    "CREATED",
                    "CONFIGURING",
                    0,
                    1,
                    {"business_terminal_ids": terminal_ids, "credential_revision_no": 1},
                )
                resource = _resource(db, account)
                self._idempotency.complete(
                    record, 201, {"test_account": resource.model_dump(mode="json")}
                )
                return resource
        except IntegrityError as error:
            raise _integrity_error(error) from error

    def list(
        self,
        token: str,
        page: int,
        page_size: int,
        filter_value: str | None,
        context: AuditContext,
    ) -> TestAccountListData:
        filters = _parse_filter(
            filter_value,
            {"project_id", "environment_id", "business_terminal_id", "lifecycle_status"},
        )
        project_id = filters.get("project_id")
        if project_id is None:
            raise _scope_required()
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "list_test_account", context
            )
            self._authentication.require_project_permissions_in_transaction(
                db, actor, "list_test_account", ("PROJECT_VIEW",), project_id, context
            )
            query = select(TestAccount).where(TestAccount.project_id == project_id)
            count = select(func.count(func.distinct(TestAccount.test_account_id))).where(
                TestAccount.project_id == project_id
            )
            if filters.get("environment_id"):
                query = query.where(TestAccount.environment_id == filters["environment_id"])
                count = count.where(TestAccount.environment_id == filters["environment_id"])
            if filters.get("lifecycle_status"):
                query = query.where(TestAccount.lifecycle_status == filters["lifecycle_status"])
                count = count.where(TestAccount.lifecycle_status == filters["lifecycle_status"])
            terminal_id = filters.get("business_terminal_id")
            if terminal_id:
                account_ids = select(AccountMappingRevision.test_account_id).where(
                    AccountMappingRevision.business_terminal_id == terminal_id,
                    AccountMappingRevision.lifecycle_status == "PUBLISHED",
                )
                query = query.where(TestAccount.test_account_id.in_(account_ids))
                count = count.where(TestAccount.test_account_id.in_(account_ids))
            accounts = list(
                db.scalars(
                    query.order_by(TestAccount.account_identifier)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            return TestAccountListData(
                items=[_resource(db, account) for account in accounts],
                page=PageMeta(page=page, page_size=page_size, total=int(db.scalar(count) or 0)),
            )

    def get(self, token: str, account_id: str, context: AuditContext) -> TestAccountResource:
        with self._factory() as db:
            actor = self._authentication.authenticate_access_in_transaction(
                db, token, "get_test_account", context
            )
            account = db.get(TestAccount, account_id)
            if account is None:
                raise _not_found()
            self._authentication.require_project_permissions_in_transaction(
                db,
                actor,
                "get_test_account",
                ("PROJECT_VIEW",),
                account.project_id,
                context,
            )
            return _resource(db, account)

    def update(
        self,
        token: str,
        account_id: str,
        body: UpdateTestAccountRequest,
        key: str,
        context: AuditContext,
    ) -> TestAccountResource:
        with self._factory.begin() as db:
            actor, account = self._locked_authorized(
                db, token, account_id, "update_test_account", context
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "update_test_account",
                key,
                _payload(body, account_id),
            )
            if replay:
                return _stored(record.response_json)
            _check_version(account.row_version, body.expected_version)
            if account.lifecycle_status == "ARCHIVED":
                raise _state_error("Archived Test Accounts are immutable.")
            if body.display_name == account.display_name:
                raise PlatformError(
                    title="No Test Account changes",
                    detail="The update has no effect.",
                    status=409,
                    code="TEST_ACCOUNT_UPDATE_NO_EFFECT",
                )
            terminal_ids = _terminal_ids(db, account.test_account_id)
            revision_no = _credential_revision_no(db, account.test_account_id)
            before = _projection(account, terminal_ids, revision_no)
            account.display_name = body.display_name
            account.row_version += 1
            account.updated_at = utc_now()
            account.updated_by = actor.user.user_id
            self._audit(
                db,
                account,
                terminal_ids,
                actor.user.user_id,
                context,
                "TEST_ACCOUNT_UPDATED",
                "update_test_account",
                account.lifecycle_status,
                before,
                _projection(account, terminal_ids, revision_no),
                body.reason,
            )
            self._event(
                db,
                account,
                "test_account.updated",
                actor.user.user_id,
                context,
                key,
                account.lifecycle_status,
                account.lifecycle_status,
                body.expected_version,
                account.row_version,
                {"changed_fields": ["display_name"]},
            )
            resource = _resource(db, account)
            self._idempotency.complete(
                record, 200, {"test_account": resource.model_dump(mode="json")}
            )
            return resource

    def rotate_secret(
        self,
        token: str,
        account_id: str,
        body: RotateTestAccountSecretRequest,
        key: str,
        context: AuditContext,
    ) -> TestAccountResource:
        with self._factory.begin() as db:
            actor, account = self._locked_authorized(
                db, token, account_id, "rotate_test_account_secret", context
            )
            record, replay = self._claim(
                db,
                actor.user.user_id,
                "rotate_test_account_secret",
                key,
                _payload(body, account_id),
            )
            if replay:
                return _stored(record.response_json)
            _check_version(account.row_version, body.expected_version)
            if account.lifecycle_status == "ARCHIVED":
                raise _state_error("Archived Test Accounts cannot rotate credentials.")
            previous = db.scalar(
                select(CredentialRevision)
                .where(
                    CredentialRevision.test_account_id == account_id,
                    CredentialRevision.lifecycle_status == "PUBLISHED",
                )
                .order_by(CredentialRevision.revision_no.desc())
                .with_for_update()
            )
            if previous is None:
                raise _state_error("The current credential revision is unavailable.")
            credential_id = new_ulid()
            encrypted = self._encrypt(credential_id, body.secret_value)
            now = utc_now()
            revision_no = previous.revision_no + 1
            new_credential = CredentialRevision(
                credential_revision_id=credential_id,
                test_account_id=account_id,
                project_id=account.project_id,
                revision_no=revision_no,
                secret_ref=f"test-account-secret:{credential_id}",
                published_at=now,
                superseded_by_revision_id=None,
                lifecycle_status="PUBLISHED",
                display_name=f"Credential revision {revision_no}",
                row_version=1,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json=None,
            )
            # Insert the new parent before the old revision points at it and before
            # the encrypted secret row enforces its FK.
            db.add(new_credential)
            db.flush()
            previous.lifecycle_status = "SUPERSEDED"
            previous.superseded_by_revision_id = credential_id
            previous.row_version += 1
            previous.updated_at = now
            previous.updated_by = actor.user.user_id
            db.add(
                TestAccountSecret(
                    credential_revision_id=credential_id,
                    encrypted_secret=encrypted.ciphertext,
                    key_id=encrypted.key_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            terminal_ids = _terminal_ids(db, account_id)
            before = _projection(account, terminal_ids, previous.revision_no)
            account.credential_state = "VALID"
            account.row_version += 1
            account.updated_at = now
            account.updated_by = actor.user.user_id
            self._audit(
                db,
                account,
                terminal_ids,
                actor.user.user_id,
                context,
                "TEST_ACCOUNT_CREDENTIAL_ROTATED",
                "rotate_test_account_secret",
                account.lifecycle_status,
                before,
                _projection(account, terminal_ids, revision_no),
                body.reason,
                credential_changed=True,
            )
            self._event(
                db,
                account,
                "test_account.credential_rotated",
                actor.user.user_id,
                context,
                key,
                account.lifecycle_status,
                account.lifecycle_status,
                body.expected_version,
                account.row_version,
                {"credential_revision_no": revision_no},
            )
            db.flush()
            resource = _resource(db, account)
            self._idempotency.complete(
                record, 200, {"test_account": resource.model_dump(mode="json")}
            )
            return resource

    def transition(
        self,
        token: str,
        account_id: str,
        action: str,
        body: TestAccountLifecycleRequest,
        key: str,
        context: AuditContext,
    ) -> TestAccountResource:
        if action not in _TRANSITIONS:
            raise _state_error("Unknown Test Account lifecycle command.")
        allowed, target, event_type = _TRANSITIONS[action]
        operation_id = f"{action.replace('-', '_')}_test_account"
        with self._factory.begin() as db:
            actor, account = self._locked_authorized(
                db, token, account_id, operation_id, context
            )
            record, replay = self._claim(
                db, actor.user.user_id, operation_id, key, _payload(body, account_id)
            )
            if replay:
                return _stored(record.response_json)
            _check_version(account.row_version, body.expected_version)
            if account.lifecycle_status not in allowed:
                raise _state_error(f"{action} is not allowed from {account.lifecycle_status}.")
            terminal_ids = _terminal_ids(db, account_id)
            revision_no = _credential_revision_no(db, account_id)
            if action == "activate":
                self._assert_activation_ready(db, account, terminal_ids)
            if action == "recover" and account.credential_state != "VALID":
                raise _state_error("Recovery requires a valid rotated credential.")
            previous = account.lifecycle_status
            before = _projection(account, terminal_ids, revision_no)
            account.lifecycle_status = target
            if action == "mark-credential-expired":
                account.credential_state = "EXPIRED"
            account.row_version += 1
            account.updated_at = utc_now()
            account.updated_by = actor.user.user_id
            member_transitions: list[dict[str, object]] = []
            if action == "archive":
                member_transitions = _archive_members(
                    db,
                    account_id,
                    actor.user.user_id,
                    account.updated_at,
                    context,
                    key,
                )
            after = _projection(account, terminal_ids, revision_no)
            if member_transitions:
                after["member_lifecycle_transitions"] = member_transitions
            self._audit(
                db,
                account,
                terminal_ids,
                actor.user.user_id,
                context,
                f"TEST_ACCOUNT_{target}",
                operation_id,
                previous,
                before,
                after,
                body.reason,
            )
            self._event(
                db,
                account,
                event_type,
                actor.user.user_id,
                context,
                key,
                previous,
                target,
                body.expected_version,
                account.row_version,
                {"reason_supplied": True},
            )
            resource = _resource(db, account)
            self._idempotency.complete(
                record, 200, {"test_account": resource.model_dump(mode="json")}
            )
            return resource

    def _locked_authorized(
        self,
        db: Session,
        token: str,
        account_id: str,
        operation_id: str,
        context: AuditContext,
    ):
        actor = self._authentication.authenticate_access_in_transaction(
            db, token, operation_id, context
        )
        account = db.scalar(
            select(TestAccount)
            .where(TestAccount.test_account_id == account_id)
            .with_for_update()
        )
        if account is None:
            raise _not_found()
        self._authentication.require_project_permissions_in_transaction(
            db, actor, operation_id, ("PROJECT_EDIT",), account.project_id, context
        )
        return actor, account

    def _assert_activation_ready(
        self, db: Session, account: TestAccount, terminal_ids: list[str]
    ) -> None:
        environment = db.get(Environment, account.environment_id)
        if (
            environment is None
            or environment.project_id != account.project_id
            or environment.lifecycle_status != "ACTIVE"
        ):
            raise _state_error("Activation requires an ACTIVE owning Environment.")
        if not terminal_ids:
            raise _state_error("Activation requires a published Business Terminal mapping.")
        terminals = list(
            db.scalars(
                select(BusinessTerminal).where(
                    BusinessTerminal.business_terminal_id.in_(terminal_ids)
                )
            )
        )
        if len(terminals) != len(terminal_ids) or any(
            item.project_id != account.project_id
            or item.environment_id != account.environment_id
            or item.lifecycle_status != "ACTIVE"
            for item in terminals
        ):
            raise _state_error("Activation requires ACTIVE in-scope Business Terminals.")
        credential = db.scalar(
            select(CredentialRevision.credential_revision_id).where(
                CredentialRevision.test_account_id == account.test_account_id,
                CredentialRevision.lifecycle_status == "PUBLISHED",
            )
        )
        if credential is None or db.get(TestAccountSecret, credential) is None:
            raise _state_error("Activation requires a published encrypted credential.")

    def _encrypt(self, credential_id: str, value: str):
        try:
            return self._secrets.encrypt_scoped(
                "test-account-credential", credential_id, value
            )
        except SecretStoreError as error:
            raise PlatformError(
                title="Test Account credential store unavailable",
                detail="The credential could not be stored securely.",
                status=503,
                code="TEST_ACCOUNT_SECRET_STORE_UNAVAILABLE",
            ) from error

    def _claim(
        self, db: Session, principal: str, operation: str, key: str, payload: bytes
    ) -> tuple[IdempotencyRecord, bool]:
        return self._idempotency.claim(db, principal, operation, key, payload)

    @staticmethod
    def _audit(
        db: Session,
        account: TestAccount,
        terminal_ids: list[str],
        actor: str,
        context: AuditContext,
        action: str,
        operation: str,
        previous_status: str | None,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
        reason: str | None,
        *,
        credential_changed: bool = False,
    ) -> None:
        db.add(
            TestAccountAudit(
                audit_id=new_ulid(),
                test_account_id=account.test_account_id,
                project_id=account.project_id,
                environment_id=account.environment_id,
                business_terminal_ids=terminal_ids,
                action=action,
                operation_id=operation,
                actor_user_id=actor,
                required_permission="PROJECT_EDIT",
                previous_status=previous_status,
                new_status=account.lifecycle_status,
                result_code="SUCCESS",
                reason=reason,
                before_json=before,
                after_json=after,
                credential_changed=credential_changed,
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
        account: TestAccount,
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
                        OutboxEvent.aggregate_id == account.test_account_id
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
                aggregate_id=account.test_account_id,
                sequence=sequence,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "event_version": "1.0.0",
                    "occurred_at": occurred_at.replace(tzinfo=UTC).isoformat(),
                    "aggregate_id": account.test_account_id,
                    "sequence": sequence,
                    "correlation_id": context.correlation_id,
                    "causation_id": causation_id,
                    "project_id": account.project_id,
                    "payload": {
                        "test_account_id": account.test_account_id,
                        "project_id": account.project_id,
                        "environment_id": account.environment_id,
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


def _resource(db: Session, account: TestAccount) -> TestAccountResource:
    mapping_status = "ARCHIVED" if account.lifecycle_status == "ARCHIVED" else "PUBLISHED"
    mappings = list(
        db.execute(
            select(AccountMappingRevision, BusinessTerminal)
            .join(
                BusinessTerminal,
                BusinessTerminal.business_terminal_id
                == AccountMappingRevision.business_terminal_id,
            )
            .where(
                AccountMappingRevision.test_account_id == account.test_account_id,
                AccountMappingRevision.lifecycle_status == mapping_status,
            )
            .order_by(BusinessTerminal.terminal_code)
        )
    )
    return TestAccountResource(
        test_account_id=account.test_account_id,
        project_id=account.project_id,
        environment_id=account.environment_id,
        account_identifier=account.account_identifier,
        display_name=account.display_name,
        lifecycle_status=account.lifecycle_status,
        credential_state=account.credential_state,
        credential_revision_no=_credential_revision_no(db, account.test_account_id),
        business_terminals=[
            TestAccountTerminalResource(
                business_terminal_id=terminal.business_terminal_id,
                terminal_code=terminal.terminal_code,
                display_name=terminal.display_name,
                terminal_type=terminal.terminal_type,
            )
            for _, terminal in mappings
        ],
        row_version=account.row_version,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _terminal_ids(db: Session, account_id: str) -> list[str]:
    return list(
        db.scalars(
            select(AccountMappingRevision.business_terminal_id)
            .where(
                AccountMappingRevision.test_account_id == account_id,
                AccountMappingRevision.lifecycle_status == "PUBLISHED",
            )
            .order_by(AccountMappingRevision.business_terminal_id)
        )
    )


def _archive_members(
    db: Session,
    account_id: str,
    actor_user_id: str,
    occurred_at: datetime,
    context: AuditContext,
    causation_id: str,
) -> list[dict[str, object]]:
    """Retire, then archive lifecycle-dependent members with their aggregate root."""
    transitions: list[dict[str, object]] = []
    for model in (CredentialRevision, AccountMappingRevision):
        members = list(
            db.scalars(
                select(model)
                .where(
                    model.test_account_id == account_id,
                    model.lifecycle_status != "ARCHIVED",
                )
                .with_for_update()
            )
        )
        for member in members:
            if member.lifecycle_status not in {"PUBLISHED", "SUPERSEDED", "RETIRED"}:
                raise _state_error(
                    "Test Account members must be published, superseded, or retired before archive."
                )
            member_kind = (
                "credential_revision"
                if model is CredentialRevision
                else "account_mapping_revision"
            )
            member_id = (
                member.credential_revision_id
                if model is CredentialRevision
                else member.account_mapping_revision_id
            )
            if member.lifecycle_status != "RETIRED":
                previous = member.lifecycle_status
                expected_version = member.row_version
                member.lifecycle_status = "RETIRED"
                member.row_version += 1
                member.updated_at = occurred_at
                member.updated_by = actor_user_id
                _member_lifecycle_event(
                    db,
                    member,
                    member_kind,
                    f"{member_kind}.retired",
                    previous,
                    "RETIRED",
                    expected_version,
                    actor_user_id,
                    context,
                    causation_id,
                )
                db.flush()
                transitions.append(
                    {
                        "member_type": member_kind,
                        "member_id": member_id,
                        "from_state": previous,
                        "to_state": "RETIRED",
                    }
                )
            expected_version = member.row_version
            member.lifecycle_status = "ARCHIVED"
            member.row_version += 1
            member.updated_at = occurred_at
            member.updated_by = actor_user_id
            _member_lifecycle_event(
                db,
                member,
                member_kind,
                f"{member_kind}.archived",
                "RETIRED",
                "ARCHIVED",
                expected_version,
                actor_user_id,
                context,
                causation_id,
            )
            transitions.append(
                {
                    "member_type": member_kind,
                    "member_id": member_id,
                    "from_state": "RETIRED",
                    "to_state": "ARCHIVED",
                }
            )
    return transitions


def _member_lifecycle_event(
    db: Session,
    member: CredentialRevision | AccountMappingRevision,
    member_kind: str,
    event_type: str,
    from_state: str,
    to_state: str,
    expected_version: int,
    actor_user_id: str,
    context: AuditContext,
    causation_id: str,
) -> None:
    aggregate_id = (
        member.credential_revision_id
        if member_kind == "credential_revision"
        else member.account_mapping_revision_id
    )
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
    payload: dict[str, object] = {
        "project_id": member.project_id,
        "from_state": from_state,
        "to_state": to_state,
        "expected_version": expected_version,
        "new_version": member.row_version,
        "changed_by": actor_user_id,
        "change_summary": {"archive_with_test_account": True},
    }
    if member_kind == "credential_revision":
        payload.update(
            {
                "credential_revision_id": member.credential_revision_id,
                "test_account_id": member.test_account_id,
                "revision_no": member.revision_no,
            }
        )
    else:
        payload["account_mapping_revision_id"] = member.account_mapping_revision_id
    event_time = utc_now()
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
                "occurred_at": event_time.replace(tzinfo=UTC).isoformat(),
                "aggregate_id": aggregate_id,
                "sequence": sequence,
                "correlation_id": context.correlation_id,
                "causation_id": causation_id,
                "project_id": member.project_id,
                "payload": payload,
            },
            occurred_at=event_time,
            published_at=None,
            attempt_count=0,
        )
    )


def _credential_revision_no(db: Session, account_id: str) -> int:
    value = db.scalar(
        select(func.max(CredentialRevision.revision_no)).where(
            CredentialRevision.test_account_id == account_id,
            CredentialRevision.lifecycle_status.in_(
                ("PUBLISHED", "SUPERSEDED", "ARCHIVED")
            ),
        )
    )
    if value is None:
        raise _state_error("The Test Account credential revision is unavailable.")
    return int(value)


def _projection(
    account: TestAccount, terminal_ids: list[str], credential_revision_no: int
) -> dict[str, object]:
    return {
        "test_account_id": account.test_account_id,
        "project_id": account.project_id,
        "environment_id": account.environment_id,
        "account_identifier": account.account_identifier,
        "display_name": account.display_name,
        "lifecycle_status": account.lifecycle_status,
        "credential_state": account.credential_state,
        "credential_revision_no": credential_revision_no,
        "business_terminal_ids": terminal_ids,
        "row_version": account.row_version,
    }


def _payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    document = body.model_dump(mode="json")
    if "secret_value" in document:
        document["secret_value"] = hashlib.sha256(
            document["secret_value"].encode("utf-8")
        ).hexdigest()
    if resource_id is not None:
        document["test_account_id"] = resource_id
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _stored(value: dict[str, object] | None) -> TestAccountResource:
    if not value or "test_account" not in value:
        raise PlatformError(
            title="Idempotency state is invalid",
            detail="The stored Test Account response is unavailable.",
            status=500,
            code="TEST_ACCOUNT_IDEMPOTENCY_STATE_INVALID",
        )
    return TestAccountResource.model_validate(value["test_account"])


def _parse_filter(value: str | None, allowed: set[str]) -> dict[str, str]:
    if not value:
        return {}
    result: dict[str, str] = {}
    for raw in value.split(";"):
        if not raw:
            continue
        key, separator, item = raw.partition("=")
        if not separator or key not in allowed or not item:
            raise PlatformError(
                title="Invalid Test Account filter",
                detail="Only governed scope and lifecycle filters are accepted.",
                status=422,
                code="TEST_ACCOUNT_FILTER_INVALID",
            )
        result[key] = item
    return result


def _check_version(actual: int, expected: int) -> None:
    if actual != expected:
        raise PlatformError(
            title="Test Account concurrency conflict",
            detail="The Test Account changed after it was loaded.",
            status=409,
            code="TEST_ACCOUNT_CONCURRENCY_CONFLICT",
        )


def _not_found() -> PlatformError:
    return PlatformError(
        title="Test Account not found",
        detail="The requested resource is unavailable in the authorized project scope.",
        status=404,
        code="TEST_ACCOUNT_NOT_FOUND",
    )


def _scope_error() -> PlatformError:
    return PlatformError(
        title="Test Account scope mismatch",
        detail="The Environment and Business Terminals must belong to the same Project scope.",
        status=409,
        code="TEST_ACCOUNT_SCOPE_MISMATCH",
    )


def _scope_required() -> PlatformError:
    return PlatformError(
        title="Test Account Project scope required",
        detail="List requests must include filter=project_id=<id>.",
        status=422,
        code="TEST_ACCOUNT_PROJECT_SCOPE_REQUIRED",
    )


def _state_error(detail: str) -> PlatformError:
    return PlatformError(
        title="Test Account state conflict",
        detail=detail,
        status=409,
        code="TEST_ACCOUNT_STATE_CONFLICT",
    )


def _identifier_conflict() -> PlatformError:
    return PlatformError(
        title="Test Account identifier conflict",
        detail="The account identifier already exists in this Environment.",
        status=409,
        code="TEST_ACCOUNT_IDENTIFIER_CONFLICT",
    )


def _integrity_error(error: IntegrityError) -> PlatformError:
    message = str(error.orig).casefold()
    if "uq_atp_test_account_business" in message or "duplicate" in message:
        return _identifier_conflict()
    return PlatformError(
        title="Test Account persistence conflict",
        detail="The Test Account command could not be committed.",
        status=409,
        code="TEST_ACCOUNT_PERSISTENCE_CONFLICT",
    )
