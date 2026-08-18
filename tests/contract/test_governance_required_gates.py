from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'gates'


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

def test_finish_success_cannot_bypass_required_gates(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'FG1')
    reconcile_task(tmp_path, 'FG1')
    with pytest.raises(RuntimeError, match='REQUIRED_GATES_NOT_EXECUTED'):
        finish(tmp_path, 'FG1', 'SUCCESS')
    _abort_if_present(tmp_path, 'FG1')

def test_failed_required_gate_blocks_success(tmp_path: Path):
    _project(tmp_path, {'app_gate': [sys.executable, '-c', 'import sys; sys.exit(3)']})
    _start_changed(tmp_path, 'FG2')
    result = run_gates(tmp_path, 'FG2', timeout=5)
    assert result['status'] == 'FAIL'
    with pytest.raises(RuntimeError, match='REQUIRED_GATES_NOT_PASS'):
        finish(tmp_path, 'FG2', 'SUCCESS')
    _abort_if_present(tmp_path, 'FG2')

def test_missing_required_gate_result_blocks_success(tmp_path: Path):
    _project(tmp_path, two_gates=True)
    _start_changed(tmp_path, 'FG3')
    result = run_gates(tmp_path, 'FG3', timeout=5)
    assert result['status'] == 'PASS'
    report_path = gate_results_path(tmp_path, 'FG3')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    report['results'] = [x for x in report['results'] if x['gate'] != 'second_gate']
    report_path.write_text(json.dumps(report), encoding='utf-8')
    with pytest.raises(RuntimeError, match='REQUIRED_GATE_RESULT_MISSING'):
        finish(tmp_path, 'FG3', 'SUCCESS')
    _abort_if_present(tmp_path, 'FG3')

def test_all_required_gates_pass_allows_success(tmp_path: Path):
    _project(tmp_path, two_gates=True)
    _start_changed(tmp_path, 'FG4')
    result = run_gates(tmp_path, 'FG4', timeout=5)
    assert result['status'] == 'PASS'
    finish(tmp_path, 'FG4', 'SUCCESS')
    assert not (tmp_path / '.tmp/agent-governance/FG4').exists()
