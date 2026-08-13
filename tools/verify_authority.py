#!/usr/bin/env python3
"""Verify the single living authority tree without copied baselines or Git."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import yaml  # type: ignore[import-untyped]

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

def _yaml_load(text: str):
    return yaml.load(text, Loader=YAML_LOADER)


def _is_mysql84_patch_version(value: object) -> bool:
    """MySQL policy locks the 8.4 LTS family, not one exact patch."""
    return isinstance(value, str) and re.match(r"^8\.4(?:\.|$)", value) is not None

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from current_facts import derive_current_facts

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "docs" / "authority"
AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
ACTIVE_DOCUMENT_STATUS = "ACTIVE_CONTROLLED_MUTABLE_AUTHORITY"
AUTH_CONTRACT = "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml"
SYSTEM_DESIGN = "编码权威事实/SYSTEM_DESIGN.yaml"
AUTH_IMPLEMENTATION_STATUSES = {
    "AUTHORITY_UPDATED_IMPLEMENTATION_PENDING",
    "IMPLEMENTED_PENDING_RUNTIME_VALIDATION",
    "IMPLEMENTED_RUNTIME_VALIDATED",
}
CONFIRMED_PRODUCT_DECISIONS = {
    "GOV-P1-002": "SYSTEM_GENERATED_ONE_TIME_TEMP_CREDENTIAL",
    "GOV-P1-003": "SOURCE_RATE_LIMIT_ENABLED_MYSQL84",
    "GOV-P1-005": "PASSWORD_CHANGE_REVOKES_REFRESH_SESSIONS_AND_REAUTHENTICATES",
}

CORE_DOCUMENTS = [
    "产品总体需求与系统边界/产品总体需求与系统边界.yaml",
    "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
    "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml",
    "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
    "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
    "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
    "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml",
]
AGENT_RULES = "系统技术架构技术选型与AGENTS/agents-rules.yaml"
REQUIRED = [
    *CORE_DOCUMENTS,
    AUTH_CONTRACT,
    "编码权威事实/SYSTEM_DESIGN.yaml",
    "编码权威事实/OPENAPI/openapi.yaml",
    "编码权威事实/DATABASE_DDL/database-schema.yaml",
    "编码权威事实/EVENT_CONTRACTS/event-registry.yaml",
    "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json",
]
FORBIDDEN_NAMES = {"MANIFEST.sha256", "baseline-index.yaml", "BASELINE_INDEX.md"}
LEGACY_ACTIVE_TOKENS = (
    "manifest_ref: MANIFEST.sha256",
    "current release manifest",
    "根级发布清单",
    "RELEASE_AND_MANIFEST",
    "FULL_BASELINE_CODEX_INPUT",
    "当前发布是正式冻结代码输入",
    "technical_status: FROZEN",
    "AUTHORITY-MODEL-R4.2-001",
    "Release只决定成员和版本",
    "预置角色默认模板仍待正式冻结",
    "FULL_CODE_READY: 仅在冻结设计发布中",
    "是当前正式代码输入基线",
    "保持R4冻结结论",
    "冻结契约实施",
    "CURRENT_FORMAL_CODE_INPUT_BASELINE",
    "R4.2 是当前",
    "R4.2作为当前",
    "Freeze Wins",
    "ROLE_SCENARIO_MENU_BASELINE_FULL_CODE_READY",
    "PERMISSION_CONCURRENCY_BASELINE_FULL_CODE_READY",
    "ACCEPTANCE_BASELINE_FULL_CODE_READY",
    "DOMAIN_BASELINE_READY",
    "DOMAIN_BASELINE_FULL_CODE_READY",
    "id_coverage_report: 基础文档发布清单.yaml",
    "current_governance_release:",
    "MANDATORY_IN_R3",
    "frozen_effect:",
    "code_baseline_readiness:",
    "baseline_readiness:",
    "CURRENT_BASELINE_FORMAL_FACTS",
    "current_package_has_frozen_design_release",
    "FORMAL_CODE_INPUT_BASELINE",
    "FROZEN_",
    "FROZEN SYSTEM_DESIGN",
    "R4.2",
    "scenario_name: 基线冻结和Codex准入",
    "business_goal: 以单一正式基线开展编码",
    "primary_output: FULL_CODE_READY编码输入",
    "READY_WITH_RUNTIME_DB_VALIDATION_PENDING",
)


def find_legacy_active_semantics(
    authority: Path,
    relative_paths: Iterable[str] | None = None,
) -> list[str]:
    """Return active current-authority references to the retired release/baseline model."""
    paths = tuple(relative_paths or (*CORE_DOCUMENTS, AGENT_RULES))
    errors: list[str] = []
    for rel in paths:
        path = authority / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in LEGACY_ACTIVE_TOKENS:
            if token.lower() in lowered:
                errors.append(f"{rel}: legacy active semantic token: {token}")
    return errors


def find_retired_active_model_errors(authority: Path) -> list[str]:
    """Reject reintroduction of the retired OBJ-085/runtime baseline-release model into current Authority."""
    tokens = ("OBJ-085", "平台设计基线发布", "platform_design_baseline_release", "PlatformDesignBaselineRelease")
    allowed = {
        "编码权威事实/DATABASE_DDL/V3__platform_contract_rebuild.sql",
        "编码权威事实/DATABASE_DDL/V8__retire_platform_design_baseline_release.sql",
        "编码权威事实/DATABASE_DDL/database-schema.yaml",
    }
    errors: list[str] = []
    for path in authority.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json", ".csv", ".md"}:
            continue
        rel = path.relative_to(authority).as_posix()
        if rel in allowed or rel.startswith("编码权威事实/HISTORICAL/") or rel.startswith("validation/") or "ADR" in Path(rel).parts:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if rel == "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json":
            payload = json.loads(text)
            payload.get("metadata", {}).pop("obj_085_retirement_provenance", None)
            text = json.dumps(payload, ensure_ascii=False)
        text = text.replace("V8__retire_platform_design_baseline_release.sql", "V8__RETIRED_GOVERNANCE_MODEL.sql")
        for token in tokens:
            if token in text:
                errors.append(f"{rel}: retired active governance token: {token}")
                break
    return errors


def find_core_metadata_errors(authority: Path) -> list[str]:
    """Validate top metadata without parsing the very large canonical YAML bodies."""
    errors: list[str] = []
    for rel in CORE_DOCUMENTS:
        path = authority / rel
        if not path.is_file():
            continue
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:40])
        authority_line = f"  authority_model: {AUTHORITY_MODEL}"
        status_line = f"  document_status: {ACTIVE_DOCUMENT_STATUS}"
        if authority_line not in head:
            errors.append(f"{rel}: missing top metadata {authority_line.strip()}")
        if status_line not in head:
            errors.append(f"{rel}: missing top metadata {status_line.strip()}")
    return errors


def find_auth_contract_state_errors(authority: Path) -> list[str]:
    """Validate P1 Auth implementation lifecycle and confirmed product decisions."""
    path = authority / AUTH_CONTRACT
    if not path.is_file():
        return [f"missing authority member: {AUTH_CONTRACT}"]
    try:
        payload = _yaml_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("root YAML value must be a mapping")
    except Exception as exc:  # pragma: no cover - defensive path
        return [f"{AUTH_CONTRACT}: cannot parse: {exc}"]

    errors: list[str] = []
    metadata = payload.get("metadata", {})
    expected_status_source = "SYSTEM_DESIGN.runtime_gate_contract.implementation_status"
    if metadata.get("implementation_status_source") != expected_status_source:
        errors.append(f"{AUTH_CONTRACT}: implementation_status_source={metadata.get('implementation_status_source')}")
    try:
        system_design = _yaml_load((authority / SYSTEM_DESIGN).read_text(encoding="utf-8"))
        implementation_status = system_design.get("runtime_gate_contract", {}).get("implementation_status")
    except Exception as exc:
        implementation_status = None
        errors.append(f"{SYSTEM_DESIGN}: cannot resolve implementation status: {exc}")
    if implementation_status not in AUTH_IMPLEMENTATION_STATUSES:
        errors.append(f"{SYSTEM_DESIGN}: implementation_status={implementation_status}")
    if metadata.get("deferred_product_decisions") != 0:
        deferred = metadata.get("deferred_product_decisions")
        errors.append(f"{AUTH_CONTRACT}: deferred_product_decisions={deferred}")

    placeholders = payload.get("product_decision_placeholders", [])
    if placeholders:
        errors.append(f"{AUTH_CONTRACT}: product_decision_placeholders must be empty")
    index = {
        item.get("decision_id"): item
        for item in payload.get("confirmed_product_decisions", [])
        if isinstance(item, dict) and item.get("decision_id")
    }
    if set(index) != set(CONFIRMED_PRODUCT_DECISIONS):
        errors.append(
            f"{AUTH_CONTRACT}: confirmed decision ids={sorted(str(key) for key in index)}"
        )
    for decision_id, selected_option in CONFIRMED_PRODUCT_DECISIONS.items():
        item = index.get(decision_id, {})
        if item.get("selected_option") != selected_option:
            errors.append(
                f"{AUTH_CONTRACT}: {decision_id} selected_option={item.get('selected_option')}"
            )
        if item.get("status") != "CONFIRMED_IN_LIVING_AUTHORITY":
            errors.append(f"{AUTH_CONTRACT}: {decision_id} status={item.get('status')}")
        if item.get("decision_source") != "CURRENT_USER_REQUEST":
            errors.append(
                f"{AUTH_CONTRACT}: {decision_id} decision_source={item.get('decision_source')}"
            )
    return errors


def find_database_gate_governance_errors(authority: Path) -> list[str]:
    """Validate the unique long-term database configuration and auth Gate owner."""
    path = authority / SYSTEM_DESIGN
    if not path.is_file():
        return [f"missing authority member: {SYSTEM_DESIGN}"]
    try:
        payload = _yaml_load(path.read_text(encoding="utf-8"))
        database_contract = payload["database_contract"]
        configuration = database_contract["connection_configuration"]
        evidence = database_contract["authentication_runtime_evidence"]
        runtime = payload["runtime_gate_contract"]
    except Exception as exc:  # pragma: no cover - defensive path
        return [f"{SYSTEM_DESIGN}: database Gate governance cannot parse: {exc}"]

    expected = {
        "application_database_url_env": "ATP_DATABASE_URL",
        "mysql_admin_url_env": "ATP_MYSQL_ADMIN_URL",
        "local_development_database": "ai_auto_test_platform_dev",
    }
    errors = [
        f"{SYSTEM_DESIGN}: {key}={configuration.get(key)}"
        for key, value in expected.items()
        if configuration.get(key) != value
    ]
    if database_contract.get("engine") != "MySQL 8.4 LTS":
        errors.append(f"{SYSTEM_DESIGN}: database engine must remain MySQL 8.4 LTS")
    if database_contract.get("patch_version_policy") != "ANY_8_4_X_WITH_CURRENT_FULL_SCHEMA_GATE_PASS":
        errors.append(f"{SYSTEM_DESIGN}: MySQL patch policy must govern the 8.4.x family instead of one fixed patch")
    architecture_path = authority / "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml"
    if architecture_path.is_file():
        architecture_text = architecture_path.read_text(encoding="utf-8")
        if "8.4.10" in architecture_text:
            errors.append("technology authority must not pin retired MySQL patch 8.4.10")
        if "patch_policy: 不锁定固定Patch" not in architecture_text:
            errors.append("technology authority must state the non-pinned MySQL 8.4.x patch policy")
    mysql_gate = evidence.get("mysql", {})
    browser_gate = evidence.get("browser", {})
    if mysql_gate.get("command") != "python tools/gates/auth_mysql_gate.py":
        errors.append(f"{SYSTEM_DESIGN}: auth MySQL Gate command mismatch")
    if mysql_gate.get("status_name") != "AUTH_MYSQL_RUNTIME_GATE":
        errors.append(f"{SYSTEM_DESIGN}: auth MySQL Gate status mismatch")
    if mysql_gate.get("isolated_database_prefix") != "ai_auto_test_platform_gate_auth_":
        errors.append(f"{SYSTEM_DESIGN}: auth MySQL Gate database prefix mismatch")
    if browser_gate.get("command") != "python tools/gates/auth_browser_gate.py":
        errors.append(f"{SYSTEM_DESIGN}: auth browser Gate command mismatch")
    if browser_gate.get("status_name") != "AUTH_BROWSER_RUNTIME_GATE":
        errors.append(f"{SYSTEM_DESIGN}: auth browser Gate status mismatch")
    if browser_gate.get("browser") != "REAL_CHROMIUM":
        errors.append(f"{SYSTEM_DESIGN}: auth browser Gate must use real Chromium")
    gate_index = {item.get("gate_id"): item for item in runtime.get("gates", []) if isinstance(item, dict)}
    if gate_index.get("AUTH_MYSQL_RUNTIME_GATE", {}).get("status") != "PASS_HISTORICAL_V3_TO_V7":
        errors.append(f"{SYSTEM_DESIGN}: auth MySQL historical evidence status drift")
    full_gate = gate_index.get("FULL_SCHEMA_MYSQL84_RUNTIME_GATE", {})
    if full_gate.get("evaluation_mode") != "MIGRATION_HEAD_FRESHNESS":
        errors.append(f"{SYSTEM_DESIGN}: full-schema evaluation mode drift")
    if "status_source" in full_gate or full_gate.get("status") not in {"PASS", "RERUN_REQUIRED"}:
        errors.append(f"{SYSTEM_DESIGN}: full-schema current status must be owned by SYSTEM_DESIGN")
    current_facts = derive_current_facts(ROOT)  # also validates dynamic non-status facts
    evidence = full_gate.get("last_execution_evidence") or {}
    if full_gate.get("status") == "PASS":
        if evidence.get("result") != "PASS" or not _is_mysql84_patch_version(evidence.get("mysql_version")):
            errors.append(f"{SYSTEM_DESIGN}: full-schema PASS evidence must record an actual MySQL 8.4.x PASS version")
        if evidence.get("validated_migration_head") != current_facts["migration"]["head"]:
            errors.append(f"{SYSTEM_DESIGN}: full-schema PASS evidence head drift")
        evidence_ref = evidence.get("evidence_ref")
        if not isinstance(evidence_ref, str) or not (authority / evidence_ref).is_file():
            errors.append(f"{SYSTEM_DESIGN}: full-schema PASS evidence_ref missing")
        else:
            try:
                payload_evidence = json.loads((authority / evidence_ref).read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{SYSTEM_DESIGN}: full-schema evidence cannot parse: {exc}")
            else:
                if payload_evidence.get("result") != "PASS" or not _is_mysql84_patch_version(payload_evidence.get("mysql_version")):
                    errors.append(f"{SYSTEM_DESIGN}: full-schema evidence result/version drift; expected actual MySQL 8.4.x")
                if payload_evidence.get("validated_migration_head") != current_facts["migration"]["head"]:
                    errors.append(f"{SYSTEM_DESIGN}: full-schema evidence migration head drift")
                if payload_evidence.get("admin_connection_source") != "ATP_MYSQL_ADMIN_URL":
                    errors.append(f"{SYSTEM_DESIGN}: full-schema evidence admin connection source drift")
                checks = payload_evidence.get("checks", {})
                for key in ("mysql_8_4_version", "empty_db_migration", "v4_seed_idempotency", "legacy_upgrade", "schema_assertions", "temporary_db_cleanup"):
                    if checks.get(key) != "PASS":
                        errors.append(f"{SYSTEM_DESIGN}: full-schema evidence {key}={checks.get(key)}")
    if any("current_status" in item for item in evidence.values() if isinstance(item, dict)):
        errors.append(f"{SYSTEM_DESIGN}: authentication_runtime_evidence must not duplicate current_status")
    return errors



def find_permission_closure_sync_errors(authority: Path) -> list[str]:
    """Keep the permission logic Authority semantically identical to formal Permission Closure."""
    permission_rel = "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml"
    closure_rel = "编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml"
    try:
        current = _yaml_load((authority / permission_rel).read_text(encoding="utf-8"))
        closure = _yaml_load((authority / closure_rel).read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"permission closure sync cannot parse: {exc}"]

    errors: list[str] = []
    permissions = current.get("permissions", [])
    roles = current.get("roles", [])
    mappings = current.get("role_permission_mappings", [])
    catalog = closure.get("permission_catalog", [])
    role_templates = closure.get("role_templates", [])
    formal_mappings = closure.get("role_permission_mappings", [])

    if (len(permissions), len(roles), len(mappings)) != (50, 12, 600):
        errors.append(
            f"{permission_rel}: RBAC counts={(len(permissions), len(roles), len(mappings))}, expected=(50, 12, 600)"
        )
    if len(catalog) != 50 or len(role_templates) != 12 or len(formal_mappings) != 600:
        errors.append(f"{closure_rel}: formal Permission Closure is not 50/12/600")

    current_catalog = {item.get("permission_id"): item for item in permissions if isinstance(item, dict)}
    formal_catalog = {item.get("permission_id"): item for item in catalog if isinstance(item, dict)}
    if current_catalog != formal_catalog:
        missing = sorted(set(formal_catalog) - set(current_catalog))
        extra = sorted(set(current_catalog) - set(formal_catalog))
        changed = sorted(
            key for key in set(current_catalog) & set(formal_catalog)
            if current_catalog[key] != formal_catalog[key]
        )
        errors.append(
            f"{permission_rel}: permission catalog drift missing={missing} extra={extra} changed={changed[:20]}"
        )

    # Role semantics are identical; closure-only approval provenance fields do not belong in the current logic projection.
    current_roles = {item.get("role_id"): item for item in roles if isinstance(item, dict)}
    normalized_formal_roles = {}
    for item in role_templates:
        if not isinstance(item, dict):
            continue
        normalized_formal_roles[item.get("role_id")] = {
            key: value for key, value in item.items()
            if key not in {"template_approval_status", "approval_source"}
        }
    if current_roles != normalized_formal_roles:
        errors.append(f"{permission_rel}: role template semantics drift from Permission Closure")

    def mapping_semantics(items):
        return {
            (item.get("role_id"), item.get("permission_id")): (
                item.get("permission_code"),
                item.get("decision"),
                item.get("data_scope"),
                item.get("conditions"),
            )
            for item in items
            if isinstance(item, dict)
        }

    if mapping_semantics(mappings) != mapping_semantics(formal_mappings):
        errors.append(f"{permission_rel}: role-permission decisions drift from Permission Closure")
    if any("release_id" in item for item in mappings if isinstance(item, dict)):
        errors.append(f"{permission_rel}: current mappings must not copy historical release_id metadata")
    return errors


def find_agent_rules_errors(authority: Path) -> list[str]:
    errors: list[str] = []
    path = authority / AGENT_RULES
    if not path.is_file():
        return [f"missing authority member: {AGENT_RULES}"]
    try:
        payload = _yaml_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("root YAML value must be a mapping")
    except Exception as exc:  # pragma: no cover - defensive path
        return [f"{AGENT_RULES}: cannot parse: {exc}"]

    rules = payload.get("rules", {})
    model = payload.get("authority_model", {})
    if rules.get("technical_status") != "CURRENT_AUTHORITY":
        errors.append(f"{AGENT_RULES}: technical_status={rules.get('technical_status')}")
    if model.get("model_id") != "AUTHORITY-MODEL-LIVING-001":
        errors.append(f"{AGENT_RULES}: model_id={model.get('model_id')}")
    responsibilities = model.get("responsibilities", [])
    authorities = {item.get("authority") for item in responsibilities if isinstance(item, dict)}
    if "LIVING_AUTHORITY_INTEGRITY" not in authorities:
        errors.append(f"{AGENT_RULES}: LIVING_AUTHORITY_INTEGRITY responsibility missing")
    if "RELEASE_AND_MANIFEST" in authorities:
        errors.append(f"{AGENT_RULES}: RELEASE_AND_MANIFEST must not be active authority")
    return errors


def main() -> int:
    errors: list[str] = []
    if not AUTHORITY.is_dir():
        errors.append("docs/authority is missing")
    if (ROOT / "docs" / "baseline").exists():
        errors.append("docs/baseline must not exist in SINGLE_LIVING_AUTHORITY mode")
    for rel in REQUIRED:
        if not (AUTHORITY / rel).is_file():
            errors.append(f"missing authority member: {rel}")

    if AUTHORITY.exists():
        for path in AUTHORITY.rglob("*"):
            if not path.is_file():
                continue
            if path.name in FORBIDDEN_NAMES:
                relative = path.relative_to(AUTHORITY).as_posix()
                errors.append(f"forbidden baseline manifest artifact: {relative}")
        if (AUTHORITY / "编码权威事实/RELEASE").exists():
            errors.append("forbidden copied release snapshot directory: 编码权威事实/RELEASE")
        legacy_semantic_errors = find_legacy_active_semantics(AUTHORITY)
        retired_model_errors = find_retired_active_model_errors(AUTHORITY)
        errors.extend(legacy_semantic_errors)
        errors.extend(retired_model_errors)
        errors.extend(find_core_metadata_errors(AUTHORITY))
        errors.extend(find_agent_rules_errors(AUTHORITY))
        errors.extend(find_auth_contract_state_errors(AUTHORITY))
        errors.extend(find_database_gate_governance_errors(AUTHORITY))
        errors.extend(find_permission_closure_sync_errors(AUTHORITY))

    report = {
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
        "git_access": "DISABLED",
        "authority_files": sum(1 for path in AUTHORITY.rglob("*") if path.is_file())
        if AUTHORITY.exists()
        else 0,
        "core_document_status": ACTIVE_DOCUMENT_STATUS,
        "auth_implementation_status": (
            _yaml_load((AUTHORITY / SYSTEM_DESIGN).read_text(encoding="utf-8")).get("runtime_gate_contract", {}).get("implementation_status")
            if (AUTHORITY / SYSTEM_DESIGN).is_file()
            else None
        ),
        "deferred_product_decisions": 0,
        "legacy_active_semantic_hits": len(find_legacy_active_semantics(AUTHORITY)) if AUTHORITY.exists() else 0,
        "retired_active_model_hits": len(find_retired_active_model_errors(AUTHORITY)) if AUTHORITY.exists() else 0,
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
