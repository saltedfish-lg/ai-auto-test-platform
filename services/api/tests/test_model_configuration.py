from __future__ import annotations

import base64
import json
import secrets
import shutil
import urllib.request
from collections.abc import Iterator
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_api.audit import AuditContext
from platform_api.errors import PlatformError
from platform_api.model_configuration_router import router
from platform_api.model_configuration_schemas import (
    ClearCapabilityDefaultModelRequest,
    CreateModelConfigRequest,
    ModelConfigLifecycleRequest,
    ModelConfigResource,
    SetCapabilityDefaultModelRequest,
    UpdateModelConfigRequest,
)
from platform_api.model_configuration_schemas import (
    TestModelConfigConnectionRequest as ConnectionTestRequest,
)
from platform_api.model_configuration_service import (
    ModelConfigurationService,
    ResolvedModelConfiguration,
    _canonical_payload,
)
from platform_api.model_gateway import GatewayConnectionResult, LiteLLMModelGateway
from platform_api.models import (
    ModelCapabilityDefault,
    ModelConfiguration,
    ModelConfigurationAudit,
    ModelConfigurationSecret,
    OutboxEvent,
)
from platform_api.secret_store import AesGcmSecretProtector, SecretStoreError
from pydantic import ValidationError


_SUBMITTER_UNSET = object()


def _model(*, status: str = "VALIDATING", updated_by: str = "submitter") -> ModelConfiguration:
    now = datetime.now(UTC).replace(tzinfo=None)
    return ModelConfiguration(
        model_config_id="M" * 26,
        config_code="EXPLORATION-PRIMARY",
        provider_code="OPENAI",
        model_name="gpt-test",
        request_timeout_seconds=15,
        lifecycle_status=status,
        display_name="Exploration primary",
        row_version=4,
        created_at=now,
        updated_at=now,
        created_by="creator",
        updated_by=updated_by,
        extension_json=None,
    )


class _Transaction:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def __enter__(self) -> _Session:
        self._session.transaction_depth += 1
        return self._session

    def __exit__(self, *args: object) -> None:
        del args
        self._session.transaction_depth -= 1


class _NestedTransaction:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        del args


class _Factory:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def begin(self) -> _Transaction:
        return _Transaction(self.session)

    def __call__(self) -> _Transaction:
        return _Transaction(self.session)


class _Session:
    def __init__(
        self,
        model: ModelConfiguration,
        *,
        secret: ModelConfigurationSecret | None = None,
        default: ModelCapabilityDefault | None = None,
        submitted_by: str | None | object = _SUBMITTER_UNSET,
        allow_create: bool = False,
    ) -> None:
        self.model = model
        self.secret = secret
        self.default = default
        self.submitted_by = (
            model.updated_by if submitted_by is _SUBMITTER_UNSET else submitted_by
        )
        self.allow_create = allow_create
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.transaction_depth = 0
        self.lock_order: list[str] = []

    def scalar(self, statement: object) -> object | None:
        sql = str(statement)
        if "FOR UPDATE" in sql:
            if "FROM atp_idempotency_record" in sql:
                self.lock_order.append("idempotency")
            elif "FROM atp_model_config" in sql:
                self.lock_order.append("model")
        if "max(atp_outbox_event.sequence)" in sql:
            return 0
        if "count(atp_model_config.model_config_id)" in sql:
            return 1
        if "FROM atp_idempotency_record" in sql:
            return getattr(self, "idempotency_record", None)
        if "FROM atp_model_config_audit" in sql:
            return self.submitted_by
        if "atp_model_config_secret.model_config_id" in sql:
            return self.secret.model_config_id if self.secret is not None else None
        if "FROM atp_model_capability_default" in sql:
            descriptions = getattr(statement, "column_descriptions", [])
            if descriptions and descriptions[0].get("expr") is ModelCapabilityDefault:
                return self.default
            if "SELECT atp_model_capability_default.row_version" in sql:
                return self.default.row_version if self.default is not None else None
            if "SELECT atp_model_capability_default.capability_code" in sql:
                return self.default.capability_code if self.default is not None else None
            return self.default
        if "FROM atp_model_config" in sql:
            if self.allow_create and "atp_model_config.config_code" in sql:
                return None
            return self.model
        return None

    def scalars(self, statement: object) -> list[object]:
        if "FROM atp_model_config" in str(statement):
            return [self.model]
        return []

    def get(self, entity: type[object], key: str) -> object | None:
        if entity is ModelConfiguration:
            return self.model if key == self.model.model_config_id else None
        if entity is ModelConfigurationSecret:
            return self.secret
        if entity is ModelCapabilityDefault:
            return self.default
        return None

    def add(self, value: object) -> None:
        self.added.append(value)
        if (
            isinstance(value, ModelConfigurationAudit)
            and value.action == "MODEL_CONFIG_REVIEW_SUBMITTED"
        ):
            self.submitted_by = value.actor_user_id

    def delete(self, value: object) -> None:
        self.deleted.append(value)

    def merge(self, value: object) -> object:
        return value

    def begin_nested(self) -> _NestedTransaction:
        return _NestedTransaction()

    def flush(self) -> None:
        return None


