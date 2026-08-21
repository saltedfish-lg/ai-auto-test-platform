from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'workspace'


from pathlib import Path

import pytest

from tools.governance.git_readonly_adapter import read_git_summary
from tools.governance.task_context import (
    load_context,
    workspace_change_records_since_start,
    workspace_changes_since_start,
)
from tools.governance.task_governance import finish, run_gates, start


def _profile(root: Path) -> None:
    (root / '.governance').mkdir(parents=True, exist_ok=True)
    (root / 'src').mkdir(parents=True, exist_ok=True)
    (root / '.governance/project.yaml').write_text(
        'schema_version: 1\nproject: {name: workspace-test}\nruntime: {use_legacy_domain_metadata: false}\n',
        encoding='utf-8',
    )
    (root / '.governance/domains.yaml').write_text(
        'schema_version: 1\ndomains:\n  APP: {kind: implementation, paths: ["src/**", "specs/**"], gates: [check]}\n',
        encoding='utf-8',
    )
    (root / '.governance/gates.yaml').write_text(
        'schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n',
        encoding='utf-8',
    )
    for name, text in {
        'authorities.yaml': 'schema_version: 1\nauthorities: {}\n',
        'reviewers.yaml': 'schema_version: 1\nreviewers: {}\n',
        'policies.yaml': 'schema_version: 1\npolicies: {}\n',
        'technology.yaml': 'schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n',
    }.items():
        (root / '.governance' / name).write_text(text, encoding='utf-8')


