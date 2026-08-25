from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar

import pytest
from platform_api.ai_exploration_router import router
from platform_api.ai_exploration_schemas import CreateAIExplorationRequest, ExplorationPlan
from platform_api.ai_exploration_service import AIExplorationService
from platform_api.audit import AuditContext
from platform_api.errors import PlatformError
from platform_api.model_configuration_service import ResolvedModelConfiguration
from platform_api.model_gateway import GatewayInvocationResult, LiteLLMModelGateway
from platform_api.models import (
    AICall,
    AIExplorationAudit,
    AIExplorationSession,
    AITask,
    IdempotencyRecord,
    Project,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _project(status: str = "ACTIVE") -> Project:
    now = _now()
    return Project(
        project_id="P" * 26,
        project_code="EXPLORATION-PROJECT",
        lifecycle_status=status,
        display_name="Exploration project",
        row_version=0,
        created_at=now,
        updated_at=now,
        created_by="U" * 26,
        updated_by="U" * 26,
        extension_json=None,
    )


class _Transaction:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def __enter__(self) -> _Session:
        return self._session

    def __exit__(self, *args: object) -> None:
        del args


class _Factory:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __call__(self) -> _Transaction:
        return _Transaction(self.session)

    def begin(self) -> _Transaction:
        return _Transaction(self.session)


class _Session:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.exploration: AIExplorationSession | None = None
        self.ai_task: AITask | None = None
        self.ai_call: AICall | None = None
        self.idempotency: IdempotencyRecord | None = None
        self.audits: list[AIExplorationAudit] = []

    def get(self, entity: type[object], key: str) -> object | None:
        if entity is Project:
            return self.project if key == self.project.project_id else None
        if entity is IdempotencyRecord:
            return (
                self.idempotency
                if self.idempotency and key == self.idempotency.idempotency_key
                else None
            )
        if entity is AITask:
            return self.ai_task if self.ai_task and key == self.ai_task.ai_task_id else None
        if entity is AICall:
            return self.ai_call if self.ai_call and key == self.ai_call.ai_call_id else None
        return None

    def scalar(self, statement: object) -> object | None:
        descriptions = getattr(statement, "column_descriptions", [])
        entity = descriptions[0].get("entity") if descriptions else None
        if entity is AIExplorationSession:
            return self.exploration
        if entity is IdempotencyRecord:
            return self.idempotency
        if entity is AITask:
            return self.ai_task
        if entity is AICall:
            return self.ai_call
        return None

    def add(self, value: object) -> None:
        if isinstance(value, AIExplorationSession):
            self.exploration = value
        elif isinstance(value, AITask):
            self.ai_task = value
        elif isinstance(value, AICall):
            self.ai_call = value
        elif isinstance(value, AIExplorationAudit):
            self.audits.append(value)

    @staticmethod
    def flush() -> None:
        return None


class _Authentication:
    def __init__(self) -> None:
        self.identity = SimpleNamespace(user=SimpleNamespace(user_id="U" * 26))
        self.permission_checks: list[tuple[str, tuple[str, ...], str]] = []

    def authenticate_access_in_transaction(self, *args: object) -> object:
        del args
        return self.identity

    def require_project_permissions_in_transaction(
        self,
        db: object,
        identity: object,
        operation_id: str,
        permission_codes: tuple[str, ...],
        project_id: str,
        context: object,
    ) -> str:
        del db, identity, context
        self.permission_checks.append((operation_id, permission_codes, project_id))
        return "ALLOWED"


class _Idempotency:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def claim(
        self,
        *args: object,
        recover_incomplete: object | None = None,
    ) -> tuple[IdempotencyRecord, bool]:
        if self.session.idempotency is not None:
            if self.session.idempotency.completed_at is not None:
                return self.session.idempotency, True
            if callable(recover_incomplete) and recover_incomplete(
                self.session, self.session.idempotency
            ):
                return self.session.idempotency, True
            raise PlatformError(
                title="Concurrent idempotent request is incomplete",
                detail="The idempotent command has not reached a terminal state.",
                status=409,
                code="AUTH_CONCURRENCY_CONFLICT",
            )
        now = _now()
        self.session.idempotency = IdempotencyRecord(
            idempotency_key="stored-key",
            contract_version=2,
            principal_id="U" * 26,
            operation_id="create_ai_exploration_session",
            request_hash="hash",
            response_status=None,
            response_json=None,
            completed_at=None,
            expires_at=now + timedelta(days=1),
        )
        return self.session.idempotency, False

    @staticmethod
    def complete(
        record: IdempotencyRecord,
        status: int,
        response_json: dict[str, object] | None,
    ) -> None:
        record.response_status = status
        record.response_json = response_json
        record.completed_at = _now()


class _Models:
    def __init__(
        self,
        result: GatewayInvocationResult | None = None,
        resolution_error: PlatformError | None = None,
    ) -> None:
        self.result = result
        self.resolution_error = resolution_error
        self.resolved = ResolvedModelConfiguration(
            model_config_id="M" * 26,
            provider_code="OPENAI",
            model_name="gpt-test",
            request_timeout_seconds=15,
            secret_reference="model-config-secret:" + "M" * 26,
            display_name="Exploration primary",
        )
        self.messages: list[dict[str, str]] | None = None
        self.invoke_count = 0

    def resolve_default(self, capability_code: str) -> ResolvedModelConfiguration:
        assert capability_code == "AI_EXPLORATION"
        if self.resolution_error is not None:
            raise self.resolution_error
        return self.resolved

    def resolve_default_in_transaction(
        self,
        _db: object,
        capability_code: str,
    ) -> ResolvedModelConfiguration:
        return self.resolve_default(capability_code)

    def invoke(
        self,
        resolved: ResolvedModelConfiguration,
        messages: list[dict[str, str]],
    ) -> GatewayInvocationResult:
        assert resolved is self.resolved
        self.invoke_count += 1
        self.messages = messages
        assert self.result is not None
        return self.result


def _request() -> CreateAIExplorationRequest:
    return CreateAIExplorationRequest(
        project_id="P" * 26,
        objective="Verify that a user can sign in and reach the dashboard",
        target_url="https://example.test/login",
    )


def _service(
    models: _Models, *, project_status: str = "ACTIVE"
) -> tuple[AIExplorationService, _Session, _Authentication]:
    session = _Session(_project(project_status))
    authentication = _Authentication()
    service = AIExplorationService(
        _Factory(session),  # type: ignore[arg-type]
        authentication,  # type: ignore[arg-type]
        _Idempotency(session),  # type: ignore[arg-type]
        models,  # type: ignore[arg-type]
    )
    return service, session, authentication


def test_ai_exploration_route_is_registered_with_exact_contract() -> None:
    operations = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in route.methods
    }
    assert operations == {
        ("POST", "/api/v1/ai-exploration-sessions", "create_ai_exploration_session")
    }


