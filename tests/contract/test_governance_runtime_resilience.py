from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'runtime-resilience'

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from tools.governance import governance_contract_test as contract_test_module, required_gate_runner
from tools.governance.governance_contract_test import (
    DEFAULT_CONTRACT_GROUP_TIMEOUT_SECONDS,
    MAX_CONTRACT_GROUP_TIMEOUT_SECONDS,
    MIN_CONTRACT_GROUP_TIMEOUT_SECONDS,
    _run_isolated_group,
    contract_group_timeout_seconds,
)
from tools.governance.authority_lock import acquire, cleanup_stale as cleanup_stale_lock, current_owner, release
from tools.governance.impact_scan import load_domain_metadata, scan
from tools.governance.incremental_closure import expand
from tools.governance.process_identity import NOT_RUNNING, inspect_process
from tools.governance.project_profile import command_tokens, gate_config
from tools.governance.required_gate_runner import (
    DEFAULT_GATE_TIMEOUT_SECONDS,
    MAX_GATE_TIMEOUT_SECONDS,
    ENGINEERING_GATE_COMMANDS,
    formal_gate_ids,
    runtime_supported_formal_gate_ids,
)
from tools.governance.task_context import cleanup_other_tasks, cleanup_task, governance_tmp_root, save_context, save_workspace_snapshot, task_dir
from tools.governance.task_governance import finish, start

ROOT = Path(__file__).resolve().parents[2]


def _scan(task_id: str, request: str, seeds: list[str]):
    try:
        return scan(ROOT, task_id, request, seeds)
    finally:
        cleanup_task(ROOT, task_id)


def _minimal_repo(root: Path) -> None:
    (root / 'README.md').write_text('demo\n', encoding='utf-8')


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT), env.get('PYTHONPATH', '')]).rstrip(os.pathsep)
    return env


