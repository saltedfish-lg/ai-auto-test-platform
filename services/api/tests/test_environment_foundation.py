import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from platform_api.environment_router import router
from platform_api.environment_schemas import (
    CreateEnvironmentRequest,
    LifecycleCommandRequest,
    UpdateEnvironmentRequest,
)
from platform_api.environment_service import (
    _ENVIRONMENT_TRANSITIONS,
    EnvironmentService,
    _apply_state_changes,
    _environment_integrity_error,
    _parse_filter,
)
from platform_api.errors import PlatformError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


def test_environment_operations_match_formal_openapi_contract() -> None:
    operations = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert operations == {
        ("GET", "/api/v1/environment", "list_environment"),
        ("POST", "/api/v1/environment", "create_environment"),
        ("GET", "/api/v1/environment/{id}", "get_environment"),
        ("PATCH", "/api/v1/environment/{id}", "update_environment"),
        ("POST", "/api/v1/environment/{id}/validate", "validate_environment"),
        ("POST", "/api/v1/environment/{id}/reconfigure", "reconfigure_environment"),
        ("POST", "/api/v1/environment/{id}/activate", "activate_environment"),
    }


def test_environment_lifecycle_commands_match_lc_009_without_patch_escape() -> None:
    assert {
        "validate": (
            frozenset({"CONFIGURING"}),
            "VALIDATING",
            "environment.validating",
        ),
        "reconfigure": (
            frozenset({"VALIDATING"}),
            "CONFIGURING",
            "environment.configuring",
        ),
        "activate": (
            frozenset({"VALIDATING", "RECOVERING"}),
            "ACTIVE",
            "environment.active",
        ),
    } == _ENVIRONMENT_TRANSITIONS
    command = LifecycleCommandRequest(expected_version=2, reason="通过验证")
    assert command.model_dump() == {"expected_version": 2, "reason": "通过验证"}
    assert "lifecycle_status" not in UpdateEnvironmentRequest.model_fields
    with pytest.raises(ValidationError):
        LifecycleCommandRequest(expected_version=2, reason="")


def test_environment_contract_has_no_terminal_revision_owner_pointer() -> None:
    CreateEnvironmentRequest(
        project_id="P" * 26,
        environment_code="TEST",
        display_name="测试环境",
    )
    assert "environment_terminal_access_revision_id" not in CreateEnvironmentRequest.model_fields
    with pytest.raises(ValidationError):
        CreateEnvironmentRequest.model_validate(
            {"project_id": "P" * 26, "environment_code": "TEST", "base_url": "https://x"}
        )


def test_environment_business_identity_is_required_and_immutable_input_is_visible() -> None:
    with pytest.raises(ValidationError):
        CreateEnvironmentRequest(environment_code="TEST")
    update = UpdateEnvironmentRequest(
        expected_version=2,
        project_id="P" * 26,
        environment_code="OTHER",
    )
    assert {"project_id", "environment_code"}.issubset(update.model_fields_set)


def test_environment_filter_is_explicitly_project_scoped() -> None:
    assert _parse_filter("project_id=P;lifecycle_status=ACTIVE") == {
        "project_id": "P",
        "lifecycle_status": "ACTIVE",
    }
    with pytest.raises(PlatformError) as raised:
        _parse_filter("unknown=value")
    assert raised.value.code == "ENVIRONMENT_FILTER_INVALID"


def test_environment_migration_resolves_project_uniqueness_and_drops_pointer() -> None:
    root = Path(__file__).resolve().parents[3]
    migration = (
        root / "docs/authority/编码权威事实/DATABASE_DDL/V12__environment_management_foundation.sql"
    ).read_text(encoding="utf-8")
    assert "environment_terminal_access_revision_id VARCHAR(26) NULL" in migration
    assert "environment_id VARCHAR(26) NULL" in migration
    assert "new_status VARCHAR(11) NULL" in migration
    assert "UNIQUE (project_id, environment_code)" in migration
    assert "CREATE TABLE atp_environment_audit" in migration
    assert "trg_atp_environment_audit_no_update" in migration
    assert "trg_atp_environment_audit_no_delete" in migration
    assert "base_url" not in migration

    terminal_migration = (
        root / "docs/authority/编码权威事实/DATABASE_DDL/V13__business_terminal_foundation.sql"
    ).read_text(encoding="utf-8")
    assert "DROP COLUMN environment_terminal_access_revision_id" in terminal_migration
    assert "current_published_revision_id" in terminal_migration

    schema = (root / "docs/authority/编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(
        encoding="utf-8"
    )
    assert "object_id: OBJ-009-AUDIT" not in schema