def _start(root: Path, task_id: str = 'TASK') -> None:
    _profile(root)
    (root / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    start(root, task_id, 'change app', ['src/a.py'])


def test_governance_works_without_git_repository(tmp_path: Path):
    _start(tmp_path, 'NOGIT')
    assert not (tmp_path / '.git').exists()
    (tmp_path / 'src/a.py').write_text('x=200\n', encoding='utf-8')
    result = run_gates(tmp_path, 'NOGIT', timeout=5)
    assert result['status'] == 'PASS', result
    finish(tmp_path, 'NOGIT', 'SUCCESS')


def test_existing_pre_task_file_is_not_current_task_change(tmp_path: Path):
    _profile(tmp_path)
    (tmp_path / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    (tmp_path / 'src/user_existing.py').write_text('already locally edited before task\n', encoding='utf-8')
    start(tmp_path, 'PREEXISTING', 'change app', ['src/a.py'])
    try:
        (tmp_path / 'src/a.py').write_text('x=222\n', encoding='utf-8')
        changed = set(workspace_changes_since_start(tmp_path, 'PREEXISTING'))
        assert 'src/a.py' in changed
        assert 'src/user_existing.py' not in changed
    finally:
        finish(tmp_path, 'PREEXISTING', 'ABORTED')


def test_workspace_baseline_detects_added_file(tmp_path: Path):
    _start(tmp_path, 'ADDED')
    try:
        (tmp_path / 'src/new.py').write_text('new=True\n', encoding='utf-8')
        records = {item['path']: item['change'] for item in workspace_change_records_since_start(tmp_path, 'ADDED')}
        assert records['src/new.py'] == 'ADDED'
    finally:
        finish(tmp_path, 'ADDED', 'ABORTED')


def test_workspace_baseline_detects_modified_file(tmp_path: Path):
    _start(tmp_path, 'MODIFIED')
    try:
        (tmp_path / 'src/a.py').write_text('x=123456\n', encoding='utf-8')
        records = {item['path']: item for item in workspace_change_records_since_start(tmp_path, 'MODIFIED')}
        assert records['src/a.py']['change'] == 'MODIFIED'
        assert len(records['src/a.py']['content_sha256']) == 64
    finally:
        finish(tmp_path, 'MODIFIED', 'ABORTED')


def test_workspace_baseline_detects_deleted_file(tmp_path: Path):
    _profile(tmp_path)
    (tmp_path / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    (tmp_path / 'src/delete_me.py').write_text('remove=True\n', encoding='utf-8')
    start(tmp_path, 'DELETED', 'change app', ['src/a.py'])
    try:
        (tmp_path / 'src/delete_me.py').unlink()
        records = {item['path']: item['change'] for item in workspace_change_records_since_start(tmp_path, 'DELETED')}
        assert records['src/delete_me.py'] == 'DELETED'
    finally:
        finish(tmp_path, 'DELETED', 'ABORTED')


def test_workspace_baseline_handles_unicode_path(tmp_path: Path):
    _profile(tmp_path)
    target = tmp_path / 'specs/产品规则/规则.yaml'
    target.parent.mkdir(parents=True)
    target.write_text('rule: old\n', encoding='utf-8')
    (tmp_path / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    start(tmp_path, 'UNICODE', 'change app', ['src/a.py'])
    try:
        target.write_text('rule: new-value\n', encoding='utf-8')
        records = {item['path']: item['change'] for item in workspace_change_records_since_start(tmp_path, 'UNICODE')}
        assert records['specs/产品规则/规则.yaml'] == 'MODIFIED'
    finally:
        finish(tmp_path, 'UNICODE', 'ABORTED')


def test_transient_pycache_is_not_task_change(tmp_path: Path):
    _start(tmp_path, 'PYCACHE')
    try:
        cache = tmp_path / 'src/__pycache__'; cache.mkdir()
        (cache / 'a.cpython-312.pyc').write_bytes(b'noise')
        assert all('__pycache__' not in path for path in workspace_changes_since_start(tmp_path, 'PYCACHE'))
    finally:
        finish(tmp_path, 'PYCACHE', 'ABORTED')


def test_governance_tmp_runtime_state_is_not_task_change(tmp_path: Path):
    _start(tmp_path, 'TMP')
    try:
        # Task runtime state exists and changes under .tmp by design.
        (tmp_path / '.tmp/agent-governance/TMP/extra-runtime.tmp').write_text('noise', encoding='utf-8')
        assert all(not path.startswith('.tmp/') for path in workspace_changes_since_start(tmp_path, 'TMP'))
    finally:
        finish(tmp_path, 'TMP', 'ABORTED')


def test_workspace_baseline_uses_current_tracking_policy_for_both_sides(tmp_path: Path):
    _profile(tmp_path)
    policy_path = tmp_path / '.governance/workspace-path-policy.yaml'
    policy_text = (Path(__file__).resolve().parents[2] / 'tools/governance/workspace-path-policy.yaml').read_text(
        encoding='utf-8',
    )
    policy_path.write_text(policy_text.replace('    - .idea\n', ''), encoding='utf-8')
    idea_file = tmp_path / '.idea/workspace.xml'
    idea_file.parent.mkdir()
    idea_file.write_text('<project/>\n', encoding='utf-8')
    (tmp_path / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    start(tmp_path, 'POLICY-CHANGE', 'change tracking policy', ['src/a.py'])
    try:
        policy_path.write_text(policy_text, encoding='utf-8')
        changed = set(workspace_changes_since_start(tmp_path, 'POLICY-CHANGE'))
        assert '.governance/workspace-path-policy.yaml' in changed
        assert '.idea/workspace.xml' not in changed
    finally:
        finish(tmp_path, 'POLICY-CHANGE', 'ABORTED')


def test_gate_freshness_is_workspace_content_based_with_fake_git_directory(tmp_path: Path):
    _start(tmp_path, 'DIGEST')
    (tmp_path / '.git').mkdir()
    (tmp_path / '.git/HEAD').write_text('not a real git repo', encoding='utf-8')
    (tmp_path / 'src/a.py').write_text('x=2\n', encoding='utf-8')
    assert run_gates(tmp_path, 'DIGEST', timeout=5)['status'] == 'PASS'
    (tmp_path / 'src/a.py').write_text('x=3\n', encoding='utf-8')
    try:
        finish(tmp_path, 'DIGEST', 'SUCCESS')
    except RuntimeError as exc:
        assert str(exc) == 'GATE_RESULT_STALE'
        finish(tmp_path, 'DIGEST', 'ABORTED')
    else:
        raise AssertionError('workspace content change reused stale Gate PASS')


def test_task_context_declares_local_workspace_as_change_source(tmp_path: Path):
    _start(tmp_path, 'SOURCE')
    try:
        ctx = load_context(tmp_path, 'SOURCE')
        assert ctx['changed_files_source'] == 'LOCAL_WORKSPACE_BASELINE'
        assert 'task_start_commit' not in ctx
    finally:
        finish(tmp_path, 'SOURCE', 'ABORTED')


def test_governance_success_is_unchanged_when_git_executable_is_unavailable(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace
    from tools.governance import git_readonly_adapter
    # Replace the adapter-local module binding instead of mutating the process-global
    # shutil module object, which would also change required_gate_runner.shutil.which.
    monkeypatch.setattr(git_readonly_adapter, 'shutil', SimpleNamespace(which=lambda name: None))
    _start(tmp_path, 'NOGITBIN')
    assert read_git_summary(tmp_path)['git_auxiliary_status'] == 'unavailable'
    (tmp_path / 'src/a.py').write_text('x=999\n', encoding='utf-8')
    result = run_gates(tmp_path, 'NOGITBIN', timeout=5)
    assert result['status'] == 'PASS', result
    finish(tmp_path, 'NOGITBIN', 'SUCCESS')


def test_workspace_path_policy_is_shared_by_tracking_impact_delivery_and_digest(tmp_path: Path):
    from tools.governance.workspace_path_policy import consumer_categories, load_policy
    _profile(tmp_path)
    policy = load_policy(tmp_path)
    expected = {'SOURCE', 'AUTHORITY', 'GENERATED_REQUIRED'}
    for consumer in ('workspace_tracking', 'impact_scan', 'gate_workspace_digest', 'delivery_package'):
        assert consumer_categories(policy, consumer) == expected


def test_workspace_baseline_reports_unicode_added_modified_and_deleted(tmp_path: Path):
    _profile(tmp_path)
    modified = tmp_path / 'specs/产品规则/修改.yaml'; modified.parent.mkdir(parents=True)
    deleted = tmp_path / 'specs/产品规则/删除.yaml'
    modified.write_text('v: old\n', encoding='utf-8')
    deleted.write_text('v: delete\n', encoding='utf-8')
    (tmp_path / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    start(tmp_path, 'UNICODEALL', 'change app', ['src/a.py'])
    try:
        modified.write_text('v: changed-value\n', encoding='utf-8')
        deleted.unlink()
        added = tmp_path / 'specs/权限规则/新增.yaml'; added.parent.mkdir(parents=True); added.write_text('v: new\n', encoding='utf-8')
        records = {item['path']: item['change'] for item in workspace_change_records_since_start(tmp_path, 'UNICODEALL')}
        assert records['specs/产品规则/修改.yaml'] == 'MODIFIED'
        assert records['specs/产品规则/删除.yaml'] == 'DELETED'
        assert records['specs/权限规则/新增.yaml'] == 'ADDED'
    finally:
        finish(tmp_path, 'UNICODEALL', 'ABORTED')


def test_task_start_baseline_does_not_hash_repository_files(tmp_path: Path, monkeypatch):
    from tools.governance import task_context
    _profile(tmp_path)
    content = b'x=1\n'
    (tmp_path / 'src/a.py').write_bytes(content)
    monkeypatch.setattr(task_context, '_workspace_file_hash', lambda path: (_ for _ in ()).throw(AssertionError('baseline must not hash content')))
    path = task_context.save_workspace_snapshot(tmp_path, 'METADATAONLY')
    payload = __import__('json').loads(path.read_text(encoding='utf-8'))
    assert payload['files']['src/a.py']['size'] == len(content)
    task_context.cleanup_task(tmp_path, 'METADATAONLY')


@pytest.mark.parametrize(
    ('task_id', 'original', 'changed'),
    [
        ('NEWLINE_LF', b'x=1\n', b'x=22\n'),
        ('NEWLINE_CRLF', b'x=1\r\n', b'x=22\r\n'),
    ],
)
def test_workspace_tracking_detects_changes_for_lf_and_crlf(
    tmp_path: Path, task_id: str, original: bytes, changed: bytes,
):
    _profile(tmp_path)
    target = tmp_path / 'src/a.py'
    target.write_bytes(original)
    start(tmp_path, task_id, 'change app', ['src/a.py'])
    try:
        target.write_bytes(changed)
        records = {item['path']: item['change'] for item in workspace_change_records_since_start(tmp_path, task_id)}
        assert records['src/a.py'] == 'MODIFIED'
    finally:
        finish(tmp_path, task_id, 'ABORTED')
