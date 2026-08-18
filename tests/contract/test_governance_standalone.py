from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'standalone'

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools.governance.impact_scan import GENERIC_AUTO_REQUIRED_GATES, scan
from tools.governance.required_gate_runner import run_required
from tools.governance.task_context import cleanup_task, gate_results_path, load_context
from tools.governance.task_governance import finish, reconcile_task, resolve_product_decision, run_gates, start
from tests.contract.governance_test_support import ROOT, STANDALONE, _write, _project, _start_changed, _abort_if_present

def test_standalone_default_profile_contains_code_quality_gate():
    data = yaml.safe_load((STANDALONE / 'templates/project-profile/.governance/gates.yaml').read_text(encoding='utf-8'))
    assert 'code_quality_gate' in data['gates']

def test_every_auto_generated_generic_gate_exists_in_standalone_registry():
    data = yaml.safe_load((STANDALONE / 'templates/project-profile/.governance/gates.yaml').read_text(encoding='utf-8'))
    assert set(GENERIC_AUTO_REQUIRED_GATES) <= set(data['gates'])

def test_standalone_high_risk_task_has_configured_code_quality_gate(tmp_path: Path):
    shutil.copytree(STANDALONE / 'templates/project-profile/.governance', tmp_path / '.governance')
    shutil.copytree(STANDALONE / 'runtime/tools', tmp_path / 'tools')
    _write(tmp_path / 'src/a.py', 'x = 1\n')
    _write(tmp_path / 'test_smoke.py', 'def test_ok():\n    assert True\n')
    ctx = start(tmp_path, 'HIGH', 'security app hardening', ['src/a.py'])
    _write(tmp_path / 'src/a.py', 'x = 2\n')
    assert 'code_quality_gate' in ctx['required_gates']
    result = run_gates(tmp_path, 'HIGH', timeout=20)
    assert result['status'] == 'PASS', result
    assert not any(x.get('status') == 'NOT_CONFIGURED' for x in result['results'])
    finish(tmp_path, 'HIGH', 'SUCCESS')

@pytest.mark.parametrize('authority_path', ['docs/authority/product.yaml', 'specs/product/rules.yaml', 'policy/rules.yaml'])
def test_authority_path_is_profile_driven(tmp_path: Path, authority_path: str):
    _project(tmp_path)
    _write(tmp_path / authority_path, 'rule: existing\n')
    _write(tmp_path / '.governance/authorities.yaml', f'''schema_version: 1
authorities:
  product:
    domains: [APP]
    paths: [{authority_path}]
''')
    _write(tmp_path / '.governance/reviewers.yaml', '''schema_version: 1
reviewers:
  product_sovereignty_reviewer:
    trigger:
      authority: [product]
''')
    out = scan(tmp_path, 'AUTH', 'modify app', ['src/a.py'])
    try:
        assert authority_path in out['authorities']
        assert 'product_sovereignty_reviewer' in out['review_triggers']
        assert 'app_gate' in out['required_gates']
    finally:
        cleanup_task(tmp_path, 'AUTH')

def test_generic_runtime_does_not_depend_on_hardcoded_docs_authority_path():
    for path in (STANDALONE / 'runtime/tools/governance').glob('*.py'):
        if path.name == 'governance_lite_validator.py':
            continue  # validator names the forbidden token only to detect it elsewhere
        assert 'docs/authority/' not in path.read_text(encoding='utf-8', errors='ignore'), path

def test_standalone_declares_python_and_pyyaml_dependency():
    req = (STANDALONE / 'requirements.txt').read_text(encoding='utf-8')
    readme = (STANDALONE / 'README.md').read_text(encoding='utf-8')
    assert 'PyYAML>=6.0,<7' in req
    assert 'python-dotenv>=1.0,<2' in req
    assert 'Python >= 3.12' in readme
    assert 'pip install -r requirements.txt' in readme

def test_agents_governance_snippet_contains_canonical_lifecycle():
    text = (STANDALONE / 'templates/AGENTS.governance-snippet.md').read_text(encoding='utf-8')
    for token in (
        'single Task Start', 'Full Impact Scan', 'Shared Task Context', 'Incremental Closure',
        'Feature Orchestrator', 'Product Sovereignty', 'Required Gates', 'SUCCESS', 'Git is user-owned',
    ):
        assert token.lower() in text.lower()
    for forbidden in ('ai-auto-test-platform', 'MySQL 8.4', 'default admin', 'PDA'):
        assert forbidden.lower() not in text.lower()

def test_standalone_dependency_install_smoke(tmp_path: Path):
    del tmp_path
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--no-index', '-r', str(STANDALONE / 'requirements.txt')],
        check=True, timeout=60, capture_output=True, text=True,
    )
    proc = subprocess.run([sys.executable, '-c', 'import yaml; print(yaml.__version__)'], check=True, timeout=20, capture_output=True, text=True)
    assert proc.stdout.strip()


