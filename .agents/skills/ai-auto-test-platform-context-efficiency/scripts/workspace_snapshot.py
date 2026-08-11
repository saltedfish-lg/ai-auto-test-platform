#!/usr/bin/env python3
"""Filesystem-only task-start snapshot and delta helper.

Git is intentionally outside Codex governance for this project. The helper
therefore fingerprints the controlled workspace directly and never invokes Git.
Snapshots and deltas must be stored outside the workspace so they cannot pollute
later scans.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SNAPSHOT_VERSION = 3
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "test-results", ".runtime", ".tmp", ".build",
    ".openapi-client-check",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def _normalized_path(path: Path | str) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _iter_controlled_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield path


def _fingerprint_tree(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(_iter_controlled_files(root), key=lambda p: p.as_posix()):
        rel = path.relative_to(root).as_posix()
        try:
            result[rel] = f"sha256:{_sha256_file(path)}"
        except OSError as exc:
            result[rel] = f"UNREADABLE:{type(exc).__name__}:{exc}"
    return result


def _digest_mapping(mapping: dict[str, str]) -> str:
    payload = "\n".join(f"{path}\0{mapping[path]}" for path in sorted(mapping))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _workspace_identity(root: Path) -> dict[str, str]:
    normalized = _normalized_path(root)
    return {
        "workspace_root": str(root.resolve()),
        "workspace_root_identity": _sha256_text(normalized),
        "identity_digest": _sha256_text(f"filesystem-only\0{normalized}"),
        "identity_mode": "FILESYSTEM_ONLY",
    }


def capture_workspace(root: Path) -> dict[str, object]:
    root = root.resolve()
    files = _fingerprint_tree(root)
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "workspace_identity": _workspace_identity(root),
        "git_access": "DISABLED",
        "file_count": len(files),
        "files": files,
        "workspace_digest": _digest_mapping(files),
    }


def _unavailable_delta(reason_code: str, message: str) -> dict[str, object]:
    return {
        "status": "UNAVAILABLE",
        "reason_code": reason_code,
        "read_error": message,
        "added": [],
        "removed": [],
        "modified": [],
        "task_delta_paths": [],
        "delta_digest": "UNAVAILABLE",
    }


def compare_snapshots(start: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    if start.get("snapshot_version") != SNAPSHOT_VERSION:
        return _unavailable_delta(
            "SNAPSHOT_VERSION_MISMATCH",
            f"task-start snapshot_version={start.get('snapshot_version')!r}; expected {SNAPSHOT_VERSION}",
        )
    if _normalized_path(str(start.get("root", ""))) != _normalized_path(str(current.get("root", ""))):
        return _unavailable_delta("SNAPSHOT_ROOT_MISMATCH", "task-start/current workspace root differs")
    start_identity = start.get("workspace_identity")
    current_identity = current.get("workspace_identity")
    if not isinstance(start_identity, dict) or not isinstance(current_identity, dict):
        return _unavailable_delta("WORKSPACE_IDENTITY_MISSING", "workspace identity is missing")
    if start_identity.get("identity_digest") != current_identity.get("identity_digest"):
        return _unavailable_delta("WORKSPACE_IDENTITY_MISMATCH", "task-start/current workspace identity differs")

    before = start.get("files")
    after = current.get("files")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return _unavailable_delta("SNAPSHOT_SCHEMA_INVALID", "files fingerprint map is missing")
    before_map = {str(k): str(v) for k, v in before.items()}
    after_map = {str(k): str(v) for k, v in after.items()}
    before_keys, after_keys = set(before_map), set(after_map)
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    modified = sorted(k for k in before_keys & after_keys if before_map[k] != after_map[k])
    task_delta_paths = sorted(set(added) | set(removed) | set(modified))
    digest_map = {f"added:{p}": after_map[p] for p in added}
    digest_map.update({f"removed:{p}": before_map[p] for p in removed})
    digest_map.update({f"modified:{p}": after_map[p] for p in modified})
    return {
        "status": "EMPTY" if not task_delta_paths else "CHANGED",
        "reason_code": None,
        "read_error": None,
        "added": added,
        "removed": removed,
        "modified": modified,
        "task_delta_paths": task_delta_paths,
        "delta_digest": _digest_mapping(digest_map),
    }


def _validate_artifact_path(root: Path, path: str | None, *, role: str) -> dict[str, object] | None:
    if not path:
        return None
    target = Path(path).expanduser().resolve()
    if _is_within(target, root):
        return _unavailable_delta(
            "SNAPSHOT_OUTPUT_INSIDE_WORKSPACE" if role == "output" else "SNAPSHOT_INPUT_INSIDE_WORKSPACE",
            f"{role} path {target!s} must be outside workspace root {root!s}",
        )
    return None


def _write_json(payload: dict[str, object], path: str | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(rendered + "\n", encoding="utf-8")
        os.replace(temp, target)
    print(rendered)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture", help="capture filesystem-only task-start/current snapshot")
    capture.add_argument("--root", default=".")
    capture.add_argument("--out")
    delta = sub.add_parser("delta", help="compare current workspace to an external task-start snapshot")
    delta.add_argument("--root", default=".")
    delta.add_argument("--start", required=True)
    delta.add_argument("--out")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    output_error = _validate_artifact_path(root, args.out, role="output")
    if output_error:
        _write_json(output_error if args.command == "capture" else {"task_start": None, "current": None, "task_delta": output_error}, None)
        return 2

    if args.command == "capture":
        _write_json(capture_workspace(root), args.out)
        return 0

    input_error = _validate_artifact_path(root, args.start, role="input")
    if input_error:
        _write_json({"task_start": None, "current": None, "task_delta": input_error}, args.out)
        return 2
    try:
        start = json.loads(Path(args.start).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        payload = {"task_start": None, "current": None, "task_delta": _unavailable_delta("SNAPSHOT_READ_ERROR", f"{type(exc).__name__}: {exc}")}
        _write_json(payload, args.out)
        return 2
    if not isinstance(start, dict):
        payload = {"task_start": start, "current": None, "task_delta": _unavailable_delta("SNAPSHOT_SCHEMA_INVALID", "task-start snapshot must be a JSON object")}
        _write_json(payload, args.out)
        return 2
    current = capture_workspace(root)
    task_delta = compare_snapshots(start, current)
    _write_json({"task_start": start, "current": current, "task_delta": task_delta}, args.out)
    return 2 if task_delta["status"] == "UNAVAILABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
