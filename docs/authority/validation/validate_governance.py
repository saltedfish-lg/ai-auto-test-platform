#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

def _yaml_load(text: str):
    return yaml.load(text, Loader=YAML_LOADER)

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
from current_facts import derive_current_facts, discover_migrations, expected_runtime_gate_status  # noqa: E402

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
    "是当前正式代码输入基线",
    "保持R4冻结结论",
    "冻结契约实施",
    "当前契约实施",
    "scenario_name: 基线冻结和Codex准入",
    "business_goal: 以单一正式基线开展编码",
    "primary_output: FULL_CODE_READY编码输入",
    "READY_WITH_RUNTIME_DB_VALIDATION_PENDING",
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
            value = _yaml_load(path.read_text(encoding="utf-8"))
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
            agent_rules = _yaml_load(agent_rules_path.read_text(encoding="utf-8"))
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
        for token in [AUTHORITY_MODEL, AUTHORITY_REL, "MUST_NOT_INVOKE_GIT", "USER_OWNS_GIT", "NO_VERSIONED_AUTHORITY_COPIES"]:
            if token not in text:
                agent_errors.append(f"AGENTS.md missing {token}")
    add("GOV-RUNTIME-AUTHORITY-MODEL", not agent_errors, "root governance declares living authority and user-owned Git", agent_errors)

    context_policy = repo_root / ".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml"
    context_errors: list[str] = []
    try:
        policy = _yaml_load(context_policy.read_text(encoding="utf-8"))
        authority = policy.get("authority_model", {})
        if authority.get("mode") != AUTHORITY_MODEL:
            context_errors.append(f"authority_model.mode={authority.get('mode')}")
        if authority.get("root") != AUTHORITY_REL:
            context_errors.append(f"authority_model.root={authority.get('root')}")
        if authority.get("versioned_authority_copies") != "forbidden":
            context_errors.append(f"versioned_authority_copies={authority.get('versioned_baseline_copies')}")
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

    # Volatile current facts are derived mechanically; governance files describe rules/sources, not current values.
    migration_errors: list[str] = []
    current_facts = derive_current_facts(repo_root)

    # A rule may only be decision-blocked when it names a genuinely unresolved current decision.
    rule_readiness_errors: list[str] = []
    core_rel = "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml"
    core_doc = docs.get(core_rel, {})
    current_decisions = core_doc.get("decisions", []) if isinstance(core_doc, dict) else []
    pending_decision_ids = {
        str(item.get("decision_id"))
        for item in current_decisions
        if isinstance(item, dict) and item.get("status") in {"PENDING_EXTERNAL_DECISION", "OPEN", "PENDING"}
    }
    if current_facts["governance"]["open_decision_count"] == 0 and pending_decision_ids:
        rule_readiness_errors.append(f"stale current pending decisions remain: {sorted(pending_decision_ids)}")
    for rule in core_doc.get("business_rules", []) if isinstance(core_doc, dict) else []:
        if not isinstance(rule, dict):
            continue
        blocked = rule.get("test_readiness") == "BLOCKED_BY_MISSING_DECISION" or rule.get("coding_status") == "BLOCKED_BY_MISSING_DECISION"
        unresolved = {str(item) for item in rule.get("unresolved_decision_ids", [])}
        if blocked and (not unresolved or not unresolved <= pending_decision_ids):
            rule_readiness_errors.append(f"{rule.get('rule_id')}: stale BLOCKED_BY_MISSING_DECISION unresolved={sorted(unresolved)}")
    conclusion_statement = str((core_doc.get("conclusion") or {}).get("statement") or "") if isinstance(core_doc, dict) else ""
    if re.search(r"\d+项[^。；]*(?:开放|未决)[^。；]*决策", conclusion_statement) or "仍有12项" in conclusion_statement:
        rule_readiness_errors.append(f"stale open-decision conclusion: {conclusion_statement}")
    add(
        "GOV-RULE-DECISION-READINESS-CONSISTENCY",
        not rule_readiness_errors,
        "business-rule decision blocking is backed only by genuinely open current decisions",
        rule_readiness_errors,
    )

    # Current core Authority files must not retain generator-era source counts or release-generator hashes.
    legacy_generator_errors: list[str] = []
    legacy_format_keys = {"generator", "generator_version", "upstream_release_id", "upstream_hash", "output_hash", "version", "release_id"}
    for rel, doc in docs.items():
        statistics = doc.get("statistics", {}) if isinstance(doc, dict) else {}
        if isinstance(statistics, dict) and "source_file_count" in statistics:
            legacy_generator_errors.append(f"{rel}: statistics.source_file_count must not be a current Authority fact")
        if isinstance(statistics, dict) and "source_file_count_scope" in statistics:
            legacy_generator_errors.append(f"{rel}: statistics.source_file_count_scope is obsolete generator-era metadata")
        format_governance = doc.get("format_governance", {}) if isinstance(doc, dict) else {}
        if isinstance(format_governance, dict):
            stale = sorted(legacy_format_keys.intersection(format_governance))
            if stale:
                legacy_generator_errors.append(f"{rel}: stale generator-era format_governance keys={stale}")
    add(
        "GOV-NO-LEGACY-GENERATOR-METADATA",
        not legacy_generator_errors,
        "current core Authority contains no obsolete consistency-repair generator/source-count metadata",
        legacy_generator_errors,
    )
    try:
        migrations = discover_migrations(root)
        if [item["name"] for item in migrations] != current_facts["migration"]["files"]:
            migration_errors.append("migration discovery is not deterministic")
        versions = [item["version"] for item in migrations]
        if versions != sorted(set(versions)):
            migration_errors.append(f"migration versions are not unique ascending: {versions}")
        database_schema = _yaml_load((root / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8"))
        for forbidden in ("migration_files", "object_table_count", "technical_table_count", "foreign_key_count"):
            if forbidden in database_schema:
                migration_errors.append(f"database-schema duplicates derived current fact {forbidden}")
        execution = database_schema.get("migration_execution", {})
        for forbidden in ("authority_chain", "current_chain"):
            if forbidden in execution:
                migration_errors.append(f"database-schema migration_execution duplicates current head/chain via {forbidden}")
        if execution.get("migration_discovery_source") != "tools/current_facts.py#discover_migrations":
            migration_errors.append("database-schema must delegate migration discovery to tools/current_facts.py")
        classification = database_schema.get("table_classification", {}).get("technical_table_names", [])
        if len(classification) != current_facts["database"]["technical_table_count"]:
            migration_errors.append("technical table classification differs from derived facts")
    except Exception as exc:
        migration_errors.append(f"database-schema/current facts: {exc}")
    try:
        system_design = _yaml_load((root / "编码权威事实/SYSTEM_DESIGN.yaml").read_text(encoding="utf-8"))
        if system_design.get("repository_topology", {}).get("migrations") != "docs/authority/编码权威事实/DATABASE_DDL":
            migration_errors.append("SYSTEM_DESIGN migration path drift")
        db_contract = system_design.get("database_contract", {})
        if db_contract.get("engine") != "MySQL 8.4 LTS":
            migration_errors.append("SYSTEM_DESIGN database engine must remain MySQL 8.4 LTS")
        if db_contract.get("patch_version_policy") != "ANY_8_4_X_WITH_CURRENT_FULL_SCHEMA_GATE_PASS":
            migration_errors.append("SYSTEM_DESIGN MySQL patch policy must govern 8.4.x, not one exact patch")
        technology_text = (root / "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml").read_text(encoding="utf-8")
        if "8.4.10" in technology_text:
            migration_errors.append("technology authority still pins retired MySQL patch 8.4.10")
        if "patch_policy: 不锁定固定Patch" not in technology_text:
            migration_errors.append("technology authority missing non-pinned MySQL 8.4.x patch policy")
        for forbidden in ("migration_release", "table_count", "object_table_count", "technical_table_count"):
            if forbidden in db_contract:
                migration_errors.append(f"SYSTEM_DESIGN duplicates derived current fact {forbidden}")
        if db_contract.get("current_facts_source") != "tools/current_facts.py#database":
            migration_errors.append("SYSTEM_DESIGN database facts source drift")
        runtime = system_design.get("runtime_gate_contract", {})
        gate_index = {item.get("gate_id"): item for item in runtime.get("gates", []) if isinstance(item, dict)}
        full_gate = gate_index.get("FULL_SCHEMA_MYSQL84_RUNTIME_GATE", {})
        if full_gate.get("evaluation_mode") != "MIGRATION_HEAD_FRESHNESS":
            migration_errors.append("full-schema runtime evaluation mode drift")
        if "status_source" in full_gate or full_gate.get("status") not in {"PASS", "RERUN_REQUIRED"}:
            migration_errors.append("full-schema current runtime status must be owned by SYSTEM_DESIGN")
        if full_gate.get("status") != expected_runtime_gate_status(full_gate, current_facts["migration"]["head"]):
            migration_errors.append("full-schema SYSTEM_DESIGN status is stale against migration-head evidence")
        evidence = full_gate.get("last_execution_evidence") or {}
        evidence_ref = evidence.get("evidence_ref")
        if full_gate.get("status") == "PASS":
            if evidence.get("result") != "PASS" or not (isinstance(evidence.get("mysql_version"), str) and re.match(r"^8\.4(?:\.|$)", evidence.get("mysql_version"))):
                migration_errors.append("full-schema PASS must be backed by an actual MySQL 8.4.x PASS evidence version")
            if evidence.get("validated_migration_head") != current_facts["migration"]["head"]:
                migration_errors.append("full-schema PASS evidence migration head drift")
            if not isinstance(evidence_ref, str):
                migration_errors.append("full-schema PASS evidence_ref missing")
            else:
                evidence_path = root / evidence_ref
                if not evidence_path.is_file():
                    migration_errors.append(f"full-schema evidence file missing: {evidence_ref}")
                else:
                    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
                    expected_checks = ("mysql_8_4_version", "empty_db_migration", "v4_seed_idempotency", "legacy_upgrade", "schema_assertions", "temporary_db_cleanup")
                    if evidence_payload.get("evidence_schema_version") != 1 or evidence_payload.get("gate_id") != "FULL_SCHEMA_MYSQL84_RUNTIME_GATE":
                        migration_errors.append("full-schema structured evidence schema/gate drift")
                    if evidence_payload.get("result") != "PASS" or not (isinstance(evidence_payload.get("mysql_version"), str) and re.match(r"^8\.4(?:\.|$)", evidence_payload.get("mysql_version"))):
                        migration_errors.append("full-schema structured evidence result/version drift; expected actual MySQL 8.4.x")
                    if evidence_payload.get("validated_migration_head") != current_facts["migration"]["head"] or evidence_payload.get("validated_migration_chain") != current_facts["migration"]["chain"]:
                        migration_errors.append("full-schema structured evidence migration facts drift")
                    if evidence_payload.get("admin_connection_source") != "ATP_MYSQL_ADMIN_URL":
                        migration_errors.append("full-schema structured evidence admin source drift")
                    evidence_checks = evidence_payload.get("checks", {})
                    if any(evidence_checks.get(key) != "PASS" for key in expected_checks):
                        migration_errors.append("full-schema structured evidence required checks are not all PASS")
                    if evidence_payload.get("secrets_in_evidence") is not False:
                        migration_errors.append("full-schema structured evidence secret policy drift")
    except Exception as exc:
        migration_errors.append(f"SYSTEM_DESIGN: {exc}")
    try:
        gate_script = (root / "validation/run_mysql84_gate.py").read_text(encoding="utf-8")
        compose = (root / "validation/mysql84-compose.yml").read_text(encoding="utf-8")
        for token in ("discover_migrations", "derive_current_facts", "validated_migration_head", 'ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"', "evidence_schema_version", "temporary_db_cleanup"):
            if token not in gate_script:
                migration_errors.append(f"run_mysql84_gate missing governed capability: {token}")
        for forbidden_env in ("ATP_MYSQL_HOST", "ATP_MYSQL_PORT", "ATP_MYSQL_USER", "ATP_MYSQL_PASSWORD"):
            if forbidden_env in gate_script:
                migration_errors.append(f"run_mysql84_gate must not use legacy split MySQL admin env: {forbidden_env}")
        formal_gate = (repo_root / "tools/mysql84_gate.py").read_text(encoding="utf-8")
        if "--evidence-output" not in formal_gate or "evidence_schema_version" not in formal_gate:
            migration_errors.append("formal MySQL gate entrypoint must expose structured evidence output")
        if "/ddl/V[0-9]*__*.sql" not in compose or "sort -n" not in compose:
            migration_errors.append("mysql84-compose must dynamically enumerate numeric migration versions")
        current_head_name = current_facts["migration"]["head_name"]
        for rel in ("AGENTS.md", ".agents/skills/ai-auto-test-platform-database/SKILL.md", ".agents/agent-roles/database-integrity-reviewer.md"):
            text = (repo_root / rel).read_text(encoding="utf-8")
            if current_head_name in text or current_facts["migration"]["chain"] in text:
                migration_errors.append(f"{rel} hard-codes the current migration head/chain")
            if "current_facts.py" not in text:
                migration_errors.append(f"{rel} must reference mechanical current-fact discovery")
    except Exception as exc:
        migration_errors.append(f"dynamic migration gate/guidance: {exc}")
    try:
        validation_policy = (repo_root / "tools/authority_validation.py").read_text(encoding="utf-8")
        for token in ("ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS", "DEFAULT_VALIDATOR_TIMEOUT_SECONDS = 600", "MAX_VALIDATOR_TIMEOUT_SECONDS = 3600"):
            if token not in validation_policy:
                migration_errors.append(f"authority validator timeout policy missing {token}")
    except Exception as exc:
        migration_errors.append(f"authority validator timeout policy: {exc}")
    add(
        "GOV-DYNAMIC-CURRENT-FACTS",
        not migration_errors,
        f"migration_head=V{current_facts['migration']['head']}; tables={current_facts['database']['table_count']}; fks={current_facts['database']['foreign_key_count']}; values are derived rather than copied",
        migration_errors,
    )

    agent_wording_errors: list[str] = []
    for agent_root in (repo_root / ".agents", repo_root / ".codex" / "agents"):
        if not agent_root.exists():
            continue
        for path in agent_root.rglob("*"):
            if not path.is_file() or path.name == "MANIFEST.sha256" or path.suffix.lower() not in {".md", ".yaml", ".yml", ".toml", ".py"}:
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            for token in ("FROZEN", "frozen", "冻结", "baseline", "Baseline", "基线"):
                if token in source:
                    agent_wording_errors.append(f"{path.relative_to(repo_root).as_posix()} contains active legacy Agent wording: {token}")
                    break
    add(
        "GOV-AGENT-NO-ACTIVE-BASELINE-FROZEN",
        not agent_wording_errors,
        "Agent/Skill current instructions use living-authority/evidence terminology rather than release-baseline/frozen semantics",
        agent_wording_errors,
    )

    acceptance_path = root / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json"
    acc_errors: list[str] = []
    acceptance_count = specified = passed_count = failed_count = blocked_count = 0
    try:
        payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {})
        items = payload.get("acceptance_closure", [])
        acceptance_count = len(items)
        specified = sum(item.get("status") == "SPECIFIED" for item in items)
        passed_count = sum(item.get("status") == "PASSED" for item in items)
        failed_count = sum(item.get("status") == "FAILED" for item in items)
        blocked_count = sum(item.get("status") == "BLOCKED_BY_ENVIRONMENT" for item in items)
        allowed_statuses = {"SPECIFIED", "PASSED", "FAILED", "BLOCKED_BY_ENVIRONMENT"}
        allowed_evidence = {"EXPECTED_NOT_EXECUTED", "NOT_STARTED", "VERIFIED", "FAILED", "BLOCKED_BY_ENVIRONMENT"}
        forbidden_metadata = {"acceptance_count", "specified_count", "passed_count", "evidence_gap_count", "current_contract_catalog"}
        leaked = sorted(forbidden_metadata.intersection(metadata))
        if leaked:
            acc_errors.append(f"acceptance metadata duplicates derived facts: {leaked}")
        if metadata.get("current_facts_source") != "tools/current_facts.py":
            acc_errors.append("acceptance current_facts_source missing")
        semantics = metadata.get("contract_reference_semantics", {})
        if semantics.get("contract_ids") != "CURRENT_LIVING_AUTHORITY_ALIASES_RESOLVED_BY_TOOLS_CURRENT_FACTS" or semantics.get("source_contract_ids_at_definition") != "HISTORICAL_TRACEABILITY_ONLY":
            acc_errors.append("acceptance contract alias semantics missing")
        allowed_aliases = set(current_facts["contracts"])
        for item in items:
            current_refs = item.get("contract_ids")
            source_refs = item.get("source_contract_ids_at_definition")
            if not isinstance(current_refs, list) or not current_refs:
                acc_errors.append(f"{item.get('acceptance_id')} current contract_ids missing")
                continue
            if not isinstance(source_refs, list) or not source_refs:
                acc_errors.append(f"{item.get('acceptance_id')} historical source_contract_ids_at_definition missing")
            for ref in current_refs:
                if ref not in allowed_aliases and not (isinstance(ref, str) and ref.startswith("ADR-")):
                    acc_errors.append(f"{item.get('acceptance_id')} non-current contract alias {ref}")
                if isinstance(ref, str) and re.search(r"-\d+\.\d+", ref):
                    acc_errors.append(f"{item.get('acceptance_id')} versioned current contract ref {ref}")
        derived = current_facts["acceptance"]
        evidence_gap_count = sum(item.get("evidence_status") != "VERIFIED" for item in items)
        if acceptance_count != derived["count"] or specified != derived["specified_count"] or passed_count != derived["passed_count"] or evidence_gap_count != derived["evidence_gap_count"]:
            acc_errors.append("acceptance counts differ from mechanically derived facts")
        if any(item.get("status") not in allowed_statuses for item in items):
            acc_errors.append("invalid acceptance status")
        if any(item.get("evidence_status") not in allowed_evidence for item in items):
            acc_errors.append("invalid evidence status")
        if any((item.get("status") == "PASSED") != (item.get("evidence_status") == "VERIFIED") for item in items):
            acc_errors.append("PASSED and VERIFIED evidence are not coherent")
    except Exception as exc:
        acc_errors.append(str(exc))
    metrics.update({"acceptance": acceptance_count, "specified": specified, "passed": passed_count, "failed": failed_count, "blocked": blocked_count})
    add("GOV-ACCEPTANCE-HONEST-STATUS", not acc_errors, "acceptance current refs are stable aliases and counts are derived from items", acc_errors)

    permission_path = root / "编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml"
    permission_sync_errors: list[str] = []
    try:
        permission = _yaml_load(permission_path.read_text(encoding="utf-8"))
        metrics.update({
            "permissions": len(permission.get("permission_catalog", [])),
            "roles": len(permission.get("role_templates", [])),
            "mappings": len(permission.get("role_permission_mappings", [])),
        })
        permission_authority = docs.get("权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml", {})
        current_permissions = permission_authority.get("permissions", [])
        current_roles = permission_authority.get("roles", [])
        current_mappings = permission_authority.get("role_permission_mappings", [])
        if (len(current_permissions), len(current_roles), len(current_mappings)) != (50, 12, 600):
            permission_sync_errors.append(
                f"permission Authority counts={(len(current_permissions), len(current_roles), len(current_mappings))}, expected=(50, 12, 600)"
            )
        if (len(permission.get("permission_catalog", [])), len(permission.get("role_templates", [])), len(permission.get("role_permission_mappings", []))) != (50, 12, 600):
            permission_sync_errors.append("formal Permission Closure must remain 50/12/600")
        current_catalog = {item.get("permission_id"): item for item in current_permissions if isinstance(item, dict)}
        formal_catalog = {item.get("permission_id"): item for item in permission.get("permission_catalog", []) if isinstance(item, dict)}
        if current_catalog != formal_catalog:
            permission_sync_errors.append("permission catalog semantics drift from formal Permission Closure")
        current_role_map = {item.get("role_id"): item for item in current_roles if isinstance(item, dict)}
        formal_role_map = {
            item.get("role_id"): {
                key: value for key, value in item.items()
                if key not in {"template_approval_status", "approval_source"}
            }
            for item in permission.get("role_templates", [])
            if isinstance(item, dict)
        }
        if current_role_map != formal_role_map:
            permission_sync_errors.append("role template semantics drift from formal Permission Closure")
        def mapping_semantics(items: list[dict[str, Any]]) -> dict[tuple[Any, Any], tuple[Any, Any, Any, Any]]:
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
        if mapping_semantics(current_mappings) != mapping_semantics(permission.get("role_permission_mappings", [])):
            permission_sync_errors.append("role-permission decision semantics drift from formal Permission Closure")
        if any("release_id" in item for item in current_mappings if isinstance(item, dict)):
            permission_sync_errors.append("current permission Authority mappings must not copy historical release_id metadata")
    except Exception as exc:
        permission_sync_errors.append(str(exc))
    add("GOV-PERMISSION-CLOSURE-SYNC", not permission_sync_errors, "permission Authority is 50/12/600 and semantically aligned with formal Permission Closure", permission_sync_errors)

    metrics["authority_files"] = sum(1 for p in root.rglob("*") if p.is_file())
    retired_model_errors: list[str] = []
    retired_tokens = ("OBJ-085", "平台设计基线发布", "platform_design_baseline_release", "PlatformDesignBaselineRelease")
    historical_allow = {
        "编码权威事实/DATABASE_DDL/V3__platform_contract_rebuild.sql",
        "编码权威事实/DATABASE_DDL/V8__retire_platform_design_baseline_release.sql",
        "编码权威事实/DATABASE_DDL/database-schema.yaml",
    }
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json", ".csv", ".md"}:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in historical_allow or rel.startswith("编码权威事实/HISTORICAL/") or rel.startswith("validation/") or "ADR" in Path(rel).parts:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if rel == "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json":
            payload = json.loads(text)
            payload.get("metadata", {}).pop("obj_085_retirement_provenance", None)
            text = json.dumps(payload, ensure_ascii=False)
        text = text.replace("V8__retire_platform_design_baseline_release.sql", "V8__RETIRED_GOVERNANCE_MODEL.sql")
        for token in retired_tokens:
            if token in text:
                retired_model_errors.append(f"{rel}: retired active governance token {token}")
                break
    try:
        schema = _yaml_load((root / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8"))
        for table in schema.get("tables", []):
            if table.get("object_id") == "OBJ-085" or table.get("table_name") == "atp_platform_design_baseline_release":
                retired_model_errors.append("database-schema current tables reintroduced retired OBJ-085/runtime table")
    except Exception as exc:
        retired_model_errors.append(f"database-schema retirement check failed: {exc}")
    add(
        "GOV-RETIRED-PLATFORM-DESIGN-BASELINE-MODEL",
        not retired_model_errors,
        "OBJ-085/platform-design-baseline-release exists only in immutable historical V3 and explicit V8 retirement evidence",
        retired_model_errors[:100],
    )

    runtime_errors: list[str] = []
    try:
        sd = _yaml_load((root / "编码权威事实/SYSTEM_DESIGN.yaml").read_text(encoding="utf-8"))
        runtime = sd.get("runtime_gate_contract", {})
        gates = {g.get("gate_id"): g for g in runtime.get("gates", []) if isinstance(g, dict)}
        if runtime.get("implementation_status") != "IMPLEMENTED_RUNTIME_VALIDATED":
            runtime_errors.append(f"implementation_status={runtime.get('implementation_status')}")
        full_gate = gates.get("FULL_SCHEMA_MYSQL84_RUNTIME_GATE", {})
        if full_gate.get("evaluation_mode") != "MIGRATION_HEAD_FRESHNESS":
            runtime_errors.append("FULL_SCHEMA_MYSQL84_RUNTIME_GATE evaluation mode drift")
        if "status_source" in full_gate or full_gate.get("status") not in {"PASS", "RERUN_REQUIRED"}:
            runtime_errors.append("FULL_SCHEMA_MYSQL84_RUNTIME_GATE current status must be stored only in SYSTEM_DESIGN")
        if full_gate.get("status") != expected_runtime_gate_status(full_gate, current_facts["migration"]["head"]):
            runtime_errors.append("FULL_SCHEMA_MYSQL84_RUNTIME_GATE stored status is stale")
        ar = _yaml_load((root / "系统技术架构技术选型与AGENTS/agents-rules.yaml").read_text(encoding="utf-8"))
        if ar.get("runtime_gate_contract_ref") != "编码权威事实/SYSTEM_DESIGN.yaml#runtime_gate_contract":
            runtime_errors.append("agents-rules runtime_gate_contract_ref drift")
        for item in ar.get("blocking_gates", []):
            if isinstance(item, dict) and "status" in item:
                runtime_errors.append(f"agents-rules duplicates current runtime status for {item.get('gate_id')}")
        product = _yaml_load((root / "产品总体需求与系统边界/产品总体需求与系统边界.yaml").read_text(encoding="utf-8"))
        readiness = product.get("authority_readiness", {})
        if readiness.get("database_runtime_gate", {}).get("status_source") != "编码权威事实/SYSTEM_DESIGN.yaml#runtime_gate_contract.gates[FULL_SCHEMA_MYSQL84_RUNTIME_GATE].status":
            runtime_errors.append("product authority_readiness database gate must reference canonical runtime status")
        if "status" in readiness.get("database_runtime_gate", {}):
            runtime_errors.append("product authority_readiness must not duplicate full-schema runtime status")
        if readiness.get("implementation_release_gate", {}).get("status_source") != "编码权威事实/SYSTEM_DESIGN.yaml#runtime_gate_contract.implementation_status":
            runtime_errors.append("product authority_readiness implementation gate must reference canonical status")
        if "status" in readiness.get("implementation_release_gate", {}):
            runtime_errors.append("product authority_readiness must not duplicate implementation status")
        auth_contract = _yaml_load((root / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(encoding="utf-8"))
        if auth_contract.get("metadata", {}).get("implementation_status_source") != "SYSTEM_DESIGN.runtime_gate_contract.implementation_status":
            runtime_errors.append("authentication contract must reference canonical implementation status")
        if "implementation_status" in auth_contract.get("metadata", {}):
            runtime_errors.append("authentication contract must not duplicate current implementation status")
        refinement = _yaml_load((root / "编码权威事实/NEEDS_REFINEMENT_CLOSURE/needs-refinement-closure.yaml").read_text(encoding="utf-8"))
        active_gaps = {item.get("gap_id"): item for item in refinement.get("execution_evidence_gaps", []) if isinstance(item, dict)}
        if "GATE-MYSQL84-001" in active_gaps:
            runtime_errors.append("resolved full-schema MySQL gate must not remain in active execution_evidence_gaps")
        resolved_evidence = {item.get("gate_id"): item for item in refinement.get("resolved_execution_evidence", []) if isinstance(item, dict)}
        full_resolved = resolved_evidence.get("FULL_SCHEMA_MYSQL84_RUNTIME_GATE", {})
        expected_evidence_ref = full_gate.get("last_execution_evidence", {}).get("evidence_ref")
        if full_gate.get("status") == "PASS":
            if full_resolved.get("resolution") != "CURRENT_RUNTIME_EVIDENCE_AVAILABLE":
                runtime_errors.append("resolved full-schema MySQL gate must declare CURRENT_RUNTIME_EVIDENCE_AVAILABLE")
            if full_resolved.get("evidence_ref") != expected_evidence_ref:
                runtime_errors.append("resolved full-schema MySQL evidence_ref must match SYSTEM_DESIGN current evidence")
        for item in refinement.get("historical_execution_evidence", []):
            if isinstance(item, dict) and "current_status" in item:
                runtime_errors.append(f"historical execution evidence must not duplicate current status: {item.get('evidence_id')}")
    except Exception as exc:
        runtime_errors.append(str(exc))
    add(
        "GOV-RUNTIME-GATE-SINGLE-STRUCTURE",
        not runtime_errors,
        "SYSTEM_DESIGN.runtime_gate_contract is the sole current runtime-gate status source",
        runtime_errors,
    )

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
