from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'runtime-resilience'

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.governance import process_identity as pi
from tools.governance.authority_lock import LOCK_NAME as AUTHORITY_LOCK_NAME
from tools.governance.authority_lock import acquire as acquire_authority_lock
from tools.governance.authority_lock import cleanup_stale as cleanup_authority_stale
from tools.governance.authority_lock import release as release_authority_lock
from tools.governance.task_context import cleanup_stale as cleanup_stale_tasks
from tools.governance.task_context import governance_tmp_root, save_context, task_dir
from tools.governance.workspace_writer_lock import LOCK_NAME as WRITER_LOCK_NAME
from tools.governance.workspace_writer_lock import acquire as acquire_writer_lock
from tools.governance.workspace_writer_lock import cleanup_stale as cleanup_writer_stale
from tools.governance.workspace_writer_lock import release as release_writer_lock

ROOT = Path(__file__).resolve().parents[2]
STANDALONE_RUNTIME = ROOT / 'agent-governance-lite/runtime/tools/governance'


def test_live_process_probe_is_non_destructive():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
    try:
        result = pi.inspect_process(child.pid)
        assert result.status == pi.RUNNING_UNVERIFIED
        assert child.poll() is None
        identity = pi.current_process_identity(child.pid)
        if identity.creation_time:
            verified = pi.inspect_process(child.pid, identity.creation_time)
            assert verified.status == pi.RUNNING_MATCH
        assert child.poll() is None
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_dead_pid_reports_not_running():
    child = subprocess.Popen([sys.executable, '-c', 'pass'])
    child.wait(timeout=5)
    assert pi.inspect_process(child.pid).status == pi.NOT_RUNNING


def test_pid_reuse_is_detected_by_creation_identity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pi, '_platform_process_snapshot', lambda pid: pi._ProcessSnapshot(pid, True, creation_time='new-owner'))
    result = pi.inspect_process(12345, 'old-owner')
    assert result.status == pi.PID_REUSED


def test_access_denied_is_conservative(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pi, '_platform_process_snapshot', lambda pid: pi._ProcessSnapshot(pid, None, status=pi.ACCESS_DENIED))
    stale, result = pi.owner_is_mechanically_stale(12345, 'owner')
    assert stale is False
    assert result.status == pi.ACCESS_DENIED


def test_windows_probe_uses_query_only_api_and_not_os_kill():
    source = inspect.getsource(pi._windows_process_snapshot)
    assert 'OpenProcess' in source
    assert 'WaitForSingleObject' in source
    assert 'GetProcessTimes' in source
    assert 'PROCESS_TERMINATE' not in source.replace('never requests PROCESS_TERMINATE', '')
    assert 'os.kill(' not in source
    assert 'TerminateProcess(' not in source


def test_runtime_modules_do_not_implement_direct_os_kill_liveness_probe():
    for base in (ROOT / 'tools/governance', STANDALONE_RUNTIME):
        for path in base.glob('*.py'):
            if path.name in {'process_identity.py', 'governance_lite_validator.py'}:
                continue
            assert 'os.kill(' not in path.read_text(encoding='utf-8', errors='ignore'), path


def test_authority_lock_records_creation_identity_and_preserves_live_owner(tmp_path: Path):
    path = acquire_authority_lock(tmp_path, 'LIVE', 'docs/authority/x.yaml')
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert 'process_creation_time' in payload
    assert cleanup_authority_stale(tmp_path) is False
    assert path.exists()
    release_authority_lock(tmp_path, 'LIVE')


def test_authority_lock_pid_reuse_recovers_without_affecting_current_process(tmp_path: Path):
    lock = governance_tmp_root(tmp_path) / AUTHORITY_LOCK_NAME
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({
        'task_id': 'STALE', 'pid': os.getpid(), 'process_creation_time': 'old-process-identity',
        'file': 'x', 'created_at': 'old', 'lock_instance_id': 'reuse-authority',
    }), encoding='utf-8')
    assert cleanup_authority_stale(tmp_path) is True
    assert not lock.exists()
    assert pi.inspect_process(os.getpid()).status == pi.RUNNING_UNVERIFIED


def test_workspace_writer_lock_records_creation_identity_and_preserves_live_owner(tmp_path: Path):
    path = acquire_writer_lock(tmp_path, 'LIVE', os.getpid())
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert 'process_creation_time' in payload
    assert cleanup_writer_stale(tmp_path) is False
    assert path.exists()
    release_writer_lock(tmp_path, 'LIVE')


def test_workspace_writer_pid_reuse_recovers_without_affecting_current_process(tmp_path: Path):
    lock = governance_tmp_root(tmp_path) / WRITER_LOCK_NAME
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({
        'task_id': 'STALE', 'pid': os.getpid(), 'process_creation_time': 'old-process-identity',
        'created_at': 'old', 'workspace': str(tmp_path), 'mode': 'writer', 'lock_instance_id': 'reuse-writer',
    }), encoding='utf-8')
    assert cleanup_writer_stale(tmp_path) is True
    assert not lock.exists()
    assert pi.inspect_process(os.getpid()).status == pi.RUNNING_UNVERIFIED


def test_task_cleanup_detects_pid_reuse_without_affecting_current_process(tmp_path: Path):
    save_context(tmp_path, 'STALE', {
        'task_pid': os.getpid(),
        'task_process_creation_time': 'old-process-identity',
        'task_status': 'ACTIVE',
    })
    assert task_dir(tmp_path, 'STALE').exists()
    assert cleanup_stale_tasks(tmp_path) == ['STALE']
    assert not task_dir(tmp_path, 'STALE').exists()
    assert pi.inspect_process(os.getpid()).status == pi.RUNNING_UNVERIFIED


def test_legacy_live_lock_without_creation_identity_is_preserved(tmp_path: Path):
    lock = governance_tmp_root(tmp_path) / AUTHORITY_LOCK_NAME
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({
        'task_id': 'LEGACY', 'pid': os.getpid(), 'file': 'x', 'created_at': 'old',
        'lock_instance_id': 'legacy-lock',
    }), encoding='utf-8')
    assert cleanup_authority_stale(tmp_path) is False
    assert lock.exists()



def test_task_start_context_records_owner_creation_identity(tmp_path: Path):
    (tmp_path / 'README.md').write_text('demo\n', encoding='utf-8')
    from tools.governance.impact_scan import scan
    from tools.governance.task_context import cleanup_task
    ctx = scan(tmp_path, 'IDENTITYCTX', 'modify README', ['README.md'], task_owner_pid=os.getpid())
    try:
        assert ctx['task_pid'] == os.getpid()
        if pi.current_process_identity().creation_time:
            assert ctx['task_process_creation_time'] == pi.current_process_identity().creation_time
    finally:
        cleanup_task(tmp_path, 'IDENTITYCTX')

def test_standalone_process_identity_helper_is_synced():
    main = (ROOT / 'tools/governance/process_identity.py').read_text(encoding='utf-8')
    standalone = (STANDALONE_RUNTIME / 'process_identity.py').read_text(encoding='utf-8')
    assert standalone == main
