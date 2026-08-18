from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def migration_set_identity(migrations: list[dict[str, Any]], authority_root: Path) -> dict[str, Any]:
    authority_root = authority_root.resolve()
    items: list[dict[str, Any]] = []
    for item in migrations:
        path = Path(item["path"]).resolve()
        items.append({
            "version": int(item["version"]),
            "relative_path": path.relative_to(authority_root).as_posix(),
            "sha256": _sha256_file(path),
        })
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "migration_count": len(items),
        "current_migration_head": items[-1]["version"] if items else None,
        "migration_set_digest": hashlib.sha256(raw).hexdigest(),
        "migrations": items,
    }


def full_schema_input_identity(
    migrations: list[dict[str, Any]],
    authority_root: Path,
    gate_source: Path,
    assertion_source: Path,
) -> dict[str, Any]:
    migration_identity = migration_set_identity(migrations, authority_root)
    return {
        **migration_identity,
        "gate_source_path": gate_source.resolve().relative_to(authority_root.parents[1]).as_posix(),
        "gate_source_digest": _sha256_file(gate_source.resolve()),
        "schema_assertion_source_path": assertion_source.resolve().relative_to(authority_root.parents[1]).as_posix(),
        "schema_assertion_source_digest": _sha256_file(assertion_source.resolve()),
    }


def validate_full_schema_evidence_freshness(evidence: dict[str, Any], current: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pairs = (
        ("current_migration_head", "validated_migration_head"),
        ("migration_set_digest", "migration_set_digest"),
        ("gate_source_digest", "gate_source_digest"),
        ("schema_assertion_source_digest", "schema_assertion_source_digest"),
    )
    for current_key, evidence_key in pairs:
        if evidence.get(evidence_key) != current.get(current_key):
            errors.append(f"stale {evidence_key}")
    return errors
