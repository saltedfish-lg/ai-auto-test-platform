#!/usr/bin/env python3
"""Filesystem-only task snapshot with mechanical source-symbol delta evidence.

Git is intentionally outside Codex governance. Snapshot v4 fingerprints the controlled
workspace plus source symbols/line hashes so Incremental Closure can mechanically derive
changed_symbols / changed_line_ranges instead of trusting caller-supplied scope.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SNAPSHOT_VERSION = 4
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "test-results", ".runtime", ".tmp", ".build",
    ".openapi-client-check",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue"}
BUSINESS_ROOTS = {"services", "packages", "workers", "runner", "apps"}
GENERATED_PARTS = {"generated", "dist", "node_modules"}
WEB_SYMBOL_RE = re.compile(
    r"(?m)^(?P<indent>\s*)(?:export\s+)?(?:async\s+)?function\s+(?P<fn>[A-Za-z_$][\w$]*)\s*\(|"
    r"^(?P<indent2>\s*)(?:export\s+)?(?:const|let|var)\s+(?P<arrow>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^\n]*\)|[A-Za-z_$][\w$]*)\s*=>|"
    r"^(?P<indent3>\s*)(?P<method>[A-Za-z_$][\w$]*)\s*\([^\n]*\)\s*\{"
)


def _normalized_path(path: Path | str) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _is_link_or_reparse(path: Path) -> bool:
    """Return True for symlinks and Windows reparse points without following them."""
    try:
        stat_result = os.lstat(path)
    except OSError:
        # Fail closed for entries whose metadata cannot be read during traversal.
        return True
    if os.path.islink(path):
        return True
    return bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def _iter_controlled_files(root: Path) -> Iterable[Path]:
    """Walk the controlled workspace with directory-level pruning.

    Ignored dependency/cache directories are removed from ``dirnames`` before os.walk
    descends into them. This prevents CP-0 from paying metadata traversal cost for tens
    of thousands of files that can never enter Snapshot v4. Symlink/reparse directories
    are also pruned so Windows junctions cannot expand or escape the controlled tree.
    """
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for name in sorted(dirnames):
            candidate = current / name
            if name in SKIP_DIRS or _is_link_or_reparse(candidate):
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            path = current / name
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if _is_link_or_reparse(path):
                continue
            yield path


def _fingerprint_tree(root: Path, controlled_files: Iterable[Path] | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    paths = controlled_files if controlled_files is not None else _iter_controlled_files(root)
    for path in sorted(paths, key=lambda p: p.as_posix()):
        rel = path.relative_to(root).as_posix()
        try:
            result[rel] = f"sha256:{_sha256_file(path)}"
        except OSError as exc:
            result[rel] = f"UNREADABLE:{type(exc).__name__}:{exc}"
    return result


def _is_business_source(path: Path, root: Path) -> bool:
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        return False
    rel = path.relative_to(root)
    if not rel.parts or rel.parts[0] not in BUSINESS_ROOTS or "tests" in rel.parts:
        return False
    if any(part in GENERATED_PARTS for part in rel.parts):
        return False
    return True


def _python_symbols(text: str) -> dict[str, dict[str, object]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    result: dict[str, dict[str, object]] = {}

    def walk(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{child.name}"
                segment = ast.get_source_segment(text, child) or ""
                start = int(getattr(child, "lineno", 1))
                end = int(getattr(child, "end_lineno", start))
                result[qualname] = {
                    "body_sha256": _sha256_text(segment),
                    "start_line": start,
                    "end_line": end,
                }
                walk(child, f"{qualname}.")
            else:
                walk(child, prefix)

    walk(tree)
    return result


def _brace_end_line(lines: list[str], start_line: int) -> int:
    depth = 0
    started = False
    for line_no in range(start_line, min(len(lines), start_line + 400) + 1):
        line = lines[line_no - 1]
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}" and started:
                depth -= 1
                if depth <= 0:
                    return line_no
    return min(len(lines), start_line + 40)


def _web_symbols(text: str) -> dict[str, dict[str, object]]:
    lines = text.splitlines()
    result: dict[str, dict[str, object]] = {}
    for match in WEB_SYMBOL_RE.finditer(text):
        name = match.group("fn") or match.group("arrow") or match.group("method")
        if not name or name in {"if", "for", "while", "switch", "catch"}:
            continue
        start_line = text.count("\n", 0, match.start()) + 1
        end_line = _brace_end_line(lines, start_line)
        segment = "\n".join(lines[start_line - 1:end_line])
        # When duplicate method names exist, keep a stable line-qualified key rather than silently overwrite.
        key = name if name not in result else f"{name}@{start_line}"
        result[key] = {
            "body_sha256": _sha256_text(segment),
            "start_line": start_line,
            "end_line": end_line,
        }
    return result


def _source_evidence(
    root: Path,
    controlled_files: Iterable[Path] | None = None,
) -> tuple[dict[str, dict[str, dict[str, object]]], dict[str, list[str]]]:
    symbols: dict[str, dict[str, dict[str, object]]] = {}
    line_hashes: dict[str, list[str]] = {}
    paths = controlled_files if controlled_files is not None else _iter_controlled_files(root)
    for path in sorted(paths, key=lambda p: p.as_posix()):
        if not _is_business_source(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        line_hashes[rel] = [_sha256_text(line) for line in text.splitlines()]
        parsed = _python_symbols(text) if path.suffix.lower() == ".py" else _web_symbols(text)
        if parsed:
            symbols[rel] = parsed
    return symbols, line_hashes


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


def snapshot_evidence_digest(snapshot: dict[str, object]) -> str:
    """Hash the stable snapshot evidence, excluding capture time and the digest itself."""
    stable_keys = (
        "snapshot_version", "root", "workspace_identity", "git_access", "file_count",
        "files", "workspace_digest", "source_symbol_fingerprints", "source_line_hashes",
        "change_scope_provenance",
    )
    payload = {key: snapshot.get(key) for key in stable_keys}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_snapshot_evidence(snapshot: dict[str, object]) -> tuple[bool, str | None]:
    """Validate self-consistency before a snapshot is accepted as mechanical evidence."""
    if snapshot.get("snapshot_version") != SNAPSHOT_VERSION:
        return False, "SNAPSHOT_VERSION_MISMATCH"
    files = snapshot.get("files")
    if not isinstance(files, dict):
        return False, "SNAPSHOT_SCHEMA_INVALID"
    files_map = {str(k): str(v) for k, v in files.items()}
    if snapshot.get("workspace_digest") != _digest_mapping(files_map):
        return False, "SNAPSHOT_WORKSPACE_DIGEST_MISMATCH"
    if snapshot.get("file_count") != len(files_map):
        return False, "SNAPSHOT_FILE_COUNT_MISMATCH"
    if snapshot.get("change_scope_provenance") != "FILESYSTEM_SNAPSHOT_V4":
        return False, "SNAPSHOT_PROVENANCE_INVALID"
    expected = snapshot_evidence_digest(snapshot)
    if snapshot.get("snapshot_evidence_digest") != expected:
        return False, "SNAPSHOT_EVIDENCE_DIGEST_MISMATCH"
    return True, None


def capture_workspace(root: Path) -> dict[str, object]:
    root = root.resolve()
    # Enumerate the workspace exactly once per capture, then reuse that stable file set
    # for hashing and source-symbol evidence. Snapshot v4 schema/semantics stay unchanged.
    controlled_files = tuple(_iter_controlled_files(root))
    files = _fingerprint_tree(root, controlled_files)
    source_symbols, source_line_hashes = _source_evidence(root, controlled_files)
    snapshot: dict[str, object] = {
        "snapshot_version": SNAPSHOT_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "workspace_identity": _workspace_identity(root),
        "git_access": "DISABLED",
        "file_count": len(files),
        "files": files,
        "workspace_digest": _digest_mapping(files),
        "source_symbol_fingerprints": source_symbols,
        "source_line_hashes": source_line_hashes,
        "change_scope_provenance": "FILESYSTEM_SNAPSHOT_V4",
    }
    snapshot["snapshot_evidence_digest"] = snapshot_evidence_digest(snapshot)
    return snapshot


def _unavailable_delta(reason_code: str, message: str) -> dict[str, object]:
    return {
        "status": "UNAVAILABLE",
        "reason_code": reason_code,
        "read_error": message,
        "added": [], "removed": [], "modified": [], "task_delta_paths": [],
        "changed_symbols": {}, "changed_line_ranges": {}, "removed_symbols": {},
        "change_scope_provenance": "FILESYSTEM_SNAPSHOT_V4",
        "delta_digest": "UNAVAILABLE",
    }


def _line_ranges(before: list[str], after: list[str]) -> list[list[int]]:
    ranges: list[list[int]] = []
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or j1 == j2:
            continue
        start, end = j1 + 1, j2
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    return ranges


def _symbol_delta(start: dict[str, object], current: dict[str, object], changed_paths: set[str]) -> tuple[dict[str, list[str]], dict[str, list[list[int]]], dict[str, list[str]]]:
    before_symbols = start.get("source_symbol_fingerprints", {})
    after_symbols = current.get("source_symbol_fingerprints", {})
    before_lines = start.get("source_line_hashes", {})
    after_lines = current.get("source_line_hashes", {})
    if not isinstance(before_symbols, dict) or not isinstance(after_symbols, dict) or not isinstance(before_lines, dict) or not isinstance(after_lines, dict):
        raise ValueError("SOURCE_SYMBOL_EVIDENCE_MISSING")
    changed_symbols: dict[str, list[str]] = {}
    removed_symbols: dict[str, list[str]] = {}
    changed_ranges: dict[str, list[list[int]]] = {}
    for path in sorted(changed_paths):
        old = before_symbols.get(path, {}) if isinstance(before_symbols.get(path, {}), dict) else {}
        new = after_symbols.get(path, {}) if isinstance(after_symbols.get(path, {}), dict) else {}
        names = sorted(
            name for name, meta in new.items()
            if name not in old
            or not isinstance(old.get(name), dict)
            or old.get(name, {}).get("body_sha256") != (meta.get("body_sha256") if isinstance(meta, dict) else None)
        )
        removed = sorted(name for name in old if name not in new)
        if names:
            changed_symbols[path] = names
        if removed:
            removed_symbols[path] = removed
        old_lines = before_lines.get(path, []) if isinstance(before_lines.get(path, []), list) else []
        new_lines = after_lines.get(path, []) if isinstance(after_lines.get(path, []), list) else []
        if new_lines and old_lines != new_lines:
            ranges = _line_ranges([str(x) for x in old_lines], [str(x) for x in new_lines])
            if ranges:
                changed_ranges[path] = ranges
    return changed_symbols, changed_ranges, removed_symbols


def compare_snapshots(start: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    if start.get("snapshot_version") != SNAPSHOT_VERSION:
        return _unavailable_delta("SNAPSHOT_VERSION_MISMATCH", f"task-start snapshot_version={start.get('snapshot_version')!r}; expected {SNAPSHOT_VERSION}")
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
    try:
        changed_symbols, changed_ranges, removed_symbols = _symbol_delta(start, current, set(task_delta_paths))
    except ValueError as exc:
        return _unavailable_delta(str(exc), "snapshot does not contain mechanical source-symbol evidence")
    digest_map = {f"added:{p}": after_map[p] for p in added}
    digest_map.update({f"removed:{p}": before_map[p] for p in removed})
    digest_map.update({f"modified:{p}": after_map[p] for p in modified})
    scope_payload = json.dumps({"changed_symbols": changed_symbols, "changed_line_ranges": changed_ranges, "removed_symbols": removed_symbols}, sort_keys=True, separators=(",", ":"))
    return {
        "status": "EMPTY" if not task_delta_paths else "CHANGED",
        "reason_code": None,
        "read_error": None,
        "added": added,
        "removed": removed,
        "modified": modified,
        "task_delta_paths": task_delta_paths,
        "changed_symbols": changed_symbols,
        "changed_line_ranges": changed_ranges,
        "removed_symbols": removed_symbols,
        "change_scope_provenance": "FILESYSTEM_SNAPSHOT_V4",
        "change_scope_digest": _sha256_text(scope_payload),
        "delta_digest": _digest_mapping(digest_map),
    }


def _validate_artifact_path(root: Path, path: str | None, *, role: str) -> dict[str, object] | None:
    if not path:
        return None
    target = Path(path).expanduser().resolve()
    if _is_within(target, root):
        return _unavailable_delta("SNAPSHOT_OUTPUT_INSIDE_WORKSPACE" if role == "output" else "SNAPSHOT_INPUT_INSIDE_WORKSPACE", f"{role} path {target!s} must be outside workspace root {root!s}")
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
    capture = sub.add_parser("capture", help="capture filesystem-only task-start/current snapshot with symbol fingerprints")
    capture.add_argument("--root", default="."); capture.add_argument("--out")
    delta = sub.add_parser("delta", help="compare current workspace to an external task-start snapshot")
    delta.add_argument("--root", default="."); delta.add_argument("--start", required=True); delta.add_argument("--out")
    args = parser.parse_args(); root = Path(args.root).resolve()
    output_error = _validate_artifact_path(root, args.out, role="output")
    if output_error:
        _write_json(output_error if args.command == "capture" else {"task_start": None, "current": None, "task_delta": output_error}, None); return 2
    if args.command == "capture":
        _write_json(capture_workspace(root), args.out); return 0
    input_error = _validate_artifact_path(root, args.start, role="input")
    if input_error:
        _write_json({"task_start": None, "current": None, "task_delta": input_error}, args.out); return 2
    try:
        start = json.loads(Path(args.start).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _write_json({"task_start": None, "current": None, "task_delta": _unavailable_delta("SNAPSHOT_READ_ERROR", f"{type(exc).__name__}: {exc}")}, args.out); return 2
    if not isinstance(start, dict):
        _write_json({"task_start": start, "current": None, "task_delta": _unavailable_delta("SNAPSHOT_SCHEMA_INVALID", "task-start snapshot must be a JSON object")}, args.out); return 2
    current = capture_workspace(root); task_delta = compare_snapshots(start, current)
    _write_json({"task_start": start, "current": current, "task_delta": task_delta}, args.out)
    return 2 if task_delta["status"] == "UNAVAILABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
