from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from platform_api.models import TestAccount as AccountModel
from platform_api.errors import PlatformError
from platform_api.audit import AuditContext
from platform_api.secret_store import AesGcmSecretProtector
from platform_api.test_account_router import router
from platform_api.test_account_schemas import (
    CreateTestAccountRequest,
    RotateTestAccountSecretRequest,
    TestAccountLifecycleRequest as LifecycleRequest,
    TestAccountResource as AccountResource,
)
from platform_api.test_account_service import (
    _TRANSITIONS,
    TestAccountService as AccountService,
    _check_version,
    _parse_filter,
    _payload,
)
from pydantic import ValidationError


def test_test_account_routes_expose_commands_without_patch_state_escape() -> None:
    operations = {route.operation_id for route in router.routes if route.operation_id}
    assert {
        "list_test_account",
        "create_test_account",
        "get_test_account",
        "update_test_account",
        "rotate_test_account_secret",
        "validate_test_account",
        "reconfigure_test_account",
        "activate_test_account",
        "mark_credential_expired_test_account",
        "recover_test_account",
        "disable_test_account",
        "archive_test_account",
    }.issubset(operations)


def test_create_contract_requires_scope_mapping_and_delivery_only_secret() -> None:
    body = CreateTestAccountRequest(
        environment_id="E" * 26,
        account_identifier="qa-user",
        business_terminal_ids=["T" * 26],
        secret_value="not-a-real-password",
        reason="test setup",
    )
    assert body.account_identifier == "qa-user"
    assert "secret_value" not in AccountResource.model_fields
    assert "business_terminal_ids" not in AccountResource.model_fields
    with pytest.raises(ValidationError):
        CreateTestAccountRequest(
            environment_id="E" * 26,
            account_identifier=" qa-user",
            business_terminal_ids=["T" * 26, "T" * 26],
            secret_value="x",
            reason="test setup",
        )


def test_secret_payload_hashes_plaintext_before_idempotency_storage() -> None:
    body = RotateTestAccountSecretRequest(
        expected_version=3,
        secret_value="not-a-real-password",
        reason="rotation",
    )
    serialized = _payload(body, "A" * 26)
    assert b"not-a-real-password" not in serialized
    assert b"secret_value" in serialized


def test_test_account_secret_uses_existing_aes_gcm_key_ring_with_scoped_aad() -> None:
    protector = AesGcmSecretProtector("active", {"active": b"K" * 32})
    encrypted = protector.encrypt_scoped(
        "test-account-credential", "C" * 26, "not-a-real-password"
    )
    assert b"not-a-real-password" not in encrypted.ciphertext
    assert (
        protector.decrypt_scoped(
            "test-account-credential",
            "C" * 26,
            encrypted.ciphertext,
            encrypted.key_id,
        )
        == "not-a-real-password"
    )
    with pytest.raises(Exception):
        protector.decrypt_scoped(
            "test-account-credential",
            "D" * 26,
            encrypted.ciphertext,
            encrypted.key_id,
        )


def test_lifecycle_matches_lc_013() -> None:
    assert _TRANSITIONS["validate"][:2] == ({"CONFIGURING"}, "VALIDATING")
    assert _TRANSITIONS["activate"][:2] == ({"VALIDATING", "RECOVERING"}, "ACTIVE")
    assert _TRANSITIONS["mark-credential-expired"][:2] == (
        {"ACTIVE"},
        "CREDENTIAL_EXPIRED",
    )
    assert _TRANSITIONS["recover"][:2] == (
        {"CREDENTIAL_EXPIRED", "DISABLED"},
        "RECOVERING",
    )
    assert _TRANSITIONS["archive"][:2] == ({"DISABLED"}, "ARCHIVED")


class _ArchiveCommandSession:
    def __init__(self) -> None:
        now = datetime(2026, 8, 28, 12, 0, 0)
        self.account = SimpleNamespace(
            test_account_id="A" * 26,
            project_id="P" * 26,
            environment_id="E" * 26,
            account_identifier="qa-user",
            display_name="QA User",
            lifecycle_status="DISABLED",
            credential_state="VALID",
            row_version=7,
            created_at=now,
            updated_at=now,
            updated_by="U" * 26,
        )
        self.credentials = [
            SimpleNamespace(
                credential_revision_id="C" * 26,
                test_account_id="A" * 26,
                project_id="P" * 26,
                revision_no=1,
                lifecycle_status="SUPERSEDED",
                row_version=2,
                updated_at=now,
                updated_by="U" * 26,
            ),
            SimpleNamespace(
                credential_revision_id="D" * 26,
                test_account_id="A" * 26,
                project_id="P" * 26,
                revision_no=2,
                lifecycle_status="PUBLISHED",
                row_version=1,
                updated_at=now,
                updated_by="U" * 26,
            ),
        ]
        self.mapping = SimpleNamespace(
            account_mapping_revision_id="M" * 26,
            test_account_id="A" * 26,
            project_id="P" * 26,
            lifecycle_status="PUBLISHED",
            row_version=1,
            updated_at=now,
            updated_by="U" * 26,
        )
        self.terminal = SimpleNamespace(
            business_terminal_id="T" * 26,
            terminal_code="management",
            display_name="Management",
            terminal_type="MANAGEMENT",
        )
        self.record = SimpleNamespace()
        self.added: list[object] = []
        self._scalars_results = iter(
            ([self.terminal.business_terminal_id], self.credentials, [self.mapping])
        )

    def scalar(self, statement: object):
        compiled = str(statement.compile())
        if "FROM atp_test_account" in compiled and "max(" not in compiled:
            return self.account
        if "max(atp_credential_revision.revision_no)" in compiled:
            if self.account.lifecycle_status == "ARCHIVED":
                assert any(
                    value == "ARCHIVED"
                    or isinstance(value, (list, tuple))
                    and "ARCHIVED" in value
                    for value in statement.compile().params.values()
                )
            return 2
        if "max(atp_outbox_event.sequence)" in compiled:
            return 0
        raise AssertionError("unexpected scalar query")

    def scalars(self, _: object):
        return next(self._scalars_results)

    def execute(self, statement: object):
        assert "ARCHIVED" in statement.compile().params.values()
        return [(self.mapping, self.terminal)]

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None


