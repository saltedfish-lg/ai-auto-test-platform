#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import yaml

AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
AUTHORITY_REL = "docs/authority"
EXPECTED_CODE_READINESS = "READY_FOR_P1_IMPLEMENTATION"
CORE = [
    "产品总体需求与系统边界/产品总体需求与系统边界.yaml",
    "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
    "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml",
    "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
    "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
    "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
    "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml",
]
FORBIDDEN_AUTHORITY_ARTIFACTS = {
    "MANIFEST.sha256",
    "baseline-index.yaml",
    "BASELINE_INDEX.md",
}
ACTIVE_DOCUMENT_STATUS = "ACTIVE_CONTROLLED_MUTABLE_AUTHORITY"
AGENT_RULES_REL = "系统技术架构技术选型与AGENTS/agents-rules.yaml"
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    repo_root = root.parents[1]

    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    metrics: dict[str, Any] = {}

    def add(name: str, passed: bool, detail: str, items: list[str] | None = None) -> None:
        issue_items = items or []
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail, "errors": issue_items})
        if not passed:
            errors.extend(f"{name}: {x}" for x in issue_items or [detail])

    add("GOV-AUTHORITY-ROOT", root.name == "authority", f"root={root}")

    missing = [rel for rel in CORE if not (root / rel).is_file()]
    add("GOV-CORE-AUTHORITY-PRESENT", not missing, f"core={len(CORE)-len(missing)}/{len(CORE)}", missing)

    parse_errors: list[str] = []
    docs: dict[str, dict[str, Any]] = {}
    for rel in CORE:
        path = root / rel
        if not path.is_file():
            continue
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("root YAML value must be a mapping")
            docs[rel] = value
        except Exception as exc:  # pragma: no cover - defensive validation path
            parse_errors.append(f"{rel}: {exc}")
    add("GOV-CORE-YAML-PARSE", not parse_errors, f"parsed={len(docs)}/{len(CORE)}", parse_errors)

    metadata_errors: list[str] = []
    for rel, doc in docs.items():
        metadata = doc.get("metadata", {})
        if metadata.get("authority_model") != AUTHORITY_MODEL:
            metadata_errors.append(f"{rel}: authority_model={metadata.get('authority_model')}")
        if metadata.get("document_status") != ACTIVE_DOCUMENT_STATUS:
            metadata_errors.append(f"{rel}: document_status={metadata.get('document_status')}")
    add(
        "GOV-LIVING-AUTHORITY-METADATA",
        not metadata_errors,
        f"core documents use {ACTIVE_DOCUMENT_STATUS}",
        metadata_errors,
    )

    legacy_semantic_errors: list[str] = []
    for rel in (*CORE, AGENT_RULES_REL):
        path = root / rel
        if not path.is_file():
            continue
        text_value = path.read_text(encoding="utf-8")
        lowered = text_value.lower()
        for token in LEGACY_ACTIVE_TOKENS:
            if token.lower() in lowered:
                legacy_semantic_errors.append(f"{rel}: legacy active semantic token: {token}")
    add(
        "GOV-NO-ACTIVE-RELEASE-MANIFEST-REFERENCES",
        not legacy_semantic_errors,
        "current authority contains no active dependency on retired release manifests/versioned frozen baselines",
        legacy_semantic_errors,
    )

    agent_rules_errors: list[str] = []
    agent_rules_path = root / AGENT_RULES_REL
    if not agent_rules_path.is_file():
        agent_rules_errors.append(f"missing {AGENT_RULES_REL}")
    else:
        try:
            agent_rules = yaml.safe_load(agent_rules_path.read_text(encoding="utf-8"))
            rules = agent_rules.get("rules", {}) if isinstance(agent_rules, dict) else {}
            authority_model = agent_rules.get("authority_model", {}) if isinstance(agent_rules, dict) else {}
            if rules.get("technical_status") != "CURRENT_AUTHORITY":
                agent_rules_errors.append(f"technical_status={rules.get('technical_status')}")
            if authority_model.get("model_id") != "AUTHORITY-MODEL-LIVING-001":
                agent_rules_errors.append(f"model_id={authority_model.get('model_id')}")
            responsibilities = authority_model.get("responsibilities", [])
            authorities = {item.get("authority") for item in responsibilities if isinstance(item, dict)}
            if "LIVING_AUTHORITY_INTEGRITY" not in authorities:
                agent_rules_errors.append("LIVING_AUTHORITY_INTEGRITY responsibility missing")
            if "RELEASE_AND_MANIFEST" in authorities:
                agent_rules_errors.append("RELEASE_AND_MANIFEST must not be active authority")
        except Exception as exc:
            agent_rules_errors.append(str(exc))
    add(
        "GOV-AGENT-RULES-LIVING-AUTHORITY",
        not agent_rules_errors,
        "active agent rules model living authority integrity rather than release-manifest ownership",
        agent_rules_errors,
    )

    readiness_errors: list[str] = []
    for rel, doc in docs.items():
        metadata = doc.get("metadata", {})
        candidates = [metadata.get(k) for k in ("coding_readiness", "platform_code_readiness", "code_readiness") if k in metadata]
        if candidates and any(value != EXPECTED_CODE_READINESS for value in candidates):
            readiness_errors.append(f"{rel}: readiness={candidates}")
        if metadata.get("pending_user_decisions", 0) not in (0, None):
            readiness_errors.append(f"{rel}: pending_user_decisions={metadata.get('pending_user_decisions')}")
    add("GOV-CURRENT-AUTHORITY-READINESS", not readiness_errors, "current authority remains code-ready", readiness_errors)

    legacy_tree = repo_root / "docs/baseline"
    add("GOV-NO-VERSIONED-BASELINE-TREE", not legacy_tree.exists(), "docs/baseline must not exist", [str(legacy_tree)] if legacy_tree.exists() else [])

    forbidden_hits: list[str] = []
    for name in FORBIDDEN_AUTHORITY_ARTIFACTS:
        for path in root.rglob(name):
            forbidden_hits.append(path.relative_to(root).as_posix())
    release_dir = root / "编码权威事实/RELEASE"
    if release_dir.exists():
        forbidden_hits.append("编码权威事实/RELEASE")
    add("GOV-NO-BASELINE-MANIFEST-OR-RELEASE-SNAPSHOT", not forbidden_hits, "living authority has no copied-baseline manifest/release snapshot", sorted(set(forbidden_hits)))

    root_agents = repo_root / "AGENTS.md"
    agent_errors: list[str] = []
    if not root_agents.is_file():
        agent_errors.append("AGENTS.md missing")
    else:
        text = root_agents.read_text(encoding="utf-8")
        for token in [AUTHORITY_MODEL, AUTHORITY_REL, "MUST_NOT_INVOKE_GIT", "USER_OWNS_GIT", "NO_VERSIONED_BASELINE_COPIES"]:
            if token not in text:
                agent_errors.append(f"AGENTS.md missing {token}")
    add("GOV-RUNTIME-AUTHORITY-MODEL", not agent_errors, "root governance declares living authority and user-owned Git", agent_errors)

    context_policy = repo_root / ".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml"
    context_errors: list[str] = []
    try:
        policy = yaml.safe_load(context_policy.read_text(encoding="utf-8"))
        authority = policy.get("authority_model", {})
        if authority.get("mode") != AUTHORITY_MODEL:
            context_errors.append(f"authority_model.mode={authority.get('mode')}")
        if authority.get("root") != AUTHORITY_REL:
            context_errors.append(f"authority_model.root={authority.get('root')}")
        if authority.get("versioned_baseline_copies") != "forbidden":
            context_errors.append(f"versioned_baseline_copies={authority.get('versioned_baseline_copies')}")
        if authority.get("codex_git_access") != "DISABLED":
            context_errors.append(f"codex_git_access={authority.get('codex_git_access')}")
    except Exception as exc:
        context_errors.append(str(exc))
    add("GOV-CONTEXT-POLICY", not context_errors, "context policy uses living authority without Git", context_errors)

    product_skill = repo_root / ".agents/skills/ai-auto-test-platform-product-sovereignty/SKILL.md"
    product_errors: list[str] = []
    if product_skill.is_file():
        text = product_skill.read_text(encoding="utf-8")
        for token in [AUTHORITY_MODEL, AUTHORITY_REL, "AUTHORITY_UPDATE_ONLY", "MUST_NOT_INVOKE_GIT"]:
            if token not in text:
                product_errors.append(f"product-sovereignty missing {token}")
        if "不得创建 R4.3/R4.4/R5.x" not in text:
            product_errors.append("product-sovereignty must explicitly forbid future copied baselines")
    else:
        product_errors.append("product-sovereignty skill missing")
    add("GOV-PRODUCT-SOVEREIGNTY-LIVING-AUTHORITY", not product_errors, "confirmed product decisions update current authority directly", product_errors)

    acceptance_path = root / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json"
    acc_errors: list[str] = []
    acceptance_count = specified = passed_count = 0
    try:
        payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
        items = payload.get("acceptance_closure", [])
        acceptance_count = len(items)
        specified = sum(item.get("status") == "SPECIFIED" for item in items)
        passed_count = sum(item.get("status") == "PASSED" for item in items)
        if acceptance_count != 1691 or specified != 1691 or passed_count != 0:
            acc_errors.append(f"acceptance={acceptance_count}, specified={specified}, passed={passed_count}")
    except Exception as exc:
        acc_errors.append(str(exc))
    metrics.update({"acceptance": acceptance_count, "specified": specified, "passed": passed_count})
    add("GOV-ACCEPTANCE-HONEST-STATUS", not acc_errors, "acceptance stays SPECIFIED until real execution evidence exists", acc_errors)

    permission_path = root / "编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml"
    try:
        permission = yaml.safe_load(permission_path.read_text(encoding="utf-8"))
        metrics.update({
            "permissions": len(permission.get("permission_catalog", [])),
            "roles": len(permission.get("role_templates", [])),
            "mappings": len(permission.get("role_permission_mappings", [])),
        })
    except Exception:
        pass

    metrics["authority_files"] = sum(1 for p in root.rglob("*") if p.is_file())
    report = {
        "authority_model": AUTHORITY_MODEL,
        "authority_root": AUTHORITY_REL,
        "validator": "validate_governance.py",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS" if not errors else "FAIL",
        "metrics": metrics,
        "checks": checks,
        "error_count": len(errors),
        "errors": errors,
    }
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
