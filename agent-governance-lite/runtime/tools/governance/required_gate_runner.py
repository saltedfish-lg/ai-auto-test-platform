from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import errno
import hashlib
import json
import os
import shlex
import shutil
import signal
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

WINDOWS_COMMAND_WRAPPERS = {'.bat', '.cmd'}
WINDOWS_DEFAULT_PATHEXT = ('.COM', '.EXE', '.BAT', '.CMD')
DEFAULT_GATE_TIMEOUT_SECONDS = 600
MIN_GATE_TIMEOUT_SECONDS = 1
MAX_GATE_TIMEOUT_SECONDS = 3600


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
    # Gate reports are UTF-8 artifacts. Pin Python child streams to the same
    # encoding so Windows' active code page cannot corrupt captured output.
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def _sanitized_captured_text(message: object, env: dict[str, str]) -> str:
    credential_urls = tuple(
        value for value in env.values()
        if isinstance(value, str) and '://' in value and '@' in value
    )
    return sanitize_database_error(message, *credential_urls)


def _captured_output_tail(message: object, env: dict[str, str], limit: int = 2000) -> str:
    return _sanitized_captured_text(message, env)[-limit:]


def _report_command(command: list[str], env: dict[str, str]) -> str:
    return _sanitized_captured_text(' '.join(shlex.quote(str(x)) for x in command), env)


def _identity_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return f'sha256:{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'


