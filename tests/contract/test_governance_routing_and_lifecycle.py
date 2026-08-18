from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'routing'

import shutil
from pathlib import Path
import pytest

from tools.governance.governance_lite_validator import validate
from tools.governance import impact_scan as impact_scan_module
from tools.governance.impact_scan import load_domain_metadata, scan
from tools.governance.required_gate_runner import (
    formal_gate_ids,
    runtime_supported_formal_gate_ids,
)
from tools.governance.task_context import cleanup_task, load_context, save_context, task_dir
from tools.governance.task_governance import lifecycle, start, finish

ROOT = Path(__file__).resolve().parents[2]


def _scan(task_id: str, request: str, seeds: list[str]):
    try:
        return scan(ROOT, task_id, request, seeds)
    finally:
        # scan may reject before creating a task; cleanup is safe for valid IDs.
        if '..' not in task_id and '/' not in task_id and '\\' not in task_id:
            cleanup_task(ROOT, task_id)


def test_auth_backend_routes_precisely():
    out = _scan('CT01', '修改认证后端逻辑', ['services/api/src/platform_api/auth_service.py'])
    assert {'BACKEND', 'AUTHENTICATION'} <= set(out['domains'])
    assert 'docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml' in out['authorities']
    assert 'AUTH_MYSQL_RUNTIME_GATE' in out['required_gates']
    assert 'backend_test' in out['required_gates']
    assert len(out['authorities']) < 10
    assert 'services/api/.governance-domain.yaml' in out['domain_metadata_used']
    assert any(x.startswith('services/api/tests/') for x in out['relevant_tests'])


def test_auth_frontend_routes_browser_gate():
    out = _scan('CT02', '修改登录页面认证交互', ['apps/web/src/views/LoginView.vue'])
    assert {'FRONTEND', 'AUTHENTICATION'} <= set(out['domains'])
    assert 'AUTH_BROWSER_RUNTIME_GATE' in out['required_gates']
    assert 'frontend_test' in out['required_gates']
    assert 'docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml' in out['authorities']
    assert 'services/api' in out['dependencies']


def test_readme_change_does_not_default_to_backend():
    out = _scan('CT03', '修改 README 文案', ['README.md'])
    assert 'BACKEND' not in out['domains']
    assert 'backend_test' not in out['required_gates']
    assert out['review_triggers'] == []


def test_authority_lifecycle_routes_precisely_and_preserves_product_sovereignty():
    target = 'docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml'
    out = _scan('CT04', '调整用户生命周期规则', [target])
    assert target in out['authorities']
    assert len(out['authorities']) <= 2
    assert 'product_sovereignty_reviewer' in out['review_triggers']
    assert 'LIFECYCLE' in out['sovereignty_categories']


def test_new_state_triggers_product_sovereignty():
    target = 'docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml'
    out = _scan('CT05', '新增用户状态', [target])
    assert 'STATE' in out['sovereignty_categories']
    assert out['product_decision_mode'] == 'PRODUCT_DECISION_REQUIRED'


def test_resource_conflict_change_triggers_product_sovereignty():
    target = 'docs/authority/权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml'
    out = _scan('CT06', '调整资源冲突规则', [target])
    assert 'RESOURCE_CONFLICT' in out['sovereignty_categories']
    assert 'product_sovereignty_reviewer' in out['review_triggers']


def test_data_retention_change_triggers_without_exact_phrase():
    target = 'docs/authority/数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml'
    out = _scan('CT07', '把数据保存期限从 30 天调整到 90 天', [target])
    assert 'DATA_RETENTION' in out['sovereignty_categories']
    assert 'product_sovereignty_reviewer' in out['review_triggers']


def test_public_contract_change_triggers_product_sovereignty():
    target = 'docs/authority/编码权威事实/OPENAPI/openapi.yaml'
    out = _scan('CT08', '调整公开产品 API 行为', [target])
    assert 'PUBLIC_PRODUCT_CONTRACT' in out['sovereignty_categories']
    assert 'product_sovereignty_reviewer' in out['review_triggers']
    assert 'openapi_client_check' in out['required_gates']


