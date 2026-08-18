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

def test_same_file_post_gate_modification_invalidates_pass(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'GF1')
    assert run_gates(tmp_path, 'GF1', timeout=5)['status'] == 'PASS'
    _write(tmp_path / 'src/a.py', 'x = 3\n')
    with pytest.raises(RuntimeError, match='GATE_RESULT_STALE'):
        finish(tmp_path, 'GF1', 'SUCCESS')
    _abort_if_present(tmp_path, 'GF1')

def test_added_file_post_gate_modification_invalidates_pass(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'GF2')
    assert run_gates(tmp_path, 'GF2', timeout=5)['status'] == 'PASS'
    _write(tmp_path / 'src/new.py', 'y = 1\n')
    assert reconcile_task(tmp_path, 'GF2')['status'] == 'PASS'
    with pytest.raises(RuntimeError, match='GATE_RESULT_STALE'):
        finish(tmp_path, 'GF2', 'SUCCESS')
    _abort_if_present(tmp_path, 'GF2')

def test_deleted_file_post_gate_modification_invalidates_pass(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'GF3')
    assert run_gates(tmp_path, 'GF3', timeout=5)['status'] == 'PASS'
    (tmp_path / 'src/a.py').unlink()
    with pytest.raises(RuntimeError, match='GATE_RESULT_STALE'):
        finish(tmp_path, 'GF3', 'SUCCESS')
    _abort_if_present(tmp_path, 'GF3')

def test_unchanged_workspace_keeps_gate_pass_current(tmp_path: Path):
    _project(tmp_path)
    _start_changed(tmp_path, 'GF4')
    assert run_gates(tmp_path, 'GF4', timeout=5)['status'] == 'PASS'
    finish(tmp_path, 'GF4', 'SUCCESS')
