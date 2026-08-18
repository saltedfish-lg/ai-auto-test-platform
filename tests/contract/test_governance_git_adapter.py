from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'workspace'


from pathlib import Path
from types import SimpleNamespace

from tools.governance import git_readonly_adapter
from tools.governance.git_readonly_adapter import FORBIDDEN_WRITE_COMMANDS, READ_ONLY_COMMANDS, read_git_summary
from tools.governance.impact_scan import scan
from tools.governance.task_context import cleanup_task


def test_git_adapter_reports_unavailable_outside_git_repository(tmp_path: Path):
    result = read_git_summary(tmp_path)
    assert result['git_auxiliary_status'] == 'unavailable'
    assert result['reason'] in {'NOT_A_GIT_REPOSITORY', 'GIT_EXECUTABLE_UNAVAILABLE'}


def test_git_executable_unavailable_is_auxiliary_only(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(git_readonly_adapter.shutil, 'which', lambda name: None)
    assert read_git_summary(tmp_path) == {
        'git_auxiliary_status': 'unavailable',
        'reason': 'GIT_EXECUTABLE_UNAVAILABLE',
    }


def test_git_adapter_uses_nul_safe_path_commands(tmp_path: Path, monkeypatch):
    (tmp_path / '.git').mkdir()
    monkeypatch.setattr(git_readonly_adapter.shutil, 'which', lambda name: '/usr/bin/git')
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1:3] == ['rev-parse', 'HEAD']:
            out = b'abc123\n'
        elif cmd[1:3] == ['branch', '--show-current']:
            out = b'main\n'
        elif cmd[1] == 'status':
            out = ' M specs/产品规则/规则.yaml'.encode('utf-8') + b'\0'
        elif cmd[1:3] == ['diff', '--name-only']:
            out = 'specs/产品规则/规则.yaml'.encode('utf-8') + b'\0'
        else:
            out = b' 1 file changed\n'
        return SimpleNamespace(returncode=0, stdout=out, stderr=b'')

    monkeypatch.setattr(git_readonly_adapter.subprocess, 'run', fake_run)
    result = read_git_summary(tmp_path)
    assert result['git_auxiliary_status'] == 'available'
    assert result['diff_paths'] == ['specs/产品规则/规则.yaml']
    status_cmd = next(cmd for cmd in calls if cmd[1] == 'status')
    names_cmd = next(cmd for cmd in calls if cmd[1:3] == ['diff', '--name-only'])
    assert '-z' in status_cmd
    assert '-z' in names_cmd


def test_git_adapter_whitelist_has_no_write_commands():
    assert READ_ONLY_COMMANDS.isdisjoint(FORBIDDEN_WRITE_COMMANDS)
    assert {'add', 'commit', 'push', 'reset', 'checkout', 'switch', 'clean'} <= FORBIDDEN_WRITE_COMMANDS


def test_git_presence_does_not_change_impact_routing(tmp_path: Path):
    (tmp_path / '.governance').mkdir()
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/a.py').write_text('x=1\n', encoding='utf-8')
    (tmp_path / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: git-boundary}\nruntime: {use_legacy_domain_metadata: false}\n', encoding='utf-8')
    (tmp_path / '.governance/domains.yaml').write_text('schema_version: 1\ndomains:\n  APP: {kind: implementation, paths: ["src/**"], gates: [check]}\n', encoding='utf-8')
    (tmp_path / '.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n', encoding='utf-8')
    for name, text in {
        'authorities.yaml': 'schema_version: 1\nauthorities: {}\n',
        'reviewers.yaml': 'schema_version: 1\nreviewers: {}\n',
        'policies.yaml': 'schema_version: 1\npolicies: {}\n',
        'technology.yaml': 'schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n',
    }.items():
        (tmp_path / '.governance' / name).write_text(text, encoding='utf-8')
    without_git = scan(tmp_path, 'WITHOUT', 'change app', ['src/a.py'])
    cleanup_task(tmp_path, 'WITHOUT')
    (tmp_path / '.git').mkdir(); (tmp_path / '.git/HEAD').write_text('junk', encoding='utf-8')
    with_git = scan(tmp_path, 'WITH', 'change app', ['src/a.py'])
    cleanup_task(tmp_path, 'WITH')
    for key in ('affected_files', 'domains', 'required_gates', 'review_triggers', 'authorities'):
        assert with_git[key] == without_git[key]
