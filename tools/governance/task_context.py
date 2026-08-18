from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .process_identity import current_process_identity, owner_is_mechanically_stale
from .workspace_path_policy import consumer_allows_relative, iter_policy_files, load_policy, policy_digest

TMP_REL = Path('.tmp/agent-governance')
TASK_ID_RE = re.compile(r'^[A-Za-z0-9._-]+$')
GLOBAL_AUTHORITY_LOCK = 'authority.lock'


def validate_task_id(task_id: str) -> str:
    if not isinstance(task_id, str) or not task_id or not TASK_ID_RE.fullmatch(task_id):
        raise ValueError('INVALID_TASK_ID')
    if task_id == '.' or '..' in task_id or '/' in task_id or '\\' in task_id or any(ord(ch) < 32 for ch in task_id):
        raise ValueError('INVALID_TASK_ID')
    return task_id


def governance_tmp_root(root: Path) -> Path:
    # Keep the governed root lexical. Resolving it would make a malicious symlink
    # become the new boundary instead of being rejected by containment.
    return (root.resolve() / TMP_REL).absolute()


def _contained_task_path(root: Path, task_id: str) -> Path:
    validate_task_id(task_id)
    base = governance_tmp_root(root)
    candidate = (base / task_id).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError('TASK_PATH_OUTSIDE_GOVERNANCE_TMP') from exc
    return candidate


def _safe_remove_task_path(root: Path, path: Path) -> None:
    base = governance_tmp_root(root)
    lexical = path.absolute()
    try:
        lexical.parent.relative_to(base.absolute())
    except ValueError as exc:
        raise ValueError('TASK_CLEANUP_OUTSIDE_GOVERNANCE_TMP') from exc
    if path.is_symlink():
        path.unlink(missing_ok=True)
        return
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError('TASK_CLEANUP_OUTSIDE_GOVERNANCE_TMP') from exc
    if resolved == base:
        raise ValueError('TASK_CLEANUP_ROOT_FORBIDDEN')
    shutil.rmtree(resolved, ignore_errors=False)


def task_dir(root: Path, task_id: str) -> Path:
    return _contained_task_path(root, task_id)


