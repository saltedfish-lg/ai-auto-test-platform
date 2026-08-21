from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = '.governance/context-efficiency.yaml'
CONTEXT_SUFFICIENT = 'CONTEXT_SUFFICIENT'
CONTEXT_EXPANSION_REQUIRED = 'CONTEXT_EXPANSION_REQUIRED'
CONTEXT_UNAVAILABLE = 'CONTEXT_UNAVAILABLE'

_DEFAULT: dict[str, Any] = {
    'context_efficiency': {'mode': 'adaptive_context_loading', 'governance_gate': False},
    'context_loading': {
        'authority': {'strategy': 'precise_slice', 'initial_records': 12, 'preview_chars': 12000, 'allow_on_demand_expand': True, 'avoid_repeat_unchanged_read': True},
        'source_code': {'strategy': 'agent_tool_driven_symbol_first', 'allow_full_file_when_required': True, 'avoid_repeat_unchanged_read': True},
        'tests': {'strategy': 'agent_tool_driven_relevant_first', 'allow_expand_when_required': True, 'avoid_repeat_unchanged_read': True},
        'tool_output': {'strategy': 'diagnostic_projection_then_expand', 'summary_chars': 4000, 'allow_raw_expand_when_required': True, 'avoid_repeat_unchanged_read': True},
        'deduplication': {'enabled': True},
        'context_history': {'enabled': True},
        'repo_intelligence_max_results': 20,
        'minimum_records_per_authority': 1,
        'minimum_records_per_domain': 1,
    },
    'authority_index': {
        'source_roots':['docs/authority'], 'cache_path':'.runtime/context-index/authority-index.sqlite3',
        'extensions':['.yaml','.yml','.json','.csv'], 'exclude_patterns':[],
        'canonical_identity_keys':['record_id','canonical_id','structural_id','id'],
        'identity_strategies':{},
    },
    'repo_intelligence': {'provider':'none','authority_role':'forbidden','max_results':20,'include_paths':[],'exclude_paths':['docs/authority/**','.env*']},
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in set(base) | set(override):
        left, right = base.get(key), override.get(key)
        if isinstance(left, dict) and isinstance(right, dict): out[key] = _merge(left, right)
        elif key in override: out[key] = right
        else: out[key] = left
    return out


def load_context_efficiency_config(root: Path) -> dict[str, Any]:
    path = root.resolve()/CONFIG_PATH; raw: dict[str, Any] = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        if isinstance(loaded, dict): raw = loaded
    return _merge(_DEFAULT, raw)


def serialized_chars(value: Any) -> int:
    if isinstance(value, str): return len(value)
    if isinstance(value, bytes): return len(value.decode('utf-8', errors='replace'))
    return len(json.dumps(value, ensure_ascii=False, separators=(',',':'), default=str))


def content_sha256(content: Any) -> str:
    if isinstance(content, bytes): raw = content
    elif isinstance(content, str): raw = content.encode('utf-8')
    else: raw = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',',':'), default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024*1024), b''): digest.update(block)
    return digest.hexdigest()


def ensure_context_history(task_context: dict[str, Any]) -> dict[str, Any]:
    history = task_context.setdefault('context_history', {})
    for name in ('authority','source_code','tests','tool_outputs','repo_intelligence'):
        if not isinstance(history.get(name), list): history[name] = []
    metrics = history.setdefault('metrics', {})
    metrics.setdefault('reused_context_count', 0); metrics.setdefault('expanded_context_count', 0); metrics.setdefault('loaded_context_count', 0)
    return history


def context_consumer_id(task_context: dict[str, Any]) -> str:
    """Return the lightweight consumer/epoch identity used for loaded-context ownership.

    Callers that resume a task with a new model/session can set either
    ``context_consumer_id`` or ``context_epoch`` on the Task Context.  When neither is
    supplied the runtime deliberately operates under the documented single-continuous-
    consumer assumption instead of pretending cross-session retention is guaranteed.
    """
    explicit = task_context.get('context_consumer_id')
    if explicit not in (None, ''):
        return str(explicit)
    epoch = task_context.get('context_epoch')
    if epoch not in (None, ''):
        return f'EPOCH:{epoch}'
    return 'SINGLE_CONTINUOUS_CONTEXT_CONSUMER'


def context_consumer_status(task_context: dict[str, Any]) -> str:
    if task_context.get('context_consumer_id') not in (None, '') or task_context.get('context_epoch') not in (None, ''):
        return 'CONSUMER_SCOPED'
    return 'SINGLE_CONTINUOUS_CONTEXT_CONSUMER_ASSUMPTION'


def history_summary(task_context: dict[str, Any]) -> dict[str, Any]:
    history = ensure_context_history(task_context); metrics = history['metrics']
    return {
        'authority_reads': len(history['authority']), 'source_code_reads': len(history['source_code']),
        'test_reads': len(history['tests']), 'tool_output_reads': len(history['tool_outputs']),
        'repo_intelligence_queries': len(history['repo_intelligence']),
        'reused_context_count': int(metrics['reused_context_count']), 'expanded_context_count': int(metrics['expanded_context_count']),
        'loaded_context_count': int(metrics['loaded_context_count']),
        'context_consumer_id': context_consumer_id(task_context),
        'context_consumer_status': context_consumer_status(task_context),
    }


def _entry_key(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(entry.get('consumer_id') or 'SINGLE_CONTINUOUS_CONTEXT_CONSUMER'),
        str(entry.get('locator') or ''),
        str(entry.get('scope') or ''),
        str(entry.get('sha256') or ''),
    )