def test_two_processes_compete_on_one_atomic_authority_lock(tmp_path: Path):
    start_flag = tmp_path / 'go'
    worker = r'''
import sys,time
from pathlib import Path
from tools.governance.authority_lock import acquire,release
root=Path(sys.argv[1]); task=sys.argv[2]; flag=Path(sys.argv[3])
while not flag.exists(): time.sleep(0.01)
try:
    acquire(root,task,'docs/authority/x.yaml')
    print('ACQUIRED', flush=True)
    time.sleep(1.5)
    release(root,task)
except RuntimeError as exc:
    print(str(exc), flush=True)
'''
    procs = [
        subprocess.Popen([sys.executable, '-c', worker, str(tmp_path), task, str(start_flag)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_subprocess_env())
        for task in ('LOCKA', 'LOCKB')
    ]
    start_flag.write_text('go', encoding='utf-8')
    outputs = []
    for proc in procs:
        out, err = proc.communicate(timeout=10)
        assert proc.returncode == 0, err
        outputs.append(out.strip())
    assert sum('ACQUIRED' in out for out in outputs) == 1, outputs
    assert sum(('AUTHORITY_LOCK_BUSY' in out or 'AUTHORITY_LOCK_ALREADY_HELD' in out) for out in outputs) == 1, outputs


def test_new_task_does_not_delete_live_authority_lock_owner(tmp_path: Path):
    _minimal_repo(tmp_path)
    worker = r'''
import os,sys,time
from pathlib import Path
from tools.governance.task_context import save_context
from tools.governance.authority_lock import acquire
root=Path(sys.argv[1])
save_context(root,'LIVE',{'task_pid':os.getpid(),'task_status':'ACTIVE'})
acquire(root,'LIVE','docs/authority/live.yaml')
print('READY',flush=True)
time.sleep(20)
'''
    proc = subprocess.Popen([sys.executable, '-c', worker, str(tmp_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_subprocess_env())
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == 'READY'
        start(tmp_path, 'NEW', '修改 README 文案', ['README.md'])
        assert task_dir(tmp_path, 'LIVE').exists()
        owner = current_owner(tmp_path)
        assert owner and owner['task_id'] == 'LIVE'
        finish(tmp_path, 'NEW', 'ABORTED')
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        cleanup_stale_lock(tmp_path)
        cleanup_other_tasks(tmp_path, 'CLEANER')


def test_release_allows_next_task_to_acquire_authority_lock(tmp_path: Path):
    acquire(tmp_path, 'A', 'docs/authority/a.yaml')
    with pytest.raises(RuntimeError, match='AUTHORITY_LOCK_BUSY'):
        acquire(tmp_path, 'B', 'docs/authority/b.yaml')
    release(tmp_path, 'A')
    path = acquire(tmp_path, 'B', 'docs/authority/b.yaml')
    assert path == governance_tmp_root(tmp_path) / 'authority.lock'
    release(tmp_path, 'B')


def test_stale_task_is_cleaned_while_live_task_is_preserved(tmp_path: Path):
    _minimal_repo(tmp_path)
    save_context(tmp_path, 'STALE', {'task_pid': 99999999, 'task_status': 'ACTIVE'})
    save_context(tmp_path, 'LIVE', {'task_pid': os.getpid(), 'task_status': 'ACTIVE'})
    start(tmp_path, 'NEW', '修改 README 文案', ['README.md'])
    try:
        assert not task_dir(tmp_path, 'STALE').exists()
        assert task_dir(tmp_path, 'LIVE').exists()
    finally:
        finish(tmp_path, 'NEW', 'ABORTED')
        cleanup_task(tmp_path, 'LIVE')


def test_default_admin_rule_change_requires_product_decision():
    authority = ROOT / 'docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml'
    assert 'admin不可删除' in authority.read_text(encoding='utf-8')
    out = _scan('SOVFIX1', '把默认 admin 改成允许删除', ['services/api/src/platform_api/user_admin_service.py'])
    assert 'product_sovereignty_reviewer' in out['review_triggers']
    assert out['product_decision_mode'] == 'PRODUCT_DECISION_REQUIRED'


def test_restoring_existing_admin_protection_does_not_reask_product_decision():
    out = _scan('SOVFIX2', '修复 admin 删除校验未生效的 bug', ['services/api/src/platform_api/user_admin_service.py'])
    assert 'product_sovereignty_reviewer' in out['review_triggers']
    assert out['product_decision_mode'] == 'PRODUCT_DECISION_NOT_REQUIRED'


def test_refresh_token_policy_change_requires_product_review():
    out = _scan('SOVFIX3', '把 refresh token 有效期改成 30 天', ['services/api/src/platform_api/session_service.py'])
    assert 'product_sovereignty_reviewer' in out['review_triggers']
    assert out['product_decision_mode'] == 'PRODUCT_DECISION_REQUIRED'
    assert 'PRODUCT_SECURITY_RULE' in out['sovereignty_categories']


def test_equivalent_auth_refactor_and_test_only_change_do_not_force_product_decision():
    refactor = _scan('SOVFIX4A', '普通认证代码等价重构', ['services/api/src/platform_api/auth_service.py'])
    assert 'product_sovereignty_reviewer' in refactor['review_triggers']
    assert refactor['product_decision_mode'] == 'PRODUCT_DECISION_NOT_REQUIRED'
    test_only = _scan('SOVFIX4B', '补充认证单元测试', ['services/api/tests/test_auth_service.py'])
    assert test_only['product_decision_mode'] != 'PRODUCT_DECISION_REQUIRED'


@pytest.mark.parametrize('prompt', [
    '给 users 表增加 last_login_at 字段',
    '修改 users 唯一索引',
    '调整 account_id 外键',
    '把 email 字段改成 nullable',
    '修改 username 字段类型和字段长度',
])
def test_gate_db_schema_semantics_trigger_full_schema_without_migration_keyword(prompt: str):
    out = _scan('DB' + str(abs(hash(prompt)))[:8], prompt, ['services/api/src/platform_api/models.py'])
    assert 'FULL_SCHEMA_MYSQL84_RUNTIME_GATE' in out['required_gates'], out


def test_gate_ui_behavior_change_triggers_real_acceptance():
    out = _scan('UIBEHAVIOR', '修改登录成功后跳转首页', ['apps/web/src/views/LoginView.vue', 'apps/web/src/router/index.ts'])
    assert 'REAL_ACCEPTANCE_GATE' in out['required_gates']


def test_gate_pure_css_does_not_trigger_real_acceptance():
    out = _scan('UICSS', '纯 CSS 调整登录页间距', ['apps/web/src/styles.css'])
    assert 'REAL_ACCEPTANCE_GATE' not in out['required_gates']
    assert 'code_quality_reviewer' not in out['review_triggers']


def test_governance_core_paths_require_validator_and_contract_tests():
    cases = [
        ('GOVAGENTS', '修改 AGENTS 治理规则', ['AGENTS.md']),
        ('GOVSKILL', '修改 Skill', ['.agents/skills/context-efficiency/SKILL.md']),
        ('GOVCODEX', '修改 Agent 配置', ['.codex/agents/default_coder.toml']),
        ('GOVTOOL', '修改治理脚本', ['tools/governance/impact_scan.py']),
    ]
    for task_id, request, seeds in cases:
        out = _scan(task_id, request, seeds)
        assert {'governance_lite_validator', 'governance_contract_test'} <= set(out['required_gates']), out



def test_governance_metadata_change_is_itself_governed():
    out = _scan('GOVMETA', '修改治理 Domain metadata', ['AGENTS.md.governance-domain.yaml'])
    assert {'governance_lite_validator', 'governance_contract_test'} <= set(out['required_gates'])

def test_code_quality_gate_has_normal_high_risk_trigger_path():
    out = _scan('CQGATE', '修复认证授权高风险逻辑', ['services/api/src/platform_api/auth_service.py'])
    assert 'code_quality_reviewer' in out['review_triggers']
    assert 'code_quality_gate' in out['required_gates']


def _save_gate_context(tmp_path: Path, task_id: str, gate: str, command: list[str] | None = None) -> None:
    profile = tmp_path / '.governance'
    profile.mkdir(parents=True, exist_ok=True)
    if command is None:
        command = ['definitely-not-a-real-executable-xyz'] if gate == 'missing_gate' else [sys.executable, '-c', 'print(1)']
    (profile / 'gates.yaml').write_text(
        f'schema_version: 1\ngates:\n  {gate}:\n    command: {json.dumps(command, ensure_ascii=False)}\n',
        encoding='utf-8',
    )
    save_workspace_snapshot(tmp_path, task_id)
    save_context(tmp_path, task_id, {
        'required_gates': [gate], 'affected_files': [], 'relevant_tests': [],
        'final_reconciliation_status': 'PASS', 'actual_changed_files': [],
    })


def _save_gate_set_context(
    tmp_path: Path,
    task_id: str,
    gates: dict[str, dict[str, object]],
) -> None:
    profile = tmp_path / '.governance'
    profile.mkdir(parents=True, exist_ok=True)
    (profile / 'gates.yaml').write_text(
        json.dumps({'schema_version': 1, 'gates': gates}, ensure_ascii=False),
        encoding='utf-8',
    )
    save_workspace_snapshot(tmp_path, task_id)
    save_context(tmp_path, task_id, {
        'required_gates': list(gates), 'affected_files': [], 'relevant_tests': [],
        'final_reconciliation_status': 'PASS', 'actual_changed_files': [],
    })


def _identity_metadata(
    capability: str,
    *,
    runtime_keys: list[str] | None = None,
    database_keys: list[str] | None = None,
) -> dict[str, object]:
    return {
        'capability': capability,
        'runtime_environment_keys': runtime_keys or [],
        'database_environment_keys': database_keys or [],
    }


def test_gate_runner_reports_command_not_found_structurally_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _save_gate_context(tmp_path, 'NF', 'missing_gate')
    monkeypatch.setitem(ENGINEERING_GATE_COMMANDS, 'missing_gate', ['definitely-not-a-real-executable-xyz'])
    report = required_gate_runner.run_required(tmp_path, 'NF', timeout=1)
    assert report['results'][0]['status'] == 'BLOCKED'
    assert report['results'][0]['reason'] == 'COMMAND_NOT_FOUND'
    assert (task_dir(tmp_path, 'NF') / 'gate-results.json').is_file()


def test_gate_runner_reports_permission_error_structurally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _save_gate_context(tmp_path, 'PERM', 'backend_test')
    monkeypatch.setattr(
        required_gate_runner,
        '_execute_command',
        lambda *a, **k: (_ for _ in ()).throw(PermissionError('denied')),
    )
    report = required_gate_runner.run_required(tmp_path, 'PERM', timeout=1)
    assert report['results'][0]['status'] == 'BLOCKED'
    assert report['results'][0]['reason'] == 'PERMISSION_ERROR'


def test_gate_runner_reports_timeout_structurally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _save_gate_context(tmp_path, 'TIME', 'backend_test')
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(a[0] if a else 'cmd', 1)
    monkeypatch.setattr(required_gate_runner, '_execute_command', boom)
    report = required_gate_runner.run_required(tmp_path, 'TIME', timeout=1)
    assert report['results'][0]['status'] == 'TIMEOUT'
    assert report['results'][0]['reason'] == 'TIMEOUT'


def test_gate_runner_captures_utf8_stdout_stderr_and_nonzero_exit(tmp_path: Path):
    command = [
        sys.executable,
        '-c',
        "import sys; print('标准输出中文'); print('标准错误中文', file=sys.stderr); raise SystemExit(7)",
    ]
    _save_gate_context(tmp_path, 'UTF8_OUTPUT', 'unicode_gate', command)
    report = required_gate_runner.run_required(tmp_path, 'UTF8_OUTPUT', timeout=5)
    result = report['results'][0]
    assert result['status'] == 'FAIL'
    assert result['reason'] == 'COMMAND_FAILED'
    assert result['exit_code'] == 7
    assert '标准输出中文' in result['stdout_tail']
    assert '标准错误中文' in result['stderr_tail']


def test_gate_runner_handles_empty_utf8_streams(tmp_path: Path):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    _save_gate_context(tmp_path, 'UTF8_EMPTY', 'empty_gate', command)
    report = required_gate_runner.run_required(tmp_path, 'UTF8_EMPTY', timeout=5)
    result = report['results'][0]
    assert result['status'] == 'PASS'
    assert result['stdout_tail'] == ''
    assert result['stderr_tail'] == ''


def test_gate_runner_redacts_database_secret_before_tail_truncation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    password = 'super-secret-boundary-password'
    database_url = f'mysql+pymysql://user:{password}@localhost:3306/app'
    command = [sys.executable, '-c', f"print({database_url!r} + 'x' * 1990)"]
    monkeypatch.setenv('TEST_DATABASE_URL', database_url)
    _save_gate_context(tmp_path, 'UTF8_REDACTION', 'redaction_gate', command)
    report = required_gate_runner.run_required(tmp_path, 'UTF8_REDACTION', timeout=5)
    result = report['results'][0]
    assert result['status'] == 'PASS'
    assert password not in result['stdout_tail']
    assert password not in json.dumps(report, ensure_ascii=False)


def test_gate_runner_reuses_same_canonical_execution_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', "print('canonical pass')"]
    metadata = _identity_metadata(
        'browser_acceptance',
        runtime_keys=['TEST_RUNTIME_NAMESPACE'],
        database_keys=['TEST_DATABASE_NAMESPACE'],
    )
    _save_gate_set_context(tmp_path, 'DEDUP_SAME', {
        'acceptance_gate': {'command': command, 'execution_identity': metadata},
        'browser_gate': {'command': command, 'execution_identity': metadata},
    })
    monkeypatch.setenv('TEST_RUNTIME_NAMESPACE', 'runtime-a')
    monkeypatch.setenv('TEST_DATABASE_NAMESPACE', 'database-a')
    calls: list[int] = []

    def execute(*args, **kwargs):
        calls.append(int(kwargs['timeout']))
        return subprocess.CompletedProcess(args[0], 0, 'canonical pass\n', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'DEDUP_SAME')
    canonical, reused = report['results']
    assert report['status'] == 'PASS'
    assert calls == [DEFAULT_GATE_TIMEOUT_SECONDS]
    assert canonical['execution_mode'] == 'EXECUTED'
    assert reused['status'] == 'PASS'
    assert reused['execution_mode'] == 'REUSED'
    assert reused['reason'] == 'DUPLICATE_CANONICAL_EXECUTION'
    assert reused['canonical_execution'] == 'acceptance_gate'
    assert reused['canonical_timeout_seconds'] == DEFAULT_GATE_TIMEOUT_SECONDS
    assert reused['execution_identity'] == canonical['execution_identity']
    assert reused['runtime_evidence']['reference'] == 'gate-results.json#/results/0'


@pytest.mark.parametrize('identity_kind', ['runtime', 'database'])
def test_gate_runner_does_not_reuse_same_command_for_different_runtime_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_kind: str,
):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    first_metadata = _identity_metadata(
        'same_capability',
        runtime_keys=['RUNTIME_A'] if identity_kind == 'runtime' else ['SHARED_RUNTIME'],
        database_keys=['DATABASE_A'] if identity_kind == 'database' else [],
    )
    second_metadata = _identity_metadata(
        'same_capability',
        runtime_keys=['RUNTIME_B'] if identity_kind == 'runtime' else ['SHARED_RUNTIME'],
        database_keys=['DATABASE_B'] if identity_kind == 'database' else [],
    )
    _save_gate_set_context(tmp_path, 'DEDUP_RUNTIME', {
        'runtime_a': {
            'command': command,
            'execution_identity': first_metadata,
        },
        'runtime_b': {
            'command': command,
            'execution_identity': second_metadata,
        },
    })
    monkeypatch.setenv('RUNTIME_A', 'one')
    monkeypatch.setenv('RUNTIME_B', 'two')
    monkeypatch.setenv('SHARED_RUNTIME', 'same')
    monkeypatch.setenv('DATABASE_A', 'database-one')
    monkeypatch.setenv('DATABASE_B', 'database-two')
    calls = 0

    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args[0], 0, '', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'DEDUP_RUNTIME')
    assert report['status'] == 'PASS'
    assert calls == 2
    assert [item['execution_mode'] for item in report['results']] == ['EXECUTED', 'EXECUTED']
    identity_field = f'{identity_kind}_identity'
    assert report['results'][0][identity_field] != report['results'][1][identity_field]


def test_gate_runner_defaults_capability_to_gate_id_and_does_not_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    _save_gate_set_context(tmp_path, 'DEDUP_CAPABILITY', {
        'capability_a': {'command': command},
        'capability_b': {'command': command},
    })
    calls = 0

    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args[0], 0, '', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'DEDUP_CAPABILITY')
    assert report['status'] == 'PASS'
    assert calls == 2
    assert [item['capability_identity'] for item in report['results']] == [
        'capability_a', 'capability_b'
    ]


