#!/usr/bin/env python3
"""Derive volatile current facts from canonical Living Authority definitions.

Definitions remain explicit (migrations, roles, permissions, operations, schemas, etc.).
Counts, current heads, catalogs and freshness are derived here so they are not copied across
Agent/Skill/docs/validators.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any

import yaml

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

def _yaml_load(text: str):
    return yaml.load(text, Loader=YAML_LOADER)

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = REPO_ROOT / "docs" / "authority"
MIGRATION_RE = re.compile(r"^V(?P<version>\d+)__(?P<name>.+)\.sql$")

CURRENT_CONTRACT_SOURCES = {
    "SYSTEM-DESIGN": ("编码权威事实/SYSTEM_DESIGN.yaml", "metadata.artifact_id"),
    "DATABASE-SCHEMA": ("编码权威事实/DATABASE_DDL/database-schema.yaml", "metadata.artifact_id"),
    "DATABASE-DDL": ("编码权威事实/DATABASE_DDL/database-schema.yaml", "metadata.artifact_id"),
    "OPENAPI": ("编码权威事实/OPENAPI/openapi.yaml", "info.x-artifact-id"),
    "EVENT-REGISTRY": ("编码权威事实/EVENT_CONTRACTS/event-registry.yaml", "metadata.artifact_id"),
    "EVENT-CONTRACTS": ("编码权威事实/EVENT_CONTRACTS/event-registry.yaml", "metadata.artifact_id"),
    "PERMISSION-CLOSURE": ("编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml", "metadata.artifact_id"),
    "AUTHENTICATION-CONTRACT": ("编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml", "metadata.artifact_id"),
}


def _load_yaml(path: Path) -> dict[str, Any]:
    value = _yaml_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping: {path}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping: {path}")
    return value


def _nested(mapping: dict[str, Any], dotted: str) -> Any:
    value: Any = mapping
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted)
        value = value[part]
    return value


def discover_migrations(authority_root: Path = AUTHORITY_ROOT) -> list[dict[str, Any]]:
    ddl_dir = authority_root / "编码权威事实" / "DATABASE_DDL"
    found: list[dict[str, Any]] = []
    for path in ddl_dir.iterdir():
        if not path.is_file():
            continue
        match = MIGRATION_RE.fullmatch(path.name)
        if not match:
            continue
        found.append({"version": int(match.group("version")), "name": path.name, "path": path})
    found.sort(key=lambda item: item["version"])
    versions = [item["version"] for item in found]
    if len(versions) != len(set(versions)):
        raise ValueError(f"duplicate migration versions: {versions}")
    if not found:
        raise ValueError(f"no formal migrations found under {ddl_dir}")
    return found


def _ddl_current_counts(migrations: list[dict[str, Any]]) -> tuple[int, int]:
    sql = "\n".join(item["path"].read_text(encoding="utf-8") for item in migrations)
    creates = set(re.findall(r"CREATE TABLE\s+`?([A-Za-z0-9_]+)`?", sql, re.I))
    drops = set(re.findall(r"DROP TABLE(?:\s+IF EXISTS)?\s+`?([A-Za-z0-9_]+)`?", sql, re.I))
    current_tables = creates - drops
    fk_rx = re.compile(
        r"ALTER TABLE\s+`?([A-Za-z0-9_]+)`?\s+ADD CONSTRAINT\s+`?([A-Za-z0-9_]+)`?\s+"
        r"FOREIGN KEY\s*\(`?([A-Za-z0-9_]+)`?\)\s+REFERENCES\s+`?([A-Za-z0-9_]+)`?",
        re.I,
    )
    foreign_keys = [match.groups() for match in fk_rx.finditer(sql)]
    current_fks = [fk for fk in foreign_keys if fk[0] in current_tables and fk[3] in current_tables]
    return len(current_tables), len(current_fks)


def _protocol_version(path: Path, constant: str) -> int:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(constant)}\s*=\s*(\d+)\s*$", text, re.M)
    if not match:
        raise ValueError(f"{constant} not found in {path}")
    return int(match.group(1))


def _current_contract_catalog(authority_root: Path) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for alias, (rel, dotted) in CURRENT_CONTRACT_SOURCES.items():
        path = authority_root / rel
        payload = _load_yaml(path)
        catalog[alias] = str(_nested(payload, dotted))
    return catalog


def _declared_acceptance_scopes(acceptance: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Derive current acceptance-scope facts from canonical range metadata, never fixed numeric bounds."""
    scopes: dict[str, dict[str, Any]] = {}
    for scope_name, scope in acceptance.items():
        if not isinstance(scope_name, str) or not scope_name.endswith("_governance") or not isinstance(scope, dict):
            continue
        declared_range = scope.get("range")
        if not isinstance(declared_range, str):
            continue
        match = re.fullmatch(r"(.+?)(\d+)\.\.(\d+)", declared_range)
        if not match:
            continue
        prefix, start_raw, end_raw = match.groups()
        start, end = int(start_raw), int(end_raw)
        if end < start:
            continue
        ids: list[str] = []
        for item in items:
            acceptance_id = item.get("acceptance_id")
            if not isinstance(acceptance_id, str) or not acceptance_id.startswith(prefix):
                continue
            suffix = acceptance_id[len(prefix):]
            if suffix.isdigit() and start <= int(suffix) <= end:
                ids.append(acceptance_id)
        scopes[scope_name] = {
            "range": declared_range,
            "count": len(ids),
            "acceptance_ids": sorted(ids),
        }
    return scopes

