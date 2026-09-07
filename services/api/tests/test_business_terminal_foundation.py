from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_api.automation_asset_service import (
    AutomationAssetService,
    _assert_login_strategy_activatable,
    _strategy_projection,
)
from platform_api.business_terminal_router import router
from platform_api.business_terminal_schemas import (
    CreateLoginStrategyRequest,
    CreateTerminalAccessRevisionRequest,
    LocalStoragePreset,
    UpdateLoginStrategyRequest,
    UpdateTerminalAccessRevisionRequest,
    normalize_web_url,
)
from platform_api.business_terminal_service import (
    _TERMINAL_TRANSITIONS,
    BusinessTerminalService,
    _assert_revision_draft_mutable,
    _check_version,
    _integrity_error,
    _parse_filter,
)
from platform_api.errors import PlatformError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


def test_business_terminal_routes_use_explicit_lifecycle_commands() -> None:
    operations = {route.operation_id for route in router.routes if route.operation_id is not None}
    assert {
        "list_business_terminal",
        "create_business_terminal",
        "get_business_terminal",
        "update_business_terminal",
        "validate_business_terminal",
        "activate_business_terminal",
        "disable_business_terminal",
        "recover_business_terminal",
        "archive_business_terminal",
        "create_login_strategy",
        "get_login_strategy",
        "update_login_strategy",
        "activate_login_strategy",
        "create_automation_asset",
        "get_automation_asset",
        "update_automation_asset",
        "create_environment_terminal_access_revision",
        "get_environment_terminal_access_revision",
        "validate_environment_terminal_access_revision",
        "return_to_draft_environment_terminal_access_revision",
        "publish_environment_terminal_access_revision",
        "update_environment_terminal_access_revision",
        "abandon_environment_terminal_access_revision",
    }.issubset(operations)


def test_login_strategy_activation_keeps_formal_lifecycle_boundary() -> None:
    _assert_login_strategy_activatable("DRAFT")
    _assert_login_strategy_activatable("RECOVERED")
    with pytest.raises(PlatformError) as raised:
        _assert_login_strategy_activatable("CREATED")
    assert raised.value.status == 409
    assert raised.value.code == "LOGIN_STRATEGY_STATE_CONFLICT"


def test_url_normalization_allows_only_absolute_web_urls() -> None:
    assert normalize_web_url("HTTPS://Example.COM:443/login") == "https://example.com/login"
    assert normalize_web_url("http://Example.COM") == "http://example.com/"
    for value in ("javascript:alert(1)", "file:///tmp/x", "/relative", "https://u:p@x.test"):
        with pytest.raises(ValueError):
            normalize_web_url(value)


def test_local_storage_contract_rejects_secret_semantics() -> None:
    assert LocalStoragePreset(key="tenant", value="demo").scope == "ORIGIN"
    with pytest.raises(ValidationError):
        LocalStoragePreset(key="access_token", value="secret")


def test_captcha_response_header_policy_is_complete_and_contains_no_runtime_value() -> None:
    CreateLoginStrategyRequest(
        project_id="P" * 26,
        automation_asset_id="A" * 26,
        captcha_policy="RESPONSE_HEADER",
        captcha_request_header_name="Show-Captcha-Code",
        captcha_request_header_value="true",
        captcha_response_header_name="x-captcha-code",
    )
    assert "captcha_value" not in CreateLoginStrategyRequest.model_fields
    with pytest.raises(ValidationError):
        CreateLoginStrategyRequest(
            project_id="P" * 26,
            automation_asset_id="A" * 26,
            captcha_policy="RESPONSE_HEADER",
            captcha_request_header_name="Show-Captcha-Code",
        )


@pytest.mark.parametrize("key", ["auth", "api_key", "password", "accessToken"])
def test_login_strategy_rejects_secret_aliases_recursively(key: str) -> None:
    with pytest.raises(ValidationError):
        CreateLoginStrategyRequest(
            project_id="P" * 26,
            automation_asset_id="A" * 26,
            session_policy={"nested": {key: "plaintext"}},
        )


@pytest.mark.parametrize(
    "field", ["local_storage_presets", "refresh_after_local_storage", "captcha_policy"]
)
def test_login_strategy_update_rejects_explicit_null_for_required_storage(field: str) -> None:
    with pytest.raises(ValidationError):
        UpdateLoginStrategyRequest.model_validate({"expected_version": 0, field: None})
    assert UpdateLoginStrategyRequest(expected_version=0).model_fields_set == {
        "expected_version"
    }


