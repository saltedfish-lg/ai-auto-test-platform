#!/usr/bin/env python3
"""Verify the single living authority tree without versioned baselines, release manifests, or Git."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "docs" / "authority"
AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
ACTIVE_DOCUMENT_STATUS = "ACTIVE_CONTROLLED_MUTABLE_AUTHORITY"
AUTH_CONTRACT = "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml"
AUTH_IMPLEMENTATION_STATUS = "IMPLEMENTED_PENDING_RUNTIME_VALIDATION"
DEFERRED_PRODUCT_DECISIONS = {
    "GOV-P1-002": "TEMPORARY_CREDENTIAL_DELIVERY_AND_WRITE_SEMANTICS",
    "GOV-P1-003": "LOGIN_REFRESH_SOURCE_RATE_LIMIT_POLICY",
    "GOV-P1-005": "CHANGE_PASSWORD_LOST_RESPONSE_IDEMPOTENT_REPLAY",
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
REQUIRED = CORE_DOCUMENTS + [
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
    """Validate P1 Auth implementation state and deferred product-decision placeholders."""
    path = authority / AUTH_CONTRACT
    if not path.is_file():
        return [f"missing authority member: {AUTH_CONTRACT}"]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("root YAML value must be a mapping")
    except Exception as exc:  # pragma: no cover - defensive path
        return [f"{AUTH_CONTRACT}: cannot parse: {exc}"]

    errors: list[str] = []
    metadata = payload.get("metadata", {})
    if metadata.get("implementation_status") != AUTH_IMPLEMENTATION_STATUS:
        errors.append(
            f"{AUTH_CONTRACT}: implementation_status={metadata.get('implementation_status')}"
        )
    if metadata.get("deferred_product_decisions") != len(DEFERRED_PRODUCT_DECISIONS):
        errors.append(
            f"{AUTH_CONTRACT}: deferred_product_decisions={metadata.get('deferred_product_decisions')}"
        )

    placeholders = payload.get("product_decision_placeholders", [])
    index = {
        item.get("decision_id"): item
        for item in placeholders
        if isinstance(item, dict) and item.get("decision_id")
    }
    if set(index) != set(DEFERRED_PRODUCT_DECISIONS):
        errors.append(f"{AUTH_CONTRACT}: deferred decision ids={sorted(index)}")
    for decision_id, expected_name in DEFERRED_PRODUCT_DECISIONS.items():
        item = index.get(decision_id, {})
        if item.get("name") != expected_name:
            errors.append(f"{AUTH_CONTRACT}: {decision_id} name={item.get('name')}")
        if item.get("status") != "BLOCKED_BY_PRODUCT_DECISION":
            errors.append(f"{AUTH_CONTRACT}: {decision_id} status={item.get('status')}")
        if item.get("decision_owner") != "USER_PRODUCT_SOVEREIGNTY":
            errors.append(f"{AUTH_CONTRACT}: {decision_id} decision_owner={item.get('decision_owner')}")
        if item.get("blocks_current_approved_scope") is not False:
            errors.append(
                f"{AUTH_CONTRACT}: {decision_id} blocks_current_approved_scope={item.get('blocks_current_approved_scope')}"
            )
        for key in ("current_fact", "issue", "blocked_scope", "implementation_rule"):
            if not str(item.get(key, "")).strip():
                errors.append(f"{AUTH_CONTRACT}: {decision_id} missing {key}")
        missing_facts = item.get("missing_facts")
        if not isinstance(missing_facts, list) or not missing_facts:
            errors.append(f"{AUTH_CONTRACT}: {decision_id} missing_facts is empty")
    return errors


def find_agent_rules_errors(authority: Path) -> list[str]:
    errors: list[str] = []
    path = authority / AGENT_RULES
    if not path.is_file():
        return [f"missing authority member: {AGENT_RULES}"]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
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
                errors.append(f"forbidden baseline manifest artifact: {path.relative_to(AUTHORITY).as_posix()}")
        if (AUTHORITY / "编码权威事实/RELEASE").exists():
            errors.append("forbidden copied release snapshot directory: 编码权威事实/RELEASE")
        errors.extend(find_legacy_active_semantics(AUTHORITY))
        errors.extend(find_core_metadata_errors(AUTHORITY))
        errors.extend(find_agent_rules_errors(AUTHORITY))
        errors.extend(find_auth_contract_state_errors(AUTHORITY))

    report = {
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
        "git_access": "DISABLED",
        "authority_files": sum(1 for path in AUTHORITY.rglob("*") if path.is_file()) if AUTHORITY.exists() else 0,
        "core_document_status": ACTIVE_DOCUMENT_STATUS,
        "auth_implementation_status": AUTH_IMPLEMENTATION_STATUS,
        "deferred_product_decisions": len(DEFERRED_PRODUCT_DECISIONS),
        "legacy_active_semantic_hits": len(find_legacy_active_semantics(AUTHORITY)) if AUTHORITY.exists() else 0,
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
