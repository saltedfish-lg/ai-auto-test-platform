from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import fnmatch
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .project_profile import (
    authority_config,
    gate_config,
    reviewer_config,
    technology_config,
    configured_list,
    configured_mapping,
    configured_request_signals,
    domain_config,
    match_any,
    runtime_config,
)
from .required_gate_runner import formal_gate_ids, formal_gates_for_conditions
from .process_identity import current_process_identity
from .task_context import context_path, save_context, validate_task_id
from .workspace_path_policy import consumer_allows_relative, iter_policy_files, load_policy

# These are generic software-engineering concepts, not project facts. Projects can
# extend/override them through .governance/policies.yaml.
BASE_REQUEST_DOMAIN_SIGNALS: dict[str, tuple[str, ...]] = {}
BASE_SOVEREIGNTY_SIGNALS: dict[str, tuple[str, ...]] = {
    'ROLE': ('新增角色', '修改角色', '角色规则', 'role model'),
    'PERMISSION': ('修改权限', '权限规则', 'permission model', 'rbac 规则'),
    'STATE': ('新增状态', '修改状态', '状态定义'),
    'STATE_MACHINE': ('状态机', '状态转换', 'state machine'),
    'BUSINESS_RULE': ('核心业务规则', '业务规则'),
    'LIFECYCLE': ('生命周期', 'lifecycle'),
    'RESOURCE_CONFLICT': ('资源冲突', '并发冲突', 'resource conflict'),
    'DATA_RETENTION': ('数据保留', '保存期限', '保留期限', 'retention'),
    'PRODUCT_SECURITY_RULE': ('正式安全规则', '产品安全规则', 'security rule'),
    'PUBLIC_PRODUCT_CONTRACT': ('公开产品契约', '公开 api 行为', 'public product contract'),
    'FORMAL_CAPABILITY_REMOVAL': ('删除正式能力', '移除正式能力', '删除功能', 'remove capability'),
}
BASE_HIGH_RISK_SIGNALS = (
    'authentication', '认证', 'authorization', '授权', 'rbac', '并发', '锁', '事务', '异常恢复',
    '重试', '幂等', '核心算法', '大规模重构', 'shared component', '共享组件', '共享库',
    'public api', '公开 api', '测试策略', 'security', '安全敏感',
)
BASE_ARCHITECTURE_SIGNALS = ('新服务', '系统边界', '架构', '核心对象', '大型 schema', '数据一致性', 'architecture')
BASE_USER_VISIBLE_SIGNALS = ('用户可见', '业务行为', 'user-visible', 'user visible behavior')
BASE_BEHAVIOR_SIGNALS = (
    '路由', '跳转', 'redirect', 'navigate', 'api 调用', '接口调用', '网络请求', '表单提交', 'submit',
    '点击行为', '点击', '数据写入', '数据读取', '状态转换', '权限', '登录', '登出', 'token', 'session',
    '业务校验', '事件处理', '交互流程', '数据绑定', '后端逻辑', 'db 变更', 'database change',
)
BASE_NON_BEHAVIOR_SIGNALS = (
    '纯 css', 'css 调整', '样式调整', '视觉间距', '静态文案', '文案修改', '文字修订', '注释',
    '不影响行为的重命名', 'rename only', 'style only',
)
BASE_BEHAVIOR_PATH_PATTERNS = (
    '**/router/**', '**/routes/**', '**/store/**', '**/stores/**', '**/service/**', '**/services/**',
    '**/api/**', '**/controller/**', '**/controllers/**', '**/handler/**', '**/handlers/**',
    '**/model/**', '**/models/**', '**/schema/**', '**/schemas/**', '**/migration/**', '**/migrations/**',
)
BASE_UI_PATH_PATTERNS = ('**/*.vue', '**/*.tsx', '**/*.jsx', '**/views/**', '**/components/**', '**/pages/**')
BASE_SCHEMA_PATH_PATTERNS = ('**/migrations/**', '**/migration/**', '**/*.sql', '**/schema.sql', '**/*schema*.yaml', '**/*schema*.yml')
BASE_SUBSTANTIVE_EXTENSIONS = ('.py', '.ts', '.tsx', '.js', '.jsx', '.vue', '.java', '.kt', '.go', '.rs', '.cs', '.sql', '.yaml', '.yml', '.json')
BASE_SENSITIVE_DOMAIN_CATEGORIES: dict[str, set[str]] = {}
RESTORATIVE_OR_EQUIVALENT_SIGNALS = (
    '修复', '恢复既有', '恢复现有', '未生效', 'bugfix', 'bug fix', '等价重构', '普通重构',
    'refactor without behavior change', '补充测试', '增加测试', 'test only',
)
EXPLICIT_PRODUCT_CHANGE_SIGNALS = (
    '改成', '改为', '允许删除', '禁止删除', '新增状态', '新增用户状态', '修改状态', '删除能力', '移除能力', '有效期',
    '保留时间', '保存期限', '权限改', '角色改', '状态机', '对外行为',
)
DB_SCHEMA_SEMANTIC_PATTERNS = (
    r'(?i)\b(add|drop|alter|modify|change)\b.{0,50}\b(column|table|index|constraint|foreign key)\b',
    r'(?i)\b(nullable|not null|unique index|foreign key|check constraint|varchar\s*\(|column type|field type)\b',
    r'增加.{0,50}(字段|表|索引|外键|约束)',
    r'(删除|修改|调整).{0,50}(字段|表|索引|外键|约束|nullable|字段类型|字段长度)',
    r'(唯一索引|外键|CHECK 约束|字段长度|数据库结构|表结构|nullable)',
)

