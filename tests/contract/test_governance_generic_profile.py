from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'workspace'


import json
import os
import subprocess
import sys
from pathlib import Path

from tools.governance.authority_lock import cleanup_stale
from tools.governance.code_quality_gate import run as run_code_quality
from tools.governance.impact_scan import scan
from tools.governance.incremental_closure import expand
from tools.governance import required_gate_runner
from tools.governance.task_context import cleanup_task, load_context, save_context, save_workspace_snapshot
from tools.governance.task_governance import finish, reconcile_task, run_gates, start

ROOT = Path(__file__).resolve().parents[2]


def _write_profile(root: Path) -> None:
    (root / '.governance').mkdir(parents=True, exist_ok=True)
    (root / '.governance/project.yaml').write_text('''schema_version: 1
project:
  name: sample-service
  type: monorepo
runtime:
  use_legacy_domain_metadata: false
  allow_no_gates: false
''', encoding='utf-8')
    (root / '.governance/domains.yaml').write_text('''schema_version: 1
domains:
  BACKEND:
    kind: implementation
    paths: ["server/**"]
    gates: [backend_check]
    authorities: ["authority/backend.yaml"]
  FRONTEND:
    kind: implementation
    paths: ["ui/**"]
    gates: [frontend_check]
    authorities: ["authority/frontend.yaml"]
''', encoding='utf-8')
    (root / '.governance/authorities.yaml').write_text('''schema_version: 1
authorities:
  backend:
    domains: [BACKEND]
    paths: [authority/backend.yaml]
  frontend:
    domains: [FRONTEND]
    paths: [authority/frontend.yaml]
''', encoding='utf-8')
    (root / '.governance/gates.yaml').write_text('''schema_version: 1
gates:
  backend_check:
    command: [python, -c, "print('backend')"]
  frontend_check:
    command: [python, -c, "print('frontend')"]
  code_quality_gate:
    command: [python, -c, "print('quality')"]
''', encoding='utf-8')
    (root / '.governance/reviewers.yaml').write_text('schema_version: 1\nreviewers: {}\n', encoding='utf-8')
    (root / '.governance/policies.yaml').write_text('schema_version: 1\npolicies: {}\n', encoding='utf-8')
    (root / '.governance/technology.yaml').write_text('''schema_version: 1
technology:
  languages:
    python:
      paths: ["**/*.py"]
      adapter: python
  adapters:
    python:
      checks: [no_unresolved_todo, python_syntax]
    generic:
      checks: [no_unresolved_todo]
''', encoding='utf-8')
    for rel in ('server/a.py', 'server/b.py', 'ui/main.tsx', 'authority/backend.yaml', 'authority/frontend.yaml'):
        path = root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('x\n', encoding='utf-8')


def test_scope_expansion_recomputes_metadata_from_final_files(tmp_path: Path):
    _write_profile(tmp_path)
    out = scan(tmp_path, 'P101', 'small backend change', ['server/a.py'])
    assert out['domains'] == ['BACKEND']
    assert 'backend_check' in out['required_gates']
    module = expand(tmp_path, 'P101', [], unknown=True)
    assert module['scope_level'] == 'MODULE'
    assert {'server/a.py', 'server/b.py'} <= set(module['affected_files'])
    repo = expand(tmp_path, 'P101', [], unknown=True)
    assert repo['scope_level'] == 'REPOSITORY'
    assert {'BACKEND', 'FRONTEND'} <= set(repo['domains'])
    assert {'backend_check', 'frontend_check'} <= set(repo['required_gates'])
    assert {'authority/backend.yaml', 'authority/frontend.yaml'} <= set(repo['authorities'])
    assert 'architecture_reviewer' in repo['review_triggers']
    cleanup_task(tmp_path, 'P101')


def test_repository_fallback_recomputes_nonempty_metadata(tmp_path: Path):
    _write_profile(tmp_path)
    out = scan(tmp_path, 'P101B', 'unclassifiable task', [])
    assert out['scope_level'] == 'REPOSITORY'
    assert out['affected_files']
    assert {'BACKEND', 'FRONTEND'} <= set(out['domains'])
    assert {'backend_check', 'frontend_check'} <= set(out['required_gates'])
    assert out['authorities']
    cleanup_task(tmp_path, 'P101B')


