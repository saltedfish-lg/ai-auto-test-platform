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
from tools.governance.project_profile import gate_config
from tools.governance.required_gate_runner import ENGINEERING_GATE_COMMANDS, formal_gate_ids, runtime_supported_formal_gate_ids
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


def test_gate_runner_reports_command_not_found_structurally_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _save_gate_context(tmp_path, 'NF', 'missing_gate')
    monkeypatch.setitem(ENGINEERING_GATE_COMMANDS, 'missing_gate', ['definitely-not-a-real-executable-xyz'])
    report = required_gate_runner.run_required(tmp_path, 'NF', timeout=1)
    assert report['results'][0]['status'] == 'BLOCKED'
    assert report['results'][0]['reason'] == 'COMMAND_NOT_FOUND'
    assert (task_dir(tmp_path, 'NF') / 'gate-results.json').is_file()


def test_gate_runner_reports_permission_error_structurally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _save_gate_context(tmp_path, 'PERM', 'backend_test')
    monkeypatch.setattr(required_gate_runner.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(PermissionError('denied')))
    report = required_gate_runner.run_required(tmp_path, 'PERM', timeout=1)
    assert report['results'][0]['status'] == 'BLOCKED'
    assert report['results'][0]['reason'] == 'PERMISSION_ERROR'


def test_gate_runner_reports_timeout_structurally(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _save_gate_context(tmp_path, 'TIME', 'backend_test')
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(a[0] if a else 'cmd', 1)
    monkeypatch.setattr(required_gate_runner.subprocess, 'run', boom)
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
