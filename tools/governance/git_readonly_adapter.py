from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

READ_ONLY_COMMANDS = {
    'status', 'diff', 'rev-parse', 'branch', 'log', 'show',
}
FORBIDDEN_WRITE_COMMANDS = {
    'add', 'commit', 'push', 'merge', 'rebase', 'reset', 'checkout', 'switch',
    'stash', 'clean', 'tag', 'cherry-pick',
}


def _run(root: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            ['git', *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _decode(data: bytes) -> str:
    return data.decode('utf-8', errors='replace').strip()


def _nul_paths(data: bytes) -> list[str]:
    return [chunk.decode('utf-8', errors='surrogateescape') for chunk in data.split(b'\0') if chunk]


def read_git_summary(root: Path, timeout: int = 5) -> dict[str, Any]:
    """Return optional read-only Git diagnostics; never a Governance authority input."""
    root = root.resolve()
    if shutil.which('git') is None:
        return {'git_auxiliary_status': 'unavailable', 'reason': 'GIT_EXECUTABLE_UNAVAILABLE'}
    if not (root / '.git').exists():
        return {'git_auxiliary_status': 'unavailable', 'reason': 'NOT_A_GIT_REPOSITORY'}

    head = _run(root, ['rev-parse', 'HEAD'], timeout)
    branch = _run(root, ['branch', '--show-current'], timeout)
    status = _run(root, ['status', '--porcelain=v1', '-z', '--untracked-files=all'], timeout)
    names = _run(root, ['diff', '--name-only', '-z'], timeout)
    stat = _run(root, ['diff', '--stat'], timeout)
    commands = [head, branch, status, names, stat]
    if any(proc is None for proc in commands):
        return {'git_auxiliary_status': 'unavailable', 'reason': 'GIT_COMMAND_ERROR'}
    assert head and branch and status and names and stat
    if any(proc.returncode != 0 for proc in commands):
        return {
            'git_auxiliary_status': 'unavailable',
            'reason': 'GIT_COMMAND_ERROR',
            'stderr': _decode(next(proc.stderr for proc in commands if proc.returncode != 0)),
        }

    # porcelain=v1 -z emits NUL-separated records. Preserve records as diagnostics;
    # Governance never consumes them for affected-files or closure.
    status_records = _nul_paths(status.stdout)
    return {
        'git_auxiliary_status': 'available',
        'branch': _decode(branch.stdout),
        'head': _decode(head.stdout),
        'status_records': status_records,
        'diff_paths': _nul_paths(names.stdout),
        'diff_stat': _decode(stat.stdout),
        'authority': False,
        'purpose': 'OPTIONAL_READ_ONLY_REVIEW_DIAGNOSTIC',
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--timeout', type=int, default=5)
    args = parser.parse_args()
    result = read_git_summary(Path(args.root), args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Optional diagnostics never fail Governance merely because Git is unavailable.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