def test_foundation_creates_ready_session_with_model_snapshot_and_structured_plan() -> None:
    result = GatewayInvocationResult(
        status="SUCCESS",
        content=(
            '{"goal":"Reach the dashboard","assumptions":["A valid user exists"],'
            '"steps":[{"sequence":1,"intent":"Open the login page",'
            '"expected_observation":"The login form is visible"}]}'
        ),
        provider_request_id="provider-request",
        message="completed",
    )
    models = _Models(result)
    service, session, authentication = _service(models)

    resource = service.create(
        "access-token",
        _request(),
        "request-key",
        AuditContext(correlation_id="correlation", source_context="source"),
    )

    assert resource.lifecycle_status == "READY"
    assert resource.plan is not None
    assert resource.plan.steps[0].sequence == 1
    assert resource.resolved_model_display_name == "Exploration primary"
    assert resource.resolved_provider_code == "OPENAI"
    assert resource.resolved_model_name == "gpt-test"
    assert [audit.action for audit in session.audits] == [
        "SESSION_CREATED",
        "PLANNING_STARTED",
        "PLANNING_SUCCEEDED",
    ]
    assert session.audits[-1].provider_request_id == "provider-request"
    assert session.idempotency is not None
    assert session.idempotency.response_status == 201
    assert authentication.permission_checks[-1][1] == ("AI_TASK_CREATE",)
    assert models.messages is not None
    assert "selectors" in models.messages[0]["content"]
    assert "model-config-secret" not in repr(resource.model_dump())