def test_gate_runner_propagates_canonical_failure_to_reused_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', 'raise SystemExit(7)']
    metadata = _identity_metadata('failing_acceptance')
    _save_gate_set_context(tmp_path, 'DEDUP_FAIL', {
        'canonical_gate': {'command': command, 'execution_identity': metadata},
        'reused_gate': {'command': command, 'execution_identity': metadata},
    })
    calls = 0

    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args[0], 7, '', 'failed')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'DEDUP_FAIL')
    canonical, reused = report['results']
    assert report['status'] == 'FAIL'
    assert calls == 1
    assert canonical['status'] == 'FAIL'
    assert reused['status'] == 'FAIL'
    assert reused['reason'] == 'DUPLICATE_CANONICAL_EXECUTION'
    assert reused['canonical_reason'] == 'COMMAND_FAILED'
    assert reused['exit_code'] == 7


def test_gate_runner_execution_identity_does_not_expose_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    password = 'dedup-secret-password'
    database_url = f'mysql+pymysql://user:{password}@localhost:3306/isolated_gate'
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    metadata = _identity_metadata(
        'secret_safe_acceptance', database_keys=['TEST_DATABASE_URL']
    )
    _save_gate_set_context(tmp_path, 'DEDUP_SECRET', {
        'gate_a': {'command': command, 'execution_identity': metadata},
        'gate_b': {'command': command, 'execution_identity': metadata},
    })
    monkeypatch.setenv('TEST_DATABASE_URL', database_url)
    monkeypatch.setattr(
        required_gate_runner,
        '_execute_command',
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '', ''),
    )
    report = required_gate_runner.run_required(tmp_path, 'DEDUP_SECRET')
    serialized = json.dumps(report, ensure_ascii=False)
    assert report['status'] == 'PASS'
    assert report['results'][1]['execution_mode'] == 'REUSED'
    assert password not in serialized
    assert database_url not in serialized