def test_login_strategy_lifecycle_events_use_strategy_identity_without_secrets() -> None:
    session = _EventSession()
    strategy = SimpleNamespace(
        login_strategy_id="L" * 26,
        automation_asset_id="A" * 26,
        project_id="P" * 26,
        display_name="strategy",
        lifecycle_status="DRAFT",
        row_version=1,
        local_storage_presets=[{"key": "locale", "value": "zh-CN"}],
        refresh_after_local_storage=True,
        captcha_policy="NONE",
        captcha_request_header_name=None,
        captcha_request_header_value=None,
        captcha_response_header_name=None,
        session_policy={"mode": "cookie"},
    )
    AutomationAssetService._event(
        session,
        strategy,
        "login_strategy.draft",
        "U" * 26,
        SimpleNamespace(correlation_id="corr"),
        "idem",
        "CREATED",
        "DRAFT",
        0,
        1,
        {"changed_fields": ["display_name"]},
    )
    payload = session.added.payload_json
    assert payload["aggregate_id"] == strategy.login_strategy_id
    assert payload["payload"]["login_strategy_id"] == strategy.login_strategy_id
    projection = _strategy_projection(strategy)
    serialized = str(projection).casefold()
    assert "zh-cn" not in serialized and "cookie" not in serialized


def test_revision_url_and_separate_terminal_creation_contract() -> None:
    revision = CreateTerminalAccessRevisionRequest(
        business_terminal_id="T" * 26,
        entry_url="https://example.test/app",
        login_url="https://example.test/login",
    )
    assert revision.entry_url == "https://example.test/app"
    assert "environment_id" not in CreateTerminalAccessRevisionRequest.model_fields
    assert "revision_no" not in CreateTerminalAccessRevisionRequest.model_fields


def test_revision_update_contract_only_exposes_draft_configuration_fields() -> None:
    request = UpdateTerminalAccessRevisionRequest(
        expected_version=3,
        entry_url="HTTPS://Example.TEST:443/corrected",
        login_strategy_id=None,
        reason="correct invalid draft",
    )
    assert request.entry_url == "https://example.test/corrected"
    assert {
        "environment_terminal_access_revision_id",
        "project_id",
        "environment_id",
        "business_terminal_id",
        "revision_no",
        "lifecycle_status",
        "published_at",
    }.isdisjoint(UpdateTerminalAccessRevisionRequest.model_fields)
    with pytest.raises(ValidationError):
        UpdateTerminalAccessRevisionRequest(expected_version=3, reason="no changes")


def test_only_never_published_draft_is_mutable_or_abandonable() -> None:
    _assert_revision_draft_mutable(
        SimpleNamespace(lifecycle_status="DRAFT", published_at=None), "edited"
    )
    for status, published_at in (
        ("VALIDATING", None),
        ("PUBLISHED", "2026-09-04T00:00:00Z"),
        ("SUPERSEDED", "2026-09-04T00:00:00Z"),
        ("DRAFT", "2026-09-04T00:00:00Z"),
    ):
        with pytest.raises(PlatformError) as raised:
            _assert_revision_draft_mutable(
                SimpleNamespace(lifecycle_status=status, published_at=published_at), "abandoned"
            )
        assert raised.value.code == "TERMINAL_ACCESS_REVISION_OPERATION_FORBIDDEN_FOR_STATE"


def test_terminal_lifecycle_matches_lc_011_and_has_no_patch_escape() -> None:
    assert _TERMINAL_TRANSITIONS["validate"][:2] == ({"CONFIGURING"}, "VALIDATING")
    assert _TERMINAL_TRANSITIONS["activate"][:2] == ({"VALIDATING", "RECOVERING"}, "ACTIVE")
    assert _TERMINAL_TRANSITIONS["archive"][:2] == ({"DISABLED"}, "ARCHIVED")


def test_terminal_cas_conflict_is_deterministic() -> None:
    _check_version(3, 3)
    with pytest.raises(PlatformError) as raised:
        _check_version(4, 3)
    assert raised.value.code == "BUSINESS_TERMINAL_CONCURRENCY_CONFLICT"


def test_terminal_filters_are_owner_scoped() -> None:
    assert _parse_filter(
        "project_id=P;environment_id=E;terminal_type=MANAGEMENT",
        {"project_id", "environment_id", "terminal_type"},
    ) == {"project_id": "P", "environment_id": "E", "terminal_type": "MANAGEMENT"}
    with pytest.raises(PlatformError):
        _parse_filter("runner_id=R", {"project_id"})


