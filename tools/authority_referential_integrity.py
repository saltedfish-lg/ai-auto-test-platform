#!/usr/bin/env python3
"""Validate structured cross-references in the active Living Authority.

Canonical registries are owned by the current Object, Rule, Lifecycle, Acceptance and Data Asset definitions.
Historical ADR/migration provenance is intentionally excluded; active YAML/JSON consumers must
not reference identifiers that are absent from those current registries.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = REPO_ROOT / "docs" / "authority"

CORE_REL = Path("核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml")
DATA_REL = Path("数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml")
ACCEPTANCE_REL = Path("编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json")
DATABASE_SCHEMA_REL = Path("编码权威事实/DATABASE_DDL/database-schema.yaml")

OBJECT_RE = re.compile(r"^OBJ-\d{3}$")
RULE_RE = re.compile(r"^BR-[A-Z0-9-]+$")
DATA_ASSET_RES = (
    re.compile(r"^DI-[A-Z0-9-]+$"),
    re.compile(r"^DA-[A-Z0-9-]+$"),
)
ACCEPTANCE_RE = re.compile(r"^ACC-(?:R3|PRD)-[A-Z0-9-]+$")
LIFECYCLE_RE = re.compile(r"^LC-[A-Z0-9-]+$")

# Historical provenance may legitimately mention identifiers retired from the current model.
EXCLUDED_PATH_PARTS = {"ADR"}


def _yaml(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=YAML_LOADER)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_registries(authority_root: Path) -> dict[str, set[str]]:
    core = _yaml(authority_root / CORE_REL)
    data = _yaml(authority_root / DATA_REL)
    acceptance = _json(authority_root / ACCEPTANCE_REL)
    return {
        "OBJECT": {
            str(item["object_id"])
            for item in core.get("objects", [])
            if isinstance(item, dict) and item.get("object_id")
        },
        "RULE": {
            str(item["rule_id"])
            for item in core.get("business_rules", [])
            if isinstance(item, dict) and item.get("rule_id")
        },
        "LIFECYCLE": {
            str(item["lifecycle_id"])
            for item in core.get("lifecycles", [])
            if isinstance(item, dict) and item.get("lifecycle_id")
        },
        "DATA_ASSET": {
            str(item["data_asset_id"])
            for item in data.get("data_assets", [])
            if isinstance(item, dict) and item.get("data_asset_id")
        },
        "ACCEPTANCE": {
            str(item["acceptance_id"])
            for item in acceptance.get("acceptance_closure", [])
            if isinstance(item, dict) and item.get("acceptance_id")
        },
    }


def _kind(value: str) -> str | None:
    if OBJECT_RE.fullmatch(value):
        return "OBJECT"
    if RULE_RE.fullmatch(value):
        return "RULE"
    if LIFECYCLE_RE.fullmatch(value):
        return "LIFECYCLE"
    if any(pattern.fullmatch(value) for pattern in DATA_ASSET_RES):
        return "DATA_ASSET"
    if ACCEPTANCE_RE.fullmatch(value):
        return "ACCEPTANCE"
    return None


def _is_definition(rel: Path, pointer: tuple[str, ...], key: str, kind: str) -> bool:
    # Only the canonical identifier field itself is a definition; other fields inside the same
    # item remain references and are validated normally.
    if rel == CORE_REL and kind == "OBJECT" and key == "object_id" and len(pointer) >= 2 and pointer[0] == "objects":
        return True
    if rel == CORE_REL and kind == "RULE" and key == "rule_id" and len(pointer) >= 2 and pointer[0] == "business_rules":
        return True
    if rel == CORE_REL and kind == "LIFECYCLE" and key == "lifecycle_id" and len(pointer) >= 2 and pointer[0] == "lifecycles":
        return True
    if rel == DATA_REL and kind == "DATA_ASSET" and key == "data_asset_id" and len(pointer) >= 2 and pointer[0] == "data_assets":
        return True
    if rel == ACCEPTANCE_REL and kind == "ACCEPTANCE" and key == "acceptance_id" and len(pointer) >= 2 and pointer[0] == "acceptance_closure":
        return True
    return False


def _walk(
    value: Any,
    rel: Path,
    registries: dict[str, set[str]],
    pointer: tuple[str, ...] = (),
) -> Iterable[dict[str, str]]:
    # Explicit retirement provenance is immutable history, not an active reference.
    if rel == ACCEPTANCE_REL and pointer[:2] == ("metadata", "obj_085_retirement_provenance"):
        return
    if rel == DATABASE_SCHEMA_REL and pointer[:2] == ("migration_execution", "retired_active_models"):
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = pointer + (str(key),)
            if isinstance(child, str):
                kind = _kind(child)
                if kind and not _is_definition(rel, pointer, str(key), kind) and child not in registries[kind]:
                    yield {
                        "kind": kind,
                        "id": child,
                        "file": rel.as_posix(),
                        "pointer": ".".join(child_pointer),
                    }
            else:
                yield from _walk(child, rel, registries, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_pointer = pointer + (str(index),)
            if isinstance(child, str):
                kind = _kind(child)
                if kind and child not in registries[kind]:
                    yield {
                        "kind": kind,
                        "id": child,
                        "file": rel.as_posix(),
                        "pointer": ".".join(child_pointer),
                    }
            else:
                yield from _walk(child, rel, registries, child_pointer)


def check(authority_root: Path = AUTHORITY_ROOT) -> tuple[dict[str, int], list[dict[str, str]]]:
    authority_root = authority_root.resolve()
    registries = _canonical_registries(authority_root)
    dangling: list[dict[str, str]] = []
    for path in sorted(authority_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        rel = path.relative_to(authority_root)
        if any(part in EXCLUDED_PATH_PARTS for part in rel.parts):
            continue
        try:
            payload = _json(path) if path.suffix.lower() == ".json" else _yaml(path)
        except Exception as exc:  # pragma: no cover - canonical syntax validators report details
            dangling.append({
                "kind": "PARSE_ERROR",
                "id": type(exc).__name__,
                "file": rel.as_posix(),
                "pointer": "",
            })
            continue
        dangling.extend(_walk(payload, rel, registries))
    counts = {kind: len(values) for kind, values in registries.items()}
    return counts, dangling


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "show"])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    authority_root = args.root.resolve() / "docs" / "authority"
    counts, dangling = check(authority_root)
    payload = {
        "registry_counts": counts,
        "dangling_count": len(dangling),
        "dangling": dangling,
    }
    if args.command == "show" or dangling:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if dangling:
        print("AUTHORITY_REFERENTIAL_INTEGRITY_FAILED")
        return 1
    print("AUTHORITY_REFERENTIAL_INTEGRITY_PASS")
    print(json.dumps({"registry_counts": counts, "dangling_count": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
