from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import ast
import json
import os
import signal
import subprocess
import sys
import tempfile
import shutil
import time
from pathlib import Path
from typing import Any

import yaml

from .workspace_path_policy import classify_relative_path, consumer_categories, is_link_or_reparse, load_policy


CONTRACT_GROUP_TIMEOUT_ENV = 'ATP_GOVERNANCE_CONTRACT_GROUP_TIMEOUT_SECONDS'
DEFAULT_CONTRACT_GROUP_TIMEOUT_SECONDS = 600
MIN_CONTRACT_GROUP_TIMEOUT_SECONDS = 1
MAX_CONTRACT_GROUP_TIMEOUT_SECONDS = 1800


def contract_group_timeout_seconds(environ: dict[str, str] | None = None) -> int:
    raw = (environ if environ is not None else os.environ).get(CONTRACT_GROUP_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_CONTRACT_GROUP_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError('GOVERNANCE_CONTRACT_GROUP_TIMEOUT_INVALID') from exc
    return _validated_contract_group_timeout_seconds(value)


def _validated_contract_group_timeout_seconds(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('GOVERNANCE_CONTRACT_GROUP_TIMEOUT_INVALID')
    if not MIN_CONTRACT_GROUP_TIMEOUT_SECONDS <= value <= MAX_CONTRACT_GROUP_TIMEOUT_SECONDS:
        raise ValueError('GOVERNANCE_CONTRACT_GROUP_TIMEOUT_OUT_OF_RANGE')
    return value


def discover_governance_tests(root: Path) -> list[Path]:
    """Discover the stable Governance Contract suite by capability naming, never release version."""
    base = root / 'tests' / 'contract'
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob('test_governance_*.py') if p.is_file())


def _write_self_probe_profile(root: Path) -> None:
    agent = root / '.governance'; agent.mkdir(parents=True, exist_ok=True)
    (root / 'src').mkdir(parents=True, exist_ok=True)
    (agent / 'project.yaml').write_text('schema_version: 1\nproject: {name: standalone-self-probe}\nruntime: {use_legacy_domain_metadata: false}\n', encoding='utf-8')
    (agent / 'domains.yaml').write_text('schema_version: 1\ndomains:\n  APP: {kind: implementation, paths: ["src/**"], gates: [check]}\n', encoding='utf-8')
    gate_text = 'schema_version: 1\ngates:\n  check:\n    command: [' + json.dumps(sys.executable) + ', -c, "print(1)"]\n'
    (agent / 'gates.yaml').write_text(gate_text, encoding='utf-8')
    (agent / 'authorities.yaml').write_text('schema_version: 1\nauthorities: {}\n', encoding='utf-8')
    (agent / 'reviewers.yaml').write_text('schema_version: 1\nreviewers: {}\n', encoding='utf-8')
    (agent / 'policies.yaml').write_text('schema_version: 1\npolicies: {}\n', encoding='utf-8')
    (agent / 'technology.yaml').write_text('schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n', encoding='utf-8')
    (agent / 'workspace-path-policy.yaml').write_text("""policy_id: WORKSPACE_PATH_POLICY
version: 1
categories:
  SOURCE: {}
  AUTHORITY: {}
  GENERATED_REQUIRED: {}
  TRANSIENT:
    path_prefixes: [.tmp]
    directory_names: [.git, .venv, .mypy_cache, .ruff_cache]
  CACHE:
    directory_names: [__pycache__, .pytest_cache, node_modules]
    suffixes: [.pyc, .pyo]
  BUILD_OUTPUT:
    directory_names: [dist, build, coverage]
  RUNTIME_OUTPUT:
    directory_names: [test-results, .runtime]
  SECRET:
    exact_names: [.env]
consumers:
  workspace_tracking: {include_categories: [SOURCE, AUTHORITY, GENERATED_REQUIRED]}
  impact_scan: {include_categories: [SOURCE, AUTHORITY, GENERATED_REQUIRED]}
  gate_workspace_digest: {include_categories: [SOURCE, AUTHORITY, GENERATED_REQUIRED]}
  delivery_package: {include_categories: [SOURCE, AUTHORITY, GENERATED_REQUIRED]}
  cleanup_validation: {forbidden_persisted_categories: [TRANSIENT, CACHE, BUILD_OUTPUT, RUNTIME_OUTPUT, SECRET]}
""", encoding='utf-8')


def _standalone_semantic_probe_errors() -> list[str]:
    errors: list[str] = []
    from .required_gate_runner import run_required
    from .task_context import load_context, save_context, workspace_change_records_since_start
    from .task_governance import finish, reconcile_task, run_gates, start

    # Workspace Baseline + no-Git workflow + transient filtering.
    with tempfile.TemporaryDirectory() as temp:
        probe = Path(temp); _write_self_probe_profile(probe)
        (probe / 'src/a.py').write_text('x=1\n', encoding='utf-8')
        (probe / 'src/user_existing.py').write_text('preexisting local edit\n', encoding='utf-8')
        start(probe, 'NOGIT', 'change app', ['src/a.py'])
        (probe / 'src/a.py').write_text('x=2\n', encoding='utf-8')
        (probe / 'src/new.py').write_text('new=1\n', encoding='utf-8')
        (probe / '__pycache__').mkdir(); (probe / '__pycache__/noise.pyc').write_bytes(b'noise')
        changes = {item['path']: item['change'] for item in workspace_change_records_since_start(probe, 'NOGIT')}
        if changes.get('src/a.py') != 'MODIFIED' or changes.get('src/new.py') != 'ADDED':
            errors.append(f'workspace baseline probe failed: {changes}')
        if 'src/user_existing.py' in changes or any('__pycache__' in path or path.startswith('.tmp/') for path in changes):
            errors.append(f'transient/pre-task isolation probe failed: {changes}')
        gate = run_gates(probe, 'NOGIT', timeout=3)
        if gate.get('status') != 'PASS':
            errors.append(f'no-git gate probe failed: {gate}')
            finish(probe, 'NOGIT', 'ABORTED')
        else:
            try:
                finish(probe, 'NOGIT', 'SUCCESS')
            except Exception as exc:
                errors.append(f'no-git finish probe failed: {exc}')
                finish(probe, 'NOGIT', 'ABORTED')

    # Required Gate bypass and Product Decision blocking.
    with tempfile.TemporaryDirectory() as temp:
        probe = Path(temp); _write_self_probe_profile(probe); (probe / 'src/a.py').write_text('x=1\n', encoding='utf-8')
        start(probe, 'BYPASS', 'change app', ['src/a.py']); (probe / 'src/a.py').write_text('x=2\n', encoding='utf-8'); reconcile_task(probe, 'BYPASS')
        try:
            finish(probe, 'BYPASS', 'SUCCESS')
            errors.append('required-gate bypass probe failed: SUCCESS accepted')
        except RuntimeError as exc:
            if str(exc) != 'REQUIRED_GATES_NOT_EXECUTED': errors.append(f'required-gate bypass wrong reason: {exc}')
            finish(probe, 'BYPASS', 'ABORTED')

        (probe / 'src/b.py').write_text('x=1\n', encoding='utf-8')
        start(probe, 'PRODUCT', 'change app', ['src/b.py']); (probe / 'src/b.py').write_text('x=2\n', encoding='utf-8'); reconcile_task(probe, 'PRODUCT')
        ctx = load_context(probe, 'PRODUCT'); ctx['product_decision_status'] = 'REQUIRED'; save_context(probe, 'PRODUCT', ctx)
        blocked = run_required(probe, 'PRODUCT', timeout=3)
        if blocked.get('status') != 'BLOCKED' or blocked.get('reason') != 'PRODUCT_DECISION_REQUIRED':
            errors.append(f'product-decision gate block probe failed: {blocked}')
        try:
            finish(probe, 'PRODUCT', 'SUCCESS')
            errors.append('product-decision finish block probe failed: SUCCESS accepted')
        except RuntimeError as exc:
            if str(exc) != 'PRODUCT_DECISION_REQUIRED': errors.append(f'product-decision finish wrong reason: {exc}')
            finish(probe, 'PRODUCT', 'ABORTED')

    # Gate PASS freshness is bound to affected-file content, not Git.
    with tempfile.TemporaryDirectory() as temp:
        probe = Path(temp); _write_self_probe_profile(probe); (probe / 'src/a.py').write_text('x=1\n', encoding='utf-8')
        start(probe, 'STALE', 'change app', ['src/a.py']); (probe / 'src/a.py').write_text('x=2\n', encoding='utf-8')
        if run_gates(probe, 'STALE', timeout=3).get('status') != 'PASS':
            errors.append('gate freshness setup failed')
            finish(probe, 'STALE', 'ABORTED')
        else:
            (probe / 'src/a.py').write_text('x=3\n', encoding='utf-8')
            try:
                finish(probe, 'STALE', 'SUCCESS')
                errors.append('gate freshness probe failed: stale PASS accepted')
            except RuntimeError as exc:
                if str(exc) != 'GATE_RESULT_STALE': errors.append(f'gate freshness wrong reason: {exc}')
                finish(probe, 'STALE', 'ABORTED')

    # Authority lock live-owner mutual exclusion.
    with tempfile.TemporaryDirectory() as temp:
        probe = Path(temp)
        module_root = str(Path(__file__).resolve().parents[2])
        holder_code = (
            'import sys,time; from pathlib import Path; sys.path.insert(0,' + repr(module_root) + '); '
            'from tools.governance.authority_lock import acquire; acquire(Path(sys.argv[1]),"HOLDER","authority"); '
            'print("ACQUIRED", flush=True); time.sleep(1.2)'
        )
        holder = subprocess.Popen([sys.executable, '-c', holder_code, str(probe)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = holder.stdout.readline().strip() if holder.stdout else ''
            second = subprocess.run([sys.executable, str(Path(__file__).with_name('authority_lock.py')), 'acquire', '--root', str(probe), '--task-id', 'SECOND', '--file', 'authority'], capture_output=True, text=True, timeout=2)
            if line != 'ACQUIRED' or second.returncode == 0:
                errors.append(f'authority lock single-owner probe failed: holder={line!r} second={second.returncode}')
        finally:
            holder.terminate()
            try: holder.wait(timeout=2)
            except subprocess.TimeoutExpired: holder.kill(); holder.wait(timeout=2)


    # Process identity safety: probe current process without changing state and detect reuse.
    from .process_identity import PID_REUSED, RUNNING_MATCH, current_process_identity, inspect_process
    identity = current_process_identity()
    current = inspect_process(identity.pid, identity.creation_time)
    if identity.creation_time and current.status != RUNNING_MATCH:
        errors.append(f'process identity live-owner probe failed: {current.status}')
    if identity.creation_time:
        reused = inspect_process(identity.pid, 'synthetic-different-creation-identity')
        if reused.status != PID_REUSED:
            errors.append(f'process identity PID reuse probe failed: {reused.status}')

    # Workspace writer ownership: one writer, readonly reviewer may coexist.
    with tempfile.TemporaryDirectory() as temp:
        probe = Path(temp); _write_self_probe_profile(probe); (probe / 'src/a.py').write_text('x=1\n', encoding='utf-8')
        try:
            start(probe, 'WRITER', 'change app', ['src/a.py'], mode='writer')
            try:
                start(probe, 'SECOND_WRITER', 'change app', ['src/a.py'], mode='writer')
                errors.append('workspace writer probe failed: second writer acquired')
                finish(probe, 'SECOND_WRITER', 'ABORTED')
            except RuntimeError as exc:
                if str(exc) != 'WORKSPACE_WRITER_BUSY':
                    errors.append(f'workspace writer wrong reason: {exc}')
            try:
                reviewer = start(probe, 'READONLY_REVIEWER', 'review app', ['src/a.py'], mode='readonly')
                if reviewer.get('task_mode') != 'readonly':
                    errors.append(f'workspace readonly reviewer mode failed: {reviewer.get("task_mode")}')
                finish(probe, 'READONLY_REVIEWER', 'ABORTED')
            except Exception as exc:
                errors.append(f'workspace readonly reviewer blocked: {exc}')
        finally:
            try: finish(probe, 'WRITER', 'ABORTED')
            except Exception: pass
    return errors

def _standalone_self_contract(root: Path) -> dict[str, Any]:
    """Mechanical fallback for installed Standalone projects that do not ship a project test suite."""
    errors: list[str] = []
    runtime = root / 'tools' / 'governance'
    required_runtime = {
        'governance_lite_validator.py', 'governance_contract_test.py', 'impact_scan.py',
        'incremental_closure.py', 'final_reconciliation.py', 'required_gate_runner.py',
        'task_governance.py', 'project_profile.py', 'task_context.py', 'authority_lock.py',
        'workspace_writer_lock.py', 'process_identity.py', 'workspace_path_policy.py', 'workspace-path-policy.yaml', 'git_readonly_adapter.py',
    }
    missing = sorted(name for name in required_runtime if not (runtime / name).is_file())
    errors.extend(f'missing runtime file: {name}' for name in missing)

    for path in sorted(runtime.glob('*.py')):
        try:
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        except Exception as exc:  # pragma: no cover - exercised only on broken delivery
            errors.append(f'python compile failed: {path.name}: {exc}')

    domains_path = root / '.governance' / 'domains.yaml'
    gates_path = root / '.governance' / 'gates.yaml'
    try:
        domains = (yaml.safe_load(domains_path.read_text(encoding='utf-8')) or {}).get('domains') or {}
        governance = domains.get('GOVERNANCE') or {}
        paths = {str(x) for x in governance.get('paths') or []}
        gates = {str(x) for x in governance.get('gates') or []}
        for expected in ('AGENTS.md', '.governance/**', '.agents/**', '.codex/**', 'tools/governance/**', 'agent-governance-lite/**'):
            if expected not in paths:
                errors.append(f'GOVERNANCE domain missing path: {expected}')
        for expected in ('governance_lite_validator', 'governance_contract_test'):
            if expected not in gates:
                errors.append(f'GOVERNANCE domain missing gate: {expected}')
    except Exception as exc:
        errors.append(f'cannot parse governance domain: {exc}')

    try:
        registry = (yaml.safe_load(gates_path.read_text(encoding='utf-8')) or {}).get('gates') or {}
        for expected in ('governance_lite_validator', 'governance_contract_test'):
            cfg = registry.get(expected) or {}
            if not cfg.get('command'):
                errors.append(f'gate registry missing command: {expected}')
    except Exception as exc:
        errors.append(f'cannot parse gate registry: {exc}')

    errors.extend(_standalone_semantic_probe_errors())
    return {
        'status': 'PASS' if not errors else 'FAIL',
        'mode': 'STANDALONE_SELF_CONTRACT',
        'test_count': 9,
        'errors': errors,
    }


def _execution_group(path: Path) -> str:
    """Read optional stable per-suite isolation metadata without importing tests."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except Exception:
        return 'default'
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GOVERNANCE_TEST_GROUP' for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value or 'default'
    return 'default'


def _contract_copy_ignore(root: Path):
    root = root.resolve()
    policy = load_policy(root)
    included = consumer_categories(policy, 'delivery_package')

    def ignore(directory: str, names: list[str]) -> list[str]:
        current = Path(directory)
        ignored: list[str] = []
        for name in names:
            candidate = current / name
            rel = candidate.relative_to(root)
            probe = rel / '__policy_probe__' if candidate.is_dir() else rel
            if is_link_or_reparse(candidate) or classify_relative_path(probe, policy) not in included:
                ignored.append(name)
        return ignored

    return ignore


def _terminate_process_tree(proc: subprocess.Popen[Any]) -> str | None:
    if proc.poll() is not None:
        return None
    error: str | None = None
    if os.name == 'nt':
        terminated = subprocess.run(
            ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10, check=False,
        )
        if terminated.returncode != 0:
            error = f'TASKKILL_EXIT_{terminated.returncode}'
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name != 'nt':
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            proc.kill()
        proc.wait(timeout=5)
    if os.name != 'nt':
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            pass
        else:
            os.killpg(proc.pid, signal.SIGKILL)
            error = 'PROCESS_GROUP_REQUIRED_SIGKILL'
    return error


def _remove_isolated_workspace(path: Path) -> str | None:
    last_error: OSError | None = None
    for _ in range(3):
        try:
            shutil.rmtree(path)
            return None
        except FileNotFoundError:
            return None
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    return str(last_error) if last_error else 'UNKNOWN_CLEANUP_ERROR'


def _run_isolated_group(root: Path, group: str, paths: list[Path], timeout_seconds: int) -> dict[str, Any]:
    """Copy the workspace once and execute one stable capability group in one pytest process."""
    timeout_seconds = _validated_contract_group_timeout_seconds(timeout_seconds)
    rel_paths = [path.relative_to(root).as_posix() for path in paths]
    temp_path = Path(tempfile.mkdtemp(prefix=f'governance-contract-{group}-'))
    result: dict[str, Any]
    try:
        isolated_root = temp_path / 'project'
        shutil.copytree(root, isolated_root, ignore=_contract_copy_ignore(root))
        log_dir = temp_path / 'logs'; log_dir.mkdir(exist_ok=True)
        stdout_path = log_dir / 'pytest.out'; stderr_path = log_dir / 'pytest.err'
        with stdout_path.open('w', encoding='utf-8') as stdout_fh, stderr_path.open('w', encoding='utf-8') as stderr_fh:
            env = os.environ.copy()
            env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            popen_options: dict[str, Any] = {'start_new_session': True} if os.name != 'nt' else {
                'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
            }
            proc = subprocess.Popen(
                [sys.executable, '-m', 'pytest', '-q', *rel_paths],
                cwd=isolated_root, stdout=stdout_fh, stderr=stderr_fh, env=env,
                **popen_options,
            )
            try:
                return_code = proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                termination_error = _terminate_process_tree(proc)
                result = {
                    'group': group, 'files': rel_paths, 'workspace_copies': 1,
                    'pytest_processes': 1, 'timeout_seconds': timeout_seconds,
                    'exit_code': 124, 'reason': 'TIMEOUT',
                }
                if termination_error:
                    result['process_tree_cleanup_error'] = termination_error
            else:
                result = {
                    'group': group, 'files': rel_paths, 'workspace_copies': 1,
                    'pytest_processes': 1, 'timeout_seconds': timeout_seconds,
                    'exit_code': int(return_code),
                }
                if return_code != 0:
                    result['stdout_tail'] = stdout_path.read_text(encoding='utf-8', errors='replace')[-6000:]
                    result['stderr_tail'] = stderr_path.read_text(encoding='utf-8', errors='replace')[-6000:]
    except Exception as exc:
        result = {
            'group': group, 'files': rel_paths, 'workspace_copies': 0,
            'pytest_processes': 0, 'timeout_seconds': timeout_seconds,
            'exit_code': 125, 'reason': f'ISOLATION_ERROR: {exc}',
        }
    cleanup_error = _remove_isolated_workspace(temp_path)
    if cleanup_error:
        result['cleanup_error'] = cleanup_error
        if result.get('reason') != 'TIMEOUT':
            result['exit_code'] = 125
            result['reason'] = 'ISOLATION_CLEANUP_ERROR'
    return result


def run(root: Path, timeout_seconds: int | None = None) -> dict[str, Any]:
    root = root.resolve()
    timeout_seconds = contract_group_timeout_seconds() if timeout_seconds is None else _validated_contract_group_timeout_seconds(timeout_seconds)
    tests = discover_governance_tests(root)
    if not tests:
        return _standalone_self_contract(root)

    grouped: dict[str, list[Path]] = {}
    for path in tests:
        grouped.setdefault(_execution_group(path), []).append(path)
    ordered_groups = [(name, sorted(paths)) for name, paths in sorted(grouped.items(), key=lambda item: (item[0] == 'authority', item[0]))]

    # Automatic discovery is the only suite registry. Each stable capability group
    # receives one isolated workspace copy and one pytest process. Groups are executed
    # sequentially because process/packaging/concurrency suites are I/O heavy; grouping
    # already removes the dominant copy amplification without sacrificing isolation.
    max_workers = 1
    group_results = [_run_isolated_group(root, name, paths, timeout_seconds) for name, paths in ordered_groups]
    overall = 0 if all(item.get('exit_code') == 0 for item in group_results) else 1
    rel = [p.relative_to(root).as_posix() for p in tests]
    return {
        'status': 'PASS' if overall == 0 else 'FAIL',
        'mode': 'PYTEST_AUTO_DISCOVERY_GROUPED_ISOLATED_WORKSPACES',
        'test_files': rel,
        'test_file_count': len(rel),
        'worker_count': max_workers,
        'group_count': len(group_results),
        'group_timeout_seconds': timeout_seconds,
        'workspace_copy_count': sum(int(item.get('workspace_copies', 0)) for item in group_results),
        'legacy_workspace_copy_count': len(rel),
        'exit_code': overall,
        'group_results': group_results,
    }



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--group', default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        timeout_seconds = contract_group_timeout_seconds()
    except ValueError as exc:
        print(json.dumps({'status': 'FAIL', 'reason': str(exc), 'environment_variable': CONTRACT_GROUP_TIMEOUT_ENV}, ensure_ascii=False, indent=2))
        return 1
    if args.group:
        tests = [p for p in discover_governance_tests(root) if _execution_group(p) == args.group]
        result = _run_isolated_group(root, args.group, tests, timeout_seconds) if tests else {
            'group': args.group, 'files': [], 'workspace_copies': 0,
            'timeout_seconds': timeout_seconds, 'exit_code': 125, 'reason': 'UNKNOWN_GROUP',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('exit_code') == 0 else 1
    result = run(root, timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
