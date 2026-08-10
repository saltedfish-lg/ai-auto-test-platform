#!/usr/bin/env python3
"""Read-only Git workspace snapshot and task-delta helper.

The helper never mutates Git state. It captures the workspace at task start and
later compares the current workspace with that snapshot so dirty paths that
predate the task are not automatically attributed to the current task.

Task-start snapshots are workspace-bound evidence. Delta comparison fails closed
when the snapshot schema version, resolved workspace root, or repository identity
does not match the current workspace.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SNAPSHOT_VERSION = 2


def _decode_z(output: bytes) -> list[str]:
    return sorted(
        {
            item.decode("utf-8", errors="replace")
            for item in output.split(b"\0")
            if item
        }
    )


def _git_z(
    root: Path, args: list[str], *, index_file: Path | None = None
) -> tuple[list[str], str | None]:
    try:
        git_env = os.environ.copy()
        git_env["GIT_OPTIONAL_LOCKS"] = "0"
        if index_file is not None:
            git_env["GIT_INDEX_FILE"] = str(index_file)
        completed = subprocess.run(
            ["git", "-C", str(root), *args, "-z"],
            check=False,
            env=git_env,
            capture_output=True,
            text=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return [], f"git {' '.join(args)} exited {completed.returncode}: {stderr}"
    return _decode_z(completed.stdout), None


def _git_text(root: Path, args: list[str]) -> tuple[str | None, str | None]:
    try:
        git_env = os.environ.copy()
        git_env["GIT_OPTIONAL_LOCKS"] = "0"
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            env=git_env,
            capture_output=True,
            text=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return None, f"git {' '.join(args)} exited {completed.returncode}: {stderr}"
    return completed.stdout.decode("utf-8", errors="replace").strip(), None



def _resolve_git_index_path(root: Path) -> tuple[Path | None, str | None]:
    """Resolve the repository/worktree index without hard-coding .git/index."""
    index_text, error = _git_text(root, ["rev-parse", "--git-path", "index"])
    if error or not index_text:
        return None, error or "git rev-parse --git-path index returned empty output"
    index_path = Path(index_text)
    if not index_path.is_absolute():
        index_path = (root / index_path).resolve()
    else:
        index_path = index_path.resolve()
    return index_path, None


@contextmanager
def _temporary_git_index(root: Path):
    """Use a disposable index copy so read-only queries cannot refresh the real index.

    Git may refresh stat/cache fields in the index while answering `git diff`. Setting
    GIT_OPTIONAL_LOCKS=0 alone does not guarantee byte-for-byte immutability of the
    repository index on every Git/platform combination. All index-backed workspace
    queries therefore point at a temporary copy outside the repository.
    """
    real_index, error = _resolve_git_index_path(root)
    if error or real_index is None:
        yield None, error or "unable to resolve Git index"
        return

    try:
        with tempfile.TemporaryDirectory(prefix="ai-auto-test-git-index-") as temp_dir:
            temp_index = Path(temp_dir) / "index"
            if real_index.is_file():
                shutil.copy2(real_index, temp_index)
            yield temp_index, None
    except OSError as exc:
        yield None, f"cannot prepare temporary Git index: {type(exc).__name__}: {exc}"


def _normalized_path(path: Path | str) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repository_identity(root: Path) -> tuple[dict[str, object], str | None]:
    root = root.resolve()
    if not (root / ".git").exists():
        root_id = _sha256_text(_normalized_path(root))
        return {
            "status": "NOT_APPLICABLE",
            "workspace_root": str(root),
            "workspace_root_identity": root_id,
            "git_toplevel": None,
            "git_common_dir": None,
            "git_common_dir_file_id": None,
            "identity_digest": f"not-applicable:{root_id}",
        }, None

    toplevel_text, error = _git_text(root, ["rev-parse", "--show-toplevel"])
    if error or not toplevel_text:
        return {}, error or "git rev-parse --show-toplevel returned empty output"
    common_text, error = _git_text(root, ["rev-parse", "--git-common-dir"])
    if error or not common_text:
        return {}, error or "git rev-parse --git-common-dir returned empty output"

    toplevel = Path(toplevel_text).resolve()
    common = Path(common_text)
    if not common.is_absolute():
        common = (root / common).resolve()
    else:
        common = common.resolve()

    file_id: str | None = None
    try:
        stat = common.stat()
        # st_dev/st_ino gives a stable identity for the lifetime of the current
        # repository directory on normal local filesystems. If unavailable/zero,
        # canonical Git paths still provide a best-effort repository identity.
        if int(getattr(stat, "st_dev", 0)) or int(getattr(stat, "st_ino", 0)):
            file_id = f"{int(getattr(stat, 'st_dev', 0))}:{int(getattr(stat, 'st_ino', 0))}"
    except OSError as exc:
        return {}, f"cannot stat git common dir {common}: {type(exc).__name__}: {exc}"

    parts = [
        _normalized_path(root),
        _normalized_path(toplevel),
        _normalized_path(common),
        file_id or "NO_FILE_ID",
    ]
    return {
        "status": "COMPLETE",
        "workspace_root": str(root),
        "workspace_root_identity": _sha256_text(_normalized_path(root)),
        "git_toplevel": str(toplevel),
        "git_common_dir": str(common),
        "git_common_dir_file_id": file_id,
        "identity_digest": _sha256_text("\n".join(parts)),
    }, None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint_paths(root: Path, paths: Iterable[str]) -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for relative in sorted(set(paths)):
        path = root / relative
        try:
            if path.is_file():
                fingerprints[relative] = f"sha256:{_sha256_file(path)}"
            elif path.exists():
                fingerprints[relative] = "EXISTS_NON_FILE"
            else:
                fingerprints[relative] = "MISSING"
        except OSError as exc:
            fingerprints[relative] = f"UNREADABLE:{type(exc).__name__}:{exc}"
    return fingerprints


def _digest_mapping(mapping: dict[str, str]) -> str:
    payload = "\n".join(f"{path}\0{mapping[path]}" for path in sorted(mapping))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _digest_categories(categories: dict[str, dict[str, str]]) -> str:
    lines: list[str] = []
    for category in sorted(categories):
        for path, fingerprint in sorted(categories[category].items()):
            lines.append(f"{category}\0{path}\0{fingerprint}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def capture_workspace(root: Path) -> dict[str, object]:
    root = root.resolve()
    captured_at = datetime.now(timezone.utc).isoformat()
    repository_identity, identity_error = _repository_identity(root)
    if identity_error:
        return _unavailable(root, captured_at, identity_error)

    repository_present = repository_identity["status"] == "COMPLETE"
    if not repository_present:
        categories = {
            "changed_paths": {},
            "untracked_paths": {},
            "tracked_deleted": {},
        }
        return {
            "snapshot_version": SNAPSHOT_VERSION,
            "captured_at": captured_at,
            "root": str(root),
            "repository_identity": repository_identity,
            "git_workspace": {"status": "NOT_APPLICABLE", "read_error": None},
            "changed_paths": [],
            "untracked_paths": [],
            "tracked_deleted": [],
            "fingerprints": categories,
            "digests": {
                "changed_paths_digest": _digest_mapping({}),
                "untracked_paths_digest": _digest_mapping({}),
                "tracked_deleted_digest": _digest_mapping({}),
                "workspace_digest": _digest_categories(categories),
            },
        }

    with _temporary_git_index(root) as (temp_index, index_error):
        if index_error or temp_index is None:
            return _unavailable(
                root,
                captured_at,
                index_error or "temporary Git index is unavailable",
                repository_identity,
            )
        unstaged, error = _git_z(root, ["diff", "--name-only"], index_file=temp_index)
        if error:
            return _unavailable(root, captured_at, error, repository_identity)
        staged, error = _git_z(
            root, ["diff", "--cached", "--name-only"], index_file=temp_index
        )
        if error:
            return _unavailable(root, captured_at, error, repository_identity)
        untracked, error = _git_z(
            root,
            ["ls-files", "--others", "--exclude-standard"],
            index_file=temp_index,
        )
        if error:
            return _unavailable(root, captured_at, error, repository_identity)
        tracked_deleted, error = _git_z(
            root, ["ls-files", "--deleted"], index_file=temp_index
        )
        if error:
            return _unavailable(root, captured_at, error, repository_identity)

    changed = sorted(set(unstaged) | set(staged) | set(tracked_deleted))
    changed_fp = _fingerprint_paths(root, changed)
    untracked_fp = _fingerprint_paths(root, untracked)
    deleted_fp = {path: "DELETED" for path in tracked_deleted}
    categories = {
        "changed_paths": changed_fp,
        "untracked_paths": untracked_fp,
        "tracked_deleted": deleted_fp,
    }
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "captured_at": captured_at,
        "root": str(root),
        "repository_identity": repository_identity,
        "git_workspace": {"status": "COMPLETE", "read_error": None},
        "changed_paths": changed,
        "untracked_paths": untracked,
        "tracked_deleted": tracked_deleted,
        "fingerprints": categories,
        "digests": {
            "changed_paths_digest": _digest_mapping(changed_fp),
            "untracked_paths_digest": _digest_mapping(untracked_fp),
            "tracked_deleted_digest": _digest_mapping(deleted_fp),
            "workspace_digest": _digest_categories(categories),
        },
    }


def _unavailable(
    root: Path,
    captured_at: str,
    error: str,
    repository_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "captured_at": captured_at,
        "root": str(root.resolve()),
        "repository_identity": repository_identity or {
            "status": "UNAVAILABLE",
            "workspace_root": str(root.resolve()),
            "workspace_root_identity": _sha256_text(_normalized_path(root)),
            "git_toplevel": None,
            "git_common_dir": None,
            "git_common_dir_file_id": None,
            "identity_digest": "UNAVAILABLE",
        },
        "git_workspace": {"status": "UNAVAILABLE", "read_error": error},
        "changed_paths": [],
        "untracked_paths": [],
        "tracked_deleted": [],
        "fingerprints": {
            "changed_paths": {},
            "untracked_paths": {},
            "tracked_deleted": {},
        },
        "digests": {
            "changed_paths_digest": "UNAVAILABLE",
            "untracked_paths_digest": "UNAVAILABLE",
            "tracked_deleted_digest": "UNAVAILABLE",
            "workspace_digest": "UNAVAILABLE",
        },
    }


def _category_delta(
    start: dict[str, str], current: dict[str, str]
) -> dict[str, list[str]]:
    start_keys = set(start)
    current_keys = set(current)
    return {
        "added": sorted(current_keys - start_keys),
        "cleared": sorted(start_keys - current_keys),
        "modified_since_start": sorted(
            path for path in start_keys & current_keys if start[path] != current[path]
        ),
    }


def _unavailable_delta(reason_code: str, message: str) -> dict[str, object]:
    return {
        "status": "UNAVAILABLE",
        "reason_code": reason_code,
        "read_error": message,
        "task_delta_paths": [],
        "delta_digest": "UNAVAILABLE",
    }


def _validate_snapshot_compatibility(
    start: dict[str, object], current: dict[str, object]
) -> dict[str, object] | None:
    version = start.get("snapshot_version")
    if version != SNAPSHOT_VERSION:
        return _unavailable_delta(
            "SNAPSHOT_VERSION_MISMATCH",
            f"task-start snapshot_version={version!r} is incompatible with supported version {SNAPSHOT_VERSION}",
        )

    start_root = start.get("root")
    current_root = current.get("root")
    if not isinstance(start_root, str) or not isinstance(current_root, str):
        return _unavailable_delta(
            "SNAPSHOT_ROOT_IDENTITY_MISSING",
            "task-start/current snapshot is missing a valid root identity",
        )
    if _normalized_path(start_root) != _normalized_path(current_root):
        return _unavailable_delta(
            "SNAPSHOT_ROOT_MISMATCH",
            f"task-start root {start_root!r} does not match current root {current_root!r}",
        )

    start_identity = start.get("repository_identity")
    current_identity = current.get("repository_identity")
    if not isinstance(start_identity, dict) or not isinstance(current_identity, dict):
        return _unavailable_delta(
            "SNAPSHOT_REPOSITORY_IDENTITY_MISSING",
            "task-start/current snapshot is missing repository_identity",
        )
    start_digest = start_identity.get("identity_digest")
    current_digest = current_identity.get("identity_digest")
    if not isinstance(start_digest, str) or not isinstance(current_digest, str):
        return _unavailable_delta(
            "SNAPSHOT_REPOSITORY_IDENTITY_MISSING",
            "task-start/current repository identity digest is missing",
        )
    if start_digest != current_digest:
        return _unavailable_delta(
            "SNAPSHOT_REPOSITORY_MISMATCH",
            "task-start snapshot belongs to a different or replaced repository/workspace",
        )
    return None


def compare_snapshots(start: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    compatibility_error = _validate_snapshot_compatibility(start, current)
    if compatibility_error is not None:
        return compatibility_error

    start_status = str(start.get("git_workspace", {}).get("status"))  # type: ignore[union-attr]
    current_status = str(current.get("git_workspace", {}).get("status"))  # type: ignore[union-attr]
    if start_status == "UNAVAILABLE" or current_status == "UNAVAILABLE":
        return _unavailable_delta(
            "GIT_METADATA_UNAVAILABLE",
            str(
                current.get("git_workspace", {}).get("read_error")  # type: ignore[union-attr]
                or start.get("git_workspace", {}).get("read_error")  # type: ignore[union-attr]
                or "Git metadata is unavailable"
            ),
        )
    if start_status == "NOT_APPLICABLE" and current_status == "NOT_APPLICABLE":
        return {
            "status": "NOT_APPLICABLE",
            "reason_code": None,
            "read_error": None,
            "task_delta_paths": [],
            "delta_digest": _digest_mapping({}),
        }
    if start_status != current_status:
        return _unavailable_delta(
            "WORKSPACE_MODE_CHANGED",
            f"workspace mode changed from {start_status} to {current_status}",
        )

    start_fp = start.get("fingerprints", {})
    current_fp = current.get("fingerprints", {})
    category_deltas: dict[str, dict[str, list[str]]] = {}
    task_paths: set[str] = set()
    for category in ("changed_paths", "untracked_paths", "tracked_deleted"):
        before = dict(start_fp.get(category, {}))  # type: ignore[union-attr]
        after = dict(current_fp.get(category, {}))  # type: ignore[union-attr]
        delta = _category_delta(before, after)
        category_deltas[category] = delta
        for paths in delta.values():
            task_paths.update(paths)

    digest_payload: dict[str, str] = {}
    for category, delta in category_deltas.items():
        for kind, paths in delta.items():
            for path in paths:
                digest_payload[f"{category}:{kind}:{path}"] = path
    delta_digest = _digest_mapping(digest_payload)
    return {
        "status": "EMPTY" if not task_paths else "CHANGED",
        "reason_code": None,
        "read_error": None,
        "categories": category_deltas,
        "task_delta_paths": sorted(task_paths),
        "delta_digest": delta_digest,
    }



def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_artifact_path_outside_workspace(
    root: Path, path: str | None, *, role: str
) -> dict[str, object] | None:
    if not path:
        return None
    target = Path(path).expanduser().resolve()
    workspace = root.resolve()
    if _is_within(target, workspace):
        return _unavailable_delta(
            "SNAPSHOT_OUTPUT_INSIDE_WORKSPACE" if role == "output" else "SNAPSHOT_INPUT_INSIDE_WORKSPACE",
            f"{role} path {str(target)!r} must be outside workspace root {str(workspace)!r}",
        )
    return None


def _write_json(payload: dict[str, object], path: str | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="capture a read-only task-start/current workspace snapshot")
    capture.add_argument("--root", default=".")
    capture.add_argument("--out")

    delta = subparsers.add_parser("delta", help="compare current workspace with a saved task-start snapshot")
    delta.add_argument("--root", default=".")
    delta.add_argument("--start", required=True)
    delta.add_argument("--out")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    output_error = _validate_artifact_path_outside_workspace(root, args.out, role="output")
    if output_error is not None:
        payload = (
            output_error
            if args.command == "capture"
            else {"task_start": None, "current": None, "task_delta": output_error}
        )
        _write_json(payload, None)
        return 2

    if args.command == "capture":
        payload = capture_workspace(root)
        _write_json(payload, args.out)
        return 2 if payload["git_workspace"]["status"] == "UNAVAILABLE" else 0  # type: ignore[index]

    start_error = _validate_artifact_path_outside_workspace(root, args.start, role="input")
    if start_error is not None:
        payload = {"task_start": None, "current": None, "task_delta": start_error}
        _write_json(payload, args.out)
        return 2

    start_path = Path(args.start)
    try:
        start = json.loads(start_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        payload = {
            "task_start": None,
            "current": None,
            "task_delta": _unavailable_delta(
                "SNAPSHOT_READ_ERROR",
                f"cannot read task-start snapshot: {type(exc).__name__}: {exc}",
            ),
        }
        _write_json(payload, args.out)
        return 2
    if not isinstance(start, dict):
        payload = {
            "task_start": start,
            "current": None,
            "task_delta": _unavailable_delta(
                "SNAPSHOT_SCHEMA_INVALID",
                "task-start snapshot root value must be a JSON object",
            ),
        }
        _write_json(payload, args.out)
        return 2

    current = capture_workspace(root)
    task_delta = compare_snapshots(start, current)
    payload = {"task_start": start, "current": current, "task_delta": task_delta}
    _write_json(payload, args.out)
    return 2 if task_delta["status"] == "UNAVAILABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
