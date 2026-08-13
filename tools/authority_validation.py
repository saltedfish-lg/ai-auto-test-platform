#!/usr/bin/env python3
"""Canonical Living Authority validator command set shared by all entrypoints."""
from __future__ import annotations

from collections import OrderedDict
import os

DEFAULT_VALIDATOR_TIMEOUT_SECONDS = 600
MIN_VALIDATOR_TIMEOUT_SECONDS = 30
MAX_VALIDATOR_TIMEOUT_SECONDS = 3600

AUTHORITY_VALIDATOR_COMMANDS = OrderedDict(
    [
        ("verify_authority", ["tools/verify_authority.py"]),
        ("validate_all", ["docs/authority/validation/validate_all.py", "--root", "docs/authority"]),
        ("validate_governance", ["docs/authority/validation/validate_governance.py", "--root", "docs/authority"]),
        ("validate_auth_contract", ["docs/authority/validation/validate_auth_contract.py", "--root", "docs/authority"]),
        ("authority_projection_check", ["tools/authority_projection.py", "check"]),
        ("current_facts_check", ["tools/current_facts.py", "check"]),
        ("authority_referential_integrity", ["tools/authority_referential_integrity.py", "check"]),
        ("openapi_client_check", ["tools/openapi_client.py", "check"]),
    ]
)


def validator_commands() -> OrderedDict[str, list[str]]:
    """Return a defensive copy so callers cannot mutate the canonical process-wide list."""
    return OrderedDict((name, list(argv)) for name, argv in AUTHORITY_VALIDATOR_COMMANDS.items())


def validator_timeout_seconds(env: dict[str, str] | None = None) -> int:
    """Return the configured per-validator timeout with fail-safe bounds.

    ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS is intentionally runtime-configurable because
    validate_all / validate_governance cost depends on workstation and filesystem speed.
    """
    source = env if env is not None else os.environ
    raw = source.get("ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS")
    if raw is None or raw == "":
        return DEFAULT_VALIDATOR_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS must be an integer") from exc
    if not MIN_VALIDATOR_TIMEOUT_SECONDS <= value <= MAX_VALIDATOR_TIMEOUT_SECONDS:
        raise ValueError(
            f"ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS must be between {MIN_VALIDATOR_TIMEOUT_SECONDS} and {MAX_VALIDATOR_TIMEOUT_SECONDS}"
        )
    return value