class _Authentication:
    def __init__(
        self,
        user_id: str = "reviewer",
        *,
        allowed: bool = True,
        super_admin: bool = False,
    ) -> None:
        self.identity = SimpleNamespace(user=SimpleNamespace(user_id=user_id))
        self.allowed = allowed
        self.super_admin = super_admin
        self.permissions: list[tuple[str, tuple[str, ...]]] = []
        self.role_checks: list[tuple[str, str]] = []

    def authenticate_access_in_transaction(self, *args: object) -> object:
        del args
        return self.identity

    def require_platform_permissions_in_transaction(
        self,
        db: object,
        identity: object,
        operation_id: str,
        permission_codes: tuple[str, ...],
        context: object,
    ) -> None:
        del db, identity, context
        self.permissions.append((operation_id, permission_codes))
        if not self.allowed:
            raise PlatformError(
                title="Forbidden",
                detail="The operation is not permitted.",
                status=403,
                code="MODEL_CONFIG_PERMISSION_DENIED",
            )

    def user_has_active_platform_role_in_transaction(
        self,
        db: object,
        user_id: str,
        role_code: str,
    ) -> bool:
        del db
        self.role_checks.append((user_id, role_code))
        return self.super_admin and role_code == "ROLE-SUPER-ADMIN"


class _Idempotency:
    def __init__(self) -> None:
        self.completed: list[tuple[int, dict[str, object] | None]] = []
        self.record = SimpleNamespace(
            idempotency_key="model-test-idempotency-key",
            request_hash="model-test-request-hash",
            response_json=None,
            response_status=None,
            completed_at=None,
            expires_at=None,
        )

    def claim(self, *args: object) -> tuple[object, bool]:
        session = args[0]
        session.idempotency_record = self.record
        return self.record, False

    def complete(self, record: object, status: int, value: dict[str, object] | None) -> None:
        del record
        self.completed.append((status, value))


class _Gateway:
    def __init__(
        self,
        result: GatewayConnectionResult,
        session: _Session | None = None,
    ) -> None:
        self.result = result
        self.session = session
        self.received_secret: str | None = None

    def test_connection(self, **values: object) -> GatewayConnectionResult:
        if self.session is not None:
            assert self.session.transaction_depth == 0
        self.received_secret = str(values["provider_secret"])
        return self.result


class _ReclaimingGateway(_Gateway):
    def test_connection(self, **values: object) -> GatewayConnectionResult:
        result = super().test_connection(**values)
        assert self.session is not None
        record = self.session.idempotency_record
        record.expires_at += timedelta(seconds=1)
        return result


class _CompletedReplacementGateway(_Gateway):
    def test_connection(self, **values: object) -> GatewayConnectionResult:
        result = super().test_connection(**values)
        assert self.session is not None
        record = self.session.idempotency_record
        record.request_hash = "replacement-request-hash"
        record.expires_at += timedelta(seconds=1)
        record.response_status = 200
        record.completed_at = datetime.now(UTC).replace(tzinfo=None)
        record.response_json = {
            "connection_result": {
                "status": "SUCCESS",
                "provider_code": "QWEN",
                "model_name": "replacement-model",
                "latency_ms": 1,
                "error_code": None,
                "message": "replacement",
            }
        }
        return result


@pytest.fixture
def key_directory() -> Iterator[Path]:
    directory = Path.cwd() / ".runtime" / f"model-secret-test-{secrets.token_hex(8)}"
    directory.mkdir(parents=True)
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


