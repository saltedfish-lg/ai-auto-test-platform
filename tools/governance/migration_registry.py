from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_migration_capabilities(authority_root: Path) -> dict[str, str]:
    path = authority_root / "编码权威事实" / "DATABASE_DDL" / "migration-capabilities.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    capabilities = payload.get("capabilities", {}) if isinstance(payload, dict) else {}
    result: dict[str, str] = {}
    for capability, spec in capabilities.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("migration_name"), str):
            raise ValueError(f"invalid migration capability {capability}")
        result[str(capability)] = spec["migration_name"]
    return result


def migration_for_capability(migrations: list[dict[str, Any]], authority_root: Path, capability: str) -> dict[str, Any]:
    registry = load_migration_capabilities(authority_root)
    target = registry.get(capability)
    matches = [item for item in migrations if item.get("name") == target]
    if len(matches) != 1:
        raise ValueError(f"migration capability {capability} must resolve exactly once")
    return matches[0]
