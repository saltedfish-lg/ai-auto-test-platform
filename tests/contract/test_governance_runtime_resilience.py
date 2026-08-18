from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'runtime-resilience'

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools.governance import required_gate_runner
from tools.governance.authority_lock import acquire, cleanup_stale as cleanup_stale_lock, current_owner, release
from tools.governance.impact_scan import load_domain_metadata, scan
from tools.governance.incremental_closure import expand
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


def _save_gate_context(tmp_path: Path, task_id: str, gate: str) -> None:
    profile = tmp_path / '.governance'
    profile.mkdir(parents=True, exist_ok=True)
    command = '[definitely-not-a-real-executable-xyz]' if gate == 'missing_gate' else '[python, -c, "print(1)"]'
    (profile / 'gates.yaml').write_text(
        f'schema_version: 1\ngates:\n  {gate}:\n    command: {command}\n',
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