def test_migration_uses_canonical_full_schema_gate():
    target = 'docs/authority/编码权威事实/DATABASE_DDL/V8__retire_platform_design_baseline_release.sql'
    out = _scan('CT09', '新增数据库 Migration', [target])
    assert 'FULL_SCHEMA_MYSQL84_RUNTIME_GATE' in out['required_gates']
    assert 'mysql_full_schema_gate' not in out['required_gates']


def test_user_visible_behavior_requires_real_acceptance_gate():
    out = _scan('CT10', '修改用户可见业务行为', ['apps/web/src/App.vue'])
    assert 'REAL_ACCEPTANCE_GATE' in out['required_gates']
    assert any('ACCEPTANCE_CLOSURE' in p for p in out['authorities'])


def test_task_id_path_escape_is_rejected(tmp_path: Path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    marker = outside / 'keep.txt'
    marker.write_text('keep', encoding='utf-8')
    for bad in ('../../outside', '..', '.', '', '/absolute', 'a\\b', 'bad\nvalue'):
        with pytest.raises(ValueError, match='INVALID_TASK_ID'):
            task_dir(tmp_path, bad)
    with pytest.raises(ValueError, match='INVALID_TASK_ID'):
        start(tmp_path, '../../outside', 'bad task', [])
    assert marker.read_text(encoding='utf-8') == 'keep'


def _minimal_repo(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('demo', encoding='utf-8')


def test_success_cleanup_removes_task_state(tmp_path: Path):
    _minimal_repo(tmp_path)
    with lifecycle(tmp_path, 'NORMAL', '修改 README 文案', ['README.md']):
        assert task_dir(tmp_path, 'NORMAL').exists()
    assert not task_dir(tmp_path, 'NORMAL').exists()


def test_failure_cleanup_removes_task_state(tmp_path: Path):
    _minimal_repo(tmp_path)
    with pytest.raises(RuntimeError):
        with lifecycle(tmp_path, 'FAIL', '修改 README 文案', ['README.md']):
            raise RuntimeError('synthetic')
    assert not task_dir(tmp_path, 'FAIL').exists()


def test_cancel_cleanup_and_stale_task_cleanup(tmp_path: Path):
    _minimal_repo(tmp_path)
    save_context(tmp_path, 'OLD', {'phase': 'abandoned', 'task_pid': 99999999, 'task_status': 'ACTIVE'})
    start(tmp_path, 'NEW', '修改 README 文案', ['README.md'])
    assert not task_dir(tmp_path, 'OLD').exists()
    assert task_dir(tmp_path, 'NEW').exists()
    finish(tmp_path, 'NEW', 'ABORTED')
    try:
        with lifecycle(tmp_path, 'CANCEL', '修改 README 文案', ['README.md']):
            raise KeyboardInterrupt()
    except KeyboardInterrupt:
        pass
    assert not task_dir(tmp_path, 'CANCEL').exists()


def test_low_risk_backend_bugfix_has_no_reviewer():
    out = _scan('CT15', 'small backend bugfix', ['services/api/src/platform_api/health.py'])
    assert out['review_triggers'] == []
    assert 'backend_test' in out['required_gates']


def test_security_sensitive_code_triggers_quality_lane():
    out = _scan('CT16', '修复认证代码 bug', ['services/api/src/platform_api/auth_service.py'])
    assert 'code_quality_reviewer' in out['review_triggers']
    assert 'SECURITY_SENSITIVE' in out['review_profiles']


def test_cross_module_change_expands_scope_and_triggers_architecture_review():
    out = _scan(
        'CT17',
        '跨 Backend Frontend API 修改',
        ['services/api/src/platform_api/health.py', 'apps/web/src/App.vue', 'docs/authority/编码权威事实/OPENAPI/openapi.yaml'],
    )
    assert {'BACKEND', 'FRONTEND', 'API_CONTRACT'} <= set(out['domains'])
    assert 'architecture_reviewer' in out['review_triggers']
    assert {'backend_test', 'frontend_test', 'openapi_client_check'} <= set(out['required_gates'])


def test_expert_capability_reference_files_exist():
    refs = ROOT / '.agents/skills/code-quality/references'
    expected = {'review-lanes.md', 'business-ui-review.md', 'comments-and-docstrings.md'}
    assert expected <= {p.name for p in refs.glob('*.md')}
    old_agent_stems = {
        'frontend_implementer', 'backend_implementer', 'database_integrity_reviewer',
        'security_rbac_reviewer', 'ui_verifier', 'contract_guardian',
    }
    current = {p.stem for p in (ROOT / '.codex/agents').glob('*.toml')}
    assert not (old_agent_stems & current)



def test_all_product_sovereignty_categories_are_routable():
    cases = [
        ('SOV_ROLE', '调整角色规则', 'docs/authority/编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml', 'ROLE'),
        ('SOV_PERMISSION', '调整权限规则', 'docs/authority/编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml', 'PERMISSION'),
        ('SOV_STATE', '新增状态', 'docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml', 'STATE'),
        ('SOV_SM', '调整状态机', 'docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml', 'STATE_MACHINE'),
        ('SOV_RULE', '调整核心业务规则', 'docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml', 'BUSINESS_RULE'),
        ('SOV_LIFE', '调整生命周期', 'docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml', 'LIFECYCLE'),
        ('SOV_CONFLICT', '调整资源冲突', 'docs/authority/权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml', 'RESOURCE_CONFLICT'),
        ('SOV_RETENTION', '把保存期限改为 90 天', 'docs/authority/数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml', 'DATA_RETENTION'),
        ('SOV_SECURITY', '调整正式安全规则', 'docs/authority/数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml', 'PRODUCT_SECURITY_RULE'),
        ('SOV_PUBLIC', '调整公开产品契约', 'docs/authority/编码权威事实/OPENAPI/openapi.yaml', 'PUBLIC_PRODUCT_CONTRACT'),
        ('SOV_REMOVE', '删除正式能力', 'docs/authority/产品总体需求与系统边界/产品总体需求与系统边界.yaml', 'FORMAL_CAPABILITY_REMOVAL'),
    ]
    for task_id, request, seed, category in cases:
        out = _scan(task_id, request, [seed])
        assert category in out['sovereignty_categories'], (task_id, out)
        assert 'product_sovereignty_reviewer' in out['review_triggers']


def test_request_path_becomes_seed_candidate_without_explicit_seed():
    out = _scan('REQPATH', '请修改 `services/api/src/platform_api/auth_service.py` 的认证错误处理', [])
    assert 'services/api/src/platform_api/auth_service.py' in out['seed_candidates']
    assert 'AUTH_MYSQL_RUNTIME_GATE' in out['required_gates']


def test_impact_scan_does_not_use_git_changed_files_as_seed_candidates():
    assert not hasattr(impact_scan_module, '_git_changed_files')
    out = _scan('CHANGED', '修复当前修改', [])
    assert out['changed_files_source'] == 'LOCAL_WORKSPACE_BASELINE'


def test_all_governance_domain_metadata_files_are_loaded():
    loaded = {r.meta_path for r in load_domain_metadata(ROOT)}
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob('*.governance-domain.yaml')
        if '.tmp' not in p.parts
    } | {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob('.governance-domain.yaml')
        if '.tmp' not in p.parts
    }
    assert on_disk == loaded


def test_task_temp_root_symlink_escape_is_rejected(tmp_path: Path):
    outside = tmp_path / 'outside-dir'
    outside.mkdir()
    (tmp_path / '.tmp').mkdir()
    (tmp_path / '.tmp/agent-governance').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='TASK_PATH_OUTSIDE_GOVERNANCE_TMP'):
        task_dir(tmp_path, 'SAFE')