def context_read_seen(task_context: dict[str, Any], category: str, *, locator: str, sha256: str, scope: str = '') -> bool:
    history = ensure_context_history(task_context)
    bucket_name = {'tool_output':'tool_outputs'}.get(category, category)
    if bucket_name not in history:
        raise ValueError(f'UNKNOWN_CONTEXT_HISTORY_CATEGORY:{category}')
    probe = {'consumer_id': context_consumer_id(task_context), 'locator': locator, 'scope': scope, 'sha256': sha256}
    return any(_entry_key(item) == _entry_key(probe) for item in history[bucket_name])


def record_context_read(task_context: dict[str, Any], category: str, *, locator: str, sha256: str, scope: str = '', expanded: bool = False, force: bool = False) -> tuple[dict[str, Any], bool]:
    history = ensure_context_history(task_context)
    bucket_name = {'tool_output':'tool_outputs'}.get(category, category)
    if bucket_name not in history:
        raise ValueError(f'UNKNOWN_CONTEXT_HISTORY_CATEGORY:{category}')
    probe={'consumer_id':context_consumer_id(task_context),'locator':locator,'scope':scope,'sha256':sha256}
    prior = next((item for item in history[bucket_name] if _entry_key(item)==_entry_key(probe)), None)
    if prior is not None and not force:
        # A prior projected/partial read must not block a normal adaptive expansion to raw/full context.
        if expanded and not bool(prior.get('expanded')):
            prior['expanded'] = True
            history['metrics']['expanded_context_count'] += 1
            return task_context, False
        history['metrics']['reused_context_count'] += 1
        return task_context, True
    if prior is not None and force:
        prior['expanded'] = bool(expanded) or bool(prior.get('expanded'))
    else:
        history[bucket_name].append({**probe, 'expanded': bool(expanded)})
        history[bucket_name] = history[bucket_name][-500:]
    history['metrics']['expanded_context_count' if expanded else 'loaded_context_count'] += 1
    return task_context, False


_DIAGNOSTIC_LINE = __import__('re').compile(
    r'(?i)(===\s*(FAILURES|ERRORS)\s*===|\bFAILED\b|\bERROR\b|AssertionError|Traceback|short test summary|\bException\b|\bError:|\bWarning:|\bE\s{2,}|[^\s:]+\.(?:py|ts|tsx|js|vue):\d+)'
)


def _diagnostic_tool_output_projection(content: str, limit: int) -> str:
    """Project large command output while preserving diagnostics; limit is a batch target, not a correctness quota."""
    lines = content.splitlines()
    if not lines:
        return content[:limit]
    diagnostic_indexes = {i for i, line in enumerate(lines) if _DIAGNOSTIC_LINE.search(line)}
    expanded_indexes: set[int] = set()
    for index in diagnostic_indexes:
        expanded_indexes.update(range(max(0, index-2), min(len(lines), index+3)))
    # Always retain a compact head and tail so environment/context and final summaries survive.
    head_count = min(len(lines), 8)
    tail_count = min(len(lines), 14)
    selected = set(range(head_count)) | set(range(max(0, len(lines)-tail_count), len(lines))) | expanded_indexes
    ordered = sorted(selected)
    parts: list[str] = []
    last = -2
    for index in ordered:
        if index != last + 1 and parts:
            parts.append('…')
        parts.append(lines[index])
        last = index
    projected = '\n'.join(parts)
    if len(projected) <= limit or diagnostic_indexes:
        # Diagnostic lines are correctness-sensitive and may exceed the soft projection target.
        return projected
    return projected[:limit] + '…'


def project_context(task_context: dict[str, Any], root: Path, category: str, content: Any, *, locator: str, scope: str = '', expand: bool = False, force: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    root=root.resolve(); out=dict(task_context); digest=content_sha256(content)
    out, reused = record_context_read(out, category, locator=locator, sha256=digest, scope=scope, expanded=expand, force=force)
    if reused:
        return out, {'category':category,'status':'REUSED_CONTEXT','locator':locator,'scope':scope,'sha256':digest,'content':None,'reuse_ref':{'locator':locator,'scope':scope,'sha256':digest}}
    cfg=load_context_efficiency_config(root)['context_loading']; projected=content; status='LOADED'
    if category=='tool_output' and not expand:
        limit=max(1,int(cfg.get('tool_output',{}).get('summary_chars',4000)))
        if isinstance(content,str) and len(content)>limit:
            projected=_diagnostic_tool_output_projection(content,limit); status='DIAGNOSTIC_SUMMARY'
    return out, {'category':category,'status':status,'locator':locator,'scope':scope,'sha256':digest,'content':projected,'expandable': status=='DIAGNOSTIC_SUMMARY'}


def project_task_context(root: Path, task_id: str, category: str, content: Any, *, locator: str, scope: str = '', expand: bool = False, force: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    from tools.governance.task_context import load_context, save_context
    root=root.resolve(); ctx=load_context(root,task_id); updated,projection=project_context(ctx,root,category,content,locator=locator,scope=scope,expand=expand,force=force); save_context(root,task_id,updated); return updated,projection


def context_decision(*, information_available: bool, information_sufficient: bool) -> str:
    if not information_available: return CONTEXT_UNAVAILABLE
    if not information_sufficient: return CONTEXT_EXPANSION_REQUIRED
    return CONTEXT_SUFFICIENT