def _validated_timeout_seconds(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('gate timeout_seconds must be an integer')
    if not MIN_GATE_TIMEOUT_SECONDS <= value <= MAX_GATE_TIMEOUT_SECONDS:
        raise ValueError(
            f'gate timeout_seconds must be between {MIN_GATE_TIMEOUT_SECONDS} '
            f'and {MAX_GATE_TIMEOUT_SECONDS}'
        )
    return value


def _gate_timeout_seconds(root: Path, gate: str, default: int) -> int:
    configured = gate_config(root).get(gate) or {}
    return _validated_timeout_seconds(configured.get('timeout_seconds', default))


def _validated_identity_keys(value: object, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item and item == item.strip() and not any(ch.isspace() for ch in item)
        for item in value
    ):
        raise ValueError(f'execution_identity.{field} must be a list of non-empty environment names')
    if len(value) != len({item.casefold() for item in value}):
        raise ValueError(f'execution_identity.{field} must not contain duplicate environment names')
    secret_tokens = {'PASSWORD', 'SECRET', 'TOKEN', 'KEY', 'CREDENTIAL'}
    for item in value:
        if secret_tokens & set(item.upper().split('_')):
            raise ValueError(
                f'execution_identity.{field} must not use secret-bearing environment names'
            )
    return list(value)


def _execution_identity_metadata(root: Path, gate: str) -> dict[str, Any]:
    configured = gate_config(root).get(gate) or {}
    raw = configured.get('execution_identity') or {}
    if not isinstance(raw, dict):
        raise ValueError('execution_identity must be a mapping')
    allowed_fields = {
        'capability', 'runtime_environment_keys', 'database_environment_keys'
    }
    unknown_fields = set(raw) - allowed_fields
    if unknown_fields:
        raise ValueError(
            'execution_identity contains unknown fields: '
            + ', '.join(sorted(str(item) for item in unknown_fields))
        )
    capability = raw.get('capability', gate)
    if (
        not isinstance(capability, str)
        or not capability.strip()
        or capability != capability.strip()
    ):
        raise ValueError('execution_identity.capability must be a non-empty string')
    return {
        # No metadata means that the gate id is its capability. This makes reuse
        # opt-in and prevents equal commands with different semantics from merging.
        'capability': capability.strip(),
        'runtime_environment_keys': _validated_identity_keys(
            raw.get('runtime_environment_keys'), field='runtime_environment_keys'
        ),
        'database_environment_keys': _validated_identity_keys(
            raw.get('database_environment_keys'), field='database_environment_keys'
        ),
    }


def _environment_identity(
    env: dict[str, str], keys: list[str]
) -> tuple[str, list[str], list[str]]:
    values: list[dict[str, Any]] = []
    present: list[str] = []
    missing: list[str] = []
    for key in keys:
        value = env.get(key)
        if value is None or not value.strip():
            missing.append(key)
            values.append({'name': key, 'state': 'UNSET'})
            continue
        present.append(key)
        # Credential URLs keep their non-secret routing identity, while other
        # explicitly configured identity values remain opaque behind the digest.
        safe_value = sanitize_database_error(value, value) if '://' in value else value
        values.append({'name': key, 'state': 'SET', 'value_digest': _identity_digest(safe_value)})
    return _identity_digest(values), present, missing


def _canonical_command_digest(command: list[str], cwd: Path, env: dict[str, str]) -> str:
    resolved = _resolve_command(str(command[0]), cwd, env)
    resolved_path = os.path.normcase(str(Path(resolved).resolve()))
    launcher = resolved_path
    if os.name == 'nt' and Path(resolved).suffix.lower() in WINDOWS_COMMAND_WRAPPERS:
        configured_comspec = env.get('COMSPEC') or os.environ.get('COMSPEC') or 'cmd.exe'
        launcher = os.path.normcase(_resolve_windows_command(configured_comspec, cwd, env))
        # Validate that the same tokens can be represented by the actual wrapper.
        for value in (resolved_path, *(str(item) for item in command[1:])):
            _quote_windows_cmd_token(value)
    # Canonical argv may carry a credential URL. Redact it before it becomes
    # identity material; the report exposes only the resulting digest.
    safe_argv = [_sanitized_captured_text(str(item), env) for item in command[1:]]
    return _identity_digest({
        'launcher': launcher,
        'executable': resolved_path,
        'argv': safe_argv,
    })


def _execution_identity(
    root: Path,
    gate: str,
    command: list[str],
    env: dict[str, str],
    workspace_digest: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    metadata = _execution_identity_metadata(root, gate)
    runtime_digest, runtime_present, runtime_missing = _environment_identity(
        env, metadata['runtime_environment_keys']
    )
    database_digest, database_present, database_missing = _environment_identity(
        env, metadata['database_environment_keys']
    )
    command_digest = _canonical_command_digest(command, root, env)
    identity = _identity_digest({
        'canonical_command': command_digest,
        'capability': metadata['capability'],
        'runtime_identity': runtime_digest,
        'database_identity': database_digest,
        'timeout_seconds': timeout_seconds,
        'workspace_digest': workspace_digest,
    })
    missing = [*runtime_missing, *database_missing]
    return {
        'execution_identity': identity,
        'canonical_command_digest': command_digest,
        'capability_identity': metadata['capability'],
        'runtime_identity': runtime_digest,
        'runtime_identity_env_keys': metadata['runtime_environment_keys'],
        'runtime_identity_present_env_keys': runtime_present,
        'database_identity': database_digest,
        'database_identity_env_keys': metadata['database_environment_keys'],
        'database_identity_present_env_keys': database_present,
        'execution_reuse_eligible': not missing,
        'missing_identity_environment_keys': missing,
    }


def _windows_pathext(env: dict[str, str]) -> tuple[str, ...]:
    raw = env.get('PATHEXT') or ';'.join(WINDOWS_DEFAULT_PATHEXT)
    extensions: list[str] = []
    for value in raw.split(';'):
        value = value.strip()
        if value:
            normalized = value if value.startswith('.') else f'.{value}'
            if normalized.upper() not in {item.upper() for item in extensions}:
                extensions.append(normalized)
    return tuple(extensions) or WINDOWS_DEFAULT_PATHEXT


def _resolve_windows_command(command: str, cwd: Path, env: dict[str, str]) -> str:
    command_path = Path(command)
    if command_path.is_absolute():
        directories = [command_path.parent]
    elif command_path.parent != Path('.'):
        directories = [(cwd / command_path.parent).resolve()]
    else:
        directories = [cwd]
        for raw in (env.get('PATH') or '').split(os.pathsep):
            raw = raw.strip().strip('"')
            if not raw:
                continue
            directory = Path(raw)
            directory = directory if directory.is_absolute() else cwd / directory
            resolved_directory = directory.resolve()
            if resolved_directory not in directories:
                directories.append(resolved_directory)
    names = [command_path.name] if command_path.suffix else [f'{command_path.name}{ext}' for ext in _windows_pathext(env)]
    for directory in directories:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return str(candidate.resolve())
    raise FileNotFoundError(errno.ENOENT, 'command not found', command)


def _resolve_command(command: str, cwd: Path, env: dict[str, str]) -> str:
    """Resolve against the child PATH and gate cwd, without a shell."""
    if os.name == 'nt':
        return _resolve_windows_command(command, cwd, env)
    command_path = Path(command)
    lookup = str((cwd / command_path).resolve()) if not command_path.is_absolute() and command_path.parent != Path('.') else command
    resolved = shutil.which(lookup, path=env.get('PATH'))
    if resolved:
        return str(Path(resolved).resolve())
    candidates: list[Path] = []
    if command_path.is_absolute():
        candidates = [command_path]
    elif command_path.parent != Path('.'):
        candidates = [(cwd / command_path).resolve()]
    else:
        for raw in (env.get('PATH') or '').split(os.pathsep):
            directory = Path(raw) if raw else cwd
            directory = directory if directory.is_absolute() else cwd / directory
            candidates.append(directory / command)
    if any(candidate.is_file() for candidate in candidates):
        raise PermissionError(errno.EACCES, 'command is not executable', command)
    raise FileNotFoundError(errno.ENOENT, 'command not found', command)


def _command_invocation(command: list[str], cwd: Path, env: dict[str, str]) -> tuple[list[str] | str, str | None]:
    if not command:
        raise FileNotFoundError(errno.ENOENT, 'empty command')
    resolved = _resolve_command(str(command[0]), cwd, env)
    resolved_command = [resolved, *(str(value) for value in command[1:])]
    if os.name != 'nt' or Path(resolved).suffix.lower() not in WINDOWS_COMMAND_WRAPPERS:
        return resolved_command, None
    configured_comspec = env.get('COMSPEC') or os.environ.get('COMSPEC') or 'cmd.exe'
    comspec = _resolve_windows_command(configured_comspec, cwd, env)
    payload = ' '.join(_quote_windows_cmd_token(value) for value in resolved_command)
    invocation = f'{subprocess.list2cmdline([comspec])} /D /V:OFF /S /C "{payload}"'
    return invocation, comspec


def _quote_windows_cmd_token(value: str) -> str:
    """Quote one cmd.exe token or reject characters that cannot be represented safely."""
    if any(character in value for character in ('"', '%', '\r', '\n', '\x00')):
        raise OSError(errno.EINVAL, 'unsafe character in Windows command-wrapper token')
    return f'"{value}"'


def _terminate_process_tree(proc: subprocess.Popen[str]) -> str | None:
    if proc.poll() is not None:
        return None
    error: str | None = None
    try:
        if os.name == 'nt':
            killed = subprocess.run(
                ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                text=True, encoding='utf-8', errors='replace', capture_output=True,
                timeout=10, check=False,
            )
            if killed.returncode != 0 and proc.poll() is None:
                error = (
                    killed.stderr
                    or killed.stdout
                    or f'taskkill exit {killed.returncode}'
                ).strip()
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
        return str(exc)
    return error


def _execute_command(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    invocation, executable = _command_invocation(command, cwd, env)
    process_group: dict[str, Any] = (
        {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)}
        if os.name == 'nt' else {'start_new_session': True}
    )
    proc = subprocess.Popen(
        invocation, cwd=cwd, env=env, executable=executable, shell=False,
        text=True, encoding='utf-8', errors='replace',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, **process_group,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        termination_error = _terminate_process_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.SubprocessError:
            stdout, stderr = exc.output or '', exc.stderr or ''
        if termination_error:
            stderr = f'{stderr}\nprocess-tree cleanup: {termination_error}'.strip()
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from exc
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


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


def run_required(root: Path, task_id: str, timeout: int = DEFAULT_GATE_TIMEOUT_SECONDS) -> dict[str, Any]:
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

    try:
        timeout = _validated_timeout_seconds(timeout)
    except ValueError as exc:
        return write_report({
            'status': 'BLOCKED',
            'reason': 'INVALID_GATE_TIMEOUT',
            'error': str(exc),
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
    executed_identities: dict[str, tuple[int, dict[str, Any]]] = {}
    gate_env = _gate_env(root)
    for gate in required:
        try:
            gate_timeout = _gate_timeout_seconds(root, gate, timeout)
        except ValueError as exc:
            results.append({
                'task_id': task_id, 'gate': gate, 'status': 'BLOCKED',
                'reason': 'INVALID_GATE_TIMEOUT', 'exit_code': None,
                'workspace_digest': gate_digest, 'timeout_seconds': None,
                'stderr_tail': str(exc),
            })
            continue
        cmd = command_for_gate(root, gate, ctx)
        if cmd is None:
            results.append({
                'task_id': task_id, 'gate': gate, 'status': 'NOT_CONFIGURED',
                'reason': 'NO_CONFIGURED_GATE', 'exit_code': None,
                'workspace_digest': gate_digest, 'timeout_seconds': gate_timeout,
            })
            continue
        started = time.time()
        execution: dict[str, Any] | None = None
        gate_result: dict[str, Any]
        try:
            execution = _execution_identity(
                root, gate, cmd, gate_env, gate_digest, gate_timeout
            )
            prior = (
                executed_identities.get(str(execution['execution_identity']))
                if execution['execution_reuse_eligible']
                else None
            )
            if prior is not None:
                canonical_index, canonical = prior
                results.append({
                    'task_id': task_id,
                    'gate': gate,
                    'status': canonical['status'],
                    'reason': 'DUPLICATE_CANONICAL_EXECUTION',
                    'canonical_reason': canonical.get('reason'),
                    'workspace_digest': gate_digest,
                    'command': _report_command(cmd, gate_env),
                    'exit_code': canonical.get('exit_code'),
                    'duration_ms': round((time.time() - started) * 1000),
                    'timeout_seconds': gate_timeout,
                    'execution_mode': 'REUSED',
                    'execution_reused': True,
                    'canonical_execution': canonical['gate'],
                    'canonical_timeout_seconds': canonical['timeout_seconds'],
                    'runtime_evidence': {
                        'reference': f'gate-results.json#/results/{canonical_index}',
                        'gate': canonical['gate'],
                        'status': canonical['status'],
                        'workspace_digest': gate_digest,
                    },
                    **execution,
                })
                continue
            proc = _execute_command(
                cmd,
                cwd=root,
                timeout=gate_timeout,
                env=gate_env,
            )
            stdout = proc.stdout or ''
            stderr = proc.stderr or ''
            status = 'PASS' if proc.returncode == 0 else 'FAIL'
            text = f'{stdout}\n{stderr}'
            if proc.returncode != 0 and ('BLOCKED' in text or 'ENVIRONMENT_UNAVAILABLE' in text or 'NOT_EXECUTED' in text):
                status = 'BLOCKED'
            gate_result = {
                'task_id': task_id, 'gate': gate, 'status': status,
                'workspace_digest': gate_digest,
                'command': _report_command(cmd, gate_env), 'exit_code': proc.returncode,
                'duration_ms': round((time.time() - started) * 1000),
                'timeout_seconds': gate_timeout,
                'stdout_tail': _captured_output_tail(stdout, gate_env), 'stderr_tail': _captured_output_tail(stderr, gate_env),
            }
            if status == 'FAIL':
                gate_result['reason'] = 'COMMAND_FAILED'
        except subprocess.TimeoutExpired as exc:
            timeout_detail = exc.stderr or exc.output or exc
            gate_result = {'task_id': task_id, 'gate': gate, 'status': 'TIMEOUT', 'reason': 'TIMEOUT', 'workspace_digest': gate_digest, 'command': _report_command(cmd, gate_env), 'exit_code': None,
                           'duration_ms': round((time.time() - started) * 1000), 'timeout_seconds': gate_timeout, 'stderr_tail': _captured_output_tail(timeout_detail, gate_env)}
        except FileNotFoundError as exc:
            gate_result = {'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'COMMAND_NOT_FOUND', 'workspace_digest': gate_digest, 'command': _report_command(cmd, gate_env), 'exit_code': None,
                           'duration_ms': round((time.time() - started) * 1000), 'timeout_seconds': gate_timeout, 'stderr_tail': _captured_output_tail(exc, gate_env)}
        except PermissionError as exc:
            gate_result = {'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'PERMISSION_ERROR', 'workspace_digest': gate_digest, 'command': _report_command(cmd, gate_env), 'exit_code': None,
                           'duration_ms': round((time.time() - started) * 1000), 'timeout_seconds': gate_timeout, 'stderr_tail': _captured_output_tail(exc, gate_env)}
        except OSError as exc:
            gate_result = {'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'OS_EXECUTION_ERROR', 'workspace_digest': gate_digest, 'command': _report_command(cmd, gate_env), 'exit_code': None,
                           'duration_ms': round((time.time() - started) * 1000), 'timeout_seconds': gate_timeout, 'stderr_tail': _captured_output_tail(exc, gate_env)}
        except subprocess.SubprocessError as exc:
            gate_result = {'task_id': task_id, 'gate': gate, 'status': 'FAIL', 'reason': 'SUBPROCESS_ERROR', 'workspace_digest': gate_digest, 'command': _report_command(cmd, gate_env), 'exit_code': None,
                           'duration_ms': round((time.time() - started) * 1000), 'timeout_seconds': gate_timeout, 'stderr_tail': _captured_output_tail(exc, gate_env)}
        except ValueError as exc:
            gate_result = {'task_id': task_id, 'gate': gate, 'status': 'BLOCKED', 'reason': 'INVALID_EXECUTION_IDENTITY', 'workspace_digest': gate_digest, 'command': _report_command(cmd, gate_env), 'exit_code': None,
                           'duration_ms': round((time.time() - started) * 1000), 'timeout_seconds': gate_timeout, 'stderr_tail': _captured_output_tail(exc, gate_env)}

        canonical_index = len(results)
        if execution is not None:
            gate_result.update({
                **execution,
                'execution_mode': 'EXECUTED',
                'execution_reused': False,
                'canonical_execution': gate,
                'canonical_timeout_seconds': gate_timeout,
                'runtime_evidence': {
                    'reference': f'gate-results.json#/results/{canonical_index}',
                    'gate': gate,
                    'status': gate_result['status'],
                    'workspace_digest': gate_digest,
                },
            })
            if execution['execution_reuse_eligible']:
                executed_identities[str(execution['execution_identity'])] = (
                    canonical_index, gate_result
                )
        results.append(gate_result)

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
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.'); p.add_argument('--task-id', required=True); p.add_argument('--timeout', type=int, default=DEFAULT_GATE_TIMEOUT_SECONDS); a = p.parse_args()
    r = run_required(Path(a.root), a.task_id, a.timeout); print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
