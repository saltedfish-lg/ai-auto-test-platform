import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from current_facts import derive_current_facts, discover_migrations  # noqa: E402

AUTHORITY = ROOT / "docs/authority"
AUTHORITY_DDL = AUTHORITY / "编码权威事实/DATABASE_DDL"


def _yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_current_migration_fact_is_mechanically_discovered_not_head_hardcoded() -> None:
    facts = derive_current_facts(ROOT)
    migrations = discover_migrations(AUTHORITY)
    schema = _yaml("docs/authority/编码权威事实/DATABASE_DDL/database-schema.yaml")
    design = _yaml("docs/authority/编码权威事实/SYSTEM_DESIGN.yaml")
    assert [item["name"] for item in migrations] == facts["migration"]["files"]
    assert [item["version"] for item in migrations] == sorted({item["version"] for item in migrations})
    assert schema["migration_execution"]["migration_discovery_source"] == "tools/current_facts.py#discover_migrations"
    for forbidden in ("migration_files", "object_table_count", "technical_table_count", "foreign_key_count"):
        assert forbidden not in schema
    for forbidden in ("authority_chain", "current_chain"):
        assert forbidden not in schema["migration_execution"]
    for forbidden in ("migration_release", "table_count", "object_table_count", "technical_table_count"):
        assert forbidden not in design["database_contract"]
    assert design["database_contract"]["current_facts_source"] == "tools/current_facts.py#database"



def test_discover_migrations_accepts_future_head_without_governance_code_change(tmp_path: Path) -> None:
    ddl = tmp_path / "编码权威事实" / "DATABASE_DDL"
    ddl.mkdir(parents=True)
    for version in (8, 9, 10):
        (ddl / f"V{version}__future_{version}.sql").write_text(f"-- V{version}\n", encoding="utf-8")
    migrations = discover_migrations(tmp_path)
    assert [item["version"] for item in migrations] == [8, 9, 10]
    assert migrations[-1]["name"] == "V10__future_10.sql"

def test_executable_full_schema_mysql_gate_discovers_future_migrations_automatically() -> None:
    facts = derive_current_facts(ROOT)
    gate = (AUTHORITY / "validation/run_mysql84_gate.py").read_text(encoding="utf-8")
    compose = (AUTHORITY / "validation/mysql84-compose.yml").read_text(encoding="utf-8")
    assertions = (AUTHORITY / "validation/mysql84_assertions.sql").read_text(encoding="utf-8")
    template = (AUTHORITY / "validation/mysql84_assertions.template.sql").read_text(encoding="utf-8")
    assert "discover_migrations" in gate and "derive_current_facts" in gate
    assert "/ddl/V[0-9]*__*.sql" in compose and "sort -n" in compose
    assert "{{TABLE_COUNT}}" in template and "{{MIGRATION_CHAIN}}" in template
    assert str(facts["database"]["table_count"]) in assertions
    assert facts["migration"]["chain"] in assertions
    assert "mysql84_upgrade_legacy_fixture.sql" in compose
    assert 'ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"' in gate
    for legacy_env in ("ATP_MYSQL_HOST", "ATP_MYSQL_PORT", "ATP_MYSQL_USER", "ATP_MYSQL_PASSWORD"):
        assert legacy_env not in gate
    formal = (ROOT / "tools/mysql84_gate.py").read_text(encoding="utf-8")
    assert "--evidence-output" in formal
    assert "evidence_schema_version" in formal


def test_formal_full_schema_gate_emits_structured_secret_free_evidence_without_execution(tmp_path: Path) -> None:
    evidence_path = tmp_path / "mysql84-evidence.json"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/mysql84_gate.py"), "--evidence-output", str(evidence_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = json.loads(result.stdout)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert stdout == evidence
    assert evidence["evidence_schema_version"] == 1
    assert evidence["gate_id"] == "FULL_SCHEMA_MYSQL84_RUNTIME_GATE"
    assert evidence["result"] == "NOT_EXECUTED_THIS_RUN"
    assert evidence["admin_connection_source"] == "ATP_MYSQL_ADMIN_URL"
    serialized = json.dumps(evidence, ensure_ascii=False)
    assert "password" not in serialized.lower()
    assert "mysql+pymysql://" not in serialized