def _protector(key_directory: Path) -> AesGcmSecretProtector:
    key_file = key_directory / "model-secret-ring.json"
    key_file.write_text(
        json.dumps(
            {
                "active_key_id": "model-test-key",
                "keys": [
                    {
                        "key_id": "model-test-key",
                        "key_material": base64.urlsafe_b64encode(b"k" * 32)
                        .rstrip(b"=")
                        .decode(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return AesGcmSecretProtector.load(key_file)


def _context() -> AuditContext:
    return AuditContext(correlation_id="model-test", source_context="test-client")


def test_model_contract_fixes_provider_whitelist_and_never_exposes_secret() -> None:
    with pytest.raises(ValidationError):
        CreateModelConfigRequest.model_validate(
            {
                "config_code": "CUSTOM",
                "provider_code": "CUSTOM",
                "model_name": "custom-model",
                "secret_value": "not-a-real-credential",
            }
        )
    with pytest.raises(ValidationError):
        CreateModelConfigRequest.model_validate(
            {
                "config_code": "OPENAI",
                "provider_code": "OPENAI",
                "model_name": "gpt-test",
                "secret_value": "not-a-real-credential",
                "base_url": "https://operator-controlled.invalid",
            }
        )

    resource = ModelConfigResource(
        model_config_id="M" * 26,
        config_code="OPENAI",
        provider_code="OPENAI",
        model_name="gpt-test",
        request_timeout_seconds=30,
        lifecycle_status="CONFIGURING",
        secret_configured=True,
        is_ai_exploration_default=False,
        ai_exploration_default_version=None,
        row_version=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    document = resource.model_dump(mode="json")
    assert document["secret_configured"] is True
    assert all("secret_value" not in key and "encrypted" not in key for key in document)


def test_idempotency_fingerprint_distinguishes_secret_rotation_without_plaintext() -> None:
    first = CreateModelConfigRequest(
        config_code="OPENAI",
        provider_code="OPENAI",
        model_name="gpt-test",
        secret_value="first-not-real",
    )
    second = CreateModelConfigRequest(
        config_code="OPENAI",
        provider_code="OPENAI",
        model_name="gpt-test",
        secret_value="second-not-real",
    )

    first_payload = _canonical_payload(first)
    second_payload = _canonical_payload(second)

    assert first_payload != second_payload
    assert b"first-not-real" not in first_payload
    assert b"second-not-real" not in second_payload


def test_lifecycle_reason_rejects_whitespace_only_values() -> None:
    with pytest.raises(ValidationError):
        ModelConfigLifecycleRequest(expected_version=0, reason="   ")


def test_create_list_and_get_model_configuration_behaviors(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    placeholder = _model(status="CONFIGURING", updated_by="operator")
    create_session = _Session(placeholder, allow_create=True)
    create_service = ModelConfigurationService(
        _Factory(create_session),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        protector,
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    created = create_service.create_model_config(
        "token",
        CreateModelConfigRequest(
            config_code="OPENAI-NEW",
            provider_code="OPENAI",
            model_name="gpt-test",
            secret_value="not-a-real-credential",
            reason="foundation setup",
        ),
        "create-key",
        _context(),
    )

    assert created.lifecycle_status == "CONFIGURING"
    assert created.row_version == 1
    created_model = next(
        value for value in create_session.added if isinstance(value, ModelConfiguration)
    )
    created_secret = next(
        value
        for value in create_session.added
        if isinstance(value, ModelConfigurationSecret)
    )
    assert b"not-a-real-credential" not in created_secret.encrypted_secret
    configuring_event = next(
        value for value in create_session.added if isinstance(value, OutboxEvent)
    )
    assert configuring_event.payload_json["payload"]["from_state"] == "CREATED"
    assert configuring_event.payload_json["payload"]["to_state"] == "CONFIGURING"

    read_session = _Session(created_model, secret=created_secret)
    read_service = ModelConfigurationService(
        _Factory(read_session),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        protector,
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )
    listed = read_service.list_model_configs("token", 1, 50, _context())
    fetched = read_service.get_model_config(
        "token", created_model.model_config_id, _context()
    )

    assert listed.page.total == 1
    assert [item.model_config_id for item in listed.items] == [created.model_config_id]
    assert fetched.model_config_id == created.model_config_id
    assert fetched.secret_configured is True


def test_permission_denial_has_zero_model_side_effects(key_directory: Path) -> None:
    session = _Session(_model(status="CONFIGURING"))
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="unauthorized", allowed=False),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.list_model_configs("token", 1, 50, _context())

    assert caught.value.status == 403
    assert session.added == []
    assert session.deleted == []


def test_litellm_dynamic_credentials_are_fail_closed_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("a provider credential must not be sent while disabled")

    monkeypatch.setattr(urllib.request, "urlopen", fail_if_called)
    result = LiteLLMModelGateway("http://127.0.0.1:4000").test_connection(
        provider_code="QWEN",
        model_name="qwen-test",
        provider_secret="not-a-real-credential",
        timeout_seconds=1,
    )

    assert result.status == "INVALID_CONFIGURATION"


def test_litellm_uses_official_dashscope_prefix_only_after_explicit_enablement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status = 200

        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def read(self, size: int) -> bytes:
            del size
            raise AssertionError("connection tests must not wait for a response body")

    def capture(request: urllib.request.Request, timeout: int) -> _Response:
        captured["payload"] = json.loads(bytes(request.data or b"{}").decode())
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", capture)
    result = LiteLLMModelGateway(
        "http://127.0.0.1:4000", dynamic_credentials_enabled=True
    ).test_connection(
        provider_code="QWEN",
        model_name="qwen-test",
        provider_secret="not-a-real-credential",
        timeout_seconds=3,
    )

    assert result.status == "SUCCESS"
    assert captured["payload"] == {
        "model": "dashscope/qwen-test",
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "max_tokens": 2,
        "temperature": 0,
        "api_key": "not-a-real-credential",
    }
    assert captured["timeout"] == 3


def test_model_secret_is_authenticated_encrypted_and_bound_to_model_identity(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    encrypted = protector.encrypt("M" * 26, "not-a-real-credential")

    assert b"not-a-real-credential" not in encrypted.ciphertext
    assert protector.decrypt("M" * 26, encrypted.ciphertext, encrypted.key_id) == (
        "not-a-real-credential"
    )
    with pytest.raises(SecretStoreError):
        protector.decrypt("N" * 26, encrypted.ciphertext, encrypted.key_id)


def test_maximum_utf8_secret_fits_the_governed_ciphertext_column(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    encrypted = protector.encrypt("M" * 26, "\U0001f512" * 4096)

    assert len(encrypted.ciphertext) == 16412


def test_model_secret_key_ring_rejects_duplicate_or_oversized_key_ids(
    key_directory: Path,
) -> None:
    key_file = key_directory / "invalid-model-secret-ring.json"
    encoded = base64.urlsafe_b64encode(b"k" * 32).rstrip(b"=").decode()
    key_file.write_text(
        json.dumps(
            {
                "active_key_id": "duplicate",
                "keys": [
                    {"key_id": "duplicate", "key_material": encoded},
                    {"key_id": "duplicate", "key_material": encoded},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SecretStoreError):
        AesGcmSecretProtector.load(key_file)

    key_file.write_text(
        json.dumps(
            {
                "active_key_id": "k" * 65,
                "keys": [{"key_id": "k" * 65, "key_material": encoded}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SecretStoreError):
        AesGcmSecretProtector.load(key_file)


def test_non_super_admin_cannot_review_own_model_configuration(
    key_directory: Path,
) -> None:
    model = _model(updated_by="same-operator")
    session = _Session(model)
    authentication = _Authentication(user_id="same-operator")
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        authentication,  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.transition_model_config(
            "token",
            model.model_config_id,
            ModelConfigLifecycleRequest(expected_version=4, reason="independent review"),
            "activation-key",
            _context(),
            action="activate",
        )

    assert caught.value.code == "MODEL_CONFIG_SELF_REVIEW_FORBIDDEN"
    assert authentication.permissions == [
        ("activate_model_config", ("MODEL_VERSION_REVIEW",))
    ]
    assert model.lifecycle_status == "VALIDATING"
    assert not any(isinstance(value, OutboxEvent) for value in session.added)


def test_super_admin_can_review_own_model_configuration_with_explicit_audit(
    key_directory: Path,
) -> None:
    model = _model(updated_by="super-admin")
    session = _Session(model, submitted_by="super-admin")
    authentication = _Authentication(user_id="super-admin", super_admin=True)
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        authentication,  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    result = service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=4, reason="emergency self review"),
        "super-admin-activation-key",
        _context(),
        action="activate",
    )

    assert result.lifecycle_status == "ACTIVE"
    assert authentication.role_checks == [("super-admin", "ROLE-SUPER-ADMIN")]
    audit = next(
        value for value in session.added if isinstance(value, ModelConfigurationAudit)
    )
    assert audit.actor_user_id == "super-admin"
    assert audit.details_json == {
        "actor_user_id": "super-admin",
        "submitter_user_id": "super-admin",
        "reviewer_user_id": "super-admin",
        "self_approval": True,
        "operator_role": "SUPER_ADMIN",
    }


def test_intervening_update_cannot_erase_submitter_identity(
    key_directory: Path,
) -> None:
    model = _model(updated_by="different-manager")
    session = _Session(model, submitted_by="same-operator")
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="same-operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.transition_model_config(
            "token",
            model.model_config_id,
            ModelConfigLifecycleRequest(expected_version=4, reason="independent review"),
            "activation-key",
            _context(),
            action="activate",
        )

    assert caught.value.code == "MODEL_CONFIG_SELF_REVIEW_FORBIDDEN"
    assert model.lifecycle_status == "VALIDATING"


def test_activation_fails_closed_without_review_submission_evidence(
    key_directory: Path,
) -> None:
    model = _model(updated_by="manager")
    session = _Session(model, submitted_by=None)
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="reviewer"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.transition_model_config(
            "token",
            model.model_config_id,
            ModelConfigLifecycleRequest(expected_version=4, reason="reviewed"),
            "activation-without-submission-key",
            _context(),
            action="activate",
        )

    assert caught.value.code == "MODEL_CONFIG_REVIEW_SUBMISSION_EVIDENCE_MISSING"
    assert model.lifecycle_status == "VALIDATING"
    assert not any(isinstance(value, OutboxEvent) for value in session.added)


def test_independent_reviewer_activates_single_config_and_emits_safe_evidence(
    key_directory: Path,
) -> None:
    model = _model(updated_by="submitter")
    encrypted = _protector(key_directory).encrypt(model.model_config_id, "credential")
    session = _Session(
        model,
        secret=ModelConfigurationSecret(
            model_config_id=model.model_config_id,
            encrypted_secret=encrypted.ciphertext,
            key_id=encrypted.key_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        ),
    )
    idempotency = _Idempotency()
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="independent-reviewer"),  # type: ignore[arg-type]
        idempotency,  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    result = service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=4, reason="reviewed"),
        "activation-key",
        _context(),
        action="activate",
    )

    assert result.lifecycle_status == "ACTIVE"
    assert result.row_version == 5
    assert result.secret_configured is True
    audit = next(
        value for value in session.added if isinstance(value, ModelConfigurationAudit)
    )
    assert audit.details_json == {
        "actor_user_id": "independent-reviewer",
        "submitter_user_id": "submitter",
        "reviewer_user_id": "independent-reviewer",
        "self_approval": False,
    }
    event = next(value for value in session.added if isinstance(value, OutboxEvent))
    assert event.event_type == "model_config.active"
    assert set(event.payload_json) == {
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "aggregate_id",
        "sequence",
        "correlation_id",
        "causation_id",
        "project_id",
        "payload",
    }
    assert event.payload_json["payload"] == {
        "model_config_id": model.model_config_id,
        "project_id": None,
        "from_state": "VALIDATING",
        "to_state": "ACTIVE",
        "expected_version": 4,
        "new_version": 5,
        "changed_by": "independent-reviewer",
        "change_summary": {
            "operation_id": "activate_model_config",
            "reason": "reviewed",
        },
    }
    assert "secret" not in json.dumps(event.payload_json).lower()
    assert "secret_value" not in json.dumps(idempotency.completed).lower()


def test_submitter_submission_evidence_is_consumed_by_independent_reviewer(
    key_directory: Path,
) -> None:
    model = _model(status="CONFIGURING", updated_by="manager")
    session = _Session(model, submitted_by=None)
    submit_service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="ordinary-submitter"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    submitted = submit_service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=4, reason="ready for review"),
        "submission-key",
        _context(),
        action="submit_review",
    )

    assert submitted.lifecycle_status == "VALIDATING"
    submission_audit = next(
        value
        for value in session.added
        if isinstance(value, ModelConfigurationAudit)
        and value.action == "MODEL_CONFIG_REVIEW_SUBMITTED"
    )
    assert submission_audit.actor_user_id == "ordinary-submitter"

    review_service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="independent-reviewer"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )
    activated = review_service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=5, reason="approved"),
        "independent-activation-key",
        _context(),
        action="activate",
    )

    assert activated.lifecycle_status == "ACTIVE"
    activation_audit = next(
        value
        for value in session.added
        if isinstance(value, ModelConfigurationAudit)
        and value.action == "MODEL_CONFIG_ACTIVATED"
    )
    assert activation_audit.details_json == {
        "actor_user_id": "independent-reviewer",
        "submitter_user_id": "ordinary-submitter",
        "reviewer_user_id": "independent-reviewer",
        "self_approval": False,
    }


def test_reviewer_can_return_invalid_configuration_for_repair(
    key_directory: Path,
) -> None:
    model = _model(status="VALIDATING", updated_by="submitter")
    session = _Session(model)
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="independent-reviewer"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    returned = service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=4, reason="credential rejected"),
        "return-key",
        _context(),
        action="return_to_configuring",
    )

    assert returned.lifecycle_status == "CONFIGURING"
    assert returned.row_version == 5
    assert any(
        isinstance(value, ModelConfigurationAudit)
        and value.action == "MODEL_CONFIG_RETURNED_TO_CONFIGURING"
        for value in session.added
    )
    event = next(value for value in session.added if isinstance(value, OutboxEvent))
    assert event.event_type == "model_config.configuring"


def test_disabled_configuration_recovery_and_reactivation_are_explicit(
    key_directory: Path,
) -> None:
    model = _model(status="DISABLED", updated_by="manager")
    session = _Session(model)
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="manager"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    recovering = service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=4, reason="operator recovery"),
        "recover-key",
        _context(),
        action="recover",
    )
    assert recovering.lifecycle_status == "RECOVERING"
    assert recovering.row_version == 5

    reviewer_service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="independent-reviewer"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )
    active = reviewer_service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=5, reason="recovery reviewed"),
        "recovery-activation-key",
        _context(),
        action="activate",
    )
    assert active.lifecycle_status == "ACTIVE"
    assert active.row_version == 6


