from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .authority_lock import current_owner as current_authority_lock_owner
from .authority_lock import release as release_authority_lock
from .final_reconciliation import reconcile
from .impact_scan import scan
from .required_gate_runner import run_required
from .task_context import cleanup_other_tasks, cleanup_task, final_reconciliation_is_current, gate_results_path, load_context, save_context, save_workspace_snapshot, validate_task_id, workspace_state_digest
from .workspace_writer_lock import acquire as acquire_workspace_writer_lock
from .workspace_writer_lock import current_owner as current_workspace_writer_owner
from .workspace_writer_lock import release as release_workspace_writer_lock


def _apply_project_context_projection(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    """Consume an optional project-owned context projection without binding Generic Runtime to it."""
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


def start(root: Path, task_id: str, request: str, seed_files: list[str] | None = None, owner_pid: int | None = None, mode: str = 'writer') -> dict[str, Any]:
    """Start one task, capture task-start workspace, then run one Full Impact Scan.

    A physical workspace permits one coding writer at a time. Read-only reviewer tasks do
    not acquire the writer lock and may coexist with the active writer.
    """
    root = root.resolve(); validate_task_id(task_id); cleanup_other_tasks(root, task_id)
    normalized_mode = str(mode or 'writer').lower()
    if normalized_mode not in {'writer', 'readonly'}:
        raise ValueError('INVALID_TASK_MODE')
    effective_pid = int(owner_pid if owner_pid is not None else os.getpid())
    acquired_writer = False
    if normalized_mode == 'writer':
        acquire_workspace_writer_lock(root, task_id, effective_pid)
        acquired_writer = True
    try:
        snapshot = save_workspace_snapshot(root, task_id)
        ctx = scan(root, task_id, request, seed_files or [], effective_pid)
        ctx['task_start_workspace_snapshot'] = snapshot.name
        ctx['task_mode'] = normalized_mode
        ctx = _apply_project_context_projection(root, ctx)
        save_context(root, task_id, ctx)
        return ctx
    except BaseException:
        if acquired_writer:
            try:
                release_workspace_writer_lock(root, task_id)
            except Exception:
                pass
        cleanup_task(root, task_id)
        raise


def reconcile_task(root: Path, task_id: str) -> dict[str, Any]:
    return reconcile(root, task_id)


def run_gates(root: Path, task_id: str, timeout: int = 600) -> dict[str, Any]:
    """Unified success-path entrypoint: reconcile first, then run required gates."""
    reconciliation = reconcile_task(root, task_id)
    if reconciliation.get('status') != 'PASS':
        return {
            'task_id': task_id,
            'status': 'BLOCKED',
            'reason': 'FINAL_RECONCILIATION_FAILED',
            'reconciliation': reconciliation,
            'results': [],
        }
    return run_required(root, task_id, timeout=timeout)


def _product_decision_status(ctx: dict[str, Any]) -> str:
    status = str(ctx.get('product_decision_status') or '').upper()
    if status in {'NOT_REQUIRED', 'REQUIRED', 'RESOLVED'}:
        return status
    return 'REQUIRED' if ctx.get('product_decision_mode') == 'PRODUCT_DECISION_REQUIRED' else 'NOT_REQUIRED'


def resolve_product_decision(root: Path, task_id: str, decision: str) -> dict[str, Any]:
    """Record an explicit user product decision; reviewers/coders cannot auto-resolve it."""
    root = root.resolve(); validate_task_id(task_id)
    text = str(decision or '').strip()
    if not text:
        raise ValueError('PRODUCT_DECISION_TEXT_REQUIRED')
    ctx = load_context(root, task_id)
    if _product_decision_status(ctx) != 'REQUIRED':
        raise ValueError('PRODUCT_DECISION_NOT_REQUIRED')
    ctx['product_decision_status'] = 'RESOLVED'
    ctx['product_decision_source'] = 'user'
    ctx['product_decision'] = text
    ctx['product_decision_resolved_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    save_context(root, task_id, ctx)
    return ctx


def _assert_success_closure(root: Path, task_id: str) -> None:
    ctx = load_context(root, task_id)
    if _product_decision_status(ctx) == 'REQUIRED':
        raise RuntimeError('PRODUCT_DECISION_REQUIRED')
    if not final_reconciliation_is_current(root, task_id, ctx):
        raise RuntimeError('FINAL_RECONCILIATION_REQUIRED')

    result_path = gate_results_path(root, task_id)
    if not result_path.is_file():
        raise RuntimeError('REQUIRED_GATES_NOT_EXECUTED')
    try:
        report = json.loads(result_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError('REQUIRED_GATE_RESULT_MISSING') from exc
    if not isinstance(report, dict) or report.get('task_id') != task_id:
        raise RuntimeError('GATE_RESULT_TASK_MISMATCH')
    if report.get('status') != 'PASS':
        if report.get('reason') == 'GATE_RESULT_STALE':
            raise RuntimeError('GATE_RESULT_STALE')
        raise RuntimeError('REQUIRED_GATES_NOT_PASS')

    required = [str(x) for x in ctx.get('required_gates', [])]
    results = [x for x in report.get('results', []) if isinstance(x, dict)]
    by_gate = {str(x.get('gate')): x for x in results if x.get('gate')}
    missing = [gate for gate in required if gate not in by_gate]
    if missing:
        raise RuntimeError('REQUIRED_GATE_RESULT_MISSING')
    if any(str(by_gate[gate].get('status')) != 'PASS' for gate in required):
        raise RuntimeError('REQUIRED_GATES_NOT_PASS')
    if any(str(by_gate[gate].get('task_id')) != task_id for gate in required):
        raise RuntimeError('GATE_RESULT_TASK_MISMATCH')

    recorded_digest = str(report.get('workspace_digest') or '')
    current_digest = workspace_state_digest(root, [str(x) for x in ctx.get('affected_files', [])])
    if not recorded_digest or current_digest != recorded_digest:
        raise RuntimeError('GATE_RESULT_STALE')


def finish(root: Path, task_id: str, outcome: str = 'SUCCESS') -> None:
    """Release local state; success requires current reconciliation, decision, and gates."""
    root = root.resolve(); validate_task_id(task_id)
    normalized = str(outcome or 'SUCCESS').upper()
    if normalized not in {'SUCCESS', 'COMPLETED', 'CANCELLED', 'ABORTED', 'FAILED'}:
        raise ValueError('INVALID_TASK_OUTCOME')
    if normalized in {'SUCCESS', 'COMPLETED'}:
        _assert_success_closure(root, task_id)
    owner = current_authority_lock_owner(root)
    if owner and owner.get('task_id') == task_id:
        release_authority_lock(root, task_id)
    writer = current_workspace_writer_owner(root)
    if writer and writer.get('task_id') == task_id:
        release_workspace_writer_lock(root, task_id)
    cleanup_task(root, task_id)


@contextmanager
def lifecycle(root: Path, task_id: str, request: str, seed_files: list[str] | None = None) -> Iterator[dict[str, Any]]:
    """Cleanup-oriented task context; it never claims successful completion by itself."""
    ctx = start(root, task_id, request, seed_files)
    try:
        yield ctx
    except KeyboardInterrupt:
        finish(root, task_id, 'CANCELLED')
        raise
    except BaseException:
        finish(root, task_id, 'FAILED')
        raise
    else:
        finish(root, task_id, 'ABORTED')


def main() -> int:
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('start'); s.add_argument('--root', default='.'); s.add_argument('--task-id', required=True); s.add_argument('--request', required=True); s.add_argument('--seed-file', action='append', default=[]); s.add_argument('--mode', choices=['writer','readonly'], default='writer')
    r = sub.add_parser('reconcile'); r.add_argument('--root', default='.'); r.add_argument('--task-id', required=True)
    g = sub.add_parser('gate'); g.add_argument('--root', default='.'); g.add_argument('--task-id', required=True); g.add_argument('--timeout', type=int, default=600)
    d = sub.add_parser('resolve-product-decision'); d.add_argument('--root', default='.'); d.add_argument('--task-id', required=True); d.add_argument('--decision', required=True)
    f = sub.add_parser('finish'); f.add_argument('--root', default='.'); f.add_argument('--task-id', required=True); f.add_argument('--outcome', default='SUCCESS', choices=['SUCCESS','COMPLETED','CANCELLED','ABORTED','FAILED'])
    args = p.parse_args()
    try:
        if args.cmd == 'start': print(json.dumps(start(Path(args.root), args.task_id, args.request, args.seed_file, owner_pid=os.getppid(), mode=args.mode), ensure_ascii=False, indent=2))
        elif args.cmd == 'reconcile':
            result = reconcile_task(Path(args.root), args.task_id); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result['status'] == 'PASS' else 1
        elif args.cmd == 'gate':
            result = run_gates(Path(args.root), args.task_id, args.timeout); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result['status'] == 'PASS' else 1
        elif args.cmd == 'resolve-product-decision':
            result = resolve_product_decision(Path(args.root), args.task_id, args.decision); print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            finish(Path(args.root), args.task_id, args.outcome)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(str(exc)); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
