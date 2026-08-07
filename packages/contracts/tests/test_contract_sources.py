from pathlib import Path

import pytest
from platform_contracts import BaselineSources, ContractViolation, JsonSchemaValidator

ROOT = Path(__file__).resolve().parents[3]
CURRENT = (ROOT / "docs" / "baseline" / "CURRENT").read_text(encoding="utf-8").strip()
BASELINE = ROOT / "docs" / "baseline" / CURRENT


def test_official_contract_sources_are_loaded_from_current_baseline() -> None:
    sources = BaselineSources(BASELINE)

    assert sources.openapi.is_file()
    assert sources.event_registry.is_file()
    schema = sources.load_event_schema("admin.active.schema.json")
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


def test_schema_validator_rejects_invalid_payload() -> None:
    validator = JsonSchemaValidator(
        {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
    )

    with pytest.raises(ContractViolation, match="required property"):
        validator.validate({})


def test_event_schema_path_cannot_escape_frozen_directory() -> None:
    with pytest.raises(ValueError, match="invalid event schema name"):
        BaselineSources(BASELINE).load_event_schema("../openapi.yaml")
