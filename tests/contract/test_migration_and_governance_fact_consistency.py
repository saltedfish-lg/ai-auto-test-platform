from pathlib import Path
import yaml
from tools.current_facts import derive_current_facts,discover_migrations,check_current_fact_governance
ROOT=Path(__file__).resolve().parents[2]; AUTH=ROOT/'docs/authority'
def test_migration_chain_is_dynamic_and_current_facts_consistent():
 facts=derive_current_facts(ROOT); assert [x['name'] for x in discover_migrations(AUTH)]==facts['migration']['files']; assert facts['migration']['head']==max(facts['migration']['versions'])
def test_database_schema_matches_derived_counts():
 facts=derive_current_facts(ROOT); schema=yaml.safe_load((AUTH/'编码权威事实/DATABASE_DDL/database-schema.yaml').read_text(encoding='utf-8')); assert len(schema['tables'])==facts['database']['table_count']
def test_runtime_gate_catalog_is_definition_only():
 d=yaml.safe_load((AUTH/'编码权威事实/SYSTEM_DESIGN.yaml').read_text(encoding='utf-8')); ids={x['gate_id'] for x in d['runtime_gate_catalog']['gates']}; assert {'AUTH_MYSQL_RUNTIME_GATE','AUTH_BROWSER_RUNTIME_GATE','FULL_SCHEMA_MYSQL84_RUNTIME_GATE'}.issubset(ids); assert all('status' not in x for x in d['runtime_gate_catalog']['gates'])
def test_current_fact_governance_passes(): assert check_current_fact_governance(ROOT)==[]
