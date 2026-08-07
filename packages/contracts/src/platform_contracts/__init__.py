"""Consumers for frozen contract sources; no formal contract is redefined here."""

from platform_contracts.schema import ContractViolation, JsonSchemaValidator
from platform_contracts.sources import BASELINE_RELEASE_ID, BaselineSources

__all__ = [
    "BASELINE_RELEASE_ID",
    "BaselineSources",
    "ContractViolation",
    "JsonSchemaValidator",
]