@pytest.mark.parametrize(
    ("initial", "body", "expected_status", "expected_event"),
    [
        (
            "ACTIVE",
            UpdateEnvironmentRequest(expected_version=3, accessibility_state="UNREACHABLE"),
            "UNREACHABLE",
            "environment.unreachable",
        ),
        (
            "UNREACHABLE",
            UpdateEnvironmentRequest(expected_version=3, accessibility_state="REACHABLE"),
            "RECOVERING",
            "environment.recovering",
        ),
        (
            "DISABLED",
            UpdateEnvironmentRequest(expected_version=3, enablement_state="ENABLED"),
            "RECOVERING",
            "environment.recovering",
        ),
    ],
)
def test_environment_state_changes_follow_lc_009(
    initial: str,
    body: UpdateEnvironmentRequest,
    expected_status: str,
    expected_event: str,
) -> None:
    environment = SimpleNamespace(
        lifecycle_status=initial,
        enablement_state="DISABLED" if initial == "DISABLED" else "ENABLED",
        accessibility_state="UNREACHABLE" if initial == "UNREACHABLE" else "REACHABLE",
    )
    event, _ = _apply_state_changes(environment, body)  # type: ignore[arg-type]
    assert environment.lifecycle_status == expected_status
    assert event == expected_event


def test_unreachable_environment_cannot_skip_recovery_to_disabled() -> None:
    environment = SimpleNamespace(
        lifecycle_status="UNREACHABLE",
        enablement_state="ENABLED",
        accessibility_state="UNREACHABLE",
    )
    with pytest.raises(PlatformError) as raised:
        _apply_state_changes(  # type: ignore[arg-type]
            environment,
            UpdateEnvironmentRequest(expected_version=3, enablement_state="DISABLED"),
        )
    assert raised.value.code == "ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE"


class _EventCaptureSession:
    def __init__(self) -> None:
        self.added: object | None = None

    def scalar(self, statement: object) -> int:
        del statement
        return 0

    def add(self, value: object) -> None:
        self.added = value


def test_environment_outbox_payload_matches_formal_event_contract() -> None:
    root = Path(__file__).resolve().parents[3]
    environment = SimpleNamespace(
        environment_id="E" * 26,
        project_id="P" * 26,
        lifecycle_status="CONFIGURING",
        row_version=1,
    )
    session = _EventCaptureSession()
    EnvironmentService._append_event(
        session,  # type: ignore[arg-type]
        environment,  # type: ignore[arg-type]
        "environment.configuring",
        "U" * 26,
        context=SimpleNamespace(correlation_id="correlation-id"),  # type: ignore[arg-type]
        causation_id="idempotency-key",
        previous_status="CREATED",
        expected_version=0,
        change_summary={"lifecycle_path": ["CREATED", "CONFIGURING"]},
    )
    assert session.added is not None
    payload = session.added.payload_json  # type: ignore[attr-defined]
    contract = (
        root
        / "docs/authority/编码权威事实/EVENT_CONTRACTS/schemas/environment.configuring.schema.json"
    ).read_text(encoding="utf-8")
    Draft202012Validator(json.loads(contract)).validate(payload)


def test_environment_service_has_no_terminal_access_ownership_dependency() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / "services/api/src/platform_api/environment_service.py").read_text(
        encoding="utf-8"
    )
    assert "atp_environment_terminal_access_revision" not in source
    assert "environment_terminal_access_revision_id" not in source


@pytest.mark.parametrize(
    ("vendor_code", "vendor_message", "expected_code"),
    [
        (
            1062,
            "Duplicate entry for key 'uq_atp_environment_business'",
            "ENVIRONMENT_CODE_CONFLICT",
        ),
        (
            1062,
            "Duplicate entry for key 'uq_atp_outbox_event_aggregate_sequence'",
            "INTERNAL_ERROR",
        ),
        (1452, "Cannot add or update a child row", "INTERNAL_ERROR"),
    ],
)
def test_only_environment_business_unique_key_maps_to_code_conflict(
    vendor_code: int, vendor_message: str, expected_code: str
) -> None:
    original = Exception(vendor_code, vendor_message)
    error = IntegrityError("statement", {}, original)
    assert _environment_integrity_error(error).code == expected_code