def test_invalid_model_plan_is_persisted_as_failed_without_raw_output() -> None:
    models = _Models(
        GatewayInvocationResult(
            status="SUCCESS",
            content='{"goal":"invalid","assumptions":[],"steps":[]}',
            provider_request_id="provider-request",
            message="completed",
        )
    )
    service, session, _ = _service(models)

    resource = service.create(
        "access-token",
        _request(),
        "request-key",
        AuditContext(correlation_id="correlation", source_context="source"),
    )

    assert resource.lifecycle_status == "FAILED"
    assert resource.plan is None
    assert resource.failure_code == "AI_EXPLORATION_MODEL_RESPONSE_INVALID"
    assert "invalid" not in (resource.failure_message or "").lower()
    assert session.exploration is not None
    assert session.exploration.plan is None


def test_completed_idempotency_replay_does_not_reresolve_changed_default() -> None:
    models = _Models(
        GatewayInvocationResult(
            status="SUCCESS",
            content=(
                '{"goal":"goal","assumptions":[],"steps":'
                '[{"sequence":1,"intent":"intent",'
                '"expected_observation":"observation"}]}'
            ),
            provider_request_id=None,
            message="completed",
        )
    )
    service, _, _ = _service(models)
    context = AuditContext(correlation_id="correlation", source_context="source")

    created = service.create("access-token", _request(), "request-key", context)
    models.resolution_error = PlatformError(
        title="Capability default unavailable",
        detail="No ACTIVE default model is bound for the requested capability.",
        status=503,
        code="MODEL_CAPABILITY_DEFAULT_UNAVAILABLE",
    )
    replayed = service.create("access-token", _request(), "request-key", context)

    assert replayed == created


def test_missing_active_default_fails_before_session_creation() -> None:
    models = _Models(
        resolution_error=PlatformError(
            title="Capability default unavailable",
            detail="No ACTIVE default model is bound for the requested capability.",
            status=503,
            code="MODEL_CAPABILITY_DEFAULT_UNAVAILABLE",
        )
    )
    service, session, _ = _service(models)

    with pytest.raises(PlatformError) as caught:
        service.create(
            "access-token",
            _request(),
            "request-key",
            AuditContext(correlation_id="correlation", source_context="source"),
        )

    assert caught.value.code == "AI_EXPLORATION_MODEL_NOT_CONFIGURED"
    assert session.exploration is None


def test_non_active_project_is_rejected_before_model_resolution() -> None:
    models = _Models()
    service, session, _ = _service(models, project_status="DISABLED")

    with pytest.raises(PlatformError) as caught:
        service.create(
            "access-token",
            _request(),
            "request-key",
            AuditContext(correlation_id="correlation", source_context="source"),
        )

    assert caught.value.code == "AI_EXPLORATION_PROJECT_UNAVAILABLE"
    assert session.exploration is None


def test_target_url_is_bounded_by_the_persisted_contract() -> None:
    with pytest.raises(ValueError):
        CreateAIExplorationRequest(
            project_id="P" * 26,
            objective="bounded target",
            target_url="https://example.test/" + ("a" * 2048),
        )


