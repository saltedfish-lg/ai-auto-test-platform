from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import json
from pathlib import Path
from typing import Any

from .impact_scan import _all_files, expand_module_scope, recompute_metadata
from .task_context import load_context, save_context
from .workspace_path_policy import consumer_allows_relative, load_policy


def _refresh_project_context_projection(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    try:
        from tools.context.context_projection import enrich_task_context
    except ModuleNotFoundError as exc:
        if str(getattr(exc, 'name', '')).startswith('tools.context'):
            return ctx
        raise
    try:
        return enrich_task_context(root, ctx)
    except Exception as exc:
        out = dict(ctx)
        out['context_efficiency'] = {
            'status': 'DEGRADED_NON_BLOCKING',
            'reason': type(exc).__name__,
            'governance_facts_unchanged': True,
        }
        return out


def expand(root: Path, task_id: str, new_files: list[str], unknown: bool = False) -> dict[str, Any]:
    """Expand impact first, then recompute every routing field from final files."""
    root = root.resolve()
    ctx = load_context(root, task_id)
    request = str(ctx.get('request', ''))
    policy = load_policy(root)
    files = {str(x) for x in ctx.get('affected_files', []) if consumer_allows_relative(root, str(x), 'impact_scan', policy)}
    files.update(str(x) for x in new_files if consumer_allows_relative(root, str(x), 'impact_scan', policy))

    level = str(ctx.get('scope_level', 'FILE_OR_DOMAIN'))
    if unknown:
        if level in {'FILE_OR_DOMAIN', 'DOMAIN'}:
            level = 'MODULE'
        elif level == 'MODULE':
            level = 'REPOSITORY'

    # Scope expansion happens before metadata finalization.
    if level == 'MODULE':
        files = expand_module_scope(root, request, files)
    elif level == 'REPOSITORY':
        files = set(_all_files(root)) | files

    derived = recompute_metadata(root, request, files)
    ctx.update(derived)
    ctx.update({
        'scope_level': level,
        'metadata_finalized_after_scope': True,
        'incremental_revision': int(ctx.get('incremental_revision', 0)) + 1,
        'final_reconciliation_status': 'NOT_RUN',
    })
    ctx.pop('actual_changed_files', None)
    ctx.pop('final_reconciliation_rounds', None)
    ctx = _refresh_project_context_projection(root, ctx)
    save_context(root, task_id, ctx)
    return ctx


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    p.add_argument('--task-id', required=True)
    p.add_argument('--file', action='append', default=[])
    p.add_argument('--unknown-edge', action='store_true')
    a = p.parse_args()
    out = expand(Path(a.root), a.task_id, a.file, a.unknown_edge)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