class _ArchiveFactory:
    def __init__(self, session: _ArchiveCommandSession) -> None:
        self.session = session

    def begin(self):
        session = self.session

        class _Transaction:
            def __enter__(self):
                return session

            def __exit__(self, *_: object) -> None:
                return None

        return _Transaction()


class _ArchiveAuthentication:
    @staticmethod
    def authenticate_access_in_transaction(*_: object):
        return SimpleNamespace(user=SimpleNamespace(user_id="U" * 26))

    @staticmethod
    def require_project_permissions_in_transaction(*_: object) -> None:
        return None


class _ArchiveIdempotency:
    def __init__(self, record: object) -> None:
        self.record = record

    def claim(self, *_: object):
        return self.record, False

    @staticmethod
    def complete(record: object, status: int, response_json: dict[str, object]) -> None:
        record.response_status = status
        record.response_json = response_json


def test_archive_command_projects_archived_member_history_without_rollback() -> None:
    session = _ArchiveCommandSession()
    service = AccountService(
        _ArchiveFactory(session),
        _ArchiveAuthentication(),
        _ArchiveIdempotency(session.record),
        SimpleNamespace(),
    )

    resource = service.transition(
        "token",
        session.account.test_account_id,
        "archive",
        LifecycleRequest(expected_version=7, reason="retired"),
        "archive-key",
        AuditContext(correlation_id="corr", source_context="test"),
    )

    assert resource.lifecycle_status == "ARCHIVED"
    assert resource.credential_revision_no == 2
    assert [item.business_terminal_id for item in resource.business_terminals] == ["T" * 26]
    assert all(item.lifecycle_status == "ARCHIVED" for item in session.credentials)
    assert session.mapping.lifecycle_status == "ARCHIVED"
    assert [item.row_version for item in session.credentials] == [4, 3]
    assert session.mapping.row_version == 3
    event_types = [getattr(item, "event_type", None) for item in session.added]
    assert event_types.count("credential_revision.retired") == 2
    assert event_types.count("credential_revision.archived") == 2
    assert event_types.count("account_mapping_revision.retired") == 1
    assert event_types.count("account_mapping_revision.archived") == 1
    audit = next(item for item in session.added if item.__class__.__name__ == "TestAccountAudit")
    assert len(audit.after_json["member_lifecycle_transitions"]) == 6
    assert session.record.response_status == 200


def test_test_account_cas_and_filters_are_project_scoped() -> None:
    _check_version(4, 4)
    with pytest.raises(PlatformError) as raised:
        _check_version(5, 4)
    assert raised.value.code == "TEST_ACCOUNT_CONCURRENCY_CONFLICT"
    assert _parse_filter(
        "project_id=P;environment_id=E;business_terminal_id=T",
        {"project_id", "environment_id", "business_terminal_id"},
    ) == {"project_id": "P", "environment_id": "E", "business_terminal_id": "T"}
    with pytest.raises(PlatformError):
        _parse_filter("runner_id=R", {"project_id"})


class _EventSession:
    def __init__(self) -> None:
        self.added = None

    def scalar(self, _: object) -> int:
        return 0

    def add(self, value: object) -> None:
        self.added = value


def test_outbox_event_contains_scope_and_cas_but_no_secret() -> None:
    session = _EventSession()
    account = SimpleNamespace(
        test_account_id="A" * 26,
        project_id="P" * 26,
        environment_id="E" * 26,
    )
    AccountService._event(
        session,
        account,
        "test_account.credential_rotated",
        "U" * 26,
        SimpleNamespace(correlation_id="corr"),
        "idem",
        "ACTIVE",
        "ACTIVE",
        3,
        4,
        {"credential_revision_no": 2},
    )
    payload = session.added.payload_json
    assert payload["payload"]["environment_id"] == "E" * 26
    assert payload["payload"]["expected_version"] == 3
    serialized = str(payload).casefold()
    assert "password" not in serialized and "ciphertext" not in serialized


def test_migration_and_openapi_keep_secret_out_of_responses() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root / "docs/authority/编码权威事实/DATABASE_DDL/V14__test_account_foundation.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE atp_test_account_secret" in migration
    assert "VARBINARY(16412)" in migration
    assert "CREATE TABLE atp_test_account_audit" in migration
    assert "fk_atp_test_account_environment_scope" in migration
    scope_constraint = next(
        constraint
        for constraint in AccountModel.__table__.foreign_key_constraints
        if constraint.name == "fk_atp_test_account_environment_scope"
    )
    assert [column.parent.name for column in scope_constraint.elements] == [
        "environment_id",
        "project_id",
    ]
    assert [column.target_fullname for column in scope_constraint.elements] == [
        "atp_environment.environment_id",
        "atp_environment.project_id",
    ]
    assert "append-only" in migration
    assert "resource_lease" not in migration.casefold()
    assert "execution_context" not in migration.casefold()

    contract = yaml.safe_load(
        (root / "docs/authority/编码权威事实/OPENAPI/openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    schemas = contract["components"]["schemas"]
    assert schemas["CreateTestAccountRequest"]["properties"]["secret_value"]["writeOnly"]
    assert "secret_value" not in schemas["TestAccountResource"]["properties"]
    assert "secret_ref" not in schemas["TestAccountResource"]["properties"]