def context_path(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / 'context.json'


WORKSPACE_SNAPSHOT_NAME = 'workspace-start.json'


def workspace_snapshot_path(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / WORKSPACE_SNAPSHOT_NAME


def _workspace_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        'file_state': 'FILE',
        'size': int(stat.st_size),
        'mtime_ns': int(stat.st_mtime_ns),
    }


def workspace_snapshot(root: Path) -> dict[str, dict[str, Any]]:
    """Capture a lightweight local-filesystem baseline for governed paths.

    The baseline deliberately stores metadata rather than hashing the repository. Content
    SHA256 is computed later only for files whose metadata changed, while Gate freshness
    hashes only the Task Context affected-files set. Git is not consulted.
    """
    root = root.resolve()
    policy = load_policy(root)
    out: dict[str, dict[str, Any]] = {}
    for path in iter_policy_files(root, 'workspace_tracking', policy):
        rel = path.relative_to(root).as_posix()
        try:
            out[rel] = _workspace_metadata(path)
        except OSError:
            continue
    return out


def save_workspace_snapshot(root: Path, task_id: str) -> Path:
    root = root.resolve()
    path = workspace_snapshot_path(root, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    policy = load_policy(root)
    payload = {
        'schema_version': 2,
        'source': 'LOCAL_WORKSPACE_BASELINE',
        'policy_digest': policy_digest(policy),
        'files': workspace_snapshot(root),
        'captured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def load_workspace_snapshot(root: Path, task_id: str) -> dict[str, dict[str, Any]]:
    path = workspace_snapshot_path(root, task_id)
    if not path.is_file():
        raise FileNotFoundError(f'WORKSPACE_SNAPSHOT_NOT_FOUND:{task_id}')
    raw = json.loads(path.read_text(encoding='utf-8'))
    files = raw.get('files') if isinstance(raw, dict) else None
    if not isinstance(files, dict):
        raise ValueError('WORKSPACE_SNAPSHOT_INVALID')
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in files.items():
        # Compatibility reader for legacy workspace snapshots that stored full hashes.
        if isinstance(value, dict):
            normalized[str(key)] = dict(value)
        else:
            normalized[str(key)] = {'file_state': 'LEGACY_HASH', 'sha256': str(value)}
    return normalized


def workspace_change_records_since_start(root: Path, task_id: str) -> list[dict[str, Any]]:
    """Return ADDED/MODIFIED/DELETED changes relative to the Task Start baseline.

    Existing local edits that predate Task Start are part of the baseline and therefore do
    not become current-task changes merely because they differ from a Git HEAD.
    """
    root = root.resolve()
    policy = load_policy(root)
    before = {
        rel: metadata
        for rel, metadata in load_workspace_snapshot(root, task_id).items()
        if consumer_allows_relative(root, rel, 'workspace_tracking', policy)
    }
    after = workspace_snapshot(root)
    records: list[dict[str, Any]] = []
    for rel in sorted(set(before) | set(after)):
        old = before.get(rel)
        new = after.get(rel)
        if old == new:
            continue
        if old is None:
            state = 'ADDED'
        elif new is None:
            state = 'DELETED'
        else:
            state = 'MODIFIED'
        record: dict[str, Any] = {'path': rel, 'change': state}
        if new is not None:
            record['metadata'] = new
            target = root / rel
            try:
                if target.is_file():
                    record['content_sha256'] = _workspace_file_hash(target)
            except OSError:
                record['content_sha256'] = 'UNREADABLE'
        else:
            record['content_sha256'] = 'DELETED'
        records.append(record)
    return records


def workspace_changes_since_start(root: Path, task_id: str) -> list[str]:
    return [str(item['path']) for item in workspace_change_records_since_start(root, task_id)]


def workspace_state_digest(root: Path, affected_files: list[str] | tuple[str, ...] | set[str]) -> str:
    """Hash Task affected-file content/state only; never Git or the whole repository."""
    root = root.resolve()
    policy = load_policy(root)
    digest = hashlib.sha256()
    for raw in sorted({str(x).replace('\\', '/') for x in affected_files}):
        rel_path = Path(raw)
        if rel_path.is_absolute() or '..' in rel_path.parts:
            state = 'INVALID_PATH'
        elif not consumer_allows_relative(root, raw, 'gate_workspace_digest', policy):
            state = 'IGNORED_BY_WORKSPACE_POLICY'
        else:
            target = root / rel_path
            try:
                if target.is_symlink():
                    state = f'SYMLINK:{os.readlink(target)}'
                elif not target.exists():
                    state = 'DELETED'
                elif target.is_file():
                    state = f'FILE:{_workspace_file_hash(target)}'
                else:
                    state = 'NON_FILE'
            except OSError as exc:
                state = f'UNREADABLE:{type(exc).__name__}'
        digest.update(raw.encode('utf-8', errors='surrogatepass'))
        digest.update(b'\0')
        digest.update(state.encode('utf-8', errors='replace'))
        digest.update(b'\0')
    return digest.hexdigest()


def gate_results_path(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / 'gate-results.json'


def final_reconciliation_is_current(root: Path, task_id: str, ctx: dict[str, Any] | None = None) -> bool:
    """Return True only when the last PASS still covers the current workspace.

    The check is intentionally lightweight: it compares the set of files changed since
    task start with the set captured by Final Reconciliation, and verifies every changed
    file remains inside Task Context. Gate freshness is enforced separately with a
    content-sensitive workspace digest.
    """
    try:
        current_ctx = dict(ctx) if ctx is not None else load_context(root, task_id)
        if current_ctx.get('final_reconciliation_status') != 'PASS':
            return False
        actual = set(workspace_changes_since_start(root, task_id))
    except (FileNotFoundError, ValueError, OSError):
        return False
    recorded = {str(x) for x in current_ctx.get('actual_changed_files', [])}
    covered = {str(x) for x in current_ctx.get('affected_files', [])}
    return actual == recorded and actual <= covered


def load_context(root: Path, task_id: str) -> dict[str, Any]:
    path = context_path(root, task_id)
    if not path.is_file():
        raise FileNotFoundError(f'TASK_CONTEXT_NOT_FOUND:{task_id}')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('TASK_CONTEXT_INVALID')
    return value


def save_context(root: Path, task_id: str, payload: dict[str, Any]) -> Path:
    path = context_path(root, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload['task_id'] = validate_task_id(task_id)
    payload['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)
    return path


def cleanup_task(root: Path, task_id: str) -> None:
    path = task_dir(root, task_id)
    if path.exists() or path.is_symlink():
        _safe_remove_task_path(root, path)



def _task_metadata(path: Path) -> dict[str, Any] | None:
    ctx = path / 'context.json'
    if not ctx.is_file():
        return None
    try:
        value = json.loads(ctx.read_text(encoding='utf-8'))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _global_lock_owner(root: Path) -> str | None:
    lock = governance_tmp_root(root) / GLOBAL_AUTHORITY_LOCK
    if not lock.is_file():
        return None
    try:
        value = json.loads(lock.read_text(encoding='utf-8'))
    except Exception:
        return None
    owner = value.get('task_id') if isinstance(value, dict) else None
    return owner if isinstance(owner, str) else None


def _mechanically_stale_task(root: Path, path: Path, current_task_id: str | None = None) -> bool:
    if current_task_id and path.name == current_task_id:
        return False
    if _global_lock_owner(root) == path.name:
        return False
    metadata = _task_metadata(path)
    if metadata is None:
        # Unknown ownership is not safe to delete automatically.
        return False
    try:
        pid = int(metadata.get('task_pid', metadata.get('pid', -1)))
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    expected_creation = metadata.get('task_process_creation_time')
    stale, _ = owner_is_mechanically_stale(pid, str(expected_creation) if expected_creation else None)
    return stale


def cleanup_other_tasks(root: Path, current_task_id: str) -> list[str]:
    """Remove only mechanically stale task directories.

    Starting a new task must never erase another live task or the task owning the
    global Authority lock. A task is auto-stale only when it has readable task
    metadata, its recorded PID is no longer alive, it is not current, and it is
    not the global lock owner.
    """
    current_task_id = validate_task_id(current_task_id)
    base = governance_tmp_root(root)
    removed: list[str] = []
    if not base.exists():
        return removed
    for path in list(base.iterdir()):
        if path.name == GLOBAL_AUTHORITY_LOCK or not (path.is_dir() or path.is_symlink()):
            continue
        if _mechanically_stale_task(root, path, current_task_id):
            _safe_remove_task_path(root, path)
            removed.append(path.name)
    return sorted(removed)


def cleanup_stale(root: Path, max_age_seconds: int = 86400) -> list[str]:
    """Compatibility/admin entrypoint; PID liveness, not age alone, decides stale."""
    del max_age_seconds  # age alone is intentionally not a deletion authority.
    base = governance_tmp_root(root)
    removed: list[str] = []
    if not base.exists():
        return removed
    for path in list(base.iterdir()):
        if path.name == GLOBAL_AUTHORITY_LOCK or not (path.is_dir() or path.is_symlink()):
            continue
        if _mechanically_stale_task(root, path):
            _safe_remove_task_path(root, path)
            removed.append(path.name)
    return sorted(removed)


@contextmanager
def task_session(root: Path, task_id: str, initial: dict[str, Any] | None = None):
    """Own one temporary task directory and clean it on success/failure/cancel."""
    root = root.resolve()
    validate_task_id(task_id)
    cleanup_other_tasks(root, task_id)
    if initial is not None:
        initial = dict(initial)
        initial.setdefault('workspace_change_source', 'LOCAL_WORKSPACE_BASELINE')
        task_pid = int(initial.setdefault('task_pid', os.getpid()))
        identity = current_process_identity(task_pid)
        initial.setdefault('task_process_creation_time', identity.creation_time)
        initial.setdefault('task_status', 'ACTIVE')
        initial.setdefault('task_started_at', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        save_context(root, task_id, initial)
    try:
        yield task_dir(root, task_id)
    finally:
        cleanup_task(root, task_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('cleanup')
    c.add_argument('--root', default='.')
    c.add_argument('--task-id', required=True)
    s = sub.add_parser('cleanup-stale')
    s.add_argument('--root', default='.')
    s.add_argument('--max-age-seconds', type=int, default=86400)
    o = sub.add_parser('cleanup-other')
    o.add_argument('--root', default='.')
    o.add_argument('--current-task-id', required=True)
    args = parser.parse_args()
    try:
        if args.cmd == 'cleanup':
            cleanup_task(Path(args.root), args.task_id)
            return 0
        if args.cmd == 'cleanup-other':
            removed = cleanup_other_tasks(Path(args.root), args.current_task_id)
        else:
            removed = cleanup_stale(Path(args.root), args.max_age_seconds)
    except ValueError as exc:
        print(str(exc))
        return 2
    print(json.dumps({'removed': removed}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