def test_same_key_recovers_interrupted_planning_without_reinvoking_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = _Models(
        GatewayInvocationResult(
            status="SUCCESS",
            content=(
                '{"goal":"goal","assumptions":[],"steps":'
                '[{"sequence":1,"intent":"intent",'
                '"expected_observation":"observation"}]}'
            ),
            provider_request_id="provider-request",
            message="completed",
        )
    )
    service, session, _ = _service(models)
    context = AuditContext(correlation_id="correlation", source_context="source")

    def _crash_before_ready(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise KeyboardInterrupt("simulated process loss after provider success")

    monkeypatch.setattr(service, "_ready", _crash_before_ready)
    with pytest.raises(KeyboardInterrupt):
        service.create("access-token", _request(), "request-key", context)

    assert session.exploration is not None
    assert session.exploration.lifecycle_status == "PLANNING"
    assert models.invoke_count == 1
    session.exploration.planning_deadline_at = _now() - timedelta(seconds=1)

    recovered = service.create("access-token", _request(), "request-key", context)

    assert recovered.lifecycle_status == "FAILED"
    assert recovered.failure_code == "AI_EXPLORATION_PLANNING_INTERRUPTED"
    assert models.invoke_count == 1
    assert session.ai_task is not None and session.ai_task.status == "FAILED"
    assert session.ai_call is not None and session.ai_call.lifecycle_status == "FAILED"
    assert session.idempotency is not None and session.idempotency.completed_at is not None
    assert session.audits[-1].action == "PLANNING_INTERRUPTED"

    audit_count = len(session.audits)
    late_result = AIExplorationService._ready(
        service,
        session.exploration.session_id,
        session.idempotency.idempotency_key,
        context,
        ExplorationPlan.model_validate(
            {
                "goal": "late provider result",
                "assumptions": [],
                "steps": [
                    {
                        "sequence": 1,
                        "intent": "must not win",
                        "expected_observation": "recovered terminal state remains authoritative",
                    }
                ],
            }
        ),
        "late-provider-request",
    )

    assert late_result.lifecycle_status == "FAILED"
    assert session.exploration.lifecycle_status == "FAILED"
    assert len(session.audits) == audit_count


def test_litellm_gateway_invokes_real_completion_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"x-litellm-request-id": "litellm-request"}

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        @staticmethod
        def read(_size: int = -1) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"goal":"goal","assumptions":[],"steps":'
                                    '[{"sequence":1,"intent":"intent",'
                                    '"expected_observation":"observation"}]}'
                                )
                            }
                        }
                    ]
                }
            ).encode()

    def _urlopen(request: urllib.request.Request, timeout: int) -> _Response:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads((request.data or b"").decode())
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    gateway = LiteLLMModelGateway(
        "http://127.0.0.1:4000",
        dynamic_credentials_enabled=True,
    )
    result = gateway.invoke(
        provider_code="OPENAI",
        model_name="gpt-test",
        provider_secret="provider-secret",
        timeout_seconds=17,
        messages=[{"role": "user", "content": "plan"}],
    )

    assert result.status == "SUCCESS"
    assert result.provider_request_id == "litellm-request"
    assert captured["url"] == "http://127.0.0.1:4000/v1/chat/completions"
    assert captured["timeout"] == 17
    assert captured["payload"] == {
        "model": "openai/gpt-test",
        "messages": [{"role": "user", "content": "plan"}],
        "temperature": 0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
        "api_key": "provider-secret",
    }


def test_litellm_gateway_rejects_oversized_response_and_bounds_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {
            "x-request-id": ("safe" * 60) + "\nsecret",
        }

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        @staticmethod
        def read(size: int = -1) -> bytes:
            assert size == LiteLLMModelGateway._MAX_RESPONSE_BYTES + 1
            return b"x" * size

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: _Response())
    result = LiteLLMModelGateway(
        "http://127.0.0.1:4000",
        dynamic_credentials_enabled=True,
    ).invoke(
        provider_code="OPENAI",
        model_name="gpt-test",
        provider_secret="provider-secret",
        timeout_seconds=17,
        messages=[{"role": "user", "content": "plan"}],
    )

    assert result.status == "INVALID_RESPONSE"
    assert result.content is None
    assert result.provider_request_id is not None
    assert len(result.provider_request_id) == 191
    assert "\n" not in result.provider_request_id