def test_gate_runner_sanitizes_secret_bearing_argv_before_identity_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    password = 'argv-dsn-secret'
    database_url = f'mysql+pymysql://user:{password}@localhost:3306/identity_probe'
    command = [sys.executable, '-c', 'raise SystemExit(0)', database_url]
    metadata = _identity_metadata('argv_secret_safe')
    _save_gate_set_context(tmp_path, 'ARGV_SECRET', {
        'argv_gate_a': {'command': command, 'execution_identity': metadata},
        'argv_gate_b': {'command': command, 'execution_identity': metadata},
    })
    hashed_material: list[object] = []
    original_digest = required_gate_runner._identity_digest

    def capture_digest(value):
        hashed_material.append(value)
        return original_digest(value)

    monkeypatch.setattr(required_gate_runner, '_identity_digest', capture_digest)
    monkeypatch.setattr(
        required_gate_runner,
        '_execute_command',
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '', ''),
    )
    report = required_gate_runner.run_required(tmp_path, 'ARGV_SECRET')
    visible_report = json.dumps(report, ensure_ascii=False)
    identity_material = json.dumps(hashed_material, ensure_ascii=False)
    assert report['status'] == 'PASS'
    assert report['results'][1]['execution_mode'] == 'REUSED'
    assert password not in visible_report
    assert database_url not in visible_report
    assert password not in identity_material
    assert database_url not in identity_material