def test_full_schema_mysql_gate_status_is_derived_from_migration_head_freshness() -> None:
    facts = derive_current_facts(ROOT)
    design = _yaml("docs/authority/编码权威事实/SYSTEM_DESIGN.yaml")
    runtime = {item["gate_id"]: item for item in design["runtime_gate_contract"]["gates"]}
    full = runtime["FULL_SCHEMA_MYSQL84_RUNTIME_GATE"]
    assert full["evaluation_mode"] == "MIGRATION_HEAD_FRESHNESS"
    assert "status_source" not in full
    assert full["status"] in {"PASS", "RERUN_REQUIRED"}
    assert "runtime_gates" not in facts
    agent_rules = _yaml("docs/authority/系统技术架构技术选型与AGENTS/agents-rules.yaml")
    assert all("status" not in item for item in agent_rules["blocking_gates"])


def test_validator_timeout_is_configurable_and_bounded() -> None:
    text = (ROOT / "tools/authority_validation.py").read_text(encoding="utf-8")
    guard = (ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/scripts/authority_write_guard.py").read_text(encoding="utf-8")
    assert "ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS" in text
    assert "DEFAULT_VALIDATOR_TIMEOUT_SECONDS = 600" in text
    assert "MAX_VALIDATOR_TIMEOUT_SECONDS = 3600" in text
    assert "timeout=timeout_seconds" in guard
    assert "timeout=180" not in guard


def test_agent_database_guidance_does_not_copy_current_migration_head() -> None:
    facts = derive_current_facts(ROOT)
    paths = [
        ROOT / "AGENTS.md",
        ROOT / ".agents/skills/ai-auto-test-platform-database/SKILL.md",
        ROOT / ".agents/agent-roles/database-integrity-reviewer.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "current_facts.py" in text, path
        assert facts["migration"]["head_name"] not in text, path
        assert facts["migration"]["chain"] not in text, path
        assert "database/migrations" not in text, path
        assert "db/migrations" not in text, path


def test_governance_protocol_versions_have_code_owners_not_document_copies() -> None:
    facts = derive_current_facts(ROOT)
    policy = _yaml(".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml")
    assert "checkpoint_schema_version" not in policy["task_resume_validation"]
    assert policy["task_resume_validation"]["checkpoint_schema_source"].endswith("task_checkpoint.py::SCHEMA_VERSION")
    assert policy["context_pack"]["workspace_snapshot_version_source"].endswith("workspace_snapshot.py::SNAPSHOT_VERSION")
    pack = (ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency/references/task-context-pack.md").read_text(encoding="utf-8")
    assert not re.search(r"checkpoint_schema_version:\s*\d+", pack)
    assert not re.search(r"snapshot_version:\s*\d+", pack)
    snapshot_policy = policy["context_pack"]["task_start_workspace_snapshot"]
    assert "snapshot_schema_version" not in snapshot_policy
    assert snapshot_policy["snapshot_schema_source"].endswith("workspace_snapshot.py::SNAPSHOT_VERSION")
    assert facts["protocols"]["checkpoint_schema_version"] >= 1
    assert facts["protocols"]["workspace_snapshot_version"] >= 1


def test_local_formal_code_write_uses_lightweight_cp0_without_full_stage_chain() -> None:
    policy = _yaml(".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml")
    local = policy["modes"]["LOCAL"]
    assert local["formal_code_write_evidence_anchor"] == "LIGHTWEIGHT_CP0_REQUIRED"
    assert local["full_stage_checkpoint_chain_required"] is False
    assert local["comment_quality_gate_required"] is True
    assert local["comment_quality_gate_attestation_required_for_terminal"] is True
    assert local["authority_transaction_allowed"] is False
    assert local["promote_to_full_before_authority_or_stage_resume"] == "required"
    assert local["lightweight_terminal_command"] == "local-complete"
    assert policy["context_pack"]["local_fingerprint"] == "required_for_formal_code_write"


def test_acceptance_current_contract_refs_use_stable_aliases() -> None:
    facts = derive_current_facts(ROOT)
    payload = json.loads((AUTHORITY / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json").read_text(encoding="utf-8"))
    semantics = payload["metadata"]["contract_reference_semantics"]
    assert semantics["contract_ids"] == "CURRENT_LIVING_AUTHORITY_ALIASES_RESOLVED_BY_TOOLS_CURRENT_FACTS"
    assert semantics["source_contract_ids_at_definition"] == "HISTORICAL_TRACEABILITY_ONLY"
    assert "current_contract_catalog" not in payload["metadata"]
    allowed = set(facts["contracts"])
    historical_seen = False
    for item in payload["acceptance_closure"]:
        current = item.get("contract_ids", [])
        historical = item.get("source_contract_ids_at_definition", [])
        assert current and historical, item["acceptance_id"]
        for ref in current:
            assert ref in allowed or ref.startswith("ADR-"), (item["acceptance_id"], ref)
            assert not re.search(r"-\d+\.\d+", ref), (item["acceptance_id"], ref)
        historical_seen = historical_seen or any(re.search(r"-\d+\.\d+", ref) for ref in historical)
    assert historical_seen


def test_current_fact_gate_rejects_reintroduced_duplicate_values() -> None:
    import subprocess
    completed = subprocess.run([sys.executable, str(ROOT / "tools/current_facts.py"), "check"], text=True, capture_output=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "CURRENT_FACTS_CONSISTENT" in completed.stdout


def test_full_schema_mysql84_pass_evidence_is_recorded_and_current_status_is_pass() -> None:
    facts = derive_current_facts(ROOT)
    design = _yaml("docs/authority/编码权威事实/SYSTEM_DESIGN.yaml")
    full = next(item for item in design["runtime_gate_contract"]["gates"] if item["gate_id"] == "FULL_SCHEMA_MYSQL84_RUNTIME_GATE")
    assert full["status"] == "PASS"
    evidence = full["last_execution_evidence"]
    assert evidence["result"] == "PASS"
    assert evidence["mysql_version"] == "8.4.11"
    assert evidence["validated_migration_head"] == facts["migration"]["head"]
    for key in ("empty_db_migration", "v4_seed_idempotency", "legacy_upgrade", "schema_assertions", "temporary_db_cleanup"):
        assert evidence[key] == "PASS"
    evidence_path = AUTHORITY / evidence["evidence_ref"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["gate_id"] == "FULL_SCHEMA_MYSQL84_RUNTIME_GATE"
    assert payload["result"] == "PASS"
    assert payload["mysql_version"] == "8.4.11"
    assert payload["validated_migration_head"] == facts["migration"]["head"]
    assert payload["validated_migration_chain"] == facts["migration"]["chain"]
    assert payload["admin_connection_source"] == "ATP_MYSQL_ADMIN_URL"
    assert all(value == "PASS" for value in payload["checks"].values())
    assert payload["secrets_in_evidence"] is False


def test_domain_counts_and_open_decisions_are_reconciled_to_current_facts() -> None:
    facts = derive_current_facts(ROOT)
    core = _yaml("docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml")
    closure = core["r3_state_closure"]
    assert closure["validated_dimensions"] == facts["domain"]["state_dimension_count"] == 124
    assert closure["lifecycle_objects"] == facts["domain"]["object_count"] == 95
    assert core["statistics"]["lifecycle_completion_count"] == 95
    assert "database_runtime_gate" not in core["coding_readiness_summary"]
    assert facts["governance"]["open_decision_count"] == 0
    tech = _yaml("docs/authority/系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml")
    scan = tech["metadata"]["source_scan_statistics"]
    assert "formal_object_count" not in scan and "pending_external_decision_count" not in scan
    assert tech["open_questions"] == []
