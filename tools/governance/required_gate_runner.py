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
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from tools.environment import project_environment, sanitize_database_error

from .project_profile import command_tokens, format_command, gate_config, project_config, runtime_config
from .task_context import final_reconciliation_is_current, load_context, task_dir, workspace_state_digest

# Compatibility hook for tests and installations without a project profile.
# Project-specific commands belong in .governance/gates.yaml, not in Generic Runtime.
ENGINEERING_GATE_COMMANDS: dict[str, list[str]] = {
    'governance_lite_validator': [sys.executable, 'tools/governance/governance_lite_validator.py', '--root', '.'],
}
GATE_COMMANDS = ENGINEERING_GATE_COMMANDS


def _gate_env(root: Path) -> dict[str, str]:
    # repo/.env is merged under the explicit process environment; shell/CI values win.
    env = project_environment(root=root)
    extra = runtime_config(root).get('python_source_paths') or []
    paths = [str((root / str(x)).resolve()) for x in extra if (root / str(x)).exists()]
    current = env.get('PYTHONPATH')
    if current:
        paths.append(current)
    if paths:
        env['PYTHONPATH'] = os.pathsep.join(paths)
    return env


def _nested(data: dict[str, Any], key: str) -> Any:
    cur: Any = data
    for part in key.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def load_runtime_gate_catalog(root: Path) -> dict[str, dict[str, Any]]:
    """Load an optional project-owned formal gate catalog by configured path."""
    root = root.resolve()
    config = project_config(root).get('formal_gate_catalog') or {}
    if not isinstance(config, dict):
        return {}
    rel = config.get('path')
    if not isinstance(rel, str) or not rel:
        return {}
    path = root / rel
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        return {}
    catalog_key = str(config.get('catalog_key') or 'runtime_gate_catalog')
    gates_key = str(config.get('gates_key') or 'gates')
    catalog = _nested(data, catalog_key)
    if not isinstance(catalog, dict):
        return {}
    gates = catalog.get(gates_key) or []
    out: dict[str, dict[str, Any]] = {}
    for item in gates:
        if not isinstance(item, dict):
            continue
        gate_id = item.get('gate_id'); command = item.get('command')
        if isinstance(gate_id, str) and gate_id and isinstance(command, str) and command:
            out[gate_id] = item
    return out


def formal_gate_ids(root: Path) -> set[str]:
    return set(load_runtime_gate_catalog(root))


def formal_gates_for_conditions(root: Path, conditions: set[str]) -> set[str]:
    selected: set[str] = set()
    for gate_id, item in load_runtime_gate_catalog(root).items():
        required_when = {str(v) for v in item.get('required_when') or []}
        if required_when & conditions:
            selected.add(gate_id)
    return selected


def runtime_supported_formal_gate_ids(root: Path) -> set[str]:
    return set(load_runtime_gate_catalog(root))


def _acceptance_command(root: Path, ctx: dict[str, Any]) -> list[str] | None:
    configured = command_tokens(runtime_config(root).get('task_acceptance_command'))
    if configured:
        return format_command(configured, root=root, task_id=str(ctx.get('task_id', '')), files=[str(x) for x in ctx.get('affected_files', [])])
    tests = [str(x) for x in ctx.get('relevant_tests', []) if isinstance(x, str)]
    py_tests = [x for x in tests if x.endswith('.py') or '/tests/' in x or x.startswith('tests/')]
    if py_tests:
        return [sys.executable, '-m', 'pytest', *py_tests, '-q']
    return None


def command_for_gate(root: Path, gate: str, ctx: dict[str, Any]) -> list[str] | None:
    root = root.resolve()
    formal = load_runtime_gate_catalog(root)
    if gate in formal:
        command = str(formal[gate]['command']).strip()
        if command == 'task-specific acceptance tests':
            return _acceptance_command(root, ctx)
        return shlex.split(command)

    configured = gate_config(root).get(gate) or {}
    tokens = command_tokens(configured.get('command')) if isinstance(configured, dict) else None
    if tokens:
        return format_command(tokens, root=root, task_id=str(ctx.get('task_id', '')), files=[str(x) for x in ctx.get('affected_files', [])])

    cmd = ENGINEERING_GATE_COMMANDS.get(gate)
    return list(cmd) if cmd else None


def _product_decision_status(ctx: dict[str, Any]) -> str:
    status = str(ctx.get('product_decision_status') or '').upper()
    if status in {'NOT_REQUIRED', 'REQUIRED', 'RESOLVED'}:
        return status
    return 'REQUIRED' if ctx.get('product_decision_mode') == 'PRODUCT_DECISION_REQUIRED' else 'NOT_REQUIRED'