def _install_standalone(distribution: Path, target: Path) -> None:
    shutil.copytree(distribution / 'templates/project-profile/.governance', target / '.governance')
    shutil.copytree(distribution / 'runtime/tools', target / 'tools')
    shutil.copytree(distribution / 'agents', target / '.codex/agents')
    shutil.copytree(distribution / 'skills', target / '.agents/skills')
    shutil.copy2(distribution / 'requirements.txt', target / 'requirements.txt')
    target.joinpath('AGENTS.md').write_text(
        (distribution / 'templates/AGENTS.governance-snippet.md').read_text(encoding='utf-8'),
        encoding='utf-8',
    )


def test_standalone_governance_domain_protects_runtime_paths():
    domains = yaml.safe_load((STANDALONE / 'templates/project-profile/.governance/domains.yaml').read_text(encoding='utf-8'))['domains']
    governance = domains['GOVERNANCE']
    assert governance['kind'] == 'infrastructure'
    assert {'AGENTS.md', '.governance/**', '.agents/**', '.codex/**', 'tools/governance/**', 'agent-governance-lite/**'} <= set(governance['paths'])
    assert {'governance_lite_validator', 'governance_contract_test'} <= set(governance['gates'])


def test_standalone_governance_runtime_change_requires_self_protection_gates(tmp_path: Path):
    _install_standalone(STANDALONE, tmp_path)
    target = tmp_path / 'tools/governance/task_governance.py'
    ctx = start(tmp_path, 'SELFPROTECT', 'maintain governance runtime', ['tools/governance/task_governance.py'])
    try:
        assert 'GOVERNANCE' in ctx['domains']
        assert {'governance_lite_validator', 'governance_contract_test'} <= set(ctx['required_gates'])
        target.write_text(target.read_text(encoding='utf-8') + '\n# standalone self-protection smoke\n', encoding='utf-8')
        reconcile_task(tmp_path, 'SELFPROTECT')
        with pytest.raises(RuntimeError, match='REQUIRED_GATES_NOT_EXECUTED'):
            finish(tmp_path, 'SELFPROTECT', 'SUCCESS')
    finally:
        _abort_if_present(tmp_path, 'SELFPROTECT')


def test_standalone_governance_runtime_change_succeeds_only_after_governance_gates_pass(tmp_path: Path):
    _install_standalone(STANDALONE, tmp_path)
    target = tmp_path / 'tools/governance/task_governance.py'
    ctx = start(tmp_path, 'SELFPROTECTPASS', 'maintain governance runtime', ['tools/governance/task_governance.py'])
    target.write_text(target.read_text(encoding='utf-8') + '\n# standalone governance gate smoke\n', encoding='utf-8')
    result = run_gates(tmp_path, 'SELFPROTECTPASS', timeout=30)
    assert result['status'] == 'PASS', result
    by_gate = {item['gate']: item for item in result['results']}
    for gate in ('governance_lite_validator', 'governance_contract_test'):
        assert gate in by_gate
        assert by_gate[gate]['status'] == 'PASS', by_gate[gate]
    finish(tmp_path, 'SELFPROTECTPASS', 'SUCCESS')
    assert not (tmp_path / '.tmp/agent-governance/SELFPROTECTPASS').exists()


def _run_installed_self_contract(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / 'tools/governance/governance_contract_test.py'), '--root', str(root)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_standalone_self_contract_detects_broken_atomic_authority_lock(tmp_path: Path):
    _install_standalone(STANDALONE, tmp_path)
    lock_file = tmp_path / 'tools/governance/authority_lock.py'
    text = lock_file.read_text(encoding='utf-8')
    assert 'os.O_WRONLY | os.O_CREAT | os.O_EXCL' in text
    lock_file.write_text(text.replace('os.O_WRONLY | os.O_CREAT | os.O_EXCL', 'os.O_WRONLY | os.O_CREAT'), encoding='utf-8')
    proc = _run_installed_self_contract(tmp_path)
    assert proc.returncode != 0
    assert 'authority lock single-owner probe failed' in proc.stdout


def test_standalone_self_contract_detects_required_gate_bypass(tmp_path: Path):
    _install_standalone(STANDALONE, tmp_path)
    governance = tmp_path / 'tools/governance/task_governance.py'
    text = governance.read_text(encoding='utf-8')
    needle = "if normalized in {'SUCCESS', 'COMPLETED'}:\n        _assert_success_closure(root, task_id)"
    assert needle in text
    governance.write_text(text.replace(needle, "if False and normalized in {'SUCCESS', 'COMPLETED'}:\n        _assert_success_closure(root, task_id)"), encoding='utf-8')
    proc = _run_installed_self_contract(tmp_path)
    assert proc.returncode != 0
    assert 'required-gate bypass probe failed' in proc.stdout
