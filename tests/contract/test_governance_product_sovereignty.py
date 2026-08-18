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

def test_product_decision_required_blocks_gate(tmp_path: Path):
    _project(tmp_path)
    ctx = _start_changed(tmp_path, 'PB1', '新增角色并改为允许删除 app')
    assert ctx['product_decision_status'] == 'REQUIRED'
    reconcile_task(tmp_path, 'PB1')
    report = run_required(tmp_path, 'PB1', timeout=5)
    assert report['status'] == 'BLOCKED'
    assert report['reason'] == 'PRODUCT_DECISION_REQUIRED'
    _abort_if_present(tmp_path, 'PB1')

def test_product_decision_required_blocks_finish_success(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'PB2', '新增角色并改为允许删除 app')
    reconcile_task(tmp_path, 'PB2')
    with pytest.raises(RuntimeError, match='PRODUCT_DECISION_REQUIRED'):
        finish(tmp_path, 'PB2', 'SUCCESS')
    _abort_if_present(tmp_path, 'PB2')

def test_resolved_product_decision_allows_gate(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'PB3', '新增角色并改为允许删除 app')
    resolve_product_decision(tmp_path, 'PB3', '用户确认新增角色可删除，并采用现有权限模型。')
    result = run_gates(tmp_path, 'PB3', timeout=5)
    assert result['status'] == 'PASS'
    assert load_context(tmp_path, 'PB3')['product_decision_status'] == 'RESOLVED'
    finish(tmp_path, 'PB3', 'SUCCESS')

def test_not_required_product_decision_does_not_block(tmp_path: Path):
    _project(tmp_path)
    ctx = _start_changed(tmp_path, 'PB4', 'ordinary app maintenance')
    assert ctx['product_decision_status'] == 'NOT_REQUIRED'
    assert run_gates(tmp_path, 'PB4', timeout=5)['status'] == 'PASS'
    finish(tmp_path, 'PB4', 'SUCCESS')
