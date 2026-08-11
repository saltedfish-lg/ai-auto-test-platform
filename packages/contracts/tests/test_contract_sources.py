from pathlib import Path

import pytest
from platform_contracts import AuthoritySources, ContractViolation, JsonSchemaValidator

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "docs" / "authority"


def test_official_contract_sources_are_loaded_from_current_authority() -> None:
    sources = AuthoritySources(AUTHORITY)
    assert sources.openapi.is_file()
    assert sources.event_registry.is_file()
    schema = sources.load_event_schema("admin.active.schema.json")
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


def test_schema_validator_rejects_invalid_payload() -> None:
    validator = JsonSchemaValidator({"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]})
    with pytest.raises(ContractViolation, match="required property"):
        validator.validate({})


def test_event_schema_path_cannot_escape_authority_directory() -> None:
    with pytest.raises(ValueError, match="invalid event schema name"):
        AuthoritySources(AUTHORITY).load_event_schema("../openapi.yaml")
