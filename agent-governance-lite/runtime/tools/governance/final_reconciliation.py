from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .incremental_closure import expand
from .task_context import load_context, save_context, task_dir, workspace_changes_since_start


def reconcile(root: Path, task_id: str, max_rounds: int = 4) -> dict[str, Any]:
    """Ensure every actual workspace change is inside the current Task Context."""
    root = root.resolve(); rounds: list[dict[str, Any]] = []
    for index in range(max_rounds):
        ctx = load_context(root, task_id)
        actual = set(workspace_changes_since_start(root, task_id))
        covered = set(str(x) for x in ctx.get('affected_files', []))
        missing = sorted(actual - covered)
        rounds.append({'round': index + 1, 'actual_changed_files': sorted(actual), 'untracked_impact_files': missing})
        if not missing:
            ctx['final_reconciliation_status'] = 'PASS'
            ctx['actual_changed_files'] = sorted(actual)
            ctx['final_reconciliation_rounds'] = index + 1
            save_context(root, task_id, ctx)
            report = {'task_id': task_id, 'status': 'PASS', 'rounds': rounds, 'executed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
            (task_dir(root, task_id) / 'final-reconciliation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            return report
        expand(root, task_id, missing, unknown=False)

    ctx = load_context(root, task_id); actual = set(workspace_changes_since_start(root, task_id)); covered = set(str(x) for x in ctx.get('affected_files', [])); remaining = sorted(actual - covered)
    ctx['final_reconciliation_status'] = 'FAIL'; ctx['actual_changed_files'] = sorted(actual); ctx['untracked_impact_files'] = remaining; save_context(root, task_id, ctx)
    report = {'task_id': task_id, 'status': 'FAIL', 'rounds': rounds, 'untracked_impact_files': remaining, 'executed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (task_dir(root, task_id) / 'final-reconciliation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.'); p.add_argument('--task-id', required=True); a = p.parse_args()
    result = reconcile(Path(a.root), a.task_id); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