# Generic gates the Runtime may add on its own. Standalone default profiles must
# provide definitions for this registry; project-defined gates remain Profile-owned.
GENERIC_AUTO_REQUIRED_GATES = frozenset({'code_quality_gate'})


@dataclass
class DomainRecord:
    meta_path: str
    owner: str
    owner_is_file: bool
    inherit: bool
    domains: set[str] = field(default_factory=set)
    depends_on: list[str] = field(default_factory=list)
    authorities: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    engineering_gates: set[str] = field(default_factory=set)
    formal_gate_conditions: set[str] = field(default_factory=set)
    reviewer_risks: set[str] = field(default_factory=set)
    sovereignty_categories: set[str] = field(default_factory=set)
    routes: list[dict[str, Any]] = field(default_factory=list)
    authority_files: list[str] = field(default_factory=list)
    path_patterns: list[str] = field(default_factory=list)
    profile_record: bool = False
    kind: str = ''


def _all_files(root: Path) -> list[str]:
    root = root.resolve()
    policy = load_policy(root)
    return sorted(path.relative_to(root).as_posix() for path in iter_policy_files(root, 'impact_scan', policy))


def _safe_relative(value: str) -> str | None:
    value = value.strip().strip('`"\'').replace('\\', '/')
    if not value or value.startswith('/') or re.match(r'^[A-Za-z]:/', value):
        return None
    parts = [p for p in value.split('/') if p not in ('', '.')]
    if not parts or '..' in parts:
        return None
    return '/'.join(parts)


def _extract_request_paths(root: Path, request: str) -> list[str]:
    del root
    candidates: set[str] = set()
    for token in re.findall(r'`([^`]+)`', request):
        rel = _safe_relative(token)
        if rel:
            candidates.add(rel)
    for token in re.findall(r'(?<![\w.-])((?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/)+[A-Za-z0-9_.\-\u4e00-\u9fff*]+|(?:AGENTS|README)\.md)', request):
        rel = _safe_relative(token)
        if rel:
            candidates.add(rel)
    return sorted(candidates)


def _metadata_owner(root: Path, meta: Path) -> tuple[str, bool]:
    rel = meta.relative_to(root).as_posix()
    if meta.name == '.governance-domain.yaml':
        return meta.parent.relative_to(root).as_posix(), False
    suffix = '.governance-domain.yaml'
    if meta.name.endswith(suffix):
        owner_name = meta.name[:-len(suffix)]
        return (meta.parent / owner_name).relative_to(root).as_posix(), True
    return rel, True


def load_domain_metadata(root: Path) -> list[DomainRecord]:
    """Load the legacy distributed metadata format for backward compatibility."""
    root = root.resolve()
    policy = load_policy(root)
    paths = {
        path for path in iter_policy_files(root, 'impact_scan', policy)
        if path.name == '.governance-domain.yaml' or path.name.endswith('.governance-domain.yaml')
    }
    records: list[DomainRecord] = []
    for meta in sorted(paths):
        try:
            raw = yaml.safe_load(meta.read_text(encoding='utf-8')) or {}
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        owner, owner_is_file = _metadata_owner(root, meta)
        records.append(DomainRecord(
            meta_path=meta.relative_to(root).as_posix(), owner=owner, owner_is_file=owner_is_file,
            inherit=bool(raw.get('inherit', True)), domains={str(x) for x in raw.get('domains') or []},
            depends_on=[str(x) for x in raw.get('depends_on') or []], authorities=[str(x) for x in raw.get('authorities') or []],
            tests=[str(x) for x in raw.get('tests') or []], engineering_gates={str(x) for x in raw.get('engineering_gates') or []},
            formal_gate_conditions={str(x) for x in raw.get('formal_gate_conditions') or []},
            reviewer_risks={str(x) for x in raw.get('reviewer_risks') or []},
            sovereignty_categories={str(x) for x in raw.get('sovereignty_categories') or []},
            routes=[x for x in raw.get('routes') or [] if isinstance(x, dict)],
            authority_files=[str(x) for x in raw.get('authority_files') or []], kind=str(raw.get('kind') or ''),
        ))
    return records


