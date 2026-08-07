"""JSON Schema validation foundation for official event schemas."""

from __future__ import annotations

from collections.abc import Mapping

from jsonschema import Draft202012Validator


class ContractViolation(ValueError):
    """Raised when a payload does not satisfy an official schema."""


class JsonSchemaValidator:
    def __init__(self, schema: Mapping[str, object]) -> None:
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(schema)

    def validate(self, payload: object) -> None:
        errors = sorted(self._validator.iter_errors(payload), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(error.message for error in errors)
            raise ContractViolation(details)
