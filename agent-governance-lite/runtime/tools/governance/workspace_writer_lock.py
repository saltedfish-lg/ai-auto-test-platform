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
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .task_context import governance_tmp_root, validate_task_id

LOCK_NAME = 'workspace-writer.lock'
RECOVERY_LOCK_NAME = 'workspace-writer.lock.recovery'


def _lock_path(root: Path) -> Path:
    return governance_tmp_root(root.resolve()) / LOCK_NAME


def _recovery_path(root: Path) -> Path:
    return governance_tmp_root(root.resolve()) / RECOVERY_LOCK_NAME


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _read_owner(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _identity(path: Path) -> tuple[int, int, int, int] | None:
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (int(st.st_dev), int(st.st_ino), int(st.st_size), int(st.st_mtime_ns))


@contextmanager
def _recovery_mutex(root: Path) -> Iterator[None]:
    base = governance_tmp_root(root.resolve())
    base.mkdir(parents=True, exist_ok=True)
    path = _recovery_path(root)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == 'nt':
            import msvcrt
            if os.path.getsize(path) == 0:
                os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def current_owner(root: Path) -> dict | None:
    path = _lock_path(root)
    if not path.is_file():
        return None
    data = _read_owner(path)
    return data or {'task_id': None, 'pid': None, 'mode': 'writer'}


def cleanup_stale(root: Path) -> bool:
    root = root.resolve()
    path = _lock_path(root)
    with _recovery_mutex(root):
        if not path.exists():
            return False
        owner = _read_owner(path)
        observed_identity = _identity(path)
        observed_instance = owner.get('lock_instance_id')
        try:
            pid = int(owner.get('pid', -1))
        except (TypeError, ValueError):
            return False
        if pid > 0 and _pid_alive(pid):
            return False
        current = _read_owner(path)
        current_identity = _identity(path)
        if current_identity is None or current_identity != observed_identity:
            return False
        if observed_instance is not None and current.get('lock_instance_id') != observed_instance:
            return False
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False


def acquire(root: Path, task_id: str, owner_pid: int | None = None) -> Path:
    root = root.resolve()
    validate_task_id(task_id)
    base = governance_tmp_root(root)
    base.mkdir(parents=True, exist_ok=True)
    path = _lock_path(root)
    cleanup_stale(root)
    payload = {
        'task_id': task_id,
        'pid': int(owner_pid if owner_pid is not None else os.getpid()),
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'workspace': str(root),
        'mode': 'writer',
        'lock_instance_id': uuid.uuid4().hex,
    }
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        owner = _read_owner(path)
        if owner.get('task_id') == task_id:
            raise RuntimeError('WORKSPACE_WRITER_ALREADY_HELD') from exc
        raise RuntimeError('WORKSPACE_WRITER_BUSY') from exc
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def release(root: Path, task_id: str) -> None:
    root = root.resolve()
    validate_task_id(task_id)
    path = _lock_path(root)
    if not path.exists():
        return
    owner = _read_owner(path)
    if owner.get('task_id') != task_id:
        raise RuntimeError('WORKSPACE_WRITER_NOT_OWNER')
    path.unlink()


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('acquire'); a.add_argument('--root', default='.'); a.add_argument('--task-id', required=True); a.add_argument('--owner-pid', type=int)
    r = sub.add_parser('release'); r.add_argument('--root', default='.'); r.add_argument('--task-id', required=True)
    s = sub.add_parser('status'); s.add_argument('--root', default='.')
    args = p.parse_args(); root = Path(args.root)
    try:
        if args.cmd == 'acquire':
            print(acquire(root, args.task_id, args.owner_pid)); return 0
        if args.cmd == 'release':
            release(root, args.task_id); return 0
        owner = current_owner(root); print(json.dumps(owner, ensure_ascii=False, indent=2) if owner else 'UNLOCKED'); return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