def test_stale_recovery_allows_only_one_writer(tmp_path: Path):
    lock = tmp_path / '.tmp/agent-governance/authority.lock'; lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({'task_id': 'DEAD', 'pid': 99999999, 'file': 'x', 'created_at': 'old', 'lock_instance_id': 'stale'}), encoding='utf-8')
    flag = tmp_path / 'go'
    release_flag = tmp_path / 'release'
    worker = r'''
import sys,time
from pathlib import Path
from tools.governance.authority_lock import acquire,release
root=Path(sys.argv[1]); task=sys.argv[2]; flag=Path(sys.argv[3]); release_flag=Path(sys.argv[4])
while not flag.exists(): time.sleep(0.005)
try:
    acquire(root,task,'authority/x.yaml'); print('ACQUIRED',flush=True)
    while not release_flag.exists(): time.sleep(0.005)
    release(root,task)
except RuntimeError as exc: print(str(exc),flush=True)
'''
    env = os.environ.copy(); env['PYTHONPATH'] = os.pathsep.join([str(ROOT), env.get('PYTHONPATH', '')]).rstrip(os.pathsep)
    procs = [subprocess.Popen([sys.executable, '-c', worker, str(tmp_path), task, str(flag), str(release_flag)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for task in ('A', 'B')]
    flag.write_text('go', encoding='utf-8')
    outputs = [proc.stdout.readline() if proc.stdout else '' for proc in procs]
    release_flag.write_text('release', encoding='utf-8')
    for proc in procs:
        out, err = proc.communicate(timeout=10); assert proc.returncode == 0, err; outputs.append(out)
    assert sum('ACQUIRED' in out for out in outputs) == 1, outputs
    cleanup_stale(tmp_path)


def test_code_quality_gate_reads_current_task_affected_files(tmp_path: Path):
    _write_profile(tmp_path)
    unresolved_marker = '# TO' + 'DO unresolved\ndef ok():\n    return 1\n'
    (tmp_path / 'server/a.py').write_text(unresolved_marker, encoding='utf-8')
    save_context(tmp_path, 'QUALITY', {'affected_files': ['server/a.py']})
    result = run_code_quality(tmp_path, 'QUALITY')
    assert result['status'] == 'FAIL'
    assert any(x.get('path') == 'server/a.py' for x in result['findings'])
    cleanup_task(tmp_path, 'QUALITY')


def test_positive_behavior_signal_takes_precedence_over_cosmetic_keyword():
    try:
        out = scan(ROOT, 'BEHAVIORPRIORITY', '样式调整，同时修改登录成功后的路由跳转', ['apps/web/src/views/LoginView.vue', 'apps/web/src/router/index.ts'])
        assert 'ACCEPTANCE' in out['domains']
        assert 'REAL_ACCEPTANCE_GATE' in out['required_gates']
    finally:
        cleanup_task(ROOT, 'BEHAVIORPRIORITY')


def test_final_workspace_reconciliation_discovers_extra_file(tmp_path: Path):
    _write_profile(tmp_path)
    start(tmp_path, 'RECON', 'small backend change', ['server/a.py'])
    try:
        (tmp_path / 'ui/new.tsx').write_text('export const added = true\n', encoding='utf-8')
        report = reconcile_task(tmp_path, 'RECON')
        ctx = load_context(tmp_path, 'RECON')
        assert report['status'] == 'PASS'
        assert 'ui/new.tsx' in ctx['affected_files']
        assert 'FRONTEND' in ctx['domains']
        assert 'frontend_check' in ctx['required_gates']
        assert set(ctx['actual_changed_files']) <= set(ctx['affected_files'])
    finally:
        finish(tmp_path, 'RECON', 'ABORTED')


def test_generic_fixture_routes_different_layout_without_runtime_change(tmp_path: Path):
    (tmp_path / '.governance').mkdir(); (tmp_path / 'src/main/java/demo').mkdir(parents=True); (tmp_path / 'ui/src').mkdir(parents=True)
    (tmp_path / 'src/main/java/demo/App.java').write_text('class App {}\n', encoding='utf-8'); (tmp_path / 'ui/src/app.tsx').write_text('export const App = 1\n', encoding='utf-8')
    (tmp_path / '.governance/project.yaml').write_text('schema_version: 1\nproject:\n  name: sample-java-service\n  type: monorepo\nruntime:\n  use_legacy_domain_metadata: false\n  allow_no_gates: false\n', encoding='utf-8')
    (tmp_path / '.governance/domains.yaml').write_text('''schema_version: 1
domains:
  SERVER:
    kind: implementation
    paths: ["src/main/java/**"]
    gates: [java_test]
  CLIENT:
    kind: implementation
    paths: ["ui/src/**"]
    gates: [ui_test]
''', encoding='utf-8')
    (tmp_path / '.governance/gates.yaml').write_text('''schema_version: 1
gates:
  java_test: {command: [python, -c, "print(1)"]}
  ui_test: {command: [python, -c, "print(1)"]}
''', encoding='utf-8')
    out = scan(tmp_path, 'FIXTURE', 'cross module change', ['src/main/java/demo/App.java', 'ui/src/app.tsx'])
    assert {'SERVER', 'CLIENT'} <= set(out['domains'])
    assert {'java_test', 'ui_test'} <= set(out['required_gates'])
    assert 'architecture_reviewer' in out['review_triggers']
    cleanup_task(tmp_path, 'FIXTURE')


def test_domain_request_only_closes_profile_metadata():
    try:
        out = scan(ROOT, 'DOMAIN_ROUTING_TASK', '修改前端登录页面', [])
        assert out['scope_level'] == 'DOMAIN'
        assert {'FRONTEND', 'AUTHENTICATION'} <= set(out['domains'])
        assert 'frontend_test' in out['required_gates']
        assert out['authorities']
        assert out['review_triggers']
    finally:
        cleanup_task(ROOT, 'DOMAIN_ROUTING_TASK')


def test_multi_domain_request_only_merges_metadata():
    try:
        out = scan(ROOT, 'MULTI_DOMAIN_ROUTING_TASK', '修改登录接口以及前端登录跳转', [])
        assert out['scope_level'] == 'DOMAIN'
        assert {'FRONTEND', 'BACKEND', 'AUTHENTICATION'} <= set(out['domains'])
        assert {'frontend_test', 'backend_test'} <= set(out['required_gates'])
        assert out['authorities']
        assert 'architecture_reviewer' in out['review_triggers']
    finally:
        cleanup_task(ROOT, 'MULTI_DOMAIN_ROUTING_TASK')


def test_required_gate_runner_blocks_without_final_reconciliation(tmp_path: Path):
    _write_profile(tmp_path)
    start(tmp_path, 'BYPASS', 'backend change', ['server/a.py'])
    try:
        (tmp_path / 'ui/new.tsx').write_text('export const x = 1\n', encoding='utf-8')
        report = required_gate_runner.run_required(tmp_path, 'BYPASS', timeout=2)
        assert report['status'] == 'BLOCKED'
        assert report['reason'] == 'FINAL_RECONCILIATION_REQUIRED'
    finally:
        finish(tmp_path, 'BYPASS', 'ABORTED')


def test_gate_entrypoint_reconciles_before_running_required_gates(tmp_path: Path):
    _write_profile(tmp_path)
    start(tmp_path, 'AUTORECON', 'backend change', ['server/a.py'])
    try:
        (tmp_path / 'ui/new.tsx').write_text('export const x = 1\n', encoding='utf-8')
        result = run_gates(tmp_path, 'AUTORECON', timeout=5)
        assert result['status'] == 'PASS', result
        ctx = load_context(tmp_path, 'AUTORECON')
        assert ctx['final_reconciliation_status'] == 'PASS'
        assert 'ui/new.tsx' in ctx['affected_files']
    finally:
        finish(tmp_path, 'AUTORECON')


def test_success_finish_requires_final_reconciliation(tmp_path: Path):
    _write_profile(tmp_path)
    start(tmp_path, 'FINISHBLOCK', 'backend change', ['server/a.py'])
    try:
        import pytest
        with pytest.raises(RuntimeError, match='FINAL_RECONCILIATION_REQUIRED'):
            finish(tmp_path, 'FINISHBLOCK')
    finally:
        if (tmp_path / '.tmp/agent-governance/FINISHBLOCK').exists():
            finish(tmp_path, 'FINISHBLOCK', 'ABORTED')


def test_no_configured_gate_is_blocked_by_default(tmp_path: Path):
    (tmp_path / '.governance').mkdir()
    (tmp_path / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: no-gate}\nruntime:\n  allow_no_gates: false\n', encoding='utf-8')
    save_workspace_snapshot(tmp_path, 'NOGATE')
    save_context(tmp_path, 'NOGATE', {'required_gates': [], 'affected_files': [], 'final_reconciliation_status': 'PASS', 'actual_changed_files': []})
    report = required_gate_runner.run_required(tmp_path, 'NOGATE', timeout=2)
    assert report['status'] == 'BLOCKED'
    assert report['reason'] == 'NO_CONFIGURED_GATE'
    cleanup_task(tmp_path, 'NOGATE')


def test_configured_project_with_no_required_gate_can_pass(tmp_path: Path):
    (tmp_path / '.governance').mkdir()
    (tmp_path / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: configured}\nruntime:\n  allow_no_gates: false\n', encoding='utf-8')
    (tmp_path / '.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n', encoding='utf-8')
    save_workspace_snapshot(tmp_path, 'NOREQ')
    save_context(tmp_path, 'NOREQ', {'required_gates': [], 'affected_files': [], 'final_reconciliation_status': 'PASS', 'actual_changed_files': []})
    report = required_gate_runner.run_required(tmp_path, 'NOREQ', timeout=2)
    assert report['status'] == 'PASS'
    assert report['reason'] == 'NO_REQUIRED_GATE'
    cleanup_task(tmp_path, 'NOREQ')


def test_explicit_allow_no_gates_can_pass(tmp_path: Path):
    (tmp_path / '.governance').mkdir()
    (tmp_path / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: zero-gate}\nruntime:\n  allow_no_gates: true\n', encoding='utf-8')
    save_workspace_snapshot(tmp_path, 'ALLOWZERO')
    save_context(tmp_path, 'ALLOWZERO', {'required_gates': [], 'affected_files': [], 'final_reconciliation_status': 'PASS', 'actual_changed_files': []})
    report = required_gate_runner.run_required(tmp_path, 'ALLOWZERO', timeout=2)
    assert report['status'] == 'PASS'
    assert report['reason'] == 'NO_CONFIGURED_GATE_ALLOWED'
    cleanup_task(tmp_path, 'ALLOWZERO')


def test_custom_domain_names_use_kind_instead_of_runtime_name_hardcoding(tmp_path: Path):
    (tmp_path / '.governance').mkdir(); (tmp_path / 'srv').mkdir(); (tmp_path / 'client').mkdir()
    (tmp_path / 'srv/a.go').write_text('package main\n', encoding='utf-8')
    (tmp_path / 'client/a.kt').write_text('class A\n', encoding='utf-8')
    (tmp_path / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: sample-cross-stack}\nruntime:\n  use_legacy_domain_metadata: false\n', encoding='utf-8')
    (tmp_path / '.governance/domains.yaml').write_text('''schema_version: 1
domains:
  SERVER:
    kind: implementation
    paths: ["srv/**"]
    gates: [server_test]
  CLIENT:
    kind: implementation
    paths: ["client/**"]
    gates: [client_test]
''', encoding='utf-8')
    (tmp_path / '.governance/gates.yaml').write_text('''schema_version: 1
gates:
  server_test: {command: [python, -c, "print(1)"]}
  client_test: {command: [python, -c, "print(1)"]}
''', encoding='utf-8')
    out = scan(tmp_path, 'CUSTOMKINDS', 'cross stack change', ['srv/a.go', 'client/a.kt'])
    try:
        assert {'SERVER', 'CLIENT'} <= set(out['domains'])
        assert {'server_test', 'client_test'} <= set(out['required_gates'])
        assert 'architecture_reviewer' in out['review_triggers']
    finally:
        cleanup_task(tmp_path, 'CUSTOMKINDS')


def test_generic_defaults_report_missing_profile_configuration_without_fake_pass(tmp_path: Path):
    (tmp_path / 'README.md').write_text('sample\n', encoding='utf-8')
    out = scan(tmp_path, 'DEFAULTS', 'unclassifiable maintenance', [])
    try:
        assert out['scope_level'] == 'REPOSITORY'
        assert out['affected_files']
        assert out['gate_configuration_status'] == 'NO_CONFIGURED_GATE'
        assert out['authority_configuration_status'] == 'NO_AUTHORITY_CONFIGURED'
    finally:
        cleanup_task(tmp_path, 'DEFAULTS')


def test_project_profile_can_route_custom_reviewer_without_runtime_change(tmp_path: Path):
    _write_profile(tmp_path)
    (tmp_path / '.governance/reviewers.yaml').write_text('''schema_version: 1
reviewers:
  custom_architecture_reviewer:
    trigger:
      domains: [BACKEND]
''', encoding='utf-8')
    out = scan(tmp_path, 'CUSTOMREVIEW', 'small backend change', ['server/a.py'])
    try:
        assert 'custom_architecture_reviewer' in out['review_triggers']
        assert 'architecture_reviewer' not in out['review_triggers']
    finally:
        cleanup_task(tmp_path, 'CUSTOMREVIEW')