def test_disabled_configuration_can_be_archived(key_directory: Path) -> None:
    model = _model(status="DISABLED", updated_by="manager")
    session = _Session(model)
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="manager"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    archived = service.transition_model_config(
        "token",
        model.model_config_id,
        ModelConfigLifecycleRequest(expected_version=4, reason="retired configuration"),
        "archive-key",
        _context(),
        action="archive",
    )

    assert archived.lifecycle_status == "ARCHIVED"
    assert any(
        isinstance(value, OutboxEvent) and value.event_type == "model_config.archived"
        for value in session.added
    )


def test_effective_default_cannot_be_disabled(key_directory: Path) -> None:
    model = _model(status="ACTIVE", updated_by="operator")
    binding = ModelCapabilityDefault(
        capability_code="AI_EXPLORATION",
        model_config_id=model.model_config_id,
        row_version=0,
        created_at=model.created_at,
        updated_at=model.updated_at,
        created_by="operator",
        updated_by="operator",
    )
    service = ModelConfigurationService(
        _Factory(_Session(model, default=binding)),  # type: ignore[arg-type]
        _Authentication(),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.transition_model_config(
            "token",
            model.model_config_id,
            ModelConfigLifecycleRequest(expected_version=4, reason="disable"),
            "disable-key",
            _context(),
            action="disable",
        )

    assert caught.value.code == "MODEL_CONFIG_DEFAULT_DISABLE_CONFLICT"
    assert model.lifecycle_status == "ACTIVE"


def test_connection_test_returns_structured_result_and_only_appends_audit(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    model = _model(status="CONFIGURING", updated_by="operator")
    encrypted = protector.encrypt(model.model_config_id, "not-a-real-credential")
    secret = ModelConfigurationSecret(
        model_config_id=model.model_config_id,
        encrypted_secret=encrypted.ciphertext,
        key_id=encrypted.key_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
    session = _Session(model, secret=secret)
    idempotency = _Idempotency()
    gateway = _Gateway(
        GatewayConnectionResult("AUTHENTICATION_FAILED", 23, "request-id", "rejected"),
        session,
    )
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(),  # type: ignore[arg-type]
        idempotency,  # type: ignore[arg-type]
        protector,
        gateway,
    )

    result = service.test_connection(
        "token",
        model.model_config_id,
        ConnectionTestRequest(reason="diagnostic"),
        "connection-test-key",
        _context(),
    )

    assert result.status == "AUTHENTICATION_FAILED"
    assert result.latency_ms == 23
    assert model.lifecycle_status == "CONFIGURING"
    assert model.row_version == 4
    assert gateway.received_secret == "not-a-real-credential"
    assert idempotency.record.expires_at is not None
    assert len(session.added) == 1
    audit = session.added[0]
    assert isinstance(audit, ModelConfigurationAudit)
    assert audit.result_code == "AUTHENTICATION_FAILED"
    assert "credential" not in json.dumps(audit.details_json).lower()
    assert session.lock_order[-2:] == ["idempotency", "model"]


def test_reclaimed_connection_attempt_cannot_complete_stale_result(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    model = _model(status="CONFIGURING", updated_by="operator")
    encrypted = protector.encrypt(model.model_config_id, "not-a-real-credential")
    session = _Session(
        model,
        secret=ModelConfigurationSecret(
            model_config_id=model.model_config_id,
            encrypted_secret=encrypted.ciphertext,
            key_id=encrypted.key_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        ),
    )
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        protector,
        _ReclaimingGateway(
            GatewayConnectionResult("SUCCESS", 1, None, "ok"), session
        ),
    )

    with pytest.raises(PlatformError) as caught:
        service.test_connection(
            "token",
            model.model_config_id,
            ConnectionTestRequest(reason="diagnostic"),
            "connection-test-key",
            _context(),
        )

    assert caught.value.code == "MODEL_CONFIG_CONNECTION_TEST_ATTEMPT_STALE"
    assert not any(
        isinstance(value, ModelConfigurationAudit) for value in session.added
    )


def test_completed_replacement_attempt_is_never_replayed_to_stale_caller(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    model = _model(status="CONFIGURING", updated_by="operator")
    encrypted = protector.encrypt(model.model_config_id, "not-a-real-credential")
    session = _Session(
        model,
        secret=ModelConfigurationSecret(
            model_config_id=model.model_config_id,
            encrypted_secret=encrypted.ciphertext,
            key_id=encrypted.key_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        ),
    )
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        protector,
        _CompletedReplacementGateway(
            GatewayConnectionResult("SUCCESS", 1, None, "old attempt"), session
        ),
    )

    with pytest.raises(PlatformError) as caught:
        service.test_connection(
            "token",
            model.model_config_id,
            ConnectionTestRequest(reason="diagnostic"),
            "connection-test-key",
            _context(),
        )

    assert caught.value.code == "MODEL_CONFIG_CONNECTION_TEST_ATTEMPT_STALE"
    assert not any(
        isinstance(value, ModelConfigurationAudit) for value in session.added
    )


def test_sensitive_update_is_rejected_outside_configuring(
    key_directory: Path,
) -> None:
    model = _model(status="DISABLED", updated_by="operator")
    service = ModelConfigurationService(
        _Factory(_Session(model)),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.update_model_config(
            "token",
            model.model_config_id,
            UpdateModelConfigRequest(
                expected_version=4,
                model_name="different-model",
                reason="not a recovery transition",
            ),
            "update-key",
            _context(),
        )

    assert caught.value.code == "MODEL_CONFIG_OPERATION_FORBIDDEN_FOR_STATE"
    assert model.lifecycle_status == "DISABLED"


def test_explicit_null_sensitive_fields_are_not_a_model_update(
    key_directory: Path,
) -> None:
    model = _model(status="CONFIGURING", updated_by="operator")
    service = ModelConfigurationService(
        _Factory(_Session(model)),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.update_model_config(
            "token",
            model.model_config_id,
            UpdateModelConfigRequest(
                expected_version=4,
                provider_code=None,
                model_name=None,
                secret_value=None,
                request_timeout_seconds=None,
                reason="no effective change",
            ),
            "null-update-key",
            _context(),
        )

    assert caught.value.code == "MODEL_CONFIG_UPDATE_EMPTY"
    assert model.row_version == 4


def test_archived_model_configuration_is_terminal(key_directory: Path) -> None:
    model = _model(status="ARCHIVED", updated_by="operator")
    service = ModelConfigurationService(
        _Factory(_Session(model)),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.update_model_config(
            "token",
            model.model_config_id,
            UpdateModelConfigRequest(
                expected_version=4,
                display_name="must not change",
                reason="terminal protection",
            ),
            "archived-update-key",
            _context(),
        )

    assert caught.value.code == "MODEL_CONFIG_OPERATION_FORBIDDEN_FOR_STATE"


def test_secret_rotation_emits_dedicated_non_secret_audit(
    key_directory: Path,
) -> None:
    protector = _protector(key_directory)
    model = _model(status="CONFIGURING", updated_by="operator")
    encrypted = protector.encrypt(model.model_config_id, "old-not-real")
    session = _Session(
        model,
        secret=ModelConfigurationSecret(
            model_config_id=model.model_config_id,
            encrypted_secret=encrypted.ciphertext,
            key_id=encrypted.key_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        ),
    )
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(user_id="operator"),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        protector,
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    service.update_model_config(
        "token",
        model.model_config_id,
        UpdateModelConfigRequest(
            expected_version=4,
            secret_value="new-not-real",
            reason="credential rotation",
        ),
        "rotation-key",
        _context(),
    )

    audits = [value for value in session.added if isinstance(value, ModelConfigurationAudit)]
    assert [audit.action for audit in audits] == [
        "MODEL_CONFIG_UPDATED",
        "MODEL_CONFIG_SECRET_UPDATED",
    ]
    assert "new-not-real" not in json.dumps([audit.details_json for audit in audits])


def test_runtime_projection_exposes_only_opaque_secret_reference() -> None:
    projection = ResolvedModelConfiguration(
        model_config_id="M" * 26,
        provider_code="OPENAI",
        model_name="gpt-test",
        request_timeout_seconds=30,
        secret_reference="model-config-secret:" + "M" * 26,
    )

    assert projection.secret_reference.startswith("model-config-secret:")
    assert "provider_secret" not in {item.name for item in fields(projection)}


def test_capability_default_is_unique_active_binding_with_optimistic_clear(
    key_directory: Path,
) -> None:
    model = _model(status="ACTIVE")
    session = _Session(model)
    idempotency = _Idempotency()
    service = ModelConfigurationService(
        _Factory(session),  # type: ignore[arg-type]
        _Authentication(),  # type: ignore[arg-type]
        idempotency,  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    binding = service.set_capability_default(
        "token",
        "AI_EXPLORATION",
        SetCapabilityDefaultModelRequest(model_config_id=model.model_config_id),
        "set-default-key",
        _context(),
    )

    assert binding.capability_code == "AI_EXPLORATION"
    assert binding.model_config_id == model.model_config_id
    assert binding.row_version == 0
    persisted = next(
        value for value in session.added if isinstance(value, ModelCapabilityDefault)
    )
    session.default = persisted

    cleared = service.clear_capability_default(
        "token",
        "AI_EXPLORATION",
        ClearCapabilityDefaultModelRequest(expected_version=0, reason="switching default"),
        "clear-default-key",
        _context(),
    )

    assert cleared.cleared is True
    assert cleared.capability_code == "AI_EXPLORATION"
    assert session.deleted == [persisted]
    audit_actions = {
        value.action
        for value in session.added
        if isinstance(value, ModelConfigurationAudit)
    }
    assert audit_actions == {"CAPABILITY_DEFAULT_SET", "CAPABILITY_DEFAULT_CLEARED"}


def test_binding_rejects_non_active_model(key_directory: Path) -> None:
    model = _model(status="VALIDATING")
    service = ModelConfigurationService(
        _Factory(_Session(model)),  # type: ignore[arg-type]
        _Authentication(),  # type: ignore[arg-type]
        _Idempotency(),  # type: ignore[arg-type]
        _protector(key_directory),
        _Gateway(GatewayConnectionResult("SUCCESS", 1, None, "ok")),
    )

    with pytest.raises(PlatformError) as caught:
        service.set_capability_default(
            "token",
            "AI_EXPLORATION",
            SetCapabilityDefaultModelRequest(model_config_id=model.model_config_id),
            "set-default-key",
            _context(),
        )

    assert caught.value.code == "MODEL_CAPABILITY_DEFAULT_MODEL_NOT_ACTIVE"


def test_exact_model_configuration_operations_are_registered() -> None:
    flattened = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in route.methods
    }
    assert flattened == {
        ("GET", "/api/v1/model-config", "list_model_config"),
        ("POST", "/api/v1/model-config", "create_model_config"),
        ("GET", "/api/v1/model-config/{id}", "get_model_config"),
        ("PATCH", "/api/v1/model-config/{id}", "update_model_config"),
        ("GET", "/api/v1/model-config-review", "list_model_config_reviews"),
        ("GET", "/api/v1/model-config-review/{id}", "get_model_config_review"),
        (
            "POST",
            "/api/v1/model-config/{id}/submit-review",
            "submit_model_config_review",
        ),
        (
            "POST",
            "/api/v1/model-config/{id}/return-to-configuring",
            "return_model_config_to_configuring",
        ),
        ("POST", "/api/v1/model-config/{id}/activate", "activate_model_config"),
        ("POST", "/api/v1/model-config/{id}/disable", "disable_model_config"),
        ("POST", "/api/v1/model-config/{id}/recover", "recover_model_config"),
        ("POST", "/api/v1/model-config/{id}/archive", "archive_model_config"),
        (
            "POST",
            "/api/v1/model-config/{id}/connection-test",
            "test_model_config_connection",
        ),
        (
            "PUT",
            "/api/v1/model-capability-default/{capability_code}",
            "set_capability_default_model",
        ),
        (
            "POST",
            "/api/v1/model-capability-default/{capability_code}/clear",
            "clear_capability_default_model",
        ),
    }