def test_formal_runtime_gate_ids_are_authority_driven_and_aligned():
    assert formal_gate_ids(ROOT) == runtime_supported_formal_gate_ids(ROOT)
    assert {
        'AUTH_MYSQL_RUNTIME_GATE', 'AUTH_BROWSER_RUNTIME_GATE',
        'FULL_SCHEMA_MYSQL84_RUNTIME_GATE', 'REAL_ACCEPTANCE_GATE',
    } <= formal_gate_ids(ROOT)


def test_governance_domain_metadata_is_actively_consumed():
    out = _scan('META', '修改认证后端逻辑', ['services/api/src/platform_api/auth_service.py'])
    assert 'services/api/.governance-domain.yaml' in out['domain_metadata_used']
    assert any(x.startswith('services/api/tests/') for x in out['relevant_tests'])


def test_task_start_uses_local_workspace_baseline_not_git_head(tmp_path: Path):
    _minimal_repo(tmp_path)
    start(tmp_path, 'BASELINE', '修改 README 文案', ['README.md'])
    try:
        ctx = load_context(tmp_path, 'BASELINE')
        assert ctx['changed_files_source'] == 'LOCAL_WORKSPACE_BASELINE'
        assert 'task_start_commit' not in ctx
        snapshot = tmp_path / '.tmp/agent-governance/BASELINE/workspace-start.json'
        payload = __import__('json').loads(snapshot.read_text(encoding='utf-8'))
        assert payload['source'] == 'LOCAL_WORKSPACE_BASELINE'
        assert payload['schema_version'] == 2
        assert {'size', 'mtime_ns', 'file_state'} <= set(payload['files']['README.md'])
    finally:
        finish(tmp_path, 'BASELINE', 'ABORTED')