def load_profile_domain_metadata(root: Path) -> list[DomainRecord]:
    records: list[DomainRecord] = []
    for name, raw in domain_config(root).items():
        patterns = [str(x) for x in raw.get('paths') or []]
        owner = str(raw.get('owner_identity') or f'@profile/{name}')
        records.append(DomainRecord(
            meta_path=f'.governance/domains.yaml#{name}', owner=owner, owner_is_file=False, inherit=True,
            domains={name, *(str(x) for x in raw.get('domains') or [])},
            depends_on=[str(x) for x in raw.get('depends_on') or []], authorities=[str(x) for x in raw.get('authorities') or []],
            tests=[str(x) for x in raw.get('tests') or []], engineering_gates={str(x) for x in raw.get('gates') or []},
            formal_gate_conditions={str(x) for x in raw.get('formal_gate_conditions') or []},
            reviewer_risks={str(x) for x in raw.get('reviewer_risks') or []},
            sovereignty_categories={str(x) for x in raw.get('sovereignty_categories') or []},
            routes=[x for x in raw.get('routes') or [] if isinstance(x, dict)],
            authority_files=[str(x) for x in raw.get('authority_files') or []], path_patterns=patterns, profile_record=True,
            kind=str(raw.get('kind') or ''),
        ))
    return records


def _routing_records(root: Path) -> list[DomainRecord]:
    profile = load_profile_domain_metadata(root)
    use_legacy = bool(runtime_config(root).get('use_legacy_domain_metadata', True))
    return profile + (load_domain_metadata(root) if use_legacy else [])


def _record_applies(record: DomainRecord, rel: str) -> bool:
    if record.path_patterns:
        return match_any(rel, record.path_patterns)
    if record.owner_is_file:
        return rel == record.owner
    return rel == record.owner or (record.inherit and rel.startswith(record.owner.rstrip('/') + '/'))


def _route_matches(route: dict[str, Any], record: DomainRecord, rel: str) -> bool:
    patterns = [str(x) for x in route.get('patterns') or []]
    if not patterns:
        return False
    if record.profile_record:
        return match_any(rel, patterns)
    if record.owner_is_file:
        relative = Path(rel).name
    elif rel == record.owner:
        relative = ''
    else:
        relative = rel[len(record.owner.rstrip('/') + '/'):]
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def _matching_records(records: list[DomainRecord], rel: str) -> list[DomainRecord]:
    profile = [r for r in records if r.profile_record and _record_applies(r, rel)]
    legacy = [r for r in records if not r.profile_record and _record_applies(r, rel)]
    if legacy:
        max_len = max(len(r.owner) for r in legacy)
        legacy = [r for r in legacy if len(r.owner) == max_len]
    return profile + legacy


def _nearest_records(records: list[DomainRecord], rel: str) -> list[DomainRecord]:
    return _matching_records(records, rel)


def _expand_paths(root: Path, specs: Iterable[str]) -> set[str]:
    files = set(_all_files(root))
    out: set[str] = set()
    for spec in specs:
        rel = _safe_relative(str(spec))
        if not rel:
            continue
        if rel in files:
            out.add(rel); continue
        prefix = rel.rstrip('/') + '/'
        matches = {f for f in files if f.startswith(prefix)}
        if matches:
            out.update(matches); continue
        out.update(f for f in files if fnmatch.fnmatch(f, rel))
    return out


def _authority_files_for_record(root: Path, record: DomainRecord) -> set[str]:
    if record.authority_files:
        return _expand_paths(root, record.authority_files)
    if record.profile_record or record.kind.lower() != 'authority':
        return set()
    owner = root / record.owner
    if record.owner_is_file and owner.is_file():
        return {record.owner}
    if owner.is_dir():
        return {
            p.relative_to(root).as_posix()
            for p in owner.iterdir()
            if p.is_file() and not p.name.endswith('.governance-domain.yaml') and p.name != '.governance-domain.yaml'
        }
    return set()


def _is_authority_path(root: Path, rel: str, records: list[DomainRecord] | None = None) -> bool:
    """Recognize Authority paths from Project Profile or legacy kind metadata."""
    for raw in authority_config(root).values():
        if match_any(rel, [str(x) for x in raw.get('paths') or []]):
            return True
    for record in records or _routing_records(root):
        if record.kind.lower() == 'authority' and _record_applies(record, rel):
            return True
        for spec in record.authority_files:
            clean = str(spec).rstrip('/')
            if rel == clean or rel.startswith(clean + '/') or match_any(rel, [str(spec)]):
                return True
    return False


def _merge_record_effects(record: DomainRecord, rel: str) -> dict[str, set[str] | list[str]]:
    effects: dict[str, set[str] | list[str]] = {
        'domains': set(record.domains), 'depends_on': list(record.depends_on), 'authorities': list(record.authorities),
        'tests': list(record.tests), 'engineering_gates': set(record.engineering_gates),
        'formal_gate_conditions': set(record.formal_gate_conditions), 'reviewer_risks': set(record.reviewer_risks),
        'sovereignty_categories': set(record.sovereignty_categories),
    }
    for route in record.routes:
        if not _route_matches(route, record, rel):
            continue
        for key in ('domains', 'engineering_gates', 'gates', 'formal_gate_conditions', 'reviewer_risks', 'sovereignty_categories'):
            target_key = 'engineering_gates' if key == 'gates' else key
            cast = effects[target_key]
            assert isinstance(cast, set)
            cast.update(str(x) for x in route.get(key) or [])
        for key in ('depends_on', 'authorities', 'tests'):
            cast = effects[key]
            assert isinstance(cast, list)
            cast.extend(str(x) for x in route.get(key) or [])
    return effects


