from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from current_facts import derive_current_facts
AUTHORITY = ROOT / "docs/authority"
RETIRED_TOKENS = (
    "OBJ-085",
    "平台设计基线发布",
    "atp_platform_design_baseline_release",
    "PlatformDesignBaselineRelease",
)


def _yaml(rel: str) -> dict:
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load((ROOT / rel).read_text(encoding="utf-8"), Loader=loader)


def test_retired_platform_design_baseline_model_is_not_current_authority() -> None:
    allowed = {
        "编码权威事实/DATABASE_DDL/V3__platform_contract_rebuild.sql",
        "编码权威事实/DATABASE_DDL/V8__retire_platform_design_baseline_release.sql",
        "编码权威事实/DATABASE_DDL/database-schema.yaml",
    }
    hits: list[str] = []
    for path in AUTHORITY.rglob("*"):
        if not path.is_file() or "validation" in path.parts or "ADR" in path.parts:
            continue
        rel = path.relative_to(AUTHORITY).as_posix()
        if rel in allowed:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if rel == "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json":
            payload = json.loads(text)
            payload.get("metadata", {}).pop("obj_085_retirement_provenance", None)
            text = json.dumps(payload, ensure_ascii=False)
        text = text.replace("V8__retire_platform_design_baseline_release.sql", "V8__RETIRED_GOVERNANCE_MODEL.sql")
        if any(token in text for token in RETIRED_TOKENS):
            hits.append(rel)
    assert not hits, hits[:20]
    schema = _yaml("docs/authority/编码权威事实/DATABASE_DDL/database-schema.yaml")
    assert all(item.get("object_id") != "OBJ-085" for item in schema["tables"])
    assert all(item.get("table_name") != "atp_platform_design_baseline_release" for item in schema["tables"])
    assert "V8__retire_platform_design_baseline_release.sql" in derive_current_facts(ROOT)["migration"]["files"]


def test_project_scoped_authorization_intersects_role_binding_and_realtime_project_duty() -> None:
    service = (ROOT / "services/api/src/platform_api/auth_service.py").read_text(encoding="utf-8")
    contract = _yaml("docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml")
    rule = str(contract["user_administration"]["role_binding"]["project_scoped_realtime_authorization"])
    for token in (
        "ProjectMember.user_id == user_id",
        "ProjectMember.project_id == project_id",
        "ProjectMember.role_id == binding_role_id",
        "ProjectMember.lifecycle_status == ACTIVE",
    ):
        assert token in service
    assert "UserRoleBinding" in rule and "ProjectMember.role_id" in rule


def test_request_validation_is_formally_422_for_every_operation() -> None:
    app = (ROOT / "services/api/src/platform_api/app.py").read_text(encoding="utf-8")
    api = _yaml("docs/authority/编码权威事实/OPENAPI/openapi.yaml")
    assert 'status = 422' in app
    assert '"AUTH_REQUEST_VALIDATION_FAILED"' in app
    assert "AUTH_REQUEST_VALIDATION_FAILED" in api["components"]["schemas"]["AuthenticationErrorCode"]["enum"]
    assert "RequestValidationFailed" in api["components"]["responses"]
    for path, path_item in api["paths"].items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"} or not isinstance(operation, dict):
                continue
            assert operation["responses"]["422"]["$ref"] == "#/components/responses/RequestValidationFailed", (method, path)