def test_governance_lite_validator_limits_its_claim_to_structure():
    result = validate(ROOT)
    assert result['status'] == 'PASS', result
    assert result['validation_scope'] == 'AGENT_SKILL_PROFILE_RUNTIME_STRUCTURE'
    assert result['semantic_complete'] is False
    assert result['contract_tests_required'] is True


def test_unclassifiable_request_falls_back_repository_and_recomputes_real_metadata():
    out = _scan('UNKNOWNREQ', '处理一个无法定位的异常', [])
    assert out['scope_level'] == 'REPOSITORY'
    assert out['affected_files']
    assert out['domains']
    assert out['required_gates']
    assert out['metadata_finalized_after_scope'] is True


def test_domain_metadata_declared_references_are_not_dead_or_dangling():
    import fnmatch
    files = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '.tmp' not in p.parts}
    for record in load_domain_metadata(ROOT):
        for value in [*record.depends_on, *record.authorities, *record.tests, *record.authority_files]:
            if any(ch in value for ch in '*?['):
                assert any(fnmatch.fnmatch(f, value) for f in files), (record.meta_path, value)
            else:
                path = ROOT / value
                assert path.exists() or any(f.startswith(value.rstrip('/') + '/') for f in files), (record.meta_path, value)


def test_runtime_gate_catalog_commands_and_ids_have_no_alias_drift():
    from tools.governance.required_gate_runner import ENGINEERING_GATE_COMMANDS, load_runtime_gate_catalog
    catalog = load_runtime_gate_catalog(ROOT)
    for gate_id, item in catalog.items():
        command = str(item['command'])
        if command == 'task-specific acceptance tests':
            continue
        parts = command.split()
        if parts and parts[0].startswith('python') and len(parts) > 1:
            assert (ROOT / parts[1]).is_file(), (gate_id, command)
    assert 'mysql_full_schema_gate' not in ENGINEERING_GATE_COMMANDS


def test_repo_wide_governance_cross_references_have_no_dangling_paths():
    import re
    patterns = (
        r'tools/governance/[A-Za-z0-9_-]+\.py',
        r'\.codex/agents/[A-Za-z0-9_-]+\.toml',
        r'\.agents/skills/[A-Za-z0-9_-]+/SKILL\.md',
        r'\.agents/skills/[A-Za-z0-9_-]+/references/[A-Za-z0-9_.-]+\.md',
        r'\.agents/agent-roles/[A-Za-z0-9_-]+\.md',
    )
    roots = [ROOT / 'AGENTS.md', ROOT / 'README.md', ROOT / '.agents', ROOT / '.codex', ROOT / '.github', ROOT / 'tools', ROOT / 'docs']
    errors = []
    for base in roots:
        paths = [base] if base.is_file() else [p for p in base.rglob('*') if p.is_file()]
        for path in paths:
            if path.suffix.lower() not in {'.md', '.py', '.yaml', '.yml', '.json', '.toml', '.txt'} and path.name not in {'AGENTS.md', 'README.md'}:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in patterns:
                for ref in re.findall(pattern, text):
                    if not (ROOT / ref).is_file():
                        errors.append(f'{path.relative_to(ROOT)} -> {ref}')
    assert not errors, errors[:20]