def test_terminal_migration_encodes_revision_ownership_and_no_future_modules() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root / "docs/authority/编码权威事实/DATABASE_DDL/V13__business_terminal_foundation.sql"
    ).read_text(encoding="utf-8")
    assert "UNIQUE (project_id, terminal_code)" in migration
    assert "UNIQUE (business_terminal_id, revision_no)" in migration
    assert "current_published_revision_id" in migration
    assert "fk_atp_terminal_access_revision_terminal_scope" in migration
    assert "fk_atp_business_terminal_current_revision" in migration
    assert "fk_atp_login_strategy_automation_asset_scope" in migration
    assert "DROP COLUMN environment_terminal_access_revision_id" in migration
    assert "login_strategy_id" in migration
    assert "MANAGEMENT" in migration and "CLIENT" in migration and "PDA" in migration
    assert "CREATE TABLE atp_business_terminal_audit" in migration
    assert "CREATE TABLE atp_login_strategy_audit" in migration
    assert "trg_atp_login_strategy_audit_no_update" in migration
    for prohibited in ("test_account", "runner_id", "resource_lease", "execution_context"):
        assert prohibited not in migration.casefold()


def test_configuration_management_migration_preserves_publication_time_without_new_state() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root
        / "docs/authority/编码权威事实/DATABASE_DDL"
        / "V19__business_terminal_configuration_management.sql"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN published_at DATETIME(6) NULL" in migration
    assert "ABANDONED" not in migration
    assert "DROP" not in migration.upper()


def test_publication_evidence_repair_clears_unprovable_historical_timestamps() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root
        / "docs/authority/编码权威事实/DATABASE_DDL"
        / "V20__business_terminal_publication_evidence_repair.sql"
    ).read_text(encoding="utf-8")
    assert "SET published_at = NULL" in migration
    assert "SUPERSEDED" in migration
    assert "RETIRED" in migration
    assert "ARCHIVED" in migration
    assert "PUBLISHED" not in migration.split("WHERE", 1)[1]


def test_only_terminal_business_key_maps_to_conflict() -> None:
    duplicate = IntegrityError(
        "statement",
        {},
        Exception(1062, "Duplicate entry for key 'uq_atp_business_terminal_business'"),
    )
    assert _integrity_error(duplicate).code == "BUSINESS_TERMINAL_CODE_CONFLICT"


class _EventSession:
    def __init__(self) -> None:
        self.added = None

    def scalar(self, _: object) -> int:
        return 0

    def add(self, value: object) -> None:
        self.added = value


def test_terminal_event_carries_cas_and_scope_without_secrets() -> None:
    session = _EventSession()
    BusinessTerminalService._event(
        session,
        "T" * 26,
        "P" * 26,
        "business_terminal.configuring",
        "U" * 26,
        SimpleNamespace(correlation_id="corr"),
        "idem",
        "CREATED",
        "CONFIGURING",
        0,
        1,
        {"changed_fields": ["lifecycle_status"]},
    )
    payload = session.added.payload_json
    assert payload["payload"]["expected_version"] == 0
    assert payload["payload"]["new_version"] == 1
    serialized = str(payload).casefold()
    assert "password" not in serialized and "captcha_value" not in serialized


def test_revision_event_uses_revision_aggregate_identity() -> None:
    session = _EventSession()
    revision_id = "R" * 26
    BusinessTerminalService._event(
        session,
        revision_id,
        "P" * 26,
        "environment_terminal_access_revision.validating",
        "U" * 26,
        SimpleNamespace(correlation_id="corr"),
        "idem",
        "DRAFT",
        "VALIDATING",
        1,
        2,
        {"revision_no": 1},
        identity_field="environment_terminal_access_revision_id",
    )
    payload = session.added.payload_json
    assert payload["aggregate_id"] == revision_id
    assert payload["payload"]["environment_terminal_access_revision_id"] == revision_id
    assert "business_terminal_id" not in payload["payload"]


@pytest.mark.parametrize(
    ("event_type", "to_state"),
    [
        ("environment_terminal_access_revision.updated", "DRAFT"),
        ("environment_terminal_access_revision.abandoned", "ABANDONED"),
    ],
)
def test_revision_management_events_are_revision_scoped_and_secret_free(
    event_type: str, to_state: str
) -> None:
    session = _EventSession()
    revision_id = "R" * 26
    BusinessTerminalService._event(
        session,
        revision_id,
        "P" * 26,
        event_type,
        "U" * 26,
        SimpleNamespace(correlation_id="corr"),
        "stable-idempotency-key",
        "DRAFT",
        to_state,
        2,
        3 if to_state == "DRAFT" else 2,
        {"changed_fields": ["entry_url"]},
        identity_field="environment_terminal_access_revision_id",
    )
    payload = session.added.payload_json
    assert payload["aggregate_id"] == revision_id
    assert payload["causation_id"] == "stable-idempotency-key"
    assert payload["payload"]["to_state"] == to_state
    assert "password" not in str(payload).casefold()
