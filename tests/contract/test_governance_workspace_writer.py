from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'workspace'

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.contract.governance_test_support import _project
from tools.governance.task_governance import finish, start
from tools.governance.workspace_writer_lock import LOCK_NAME, current_owner


def test_two_writer_tasks_cannot_be_active_in_same_workspace(tmp_path: Path):
    _project(tmp_path)
    module_root = str(Path(__file__).resolve().parents[2])
    holder_code = (
        'import os,sys,time; from pathlib import Path; '
        f'sys.path.insert(0,{module_root!r}); '
        'from tools.governance.task_governance import start,finish; '
        'root=Path(sys.argv[1]); start(root,"WRITER_A","change app",["src/a.py"],owner_pid=os.getpid(),mode="writer"); '
        'print("ACQUIRED",flush=True); time.sleep(4); finish(root,"WRITER_A","ABORTED")'
    )
    holder = subprocess.Popen([sys.executable, '-c', holder_code, str(tmp_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == 'ACQUIRED'
        with pytest.raises(RuntimeError, match='WORKSPACE_WRITER_BUSY'):
            start(tmp_path, 'WRITER_B', 'change app', ['src/a.py'], owner_pid=os.getpid(), mode='writer')
    finally:
        holder.terminate()
        try:
            holder.wait(timeout=3)
        except subprocess.TimeoutExpired:
            holder.kill(); holder.wait(timeout=3)


def test_readonly_reviewer_can_coexist_with_writer(tmp_path: Path):
    _project(tmp_path)
    start(tmp_path, 'WRITER', 'change app', ['src/a.py'], mode='writer')
    try:
        readonly = start(tmp_path, 'REVIEWER', 'review app change', ['src/a.py'], mode='readonly')
        assert readonly['task_mode'] == 'readonly'
        owner = current_owner(tmp_path)
        assert owner and owner['task_id'] == 'WRITER'
        finish(tmp_path, 'REVIEWER', 'ABORTED')
        assert current_owner(tmp_path)['task_id'] == 'WRITER'
    finally:
        finish(tmp_path, 'WRITER', 'ABORTED')


def test_second_writer_can_start_after_first_finishes(tmp_path: Path):
    _project(tmp_path)
    start(tmp_path, 'FIRST', 'change app', ['src/a.py'], mode='writer')
    finish(tmp_path, 'FIRST', 'ABORTED')
    ctx = start(tmp_path, 'SECOND', 'change app', ['src/a.py'], mode='writer')
    try:
        assert ctx['task_mode'] == 'writer'
        assert current_owner(tmp_path)['task_id'] == 'SECOND'
    finally:
        finish(tmp_path, 'SECOND', 'ABORTED')


def test_stale_workspace_writer_lock_is_recovered(tmp_path: Path):
    _project(tmp_path)
    base = tmp_path / '.tmp/agent-governance'; base.mkdir(parents=True, exist_ok=True)
    (base / LOCK_NAME).write_text(json.dumps({
        'task_id': 'STALE', 'pid': 99999999, 'created_at': '2000-01-01T00:00:00Z',
        'workspace': str(tmp_path), 'mode': 'writer', 'lock_instance_id': 'stale-instance',
    }), encoding='utf-8')
    ctx = start(tmp_path, 'RECOVERED', 'change app', ['src/a.py'], mode='writer')
    try:
        assert ctx['task_mode'] == 'writer'
        assert current_owner(tmp_path)['task_id'] == 'RECOVERED'
    finally:
        finish(tmp_path, 'RECOVERED', 'ABORTED')