def test_gate_runner_does_not_reuse_different_command_or_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    metadata = _identity_metadata('command_difference')
    _save_gate_set_context(tmp_path, 'COMMAND_DIFFERENCE', {
        'command_a': {
            'command': [sys.executable, '-c', "print('a')"],
            'execution_identity': metadata,
        },
        'command_b': {
            'command': [sys.executable, '-c', "print('b')"],
            'execution_identity': metadata,
        },
    })
    calls = 0

    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args[0], 0, '', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'COMMAND_DIFFERENCE')
    assert report['status'] == 'PASS'
    assert calls == 2
    assert report['results'][0]['canonical_command_digest'] != report['results'][1]['canonical_command_digest']


def test_gate_runner_missing_declared_identity_key_disables_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    metadata = _identity_metadata(
        'missing_runtime_identity', runtime_keys=['ABSENT_RUNTIME_NAMESPACE']
    )
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    _save_gate_set_context(tmp_path, 'MISSING_IDENTITY', {
        'missing_a': {'command': command, 'execution_identity': metadata},
        'missing_b': {'command': command, 'execution_identity': metadata},
    })
    monkeypatch.delenv('ABSENT_RUNTIME_NAMESPACE', raising=False)
    calls = 0

    def execute(*args, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(args[0], 0, '', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'MISSING_IDENTITY')
    assert report['status'] == 'PASS'
    assert calls == 2
    assert all(not item['execution_reuse_eligible'] for item in report['results'])
    assert all(
        item['missing_identity_environment_keys'] == ['ABSENT_RUNTIME_NAMESPACE']
        for item in report['results']
    )


def test_gate_runner_uses_default_and_capability_specific_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    _save_gate_set_context(tmp_path, 'GATE_TIMEOUTS', {
        'ordinary_gate': {'command': command},
        'governance_contract_capability': {'command': command, 'timeout_seconds': 900},
    })
    observed: list[int] = []

    def execute(*args, **kwargs):
        observed.append(int(kwargs['timeout']))
        return subprocess.CompletedProcess(args[0], 0, '', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'GATE_TIMEOUTS')
    assert report['status'] == 'PASS'
    assert observed == [DEFAULT_GATE_TIMEOUT_SECONDS, 900]
    assert [item['timeout_seconds'] for item in report['results']] == [600, 900]


def test_gate_runner_does_not_reuse_different_effective_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    metadata = _identity_metadata('timeout_identity')
    _save_gate_set_context(tmp_path, 'DIFFERENT_TIMEOUT', {
        'short_timeout': {
            'command': command,
            'execution_identity': metadata,
            'timeout_seconds': 2,
        },
        'long_timeout': {
            'command': command,
            'execution_identity': metadata,
            'timeout_seconds': 3,
        },
    })
    observed: list[int] = []

    def execute(*args, **kwargs):
        observed.append(int(kwargs['timeout']))
        return subprocess.CompletedProcess(args[0], 0, '', '')

    monkeypatch.setattr(required_gate_runner, '_execute_command', execute)
    report = required_gate_runner.run_required(tmp_path, 'DIFFERENT_TIMEOUT')
    assert report['status'] == 'PASS'
    assert observed == [2, 3]
    assert [item['execution_mode'] for item in report['results']] == ['EXECUTED', 'EXECUTED']
    assert report['results'][0]['execution_identity'] != report['results'][1]['execution_identity']


def test_gate_runner_reuses_canonical_timeout_without_passing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    metadata = _identity_metadata('timeout_reuse')
    _save_gate_set_context(tmp_path, 'REUSED_TIMEOUT', {
        'canonical_timeout': {
            'command': command,
            'execution_identity': metadata,
            'timeout_seconds': 2,
        },
        'duplicate_timeout': {
            'command': command,
            'execution_identity': metadata,
            'timeout_seconds': 2,
        },
    })
    calls = 0

    def timeout(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(args[0], kwargs['timeout'])

    monkeypatch.setattr(required_gate_runner, '_execute_command', timeout)
    report = required_gate_runner.run_required(tmp_path, 'REUSED_TIMEOUT')
    canonical, reused = report['results']
    assert report['status'] == 'FAIL'
    assert calls == 1
    assert canonical['status'] == 'TIMEOUT'
    assert reused['status'] == 'TIMEOUT'
    assert reused['status'] != 'PASS'
    assert reused['execution_mode'] == 'REUSED'
    assert reused['reason'] == 'DUPLICATE_CANONICAL_EXECUTION'
    assert reused['canonical_reason'] == 'TIMEOUT'
    assert reused['canonical_timeout_seconds'] == 2


def test_project_profile_declares_acceptance_reuse_and_governance_timeout():
    gates = gate_config(ROOT)
    acceptance = gates['REAL_ACCEPTANCE_GATE']['execution_identity']
    browser = gates['playwright_test']['execution_identity']
    assert acceptance == browser
    assert acceptance['capability'] == 'project_management_browser_acceptance'
    assert acceptance['runtime_environment_keys'] == [
        'PLAYWRIGHT_BASE_URL', 'PLAYWRIGHT_TEST_FILE'
    ]
    assert acceptance['database_environment_keys'] == ['ATP_PROJECT_E2E_CODE']
    assert 'ATP_DATABASE_URL' not in acceptance['database_environment_keys']
    assert gates['governance_contract_test']['timeout_seconds'] >= 900
    template = ROOT / 'agent-governance-lite/templates/project-profile/.governance/gates.yaml'
    template_gates = yaml.safe_load(template.read_text(encoding='utf-8'))['gates']
    assert template_gates['governance_contract_test']['timeout_seconds'] >= 900
    context = {'task_id': 'PROFILE_PROBE', 'affected_files': [], 'relevant_tests': []}
    acceptance_command = required_gate_runner.command_for_gate(
        ROOT, 'REAL_ACCEPTANCE_GATE', context
    )
    browser_command = required_gate_runner.command_for_gate(ROOT, 'playwright_test', context)
    assert command_tokens(gates['REAL_ACCEPTANCE_GATE']['command']) == browser_command
    assert acceptance_command == browser_command


@pytest.mark.parametrize('identity', [
    {'capability': 'valid', 'unknown_field': 'not-allowed'},
    {'capability': ' valid '},
    {'capability': 'valid', 'runtime_environment_keys': ['RUNTIME_ID', 'runtime_id']},
    {'capability': 'valid', 'runtime_environment_keys': [' BAD_NAME']},
    {'capability': 'valid', 'runtime_environment_keys': ['API_TOKEN']},
])
def test_gate_runner_rejects_ambiguous_execution_identity_metadata(
    tmp_path: Path,
    identity: dict[str, object],
):
    _save_gate_set_context(tmp_path, 'INVALID_IDENTITY', {
        'invalid_identity_gate': {
            'command': [sys.executable, '-c', 'raise SystemExit(0)'],
            'execution_identity': identity,
        },
    })
    report = required_gate_runner.run_required(tmp_path, 'INVALID_IDENTITY')
    result = report['results'][0]
    assert report['status'] == 'BLOCKED'
    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'INVALID_EXECUTION_IDENTITY'


def test_gate_runner_reports_capability_timeout_as_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    command = [sys.executable, '-c', 'raise SystemExit(0)']
    _save_gate_set_context(tmp_path, 'CAPABILITY_TIMEOUT', {
        'timed_gate': {'command': command, 'timeout_seconds': 2},
    })

    def timeout(*args, **kwargs):
        assert kwargs['timeout'] == 2
        raise subprocess.TimeoutExpired(args[0], 2)

    monkeypatch.setattr(required_gate_runner, '_execute_command', timeout)
    report = required_gate_runner.run_required(tmp_path, 'CAPABILITY_TIMEOUT')
    result = report['results'][0]
    assert report['status'] == 'FAIL'
    assert result['status'] == 'TIMEOUT'
    assert result['reason'] == 'TIMEOUT'
    assert result['timeout_seconds'] == 2


@pytest.mark.parametrize('invalid', [0, MAX_GATE_TIMEOUT_SECONDS + 1, '900', True])
def test_gate_runner_rejects_invalid_capability_timeout(
    tmp_path: Path,
    invalid: object,
):
    _save_gate_set_context(tmp_path, 'INVALID_CAPABILITY_TIMEOUT', {
        'invalid_timeout_gate': {
            'command': [sys.executable, '-c', 'raise SystemExit(0)'],
            'timeout_seconds': invalid,
        },
    })
    report = required_gate_runner.run_required(tmp_path, 'INVALID_CAPABILITY_TIMEOUT')
    result = report['results'][0]
    assert report['status'] == 'BLOCKED'
    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'INVALID_GATE_TIMEOUT'
    assert result['timeout_seconds'] is None


@pytest.mark.skipif(os.name != 'nt', reason='Windows PATH/PATHEXT behavior')
def test_gate_runner_resolves_bare_windows_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    executable = Path(sys.executable)
    monkeypatch.setenv(
        'PATH',
        os.pathsep.join([str(executable.parent), os.environ.get('PATH', '')]),
    )
    _save_gate_context(
        tmp_path,
        'WINDOWS_BARE_EXECUTABLE',
        'bare_executable_gate',
        [executable.name, '-c', "print('bare executable pass')"],
    )
    report = required_gate_runner.run_required(
        tmp_path,
        'WINDOWS_BARE_EXECUTABLE',
        timeout=5,
    )
    result = report['results'][0]
    assert result['status'] == 'PASS'
    assert 'bare executable pass' in result['stdout_tail']


@pytest.mark.skipif(os.name != 'nt', reason='Windows .cmd wrapper behavior')
def test_gate_runner_resolves_cmd_from_path_and_quotes_metacharacters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    spaced_argument = 'argument with spaces'
    metachar_argument = 'safe&echo.injected>canary.txt'
    canary = tmp_path / 'canary.txt'
    checker = tmp_path / 'check wrapper argument.py'
    checker.write_text(
        'import sys\n'
        'valid = '
        f'sys.argv[1] == {spaced_argument!r} and '
        f'sys.argv[2] == {metachar_argument!r}\n'
        'raise SystemExit(0 if valid else 9)\n',
        encoding='utf-8',
    )
    wrapper_dir = tmp_path / 'command&wrappers'
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / 'gate&probe.cmd'
    wrapper.write_text(
        '@echo off\n'
        f'"{sys.executable}" "{checker}" "%~1" "%~2"\n',
        encoding='utf-8',
    )
    monkeypatch.setenv(
        'PATH',
        os.pathsep.join([str(wrapper_dir), os.environ.get('PATH', '')]),
    )
    monkeypatch.setenv('PATHEXT', '.EXE;.CMD;.BAT')
    _save_gate_context(
        tmp_path,
        'WINDOWS_CMD_PATH',
        'cmd_path_gate',
        ['gate&probe', spaced_argument, metachar_argument],
    )
    report = required_gate_runner.run_required(tmp_path, 'WINDOWS_CMD_PATH', timeout=5)
    assert report['results'][0]['status'] == 'PASS'
    assert not canary.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows .cmd wrapper behavior')
def test_gate_runner_rejects_unsafe_cmd_expansion_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    wrapper_dir = tmp_path / 'command-wrappers'
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / 'gate-probe.cmd'
    wrapper.write_text('@echo off\nexit /b 0\n', encoding='utf-8')
    monkeypatch.setenv(
        'PATH',
        os.pathsep.join([str(wrapper_dir), os.environ.get('PATH', '')]),
    )
    monkeypatch.setenv('PATHEXT', '.EXE;.CMD;.BAT')
    _save_gate_context(
        tmp_path,
        'WINDOWS_CMD_UNSAFE_TOKEN',
        'cmd_unsafe_token_gate',
        ['gate-probe', '%PATH%'],
    )
    report = required_gate_runner.run_required(
        tmp_path,
        'WINDOWS_CMD_UNSAFE_TOKEN',
        timeout=5,
    )
    result = report['results'][0]
    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'OS_EXECUTION_ERROR'


@pytest.mark.skipif(os.name != 'nt', reason='Windows process-tree behavior')
def test_gate_runner_timeout_terminates_windows_cmd_process_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pid_file = tmp_path / 'child pid.txt'
    script = tmp_path / 'spawn child.py'
    script.write_text(
        'import subprocess, sys, time\n'
        'from pathlib import Path\n'
        'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
        'Path(sys.argv[1]).write_text(str(child.pid), encoding="utf-8")\n'
        'time.sleep(30)\n',
        encoding='utf-8',
    )
    wrapper_dir = tmp_path / 'timeout wrappers'
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / 'timeout-probe.cmd'
    wrapper.write_text(
        f'@echo off\n"{sys.executable}" "{script}" "%~1"\n',
        encoding='utf-8',
    )
    monkeypatch.setenv(
        'PATH',
        os.pathsep.join([str(wrapper_dir), os.environ.get('PATH', '')]),
    )
    monkeypatch.setenv('PATHEXT', '.EXE;.CMD;.BAT')
    _save_gate_context(
        tmp_path,
        'WINDOWS_CMD_TIMEOUT',
        'cmd_timeout_gate',
        ['timeout-probe', str(pid_file)],
    )
    report = required_gate_runner.run_required(
        tmp_path,
        'WINDOWS_CMD_TIMEOUT',
        timeout=2,
    )
    assert report['results'][0]['status'] == 'TIMEOUT'
    child_pid = int(pid_file.read_text(encoding='utf-8'))
    deadline = time.time() + 5
    while time.time() < deadline and inspect_process(child_pid).status != NOT_RUNNING:
        time.sleep(0.05)
    assert inspect_process(child_pid).status == NOT_RUNNING


def test_governance_contract_group_timeout_configuration_is_bounded():
    assert DEFAULT_CONTRACT_GROUP_TIMEOUT_SECONDS == 600
    assert DEFAULT_CONTRACT_GROUP_TIMEOUT_SECONDS > 180
    assert contract_group_timeout_seconds({}) == DEFAULT_CONTRACT_GROUP_TIMEOUT_SECONDS
    assert contract_group_timeout_seconds({'ATP_GOVERNANCE_CONTRACT_GROUP_TIMEOUT_SECONDS': str(MIN_CONTRACT_GROUP_TIMEOUT_SECONDS)}) == MIN_CONTRACT_GROUP_TIMEOUT_SECONDS
    assert contract_group_timeout_seconds({'ATP_GOVERNANCE_CONTRACT_GROUP_TIMEOUT_SECONDS': str(MAX_CONTRACT_GROUP_TIMEOUT_SECONDS)}) == MAX_CONTRACT_GROUP_TIMEOUT_SECONDS
    for raw in ('invalid', str(MIN_CONTRACT_GROUP_TIMEOUT_SECONDS - 1), str(MAX_CONTRACT_GROUP_TIMEOUT_SECONDS + 1)):
        with pytest.raises(ValueError):
            contract_group_timeout_seconds({'ATP_GOVERNANCE_CONTRACT_GROUP_TIMEOUT_SECONDS': raw})


def test_governance_contract_group_timeout_is_reported_as_failure(tmp_path: Path):
    test_file = tmp_path / 'tests/contract/test_governance_timeout_probe.py'
    test_file.parent.mkdir(parents=True)
    test_file.write_text('import time\ndef test_slow():\n    time.sleep(2)\n', encoding='utf-8')
    result = _run_isolated_group(tmp_path, 'timeout-probe', [test_file], timeout_seconds=1)
    assert result['group'] == 'timeout-probe'
    assert result['timeout_seconds'] == 1
    assert result['exit_code'] == 124, result
    assert result['reason'] == 'TIMEOUT'


def test_governance_contract_copy_uses_workspace_path_policy(tmp_path: Path):
    policy_dir = tmp_path / '.governance'
    policy_dir.mkdir()
    shutil.copy2(ROOT / '.governance/workspace-path-policy.yaml', policy_dir / 'workspace-path-policy.yaml')
    test_file = tmp_path / 'tests/contract/test_governance_copy_policy_probe.py'
    test_file.parent.mkdir(parents=True)
    excluded = ['.env', '.env.local', 'secret.pem', 'secret.key', '.idea/workspace.xml', 'venv/noise.py', 'outputs/result.json', 'playwright-report/index.html']
    for rel in excluded:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('secret-or-runtime-output', encoding='utf-8')
    (tmp_path / '.env.example').write_text('SAFE_PLACEHOLDER=\n', encoding='utf-8')
    test_file.write_text(
        'from pathlib import Path\n'
        f'EXCLUDED = {excluded!r}\n'
        'def test_copy_policy():\n'
        '    assert Path(".env.example").is_file()\n'
        '    assert not [path for path in EXCLUDED if Path(path).exists()]\n',
        encoding='utf-8',
    )
    result = _run_isolated_group(tmp_path, 'copy-policy-probe', [test_file], timeout_seconds=10)
    assert result['exit_code'] == 0, result


def test_governance_contract_copy_rejects_reparse_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    policy_dir = tmp_path / '.governance'
    policy_dir.mkdir()
    shutil.copy2(ROOT / '.governance/workspace-path-policy.yaml', policy_dir / 'workspace-path-policy.yaml')
    candidate = tmp_path / 'junction-like-directory'
    candidate.mkdir()
    monkeypatch.setattr(contract_test_module, 'is_link_or_reparse', lambda path: path == candidate)
    ignored = contract_test_module._contract_copy_ignore(tmp_path)(str(tmp_path), [candidate.name])
    assert ignored == [candidate.name]


def test_governance_contract_timeout_terminates_child_process_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pid_file = tmp_path / 'child.pid'
    test_file = tmp_path / 'tests/contract/test_governance_process_tree_probe.py'
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        'import os, subprocess, sys, time\n'
        'from pathlib import Path\n'
        'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
        'Path(os.environ["ATP_CONTRACT_CHILD_PID_FILE"]).write_text(str(child.pid), encoding="utf-8")\n'
        'def test_child_process_tree():\n'
        '    time.sleep(30)\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('ATP_CONTRACT_CHILD_PID_FILE', str(pid_file))
    result = _run_isolated_group(tmp_path, 'process-tree-probe', [test_file], timeout_seconds=5)
    assert result['exit_code'] == 124
    child_pid = int(pid_file.read_text(encoding='utf-8'))
    deadline = time.time() + 5
    while time.time() < deadline and inspect_process(child_pid).status != NOT_RUNNING:
        time.sleep(0.05)
    assert inspect_process(child_pid).status == NOT_RUNNING


def test_standalone_runtime_mirrors_current_governance_capabilities():
    runtime = ROOT / 'agent-governance-lite/runtime/tools/governance'
    for name in (
        'code_quality_gate.py',
        'required_gate_runner.py',
        'governance_contract_test.py',
        'impact_scan.py',
        'task_context.py',
        'workspace_path_policy.py',
        'workspace-path-policy.yaml',
    ):
        assert (ROOT / 'tools/governance' / name).read_bytes() == (runtime / name).read_bytes()


def test_task_lifecycle_documentation_has_one_formal_start_entry():
    docs = [
        ROOT / 'AGENTS.md',
        ROOT / '.agents/skills/context-efficiency/SKILL.md',
        ROOT / '.agents/skills/feature-orchestrator/SKILL.md',
    ]
    text = '\n'.join(p.read_text(encoding='utf-8') for p in docs)
    assert 'task_governance.py start' in text
    assert 'python tools/governance/impact_scan.py' not in text
    assert '内部实现/Contract Test 辅助入口' in text


def test_business_ui_profile_is_risk_triggered_not_global():
    ref = ROOT / '.agents/skills/code-quality/references/business-ui-review.md'
    assert ref.is_file()
    major = _scan('BUI1', '新增复杂表单页面并调整信息架构', ['apps/web/src/views/LoginView.vue'])
    assert 'BUSINESS_UI_REVIEW' in major['review_profiles']
    assert 'code_quality_reviewer' in major['review_triggers']
    small = _scan('BUI2', '纯 CSS 调整', ['apps/web/src/styles.css'])
    assert 'BUSINESS_UI_REVIEW' not in small['review_profiles']


def test_gate_registry_and_impact_routing_are_bidirectionally_consistent():
    assert formal_gate_ids(ROOT) == runtime_supported_formal_gate_ids(ROOT)
    metadata_gates: set[str] = set()
    for record in load_domain_metadata(ROOT):
        metadata_gates.update(record.engineering_gates)
        for route in record.routes:
            metadata_gates.update(str(x) for x in route.get('engineering_gates') or [])
    configured_gates = set(ENGINEERING_GATE_COMMANDS) | set(gate_config(ROOT))
    assert metadata_gates <= configured_gates, metadata_gates - configured_gates
    assert 'governance_contract_test' in metadata_gates
    assert 'code_quality_gate' in _scan('GATELIVE', '修复认证高风险逻辑', ['services/api/src/platform_api/auth_service.py'])['required_gates']


def test_no_dead_governance_metadata_for_core_paths():
    owners = {r.owner for r in load_domain_metadata(ROOT)}
    assert {'AGENTS.md', '.agents', '.codex', 'tools/governance'} <= owners


def test_incremental_closure_adds_schema_gate_for_new_schema_dependency():
    task_id = 'INCRDB'
    try:
        scan(ROOT, task_id, '普通后端修改', ['services/api/src/platform_api/health.py'])
        out = expand(ROOT, task_id, ['docs/authority/编码权威事实/DATABASE_DDL/V8__retire_platform_design_baseline_release.sql'])
        assert 'FULL_SCHEMA_MYSQL84_RUNTIME_GATE' in out['required_gates']
    finally:
        cleanup_task(ROOT, task_id)


def test_incremental_closure_adds_acceptance_gate_for_new_ui_behavior_dependency():
    task_id = 'INCRUI'
    try:
        scan(ROOT, task_id, '普通前端修改', ['apps/web/src/styles.css'])
        out = expand(ROOT, task_id, ['apps/web/src/views/LoginView.vue'])
        assert 'REAL_ACCEPTANCE_GATE' in out['required_gates']
    finally:
        cleanup_task(ROOT, task_id)
