from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'validator'

import re
from pathlib import Path

import yaml

from tools.governance.governance_contract_test import discover_governance_tests
from tools.governance.governance_lite_validator import validate

ROOT = Path(__file__).resolve().parents[2]


def test_governance_contract_gate_uses_dynamic_suite_discovery():
    gates = yaml.safe_load((ROOT / '.governance/gates.yaml').read_text(encoding='utf-8'))['gates']
    command = gates['governance_contract_test']['command']
    assert command == ['python', 'tools/governance/governance_contract_test.py', '--root', '.']
    discovered = {p.name for p in discover_governance_tests(ROOT)}
    assert 'test_governance_required_gates.py' in discovered
    assert 'test_governance_gate_freshness.py' in discovered
    assert 'test_governance_product_sovereignty.py' in discovered
    assert 'test_governance_standalone.py' in discovered
    assert 'test_governance_packaging.py' in discovered


def test_governance_test_files_do_not_use_release_version_labels():
    bad = []
    pattern = re.compile(r'(?:^|_)(?:r\d+|final(?:fixed)?|fixed|closure)(?:_|\.|$)', re.IGNORECASE)
    for path in (ROOT / 'tests/contract').glob('test_governance_*.py'):
        if pattern.search(path.name):
            bad.append(path.name)
    assert bad == []


def test_governance_validator_passes_after_test_structure_migration():
    result = validate(ROOT)
    assert result['status'] == 'PASS', result
    assert result['error_count'] == 0


def _copy_validator_fixture(tmp_path: Path) -> Path:
    import shutil
    target = tmp_path / 'repo'
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.tmp', '__pycache__', '*.pyc', '.pytest_cache'))
    return target


def test_generic_validator_allows_extra_agent_and_skill(tmp_path: Path):
    root = _copy_validator_fixture(tmp_path)
    agent = root / '.codex/agents/domain_reviewer.toml'
    agent.write_text('name = "domain_reviewer"\nsandbox_mode = "read-only"\n', encoding='utf-8')
    skill = root / '.agents/skills/custom-skill'; skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: custom-skill\ndescription: project extension\n---\n', encoding='utf-8')
    reviewers = yaml.safe_load((root / '.governance/reviewers.yaml').read_text(encoding='utf-8'))
    reviewers.setdefault('reviewers', {})['domain_reviewer'] = {'trigger': {'risk': ['CUSTOM_RISK']}}
    (root / '.governance/reviewers.yaml').write_text(yaml.safe_dump(reviewers, sort_keys=False), encoding='utf-8')
    (root / 'AGENTS.md').write_text((root / 'AGENTS.md').read_text(encoding='utf-8') + '\nUse $custom-skill when project policy triggers it.\n', encoding='utf-8')
    result = validate(root)
    assert result['status'] == 'PASS', result
    assert result['agent_count'] == 5
    assert result['skill_count'] == 5
    assert result['core_agent_count'] == 4
    assert result['core_skill_count'] == 4


def test_generic_validator_fails_when_core_agent_missing(tmp_path: Path):
    root = _copy_validator_fixture(tmp_path)
    (root / '.codex/agents/default_coder.toml').unlink()
    result = validate(root)
    assert result['status'] == 'FAIL'
    assert any('missing core agents' in err and 'default_coder.toml' in err for err in result['errors'])


def test_generic_validator_fails_when_referenced_extra_agent_is_missing(tmp_path: Path):
    root = _copy_validator_fixture(tmp_path)
    data = yaml.safe_load((root / '.governance/reviewers.yaml').read_text(encoding='utf-8'))
    data.setdefault('reviewers', {})['domain_reviewer'] = {'trigger': {'risk': ['CUSTOM_RISK']}}
    (root / '.governance/reviewers.yaml').write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    result = validate(root)
    assert result['status'] == 'FAIL'
    assert any('reviewer config references missing agent domain_reviewer' in err for err in result['errors'])


def test_governance_test_function_version_labels_are_rejected(tmp_path: Path):
    from tools.governance.governance_lite_validator import _versioned_governance_test_naming_errors
    base = tmp_path / 'tests/contract'; base.mkdir(parents=True)
    (base / 'test_governance_required_gates.py').write_text(
        'def test_r123_release_fix():\n    pass\n\ndef test_required_gate_cannot_be_bypassed():\n    pass\n',
        encoding='utf-8',
    )
    errors = _versioned_governance_test_naming_errors(tmp_path)
    assert any('test_r123_release_fix' in err for err in errors)
    assert not any('test_required_gate_cannot_be_bypassed' in err for err in errors)


def test_capability_named_governance_test_functions_are_allowed(tmp_path: Path):
    from tools.governance.governance_lite_validator import _versioned_governance_test_naming_errors
    base = tmp_path / 'tests/contract'; base.mkdir(parents=True)
    (base / 'test_governance_task_lifecycle.py').write_text(
        'def test_final_workspace_reconciliation_is_required():\n    pass\n\ndef test_incremental_closure_adds_new_impact():\n    pass\n',
        encoding='utf-8',
    )
    assert _versioned_governance_test_naming_errors(tmp_path) == []


def test_generic_validator_fails_when_referenced_extra_skill_is_missing(tmp_path: Path):
    root = _copy_validator_fixture(tmp_path)
    (root / 'AGENTS.md').write_text((root / 'AGENTS.md').read_text(encoding='utf-8') + '\nUse $missing-project-skill for this domain.\n', encoding='utf-8')
    result = validate(root)
    assert result['status'] == 'FAIL'
    assert any('missing skill missing-project-skill' in err for err in result['errors'])