def test_authority_projection_generator_is_canonical_consistency_gate() -> None:
    validator = (ROOT / "tools/authority_validation.py").read_text(encoding="utf-8")
    assert "authority_projection_check" in validator
    result = subprocess.run(
        [sys.executable, "tools/authority_projection.py", "check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for rel in (
        "docs/authority/编码权威事实/SYSTEM_DESIGN.md",
        "docs/authority/编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "GENERATED_PROJECTION" in text and "DO_NOT_EDIT_MANUALLY" in text
    csv_projection = ROOT / "docs/authority/编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.csv"
    assert csv_projection.is_file()
    assert "state_dimension_id,object_id,object_name" in csv_projection.read_text(encoding="utf-8-sig").splitlines()[0]
    for rel, header in (
        ("docs/authority/编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.csv", "acceptance_id,requirement_ids"),
        ("docs/authority/编码权威事实/PERMISSION_CLOSURE/role-permission-matrix.csv", "mapping_id,role_id,permission_id"),
        ("docs/authority/编码权威事实/OPENAPI/operation-permission-mapping.csv", "operationId,method,path"),
        ("docs/authority/编码权威事实/DATABASE_DDL/object-table-mapping.csv", "object_id,name,object_type,aggregate_id"),
    ):
        projection = ROOT / rel
        assert projection.is_file(), rel
        assert header in projection.read_text(encoding="utf-8-sig").splitlines()[0]
    assert not (ROOT / "docs/authority/编码权威事实/SYSTEM_DESIGN.docx").exists(), "stale unmanaged SYSTEM_DESIGN.docx projection must be retired"


def test_runtime_gate_has_one_current_status_owner() -> None:
    design = _yaml("docs/authority/编码权威事实/SYSTEM_DESIGN.yaml")
    db = design["database_contract"]
    runtime = design["runtime_gate_contract"]
    index = {item["gate_id"]: item for item in runtime["gates"]}
    full = index["FULL_SCHEMA_MYSQL84_RUNTIME_GATE"]
    assert full["evaluation_mode"] == "MIGRATION_HEAD_FRESHNESS"
    assert "status_source" not in full and full["status"] in {"PASS", "RERUN_REQUIRED"}
    assert "runtime_gates" not in derive_current_facts(ROOT)
    assert "authentication_runtime_gates" not in db
    assert "authentication_runtime_evidence" in db
    assert all("current_status" not in item for item in db["authentication_runtime_evidence"].values())
    assert "mysql84_runtime_gate" not in db and "browser_runtime_gate" not in db
    assert db["migration_execution"]["full_schema_gate_status_source"] == "编码权威事实/SYSTEM_DESIGN.yaml#runtime_gate_contract.gates[FULL_SCHEMA_MYSQL84_RUNTIME_GATE].status"
    assert "full_schema_gate_status" not in db["migration_execution"]
    assert design["metadata"]["implementation_status_source"] == "SYSTEM_DESIGN.runtime_gate_contract.implementation_status"
    assert "implementation_release_readiness" not in design["metadata"]
    assert design["release_gate"]["implementation_release_readiness"]["status_source"] == "SYSTEM_DESIGN.runtime_gate_contract.implementation_status"
    assert "status" not in design["release_gate"]["implementation_release_readiness"]
    refinement = _yaml("docs/authority/编码权威事实/NEEDS_REFINEMENT_CLOSURE/needs-refinement-closure.yaml")
    gaps = {item["gap_id"]: item for item in refinement["execution_evidence_gaps"]}
    assert "GATE-MYSQL84-001" not in gaps
    assert "status" not in gaps["GATE-EVIDENCE-001"] and gaps["GATE-EVIDENCE-001"]["status_source"].endswith("REAL_ACCEPTANCE_EVIDENCE].status")
    resolved = {item["gate_id"]: item for item in refinement.get("resolved_execution_evidence", [])}
    assert resolved["FULL_SCHEMA_MYSQL84_RUNTIME_GATE"]["resolution"] == "CURRENT_RUNTIME_EVIDENCE_AVAILABLE"
    assert resolved["FULL_SCHEMA_MYSQL84_RUNTIME_GATE"]["evidence_ref"].endswith("mysql84-full-schema-v3-v8-2026-08-13.json")
    historical = {item["evidence_id"]: item for item in refinement.get("historical_execution_evidence", [])}
    mysql_history = historical["GATE-MYSQL84-001-PRE-V7-REPAIR"]
    assert mysql_history["historical_status"] == "PASS"
    assert "current_status" not in mysql_history
    assert mysql_history["superseded_by_evidence_ref"].endswith("mysql84-full-schema-v3-v8-2026-08-13.json")
    agent_rules = _yaml("docs/authority/系统技术架构技术选型与AGENTS/agents-rules.yaml")
    assert all("status" not in item for item in agent_rules["blocking_gates"])


def test_no_active_r42_freeze_or_formal_baseline_wording() -> None:
    acceptance = json.loads((AUTHORITY / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json").read_text(encoding="utf-8"))
    assert all(item.get("governance_revision") != "R4.2_P1_AUTHENTICATION_CONTRACT_COMPLETION" for item in acceptance["acceptance_closure"])
    active_tokens = (
        "CURRENT_FORMAL_CODE_INPUT_BASELINE",
        "Freeze Wins",
        "FROZEN_PERMISSION",
        "FROZEN_PERMISSION_MAPPING",
        "FROZEN_BY_REPAIR",
        "FROZEN_V1_SLO",
        "FROZEN_",
        "FROZEN SYSTEM_DESIGN",
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
    )
    allowed_history = {
        "编码权威事实/DATABASE_DDL/V3__platform_contract_rebuild.sql",
        "编码权威事实/DATABASE_DDL/V5__platform_authentication_contract.sql",
        "编码权威事实/ADR/ADR-register.yaml",
        "编码权威事实/ADR/ADR-033_P1认证安全审计与JWTKeyRing治理闭环.md",
        "编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml",
        "编码权威事实/EVENT_CONTRACTS/event-registry.yaml",
    }
    hits = []
    for path in AUTHORITY.rglob("*"):
        if not path.is_file() or "validation" in path.parts:
            continue
        rel = path.relative_to(AUTHORITY).as_posix()
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if any(token in text for token in active_tokens):
            hits.append(rel)
        if "R4.2" in text and rel not in allowed_history:
            hits.append(rel + ":R4.2")
    assert not hits, hits[:20]


def test_closed_decisions_do_not_leave_current_business_rules_decision_blocked() -> None:
    core = _yaml("docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml")
    pending = {
        item["decision_id"]
        for item in core["decisions"]
        if item.get("status") in {"PENDING_EXTERNAL_DECISION", "OPEN", "PENDING"}
    }
    assert pending == set()
    blocked = [
        item["rule_id"]
        for item in core["business_rules"]
        if item.get("coding_status") == "BLOCKED_BY_MISSING_DECISION"
        or item.get("test_readiness") == "BLOCKED_BY_MISSING_DECISION"
    ]
    assert blocked == []
    assert all(item.get("coding_status") == "CONTRACT_SPECIFIED" for item in core["business_rules"])
    assert "12项" not in core["conclusion"]["statement"]
    assert "不存在未关闭的产品或架构决策" in core["conclusion"]["statement"]


def test_agent_runtime_instructions_have_no_active_baseline_or_frozen_vocabulary() -> None:
    hits: list[str] = []
    tokens = ("正式基线", "基线", "baseline", "Baseline", "frozen", "FROZEN", "冻结")
    for base in (ROOT / ".agents", ROOT / ".codex" / "agents"):
        for path in base.rglob("*"):
            if not path.is_file() or path.name == "MANIFEST.sha256" or path.suffix.lower() not in {".md", ".yaml", ".yml", ".toml", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(token in text for token in tokens):
                hits.append(path.relative_to(ROOT).as_posix())
    assert hits == []


def test_current_core_authorities_have_no_obsolete_generator_metadata() -> None:
    core_rels = (
        "产品总体需求与系统边界/产品总体需求与系统边界.yaml",
        "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
        "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml",
        "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
        "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
        "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
        "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml",
    )
    forbidden_format_keys = {"generator", "generator_version", "upstream_release_id", "upstream_hash", "output_hash", "version", "release_id"}
    for rel in core_rels:
        payload = _yaml("docs/authority/" + rel)
        statistics = payload.get("statistics") or {}
        assert "source_file_count" not in statistics, rel
        assert "source_file_count_scope" not in statistics, rel
        assert forbidden_format_keys.isdisjoint(payload.get("format_governance", {})), rel