def _signal_in_text(text: str, signal: str) -> bool:
    signal = signal.lower()
    if re.fullmatch(r'[a-z0-9 _-]+', signal):
        pattern = r'(?<![a-z0-9_])' + re.escape(signal).replace(r'\ ', r'\s+') + r'(?![a-z0-9_])'
        return re.search(pattern, text) is not None
    return signal in text


def _merged_signal_map(root: Path, key: str, baseline: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    out = {k: tuple(v) for k, v in baseline.items()}
    for name, values in configured_request_signals(root, key).items():
        out[name] = tuple(dict.fromkeys((*out.get(name, ()), *values)))
    return out


def _request_domains(request: str, root: Path | None = None) -> set[str]:
    text = request.lower()
    signals = BASE_REQUEST_DOMAIN_SIGNALS if root is None else _merged_signal_map(root, 'request_domain_signals', BASE_REQUEST_DOMAIN_SIGNALS)
    domains = {domain for domain, words in signals.items() if any(_signal_in_text(text, word) for word in words)}
    # Small semantic implications keep request routing aligned with the project's domain model
    # without adding another scan or a second routing engine.
    changed = True
    while changed:
        changed = False
        implied: set[str] = set()
        if domains & {'CREDENTIAL', 'SESSION', 'ACCOUNT_SECURITY'}:
            implied.add('AUTHENTICATION')
        if domains & {'RBAC', 'DEFAULT_ADMIN'}:
            implied.add('AUTHORIZATION')
        if 'DEFAULT_ADMIN' in domains:
            implied.add('RBAC')
        before = len(domains); domains.update(implied); changed = len(domains) != before
    return domains


def _request_sovereignty(request: str, root: Path | None = None) -> set[str]:
    text = request.lower()
    signals = BASE_SOVEREIGNTY_SIGNALS if root is None else _merged_signal_map(root, 'sovereignty_signals', BASE_SOVEREIGNTY_SIGNALS)
    return {category for category, words in signals.items() if any(_signal_in_text(text, word) for word in words)}


def _is_test_or_nonruntime_file(rel: str, root: Path | None = None) -> bool:
    low = rel.lower(); name = Path(low).name
    if root is not None:
        patterns = configured_list(root, 'nonruntime_path_patterns')
        if patterns and match_any(rel, patterns):
            return True
    return rel.startswith('tests/') or '/tests/' in rel or '/e2e/' in rel or name.startswith('test_') or '.test.' in name or '.spec.' in name or low.endswith(('.md', '.txt'))


def _database_schema_changed(request: str, seeds: Iterable[str], root: Path | None = None) -> bool:
    patterns = list(BASE_SCHEMA_PATH_PATTERNS)
    if root is not None:
        patterns.extend(configured_list(root, 'database_schema_path_patterns'))
    for rel in map(str, seeds):
        if _is_test_or_nonruntime_file(rel, root):
            continue
        if match_any(rel, patterns):
            return True
    custom_regex = configured_list(root, 'database_schema_request_patterns') if root is not None else ()
    return any(re.search(pattern, request) for pattern in (*DB_SCHEMA_SEMANTIC_PATTERNS, *custom_regex))


def _has_behavior_signal(request: str, seeds: Iterable[str], root: Path | None = None) -> bool:
    text = request.lower()
    request_signals = list(BASE_BEHAVIOR_SIGNALS)
    path_patterns = list(BASE_BEHAVIOR_PATH_PATTERNS)
    if root is not None:
        request_signals.extend(configured_list(root, 'behavior_request_signals'))
        path_patterns.extend(configured_list(root, 'behavior_path_patterns'))
    if any(_signal_in_text(text, signal) for signal in request_signals):
        return True
    runtime_seeds = [str(x) for x in seeds if not _is_test_or_nonruntime_file(str(x), root)]
    return any(match_any(rel, path_patterns) for rel in runtime_seeds)


def _pure_ui_non_behavior(request: str, seeds: Iterable[str], root: Path | None = None) -> bool:
    text = request.lower()
    signals = list(BASE_NON_BEHAVIOR_SIGNALS)
    if root is not None:
        signals.extend(configured_list(root, 'non_behavior_request_signals'))
    runtime_seeds = [str(x) for x in seeds if not _is_test_or_nonruntime_file(str(x), root)]
    css_only = bool(runtime_seeds) and all(
        x.lower().endswith(('.css', '.scss', '.less', '.sass')) or '/styles/' in x.lower()
        for x in runtime_seeds
    )
    # A page/business noun such as "login page" is not by itself a behavioral change.
    # For CSS-only changes, explicit cosmetic intent wins unless there is a strong action signal.
    strong_behavior = (
        '路由', '跳转', 'redirect', 'navigate', 'api 调用', '接口调用', '网络请求', '表单提交', 'submit',
        '点击行为', '数据写入', '数据读取', '状态转换', '业务校验', '事件处理', '交互流程', '数据绑定',
        '后端逻辑', 'db 变更', 'database change',
    )
    if root is not None:
        strong_behavior = (*strong_behavior, *configured_list(root, 'behavior_request_signals'))
    if css_only and any(_signal_in_text(text, signal) for signal in signals):
        if not any(_signal_in_text(text, signal) for signal in strong_behavior):
            return True
    # Otherwise positive behavioral evidence has precedence over cosmetic wording.
    if _has_behavior_signal(request, seeds, root):
        return False
    if any(_signal_in_text(text, signal) for signal in signals):
        return True
    return css_only


def _user_visible_behavior_changed(request: str, seeds: Iterable[str], domains: set[str], root: Path | None = None) -> bool:
    if _pure_ui_non_behavior(request, seeds, root):
        return False
    text = request.lower()
    signals = list(BASE_USER_VISIBLE_SIGNALS) + list(BASE_BEHAVIOR_SIGNALS)
    ui_patterns = list(BASE_UI_PATH_PATTERNS)
    if root is not None:
        signals.extend(configured_list(root, 'user_visible_request_signals'))
        ui_patterns.extend(configured_list(root, 'user_visible_path_patterns'))
    runtime_seeds = [str(x) for x in seeds if not _is_test_or_nonruntime_file(str(x), root)]
    explicit = any(_signal_in_text(text, x) for x in signals)
    ui_touched = any(match_any(rel, ui_patterns) for rel in runtime_seeds)
    configured_ui_domains = set(configured_list(root, 'user_visible_domains')) if root is not None else set()
    ui_domain = bool(domains & configured_ui_domains)
    # Once a non-cosmetic UI implementation file is in the final affected set, treat it
    # as potentially user-visible even when the original request wording was generic.
    return bool(runtime_seeds) and (ui_touched or ui_domain) and (explicit or ui_touched)


def _business_ui_review_required(request: str, seeds: Iterable[str], root: Path | None = None) -> bool:
    if _pure_ui_non_behavior(request, seeds, root):
        return False
    signals = configured_list(root, 'business_ui_review_signals') if root is not None else ()
    if not signals:
        signals = ('新增页面', '页面改造', '菜单', '信息架构', '复杂表单', '复杂表格', '确认弹窗', 'modal', 'drawer', 'wizard', '跨页面', '业务流程', '关键操作', '批量操作')
    ui_patterns = list(BASE_UI_PATH_PATTERNS)
    if root is not None:
        ui_patterns.extend(configured_list(root, 'user_visible_path_patterns'))
    text = request.lower()
    return any(match_any(str(x), ui_patterns) for x in seeds) and any(_signal_in_text(text, signal) for signal in signals)


def _substantive_implementation_change(seeds: Iterable[str], root: Path | None = None) -> bool:
    extensions = set(BASE_SUBSTANTIVE_EXTENSIONS)
    if root is not None:
        extensions.update(configured_list(root, 'substantive_extensions'))
    for rel in map(str, seeds):
        if _is_test_or_nonruntime_file(rel, root) or _is_authority_path(root, rel):
            continue
        if Path(rel).suffix.lower() in extensions:
            return True
    return False


def _product_decision_mode(request: str, review_required: bool) -> str:
    if not review_required:
        return 'IMPLEMENTATION_WITHIN_AUTHORITY'
    text = request.lower()
    if any(signal.lower() in text for signal in EXPLICIT_PRODUCT_CHANGE_SIGNALS):
        return 'PRODUCT_DECISION_REQUIRED'
    if any(signal.lower() in text for signal in RESTORATIVE_OR_EQUIVALENT_SIGNALS):
        return 'PRODUCT_DECISION_NOT_REQUIRED'
    return 'PRODUCT_SOVEREIGNTY_REVIEW_REQUIRED'


def infer_domains(request: str, files: list[str], root: Path | None = None) -> set[str]:
    domains = _request_domains(request, root)
    if root is not None:
        records = _routing_records(root)
        for rel in files:
            for record in _matching_records(records, rel):
                domains.update(_merge_record_effects(record, rel)['domains'])  # type: ignore[arg-type]
    return domains


def _implementation_domains(records: list[DomainRecord], domains: set[str]) -> set[str]:
    """Return implementation-domain records matched by current domains.

    Domain names are project facts. Generic Runtime only interprets the metadata
    ``kind`` attribute and never relies on names such as backend/frontend/server/client.
    """
    return {record.meta_path for record in records if record.kind.lower() == 'implementation' and record.domains & domains}


def _dependency_closure(root: Path, records: list[DomainRecord], initial: Iterable[str]) -> tuple[set[str], set[str]]:
    queue = list(dict.fromkeys(str(x) for x in initial)); seen: set[str] = set(); authorities: set[str] = set()
    by_owner = {r.owner: r for r in records}
    for record in records:
        for domain in record.domains:
            by_owner.setdefault(f'domain:{domain}', record)
    while queue:
        dep = str(queue.pop(0))
        safe = _safe_relative(dep) if not dep.startswith('domain:') else dep
        if not safe or safe in seen:
            continue
        seen.add(safe)
        record = by_owner.get(safe)
        if record:
            authorities.update(_authority_files_for_record(root, record)); queue.extend(record.depends_on); authorities.update(_expand_paths(root, record.authorities))
        elif _is_authority_path(root, safe, records):
            authorities.update(_expand_paths(root, [safe]))
    return seen, authorities


def _authority_paths_for_domains(root: Path, domains: set[str]) -> set[str]:
    out: set[str] = set()
    for _, raw in authority_config(root).items():
        auth_domains = {str(x) for x in raw.get('domains') or []}
        if auth_domains & domains:
            out.update(_expand_paths(root, [str(x) for x in raw.get('paths') or []]))
    return out


def _sensitive_domain_categories(root: Path) -> dict[str, set[str]]:
    out = {k: set(v) for k, v in BASE_SENSITIVE_DOMAIN_CATEGORIES.items()}
    custom = configured_mapping(root, 'sensitive_domain_categories')
    for domain, categories in custom.items():
        if isinstance(categories, list):
            out[str(domain)] = {str(x) for x in categories}
    return out


def _configured_reviewer_routes(
    root: Path,
    domains: set[str],
    reviewer_risks: set[str],
    sovereignty: set[str],
    authorities: set[str],
) -> set[str]:
    """Route reviewers from Project Profile when configured; otherwise use safe generic defaults."""
    configured = reviewer_config(root)
    if not configured:
        out: set[str] = set()
        if 'ARCHITECTURE' in reviewer_risks:
            out.add('architecture_reviewer')
        if sovereignty or 'PRODUCT_SOVEREIGNTY_SENSITIVE' in reviewer_risks:
            out.add('product_sovereignty_reviewer')
        if reviewer_risks & {'CODE_QUALITY_HIGH_RISK', 'SECURITY_SENSITIVE', 'HIGH_REGRESSION_RISK', 'BUSINESS_UI_REVIEW'}:
            out.add('code_quality_reviewer')
        return out

    authority_names: set[str] = set()
    for name, raw in authority_config(root).items():
        paths = [str(x) for x in raw.get('paths') or []]
        if any(any(match_any(path, [spec]) or match_any(spec, [path]) for spec in paths) for path in authorities):
            authority_names.add(name)
    out: set[str] = set()
    for name, raw in configured.items():
        trigger = raw.get('trigger') or {}
        if not isinstance(trigger, dict):
            continue
        risk = {str(x) for x in trigger.get('risk') or []}
        trigger_domains = {str(x) for x in trigger.get('domains') or []}
        trigger_authorities = {str(x) for x in trigger.get('authority') or []}
        if (
            risk & reviewer_risks
            or trigger_domains & domains
            or trigger_authorities & authority_names
            or (bool(trigger.get('sovereignty_any')) and bool(sovereignty))
        ):
            out.add(name)
    return out


def _profile_owners(root: Path, domains: set[str]) -> set[str]:
    owners: set[str] = set()
    for name, raw in domain_config(root).items():
        configured_domains = {name, *(str(x) for x in raw.get('domains') or [])}
        if not (configured_domains & domains):
            continue
        values = raw.get('owners')
        if isinstance(values, list):
            owners.update(str(x) for x in values if str(x).strip())
        owner = raw.get('owner') or raw.get('owner_identity')
        if owner:
            owners.add(str(owner))
    return owners


def _technology_profiles(root: Path, files: Iterable[str]) -> tuple[set[str], set[str]]:
    tech = technology_config(root)
    language_profiles: set[str] = set()
    framework_profiles: set[str] = set()
    for name, raw in (tech.get('languages') or {}).items():
        if isinstance(raw, dict) and any(match_any(rel, [str(x) for x in raw.get('paths') or []]) for rel in files):
            language_profiles.add(str(name))
    for name, raw in (tech.get('frameworks') or {}).items():
        if isinstance(raw, dict) and any(match_any(rel, [str(x) for x in raw.get('paths') or []]) for rel in files):
            framework_profiles.add(str(name))
    return language_profiles, framework_profiles


def _merge_logical_domain_metadata(
    root: Path,
    domains: set[str],
    records: list[DomainRecord],
    *,
    dependencies: set[str],
    authorities: set[str],
    relevant_tests: set[str],
    engineering_gates: set[str],
    formal_conditions: set[str],
    reviewer_risks: set[str],
    sovereignty: set[str],
    metadata_used: set[str],
) -> None:
    """Close metadata for DOMAIN-scope tasks that have no concrete seed files.

    Only profile records whose configured domain/aliases intersect the request domains
    are merged. Route-level metadata is intentionally not applied because there is no
    concrete path to satisfy a route pattern.
    """
    authority_specs: set[str] = set()
    test_specs: set[str] = set()
    for record in records:
        if not record.profile_record or not (record.domains & domains):
            continue
        metadata_used.add(record.meta_path)
        domains.update(record.domains)
        dependencies.update(record.depends_on)
        authority_specs.update(record.authorities)
        test_specs.update(record.tests)
        engineering_gates.update(record.engineering_gates)
        formal_conditions.update(record.formal_gate_conditions)
        reviewer_risks.update(record.reviewer_risks)
        sovereignty.update(record.sovereignty_categories)
        authorities.update(_authority_files_for_record(root, record))
    authorities.update(_expand_paths(root, authority_specs))
    relevant_tests.update(_expand_paths(root, test_specs))


def recompute_metadata(root: Path, request: str, affected_files: Iterable[str], logical_domains: Iterable[str] = ()) -> dict[str, Any]:
    """Compute every derived routing field from the final affected-file set."""
    root = root.resolve(); files = sorted(set(str(x) for x in affected_files)); records = _routing_records(root)
    domains = _request_domains(request, root); dependencies: set[str] = set(); authorities: set[str] = set(); relevant_tests: set[str] = set()
    engineering_gates: set[str] = set(); formal_conditions: set[str] = set(); reviewer_risks: set[str] = set(); sovereignty = _request_sovereignty(request, root); metadata_used: set[str] = set()
    authority_specs: set[str] = set(); test_specs: set[str] = set(); authority_record_cache: dict[str, set[str]] = {}

    logical = {str(x) for x in logical_domains}
    if logical:
        domains.update(logical)
        _merge_logical_domain_metadata(
            root, domains, records, dependencies=dependencies, authorities=authorities, relevant_tests=relevant_tests,
            engineering_gates=engineering_gates, formal_conditions=formal_conditions, reviewer_risks=reviewer_risks,
            sovereignty=sovereignty, metadata_used=metadata_used,
        )

    for rel in files:
        for record in _matching_records(records, rel):
            metadata_used.add(record.meta_path); effects = _merge_record_effects(record, rel)
            domains.update(effects['domains'])  # type: ignore[arg-type]
            dependencies.update(effects['depends_on'])  # type: ignore[arg-type]
            authority_specs.update(str(x) for x in effects['authorities'])  # type: ignore[arg-type]
            test_specs.update(str(x) for x in effects['tests'])  # type: ignore[arg-type]
            engineering_gates.update(effects['engineering_gates'])  # type: ignore[arg-type]
            formal_conditions.update(effects['formal_gate_conditions'])  # type: ignore[arg-type]
            reviewer_risks.update(effects['reviewer_risks'])  # type: ignore[arg-type]
            sovereignty.update(effects['sovereignty_categories'])  # type: ignore[arg-type]
            if record.meta_path not in authority_record_cache:
                authority_record_cache[record.meta_path] = _authority_files_for_record(root, record)
            authorities.update(authority_record_cache[record.meta_path])

    authorities.update(_expand_paths(root, authority_specs)); relevant_tests.update(_expand_paths(root, test_specs))
    deps, dep_authorities = _dependency_closure(root, records, dependencies); dependencies = deps; authorities.update(dep_authorities)
    if _database_schema_changed(request, files, root):
        schema_domain = str(configured_mapping(root, 'semantic_domains').get('database_schema') or '')
        schema_condition = str(configured_mapping(root, 'formal_conditions').get('database_schema_changed') or '')
        if schema_domain:
            domains.add(schema_domain)
        if schema_condition:
            formal_conditions.add(schema_condition)
    if _user_visible_behavior_changed(request, files, domains, root):
        acceptance_domain = str(configured_mapping(root, 'semantic_domains').get('acceptance') or '')
        acceptance_condition = str(configured_mapping(root, 'formal_conditions').get('user_visible_behavior_changed') or '')
        if acceptance_domain:
            domains.add(acceptance_domain)
        if acceptance_condition:
            formal_conditions.add(acceptance_condition)
    text = request.lower()
    arch_signals = (*BASE_ARCHITECTURE_SIGNALS, *configured_list(root, 'architecture_request_signals'))
    risk_signals = (*BASE_HIGH_RISK_SIGNALS, *configured_list(root, 'high_risk_request_signals'))
    if any(_signal_in_text(text, x) for x in arch_signals): reviewer_risks.add('ARCHITECTURE')
    if any(_signal_in_text(text, x) for x in risk_signals): reviewer_risks.add('CODE_QUALITY_HIGH_RISK')
    if _business_ui_review_required(request, files, root): reviewer_risks.update({'BUSINESS_UI_REVIEW', 'CODE_QUALITY_HIGH_RISK'})

    sensitive_map = _sensitive_domain_categories(root); sensitive_domains = domains & set(sensitive_map)
    if sensitive_domains and _substantive_implementation_change(files, root):
        reviewer_risks.add('PRODUCT_SOVEREIGNTY_SENSITIVE')
        for domain in sensitive_domains: sovereignty.update(sensitive_map.get(domain, set()))
    authorities.update(_authority_paths_for_domains(root, domains))

    implementation_domains = _implementation_domains(records, domains)
    if len(implementation_domains) >= 2: reviewer_risks.update({'ARCHITECTURE', 'CODE_QUALITY_HIGH_RISK'})

    sovereignty_review_required = bool(sovereignty or 'PRODUCT_SOVEREIGNTY_SENSITIVE' in reviewer_risks)
    review = _configured_reviewer_routes(root, domains, reviewer_risks, sovereignty, authorities)
    if 'code_quality_reviewer' in review:
        engineering_gates.update(GENERIC_AUTO_REQUIRED_GATES)

    formal_gates = formal_gates_for_conditions(root, formal_conditions)
    language_profiles, framework_profiles = _technology_profiles(root, files)
    owners = _profile_owners(root, domains)
    return {
        'affected_files': files, 'authorities': sorted(authorities), 'dependencies': sorted(dependencies),
        'relevant_tests': sorted(relevant_tests), 'domains': sorted(domains),
        'required_gates': sorted(engineering_gates | formal_gates), 'formal_gate_conditions': sorted(formal_conditions),
        'review_triggers': sorted(review), 'review_profiles': sorted(reviewer_risks), 'risk_flags': sorted(reviewer_risks),
        'sovereignty_categories': sorted(sovereignty),
        'owners': sorted(owners), 'language_profiles': sorted(language_profiles), 'framework_profiles': sorted(framework_profiles),
        'gate_configuration_status': 'CONFIGURED' if (gate_config(root) or formal_gate_ids(root)) else 'NO_CONFIGURED_GATE',
        'authority_configuration_status': 'CONFIGURED' if authority_config(root) else 'NO_AUTHORITY_CONFIGURED',
        'product_sovereignty_required': sovereignty_review_required, 'product_sovereignty_review_required': sovereignty_review_required,
        'product_decision_mode': _product_decision_mode(request, sovereignty_review_required), 'domain_metadata_used': sorted(metadata_used),
    }


def expand_module_scope(root: Path, request: str, files: Iterable[str]) -> set[str]:
    """Expand to configured modules first; metadata is recomputed afterwards."""
    root = root.resolve(); records = _routing_records(root); all_files = _all_files(root); preliminary_domains = _request_domains(request, root)
    matched_records: set[str] = set()
    for rel in files:
        for record in _matching_records(records, str(rel)):
            preliminary_domains.update(record.domains); matched_records.add(record.meta_path)
    out = set(str(x) for x in files)
    for record in records:
        if record.domains & preliminary_domains and record.kind.lower() != 'authority':
            if record.path_patterns:
                out.update(f for f in all_files if match_any(f, record.path_patterns))
            elif not record.owner_is_file and not record.owner.startswith('@profile/'):
                prefix = record.owner.rstrip('/') + '/'; out.update(f for f in all_files if f == record.owner or f.startswith(prefix))
    return out


def scan(root: Path, task_id: str, request: str, seed_files: list[str] | None = None, task_owner_pid: int | None = None) -> dict[str, Any]:
    """Run the single Full Impact Scan from request/Profile/workspace facts, never Git."""
    root = root.resolve(); validate_task_id(task_id)
    if context_path(root, task_id).exists(): raise RuntimeError('FULL_IMPACT_SCAN_ALREADY_EXISTS')
    explicit = {_safe_relative(x) for x in (seed_files or [])}; request_paths = set(_extract_request_paths(root, request))
    policy = load_policy(root)
    seeds = sorted(x for x in (explicit | request_paths) if x and consumer_allows_relative(root, x, 'impact_scan', policy))
    request_domains = _request_domains(request, root); affected = set(seeds); scope_level = 'FILE_OR_DOMAIN'
    if not seeds and not request_domains:
        scope_level = 'REPOSITORY'; affected.update(_all_files(root))
    elif not seeds and request_domains:
        scope_level = 'DOMAIN'

    derived = recompute_metadata(root, request, affected, request_domains if scope_level == 'DOMAIN' else ())
    effective_pid = int(task_owner_pid if task_owner_pid is not None else os.getpid())
    process_identity = current_process_identity(effective_pid)
    payload: dict[str, Any] = {
        'schema_version': 5, 'request': request, 'task_pid': effective_pid,
        'task_process_creation_time': process_identity.creation_time,
        'task_status': 'ACTIVE', 'task_started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scan_mode': 'SINGLE_FULL_IMPACT_SCAN', 'seed_candidates': seeds, 'scope_level': scope_level,
        'changed_files_source': 'LOCAL_WORKSPACE_BASELINE', 'metadata_finalized_after_scope': True,
        'final_reconciliation_status': 'NOT_RUN',
    }
    payload.update(derived)
    payload['product_decision_status'] = (
        'REQUIRED' if payload.get('product_decision_mode') == 'PRODUCT_DECISION_REQUIRED' else 'NOT_REQUIRED'
    )
    save_context(root, task_id, payload)
    return payload


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.'); p.add_argument('--task-id', required=True); p.add_argument('--request', required=True); p.add_argument('--seed-file', action='append', default=[])
    a = p.parse_args()
    try: out = scan(Path(a.root), a.task_id, a.request, a.seed_file)
    except (RuntimeError, ValueError) as exc: print(str(exc)); return 2
    print(json.dumps(out, ensure_ascii=False, indent=2)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