@lru_cache(maxsize=4)
def derive_current_facts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    authority_root = repo_root / "docs" / "authority"
    migrations = discover_migrations(authority_root)
    migration_names = [item["name"] for item in migrations]
    migration_versions = [item["version"] for item in migrations]
    table_count, fk_count = _ddl_current_counts(migrations)

    db_schema = _load_yaml(authority_root / "编码权威事实/DATABASE_DDL/database-schema.yaml")
    permission = _load_yaml(authority_root / "编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml")
    openapi = _load_yaml(authority_root / "编码权威事实/OPENAPI/openapi.yaml")
    events = _load_yaml(authority_root / "编码权威事实/EVENT_CONTRACTS/event-registry.yaml")
    acceptance = _load_json(authority_root / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json")
    core = _load_yaml(authority_root / "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml")
    product = _load_yaml(authority_root / "产品总体需求与系统边界/产品总体需求与系统边界.yaml")
    state_registry = _load_yaml(authority_root / "编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml")

    technical_names = list(db_schema.get("table_classification", {}).get("technical_table_names", []))
    object_table_count = table_count - len(technical_names) if technical_names else None

    paths = openapi.get("paths", {})
    methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    operation_count = sum(
        1 for item in paths.values() if isinstance(item, dict) for method, op in item.items()
        if method.lower() in methods and isinstance(op, dict)
    )
    schema_count = len(openapi.get("components", {}).get("schemas", {}))

    acceptance_items = acceptance.get("acceptance_closure", [])
    acceptance_status = {
        key: sum(1 for item in acceptance_items if item.get("status") == key)
        for key in ("SPECIFIED", "PASSED", "FAILED", "BLOCKED")
    }
    evidence_gap_count = sum(1 for item in acceptance_items if item.get("evidence_status") != "VERIFIED")

    return {
        "authority_model": "SINGLE_LIVING_AUTHORITY",
        "migration": {
            "files": migration_names,
            "versions": migration_versions,
            "head": migration_versions[-1],
            "head_name": migration_names[-1],
            "chain": " → ".join(f"V{version}" for version in migration_versions),
            "file_chain": " → ".join(migration_names),
        },
        "database": {
            "table_count": table_count,
            "foreign_key_count": fk_count,
            "technical_table_names": technical_names,
            "technical_table_count": len(technical_names),
            "object_table_count": object_table_count,
        },
        "rbac": {
            "permission_count": len(permission.get("permission_catalog", [])),
            "role_count": len(permission.get("role_templates", [])),
            "mapping_count": len(permission.get("role_permission_mappings", [])),
        },
        "openapi": {
            "path_count": len(paths),
            "operation_count": operation_count,
            "schema_count": schema_count,
        },
        "events": {"event_count": len(events.get("events", []))},
        "acceptance": {
            "count": len(acceptance_items),
            "declared_scopes": _declared_acceptance_scopes(acceptance, acceptance_items),
            "specified_count": acceptance_status["SPECIFIED"],
            "passed_count": acceptance_status["PASSED"],
            "failed_count": acceptance_status["FAILED"],
            "blocked_count": acceptance_status["BLOCKED"],
            "evidence_gap_count": evidence_gap_count,
        },
        "domain": {
            "object_count": len(core.get("objects", [])),
            "state_dimension_count": len(core.get("state_dimensions", [])),
            "authentication_state_owner_count": len(state_registry.get("authentication_state_owners", [])),
        },
        "governance": {
            "open_decision_count": len(product.get("open_decisions", [])),
        },
        "contracts": _current_contract_catalog(authority_root),
    }



def check_current_fact_governance(repo_root: Path = REPO_ROOT) -> list[str]:
    repo_root = repo_root.resolve()
    authority_root = repo_root / "docs" / "authority"
    errors: list[str] = []
    facts = derive_current_facts(repo_root)

    db_schema = _load_yaml(authority_root / "编码权威事实/DATABASE_DDL/database-schema.yaml")
    for key in ("migration_files", "object_table_count", "technical_table_count", "foreign_key_count"):
        if key in db_schema:
            errors.append(f"database-schema duplicates derived fact: {key}")
    execution = db_schema.get("migration_execution", {})
    for key in ("authority_chain", "current_chain"):
        if key in execution:
            errors.append(f"database-schema migration_execution duplicates derived fact: {key}")
    if execution.get("migration_discovery_source") != "tools/current_facts.py#discover_migrations":
        errors.append("database-schema migration discovery source drift")

    system_design = _load_yaml(authority_root / "编码权威事实/SYSTEM_DESIGN.yaml")
    for key in ("migration_release", "table_count", "object_table_count", "technical_table_count"):
        if key in system_design.get("database_contract", {}):
            errors.append(f"SYSTEM_DESIGN database_contract duplicates derived fact: {key}")
    for key in ("permission_count", "role_count", "mapping_count"):
        if key in system_design.get("permission_contract", {}):
            errors.append(f"SYSTEM_DESIGN permission_contract duplicates derived fact: {key}")
    for key in ("dimension_count", "state_dimension_count", "authentication_state_owner_count"):
        if key in system_design.get("state_contract", {}):
            errors.append(f"SYSTEM_DESIGN state_contract duplicates derived fact: {key}")
    gate_catalog = system_design.get("runtime_gate_catalog", {})
    gate_ids = {item.get("gate_id") for item in gate_catalog.get("gates", []) if isinstance(item, dict)}
    required_gate_ids = {"AUTH_MYSQL_RUNTIME_GATE", "AUTH_BROWSER_RUNTIME_GATE", "FULL_SCHEMA_MYSQL84_RUNTIME_GATE", "REAL_ACCEPTANCE_GATE"}
    if not required_gate_ids.issubset(gate_ids):
        errors.append(f"SYSTEM_DESIGN runtime gate catalog missing: {sorted(required_gate_ids - gate_ids)}")
    for item in gate_catalog.get("gates", []):
        if isinstance(item, dict) and any(key in item for key in ("status", "last_execution_evidence", "evidence_ref", "rerun_reason")):
            errors.append(f"SYSTEM_DESIGN runtime gate definition persists temporary result state: {item.get('gate_id')}")

    permission = _load_yaml(authority_root / "编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml")
    for key in ("permission_count", "role_count", "role_permission_mapping_count"):
        if key in permission.get("metadata", {}):
            errors.append(f"permission-closure metadata duplicates derived fact: {key}")
    events = _load_yaml(authority_root / "编码权威事实/EVENT_CONTRACTS/event-registry.yaml")
    if "event_count" in events.get("metadata", {}):
        errors.append("event-registry metadata duplicates derived event_count")
    state_registry = _load_yaml(authority_root / "编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml")
    for key in ("state_dimension_count", "authentication_state_owner_count"):
        if key in state_registry.get("metadata", {}):
            errors.append(f"state-owner-registry metadata duplicates derived fact: {key}")
    if state_registry.get("metadata", {}).get("current_facts_source") != "tools/current_facts.py#domain":
        errors.append("state-owner-registry current facts source drift")
    acceptance = _load_json(authority_root / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json")
    metadata = acceptance.get("metadata", {})
    for key in ("acceptance_count", "specified_count", "passed_count", "evidence_gap_count", "current_contract_catalog"):
        if key in metadata:
            errors.append(f"acceptance metadata duplicates derived fact: {key}")
    for scope_name, scope in acceptance.items():
        if not isinstance(scope_name, str) or not scope_name.endswith("_governance") or not isinstance(scope, dict):
            continue
        for key in ("reused_items", "revised_items", "new_items", "acceptance_count", "scope_count"):
            if key in scope:
                errors.append(f"{scope_name} duplicates derived acceptance scope count: {key}")
    allowed_aliases = set(facts["contracts"])
    for item in acceptance.get("acceptance_closure", []):
        for ref in item.get("contract_ids", []):
            if isinstance(ref, str) and ref.startswith("ADR-"):
                continue
            if ref not in allowed_aliases:
                errors.append(f"{item.get('acceptance_id')}: current contract ref is not a stable alias: {ref}")
                if len(errors) > 100:
                    return errors

    core = _load_yaml(authority_root / "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml")
    closure = core.get("r3_state_closure", {})
    if closure.get("validated_dimensions") != facts["domain"]["state_dimension_count"]:
        errors.append("core r3_state_closure validated_dimensions drift")
    if closure.get("lifecycle_objects") != facts["domain"]["object_count"]:
        errors.append("core r3_state_closure lifecycle_objects drift")
    if closure.get("current_facts_source") != "tools/current_facts.py#domain":
        errors.append("core r3_state_closure current facts source drift")
    coding = core.get("coding_readiness_summary", {})
    if "database_runtime_gate" in coding:
        errors.append("core coding_readiness_summary must not duplicate Runtime Gate status")

    tech = _load_yaml(authority_root / "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml")
    scan_stats = tech.get("metadata", {}).get("source_scan_statistics", {})
    if "formal_object_count" in scan_stats or "pending_external_decision_count" in scan_stats:
        errors.append("technology authority must not duplicate current object/open-decision counts")
    if scan_stats.get("formal_object_count_source") != "tools/current_facts.py#domain.object_count":
        errors.append("technology authority object count source drift")
    if scan_stats.get("open_decision_count_source") != "tools/current_facts.py#governance.open_decision_count":
        errors.append("technology authority open decision count source drift")
    open_question_members = (
        "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml",
        "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
        "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
        "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
        "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
    )
    for rel in open_question_members:
        payload = _load_yaml(authority_root / rel)
        if payload.get("open_questions") not in (None, []):
            errors.append(f"{rel} contains closed decisions as active open_questions")
    if facts["governance"]["open_decision_count"] != 0:
        errors.append(f"current open decision count must be 0, got {facts['governance']['open_decision_count']}")

    return errors

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["show", "field", "check"])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--name")
    args = parser.parse_args()
    facts = derive_current_facts(args.root)
    if args.command == "check":
        errors = check_current_fact_governance(args.root)
        if errors:
            print("CURRENT_FACT_GOVERNANCE_DRIFT")
            for error in errors:
                print(error)
            return 1
        print("CURRENT_FACTS_CONSISTENT")
        return 0
    if args.command == "show":
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return 0
    if not args.name:
        raise SystemExit("--name is required for field")
    value: Any = facts
    for part in args.name.split("."):
        if not isinstance(value, dict) or part not in value:
            raise SystemExit(f"unknown current fact: {args.name}")
        value = value[part]
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False))
    else:
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
