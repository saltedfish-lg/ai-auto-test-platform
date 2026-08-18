from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'authority'

import importlib
import json
import subprocess
import sys
from pathlib import Path

from tools.governance.final_reconciliation import reconcile
from tools.governance.required_gate_runner import run_required
from tools.governance.task_context import save_context, save_workspace_snapshot, task_dir

ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=cwd, text=True, capture_output=True, timeout=600)


def test_authority_validator_direct_cli_passes() -> None:
    result = _run('tools/verify_authority.py', cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['status'] == 'PASS'


def test_authority_validator_direct_cli_works_outside_repository_root(tmp_path: Path) -> None:
    result = _run(str(ROOT / 'tools/verify_authority.py'), cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['status'] == 'PASS'


def test_dev_authority_uses_same_validator_successfully() -> None:
    result = _run('tools/dev.py', 'authority', cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_governance_validator_package_import_succeeds() -> None:
    module = importlib.import_module('tools.governance.governance_lite_validator')
    assert callable(module.validate)


def test_required_gate_runner_package_import_succeeds() -> None:
    module = importlib.import_module('tools.governance.required_gate_runner')
    assert callable(module.run_required)


def test_authority_validator_required_gate_executes_pass() -> None:
    task_id = 'AUTHORITY_CLI_GATE'
    directory = task_dir(ROOT, task_id)
    if directory.exists():
        import shutil
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    save_workspace_snapshot(ROOT, task_id)
    save_context(ROOT, task_id, {
        'task_id': task_id,
        'scope_level': 'FILE_OR_DOMAIN',
        'affected_files': [],
        'required_gates': ['authority_validators'],
        'product_decision_status': 'NOT_REQUIRED',
        'task_start_workspace_snapshot': 'workspace-start.json',
    })
    reconcile(ROOT, task_id)
    report = run_required(ROOT, task_id, timeout=600)
    try:
        assert report['status'] == 'PASS', report
        item = next(x for x in report['results'] if x['gate'] == 'authority_validators')
        assert item['status'] == 'PASS', item
    finally:
        import shutil
        shutil.rmtree(directory, ignore_errors=True)