def run_required(root: Path, task_id: str, timeout: int = 600) -> dict[str, Any]:
    root = root.resolve()
    ctx = load_context(root, task_id)

    def write_report(report: dict[str, Any]) -> dict[str, Any]:
        report.setdefault('task_id', task_id)
        report.setdefault('executed_at', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        out = task_dir(root, task_id) / 'gate-results.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return report

    # Product sovereignty is a mechanical gate. Reviewers may explain the decision,
    # but only an explicit user resolution can move REQUIRED -> RESOLVED.
    if _product_decision_status(ctx) == 'REQUIRED':
        return write_report({
            'status': 'BLOCKED',
            'reason': 'PRODUCT_DECISION_REQUIRED',
            'results': [],
        })

    # Final Workspace Reconciliation is a mechanical precondition, not a convention.
    if not final_reconciliation_is_current(root, task_id, ctx):
        return write_report({
            'status': 'BLOCKED',
            'reason': 'FINAL_RECONCILIATION_REQUIRED',
            'results': [],
        })

    affected_files = [str(x) for x in ctx.get('affected_files', [])]
    gate_digest = workspace_state_digest(root, affected_files)
    configured_gates = gate_config(root)
    configured_formal = load_runtime_gate_catalog(root)
    allow_no_gates = bool(runtime_config(root).get('allow_no_gates', False))
    if not configured_gates and not configured_formal:
        if allow_no_gates:
            return write_report({
                'status': 'PASS',
                'reason': 'NO_CONFIGURED_GATE_ALLOWED',
                'workspace_digest': gate_digest,
                'results': [],
            })
        return write_report({
            'status': 'BLOCKED',
            'reason': 'NO_CONFIGURED_GATE',
            'workspace_digest': gate_digest,
            'results': [],
        })

    required = [str(x) for x in ctx.get('required_gates', [])]
    if not required:
        return write_report({
            'status': 'PASS',
            'reason': 'NO_REQUIRED_GATE',
            'workspace_digest': gate_digest,
            'results': [],
        })

    results: list[dict[str, Any]] = []
    for gate in required:
        cmd = command_for_gate(root, gate, ctx)
        if cmd is None:
            results.append({
                'task_id': task_id, 'gate': gate, 'status': 'NOT_CONFIGURED',
                'reason': 'NO_CONFIGURED_GATE', 'exit_code': None,
                'workspace_digest': gate_digest,
            })
            continue
        started = time.time()
        try:
            proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=timeout, env=_gate_env(root))
            status = 'PASS' if proc.returncode == 0 else 'FAIL'
            text = f'{proc.stdout}\n{proc.stderr}'
            if proc.returncode != 0 and ('BLOCKED' in text or 'ENVIRONMENT_UNAVAILABLE' in text or 'NOT_EXECUTED' in text):
                status = 'BLOCKED'
            results.append({
                'task_id': task_id, 'gate': gate, 'status': status,
                'workspace_digest': gate_digest,
                'command': ' '.join(shlex.quote(str(x)) for x in cmd), 'exit_code': proc.returncode,
                'duration_ms': round((time.time() - started) * 1000),
                'stdout_tail': sanitize_database_error(proc.stdout[-2000:]), 'stderr_tail': sanitize_database_error(proc.stderr[-2000:]),
            })
        except subprocess.TimeoutExpired as exc:
            results.append({'task_id': task_id, 'gate': gate, 'status': 'TIMEOUT', 'reason': 'TIMEOUT', 'workspace_digest': gate_digest, 'command': ' '.join(map(str, cmd)), 'exit_code': None,
                            'duration_ms': round((time.time() - started) * 1000), 'stderr_tail': sanitize_database_error(str(exc)[-2000:])})
        except FileNotFoundError as exc:
            results.append({'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'COMMAND_NOT_FOUND', 'workspace_digest': gate_digest, 'command': ' '.join(map(str, cmd)), 'exit_code': None,
                            'duration_ms': round((time.time() - started) * 1000), 'stderr_tail': sanitize_database_error(str(exc)[-2000:])})
        except PermissionError as exc:
            results.append({'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'PERMISSION_ERROR', 'workspace_digest': gate_digest, 'command': ' '.join(map(str, cmd)), 'exit_code': None,
                            'duration_ms': round((time.time() - started) * 1000), 'stderr_tail': sanitize_database_error(str(exc)[-2000:])})
        except OSError as exc:
            results.append({'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'OS_EXECUTION_ERROR', 'workspace_digest': gate_digest, 'command': ' '.join(map(str, cmd)), 'exit_code': None,
                            'duration_ms': round((time.time() - started) * 1000), 'stderr_tail': sanitize_database_error(str(exc)[-2000:])})
        except subprocess.SubprocessError as exc:
            results.append({'task_id': task_id, 'gate': gate, 'status': 'FAIL', 'reason': 'SUBPROCESS_ERROR', 'workspace_digest': gate_digest, 'command': ' '.join(map(str, cmd)), 'exit_code': None,
                            'duration_ms': round((time.time() - started) * 1000), 'stderr_tail': sanitize_database_error(str(exc)[-2000:])})

    # A workspace mutation during gate execution invalidates the whole run.
    current_digest = workspace_state_digest(root, affected_files)
    if current_digest != gate_digest:
        return write_report({
            'status': 'BLOCKED',
            'reason': 'GATE_RESULT_STALE',
            'workspace_digest': gate_digest,
            'current_workspace_digest': current_digest,
            'results': results,
        })

    statuses = {str(x.get('status')) for x in results}
    if statuses == {'PASS'}:
        overall = 'PASS'
        reason = None
    elif statuses & {'BLOCKED', 'NOT_CONFIGURED'}:
        overall = 'BLOCKED'
        reason = 'REQUIRED_GATES_NOT_PASS'
    else:
        overall = 'FAIL'
        reason = 'REQUIRED_GATES_NOT_PASS'
    report: dict[str, Any] = {
        'status': overall,
        'workspace_digest': gate_digest,
        'results': results,
    }
    if reason:
        report['reason'] = reason
    return write_report(report)


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.'); p.add_argument('--task-id', required=True); p.add_argument('--timeout', type=int, default=600); a = p.parse_args()
    r = run_required(Path(a.root), a.task_id, a.timeout); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
