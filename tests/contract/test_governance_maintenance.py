from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'validator'

import shutil
from pathlib import Path

import yaml

from tools.governance.governance_contract_test import _execution_group, discover_governance_tests
from tools.governance.governance_lite_validator import validate

ROOT = Path(__file__).resolve().parents[2]
STANDALONE = ROOT / 'agent-governance-lite'


def _copy_repo(tmp_path: Path) -> Path:
    target = tmp_path / 'repo'
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.git', '.tmp', '__pycache__', '*.pyc', '.pytest_cache'))
    return target


def test_root_readme_lifecycle_includes_required_gate_and_workspace_baseline():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'task_governance gate' in text
    assert 'Workspace Baseline' in text
    assert 'Required Gates' in text
    assert 'Gate Freshness Verification' in text
    assert 'git rev-parse HEAD' not in text
    assert 'Git 仅为可选只读' in text


def test_directory_roles_are_explicit_and_non_ambiguous():
    text = (ROOT / 'README.md').read_text(encoding='utf-8') + '\n' + (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert '.governance/' in text
    assert '.agents/skills/' in text
    assert '.codex/agents/' in text
    assert 'Agent = Who' in text
    assert 'Skill = How' in text
    assert 'Governance Profile = Rules' in text


def test_validator_accepts_current_governance_profile_directory():
    result = validate(ROOT)
    assert result['status'] == 'PASS', result


def test_validator_rejects_legacy_agent_profile_directory(tmp_path: Path):
    root = _copy_repo(tmp_path)
    shutil.move(root / '.governance', root / '.agent')
    result = validate(root)
    assert result['status'] == 'FAIL'
    assert any('DEPRECATED_AGENT_PROFILE_DIRECTORY' in err for err in result['errors'])


def test_validator_rejects_legacy_and_current_profile_directories_together(tmp_path: Path):
    root = _copy_repo(tmp_path)
    shutil.copytree(root / '.governance', root / '.agent')
    result = validate(root)
    assert result['status'] == 'FAIL'
    assert any('LEGACY_GOVERNANCE_DIRECTORY_PRESENT' in err for err in result['errors'])


def test_standalone_template_only_uses_governance_profile_directory():
    profile = STANDALONE / 'templates/project-profile'
    assert (profile / '.governance').is_dir()
    assert not (profile / '.agent').exists()


def test_governance_contract_grouping_preserves_discovery_and_reduces_workspace_copies():
    tests = discover_governance_tests(ROOT)
    assert tests
    groups = {_execution_group(path) for path in tests}
    assert len(groups) < len(tests)
    assert {'routing', 'runtime-resilience', 'standalone', 'validator', 'workspace'} <= groups


def test_git_policy_is_not_duplicated_in_project_profile():
    for path in (
        ROOT / '.governance/policies.yaml',
        STANDALONE / 'templates/project-profile/.governance/policies.yaml',
    ):
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        assert 'git_policy' not in (data.get('policies') or {})


def test_runtime_and_semantic_governance_tests_have_no_release_specific_coupling():
    scopes = [ROOT / 'tools/governance', ROOT / 'agent-governance-lite/runtime/tools/governance', ROOT / 'tests/contract']
    import re
    release_coupling = re.compile(r'(?:pre|post)-R\d+|R\d+(?:DOMAIN|MULTI)|test_r\d+_gate_fix', re.IGNORECASE)
    findings = []
    for base in scopes:
        for path in base.rglob('*.py'):
            text = path.read_text(encoding='utf-8', errors='ignore')
            for match in release_coupling.finditer(text):
                findings.append(f'{path.relative_to(ROOT)}:{match.group(0)}')
    assert findings == []


def test_database_migration_versions_and_authority_business_ids_are_untouched():
    assert (ROOT / 'docs/authority/编码权威事实/DATABASE_DDL/V6__p1_auth_governance_closure.sql').is_file()
    assert (ROOT / 'docs/authority/编码权威事实/DATABASE_DDL/V7__p1_remaining_authentication_closure.sql').is_file()
    text = (ROOT / 'tests/contract/test_authority_referential_integrity.py').read_text(encoding='utf-8')
    assert 'DI-R4-999-PK' in text
    assert 'DI-R4-084-PK' in text
