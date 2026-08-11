#!/usr/bin/env python3
"""Compact repository-wide impact scanner for the single living authority model.

The scanner never invokes Git. It searches the active source tree broadly,
loads only compact hit metadata, and enforces at most one successful formal
FULL_IMPACT_SCAN per task. Historical version directories are not part of the
active authority model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "test-results", ".runtime", ".tmp", ".build",
    ".openapi-client-check",
}
LARGE_FILE_BYTES = 4 * 1024 * 1024
SAMPLE_LIMIT = 20
DEFAULT_REQUIRED_ROOTS = (
    "AGENTS.md", "package.json", "package-lock.json", "pyproject.toml",
    "requirements-dev.lock", ".env.example", ".editorconfig",
    ".gitattributes", ".gitignore", "apps", "services", "workers",
    "runner", "packages", "tests", "tools", "docs/authority",
)
DEFAULT_OPTIONAL_ROOTS = ("db", ".github")
DEFAULT_GOVERNANCE_ROOTS = (".agents", ".codex")
AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
AUTHORITY_ROOT = "docs/authority"
SCAN_STATE_VERSION = 2
FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS = 1


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _canonical_guard_path(root: Path, task_id: str) -> Path:
    identity = hashlib.sha256(f"{root.resolve()}\0{task_id}".encode("utf-8")).hexdigest()
    return Path(tempfile.gettempdir()) / "ai-auto-test-platform-impact-scan" / f"{identity}.json"


def _emit_guard_failure(args: argparse.Namespace, code: str, message: str, state: dict[str, object] | None = None) -> int:
    count = int((state or {}).get("successful_run_count", 0))
    payload = {
        "scan_governance": {
            "mode": "FULL_IMPACT_SCAN",
            "status": "REJECTED",
            "error_code": code,
            "message": message,
            "task_id": getattr(args, "task_id", None),
            "successful_run_count": count,
            "max_successful_runs": FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS,
            "full_rescan_allowed": count < FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS,
        }
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2) if getattr(args, "json", False) else f"{code}: {message}")
    return 3


def _load_scan_state(path: Path) -> tuple[dict[str, object] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return (data, None) if isinstance(data, dict) else (None, "scan state must be a JSON object")


def _write_scan_state(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _scope_digest(args: argparse.Namespace, root: Path) -> str:
    payload = {
        "root": str(root.resolve()),
        "terms": list(args.terms),
        "regex": bool(args.regex),
        "risk": args.risk,
        "include_governance": bool(args.include_governance),
        "authority_model": AUTHORITY_MODEL,
        "authority_root": AUTHORITY_ROOT,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sample_append(samples: list[str], value: str) -> None:
    if len(samples) < SAMPLE_LIMIT:
        samples.append(value)


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def is_probably_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            sample = handle.read(4096)
    except OSError:
        return False
    return b"\x00" in sample


def _load_policy_list(lines: list[str], key: str) -> list[str]:
    values: list[str] = []
    active = False
    base_indent = 0
    needle = f"{key}:"
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if stripped == needle:
            active = True
            base_indent = indent
            continue
        if active:
            if indent <= base_indent and not stripped.startswith("-"):
                break
            if stripped.startswith("-"):
                value = stripped[1:].strip().strip('"\'')
                if value:
                    values.append(value)
    return values


def load_search_policy(root: Path) -> tuple[list[str], list[str], list[str]]:
    policy = root / ".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml"
    if not policy.is_file():
        return list(DEFAULT_REQUIRED_ROOTS), list(DEFAULT_OPTIONAL_ROOTS), list(DEFAULT_GOVERNANCE_ROOTS)
    try:
        lines = policy.read_text(encoding="utf-8").splitlines()
    except OSError:
        return list(DEFAULT_REQUIRED_ROOTS), list(DEFAULT_OPTIONAL_ROOTS), list(DEFAULT_GOVERNANCE_ROOTS)
    return (
        _load_policy_list(lines, "required_roots") or list(DEFAULT_REQUIRED_ROOTS),
        _load_policy_list(lines, "optional_roots") or list(DEFAULT_OPTIONAL_ROOTS),
        _load_policy_list(lines, "governance_roots") or list(DEFAULT_GOVERNANCE_ROOTS),
    )


def resolve_search_roots(root: Path, include_governance: bool) -> tuple[list[Path], list[str], list[str]]:
    required, optional, governance = load_search_policy(root)
    resolved: list[Path] = []
    missing_required: list[str] = []
    missing_optional: list[str] = []
    for item in required:
        candidate = root / item
        (resolved if candidate.exists() else missing_required).append(candidate if candidate.exists() else item)  # type: ignore[arg-type]
    for item in optional:
        candidate = root / item
        (resolved if candidate.exists() else missing_optional).append(candidate if candidate.exists() else item)  # type: ignore[arg-type]
    if include_governance:
        for item in governance:
            candidate = root / item
            if candidate.exists():
                resolved.append(candidate)
            else:
                missing_required.append(item)
    # de-duplicate nested roots while preserving explicit files.
    unique: list[Path] = []
    seen: set[str] = set()
    for path in resolved:
        key = str(Path(path).resolve())
        if key not in seen:
            seen.add(key)
            unique.append(Path(path))
    return unique, [str(x) for x in missing_required], [str(x) for x in missing_optional]


def iter_files(root: Path, roots: Iterable[Path]) -> Iterable[Path]:
    emitted: set[Path] = set()
    for entry in roots:
        if entry.is_file():
            if entry not in emitted:
                emitted.add(entry); yield entry
            continue
        if not entry.is_dir():
            continue
        for path in entry.rglob("*"):
            if not path.is_file():
                continue
            try: rel = path.relative_to(root)
            except ValueError: continue
            if is_skipped(rel):
                continue
            if path not in emitted:
                emitted.add(path); yield path


def classify_path(relative: str) -> str:
    if relative.startswith("docs/authority/"):
        return "authority"
    if relative.startswith(".agents/") or relative.startswith(".codex/"):
        return "governance"
    if relative.startswith(".github/"):
        return "ci"
    for prefix, name in (
        ("apps/", "frontend"), ("services/", "backend"), ("workers/", "worker"),
        ("runner/", "runner"), ("packages/", "package"), ("tests/", "tests"),
        ("tools/", "tools"), ("db/", "database"),
    ):
        if relative.startswith(prefix): return name
    return "root-engineering"


def _compile_terms(terms: list[str], regex: bool) -> list[re.Pattern[str]]:
    flags = re.IGNORECASE
    return [re.compile(term if regex else re.escape(term), flags) for term in terms]


def scan_text_file(path: Path, patterns: list[re.Pattern[str]]) -> tuple[list[dict[str, object]], bool, str | None]:
    hits: list[dict[str, object]] = []
    large = False
    try:
        large = path.stat().st_size >= LARGE_FILE_BYTES
        if is_probably_binary(path):
            return [], large, None
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                matched = [p.pattern for p in patterns if p.search(line)]
                if matched:
                    hits.append({"line": line_no, "terms": matched, "preview": line.strip()[:240]})
                    if len(hits) >= SAMPLE_LIMIT:
                        break
        return hits, large, None
    except OSError as exc:
        return [], large, f"{type(exc).__name__}: {exc}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Single living authority impact scanner")
    parser.add_argument("terms", nargs="+", help="search seeds")
    parser.add_argument("--root", default=".")
    parser.add_argument("--regex", action="store_true")
    parser.add_argument("--risk", choices=("LOCAL", "CROSS_MODULE", "HIGH_RISK"), default="LOCAL")
    parser.add_argument("--include-governance", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--formal-task", action="store_true")
    parser.add_argument("--task-id")
    parser.add_argument("--scan-state")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.root).resolve()
    scan_state_path: Path | None = None
    guard_path: Path | None = None
    previous_state: dict[str, object] | None = None

    if args.formal_task:
        if not args.task_id or not args.scan_state:
            return _emit_guard_failure(args, "FORMAL_SCAN_STATE_REQUIRED", "--task-id and --scan-state are required")
        scan_state_path = Path(args.scan_state).expanduser().resolve()
        if _is_within(scan_state_path, root):
            return _emit_guard_failure(args, "SCAN_STATE_INSIDE_WORKSPACE", "formal scan state must be outside workspace")
        guard_path = _canonical_guard_path(root, args.task_id)
        previous_state, error = _load_scan_state(scan_state_path)
        if error:
            return _emit_guard_failure(args, "SCAN_STATE_CORRUPTED", error)
        canonical, error = _load_scan_state(guard_path)
        if error:
            return _emit_guard_failure(args, "CANONICAL_GUARD_CORRUPTED", error)
        for state in (previous_state, canonical):
            if state and int(state.get("successful_run_count", 0)) >= FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS:
                return _emit_guard_failure(args, "IMPACT_SCAN_ALREADY_COMPLETED", "this task already has one successful FULL_IMPACT_SCAN", state)

    roots, missing_required, missing_optional = resolve_search_roots(root, args.include_governance)
    patterns = _compile_terms(args.terms, args.regex)
    scanned = 0
    errors: list[str] = []
    group_scanned: Counter[str] = Counter()
    matched_groups: Counter[str] = Counter()
    results: list[dict[str, object]] = []
    large_samples: list[str] = []
    for path in iter_files(root, roots):
        rel = path.relative_to(root).as_posix()
        scanned += 1
        group = classify_path(rel)
        group_scanned[group] += 1
        hits, large, error = scan_text_file(path, patterns)
        if large: _sample_append(large_samples, rel)
        if error:
            errors.append(f"{rel}: {error}")
            continue
        if hits:
            matched_groups[group] += 1
            results.append({"path": rel, "group": group, "hits": hits})

    authority_present = (root / AUTHORITY_ROOT).is_dir()
    scope_complete = not missing_required and not errors and authority_present
    blockers: list[str] = []
    if missing_required: blockers.append("missing_required_scope")
    if errors: blockers.append("scan_errors")
    if not authority_present: blockers.append("living_authority_missing")
    closure_safe = scope_complete
    scan_digest = _scope_digest(args, root)
    successful_before = int((previous_state or {}).get("successful_run_count", 0))
    successful_after = successful_before + (1 if args.formal_task and closure_safe else 0)

    payload: dict[str, object] = {
        "policy": "SEARCH_BROAD_LOAD_NARROW_VERIFY_BROAD",
        "authority": {"model": AUTHORITY_MODEL, "root": AUTHORITY_ROOT, "versioned_baseline_copies": False},
        "git_access": "DISABLED",
        "scope": {
            "required_roots_complete": not missing_required,
            "missing_required_roots": missing_required,
            "missing_optional_roots": missing_optional,
            "governance_included": bool(args.include_governance),
            "scope_complete": scope_complete,
        },
        "scan": {
            "risk": args.risk,
            "files_scanned": scanned,
            "groups_scanned": dict(group_scanned),
            "matched_file_count": len(results),
            "matched_groups": dict(matched_groups),
            "error_count": len(errors),
            "errors": errors[:SAMPLE_LIMIT],
            "scan_digest": scan_digest,
        },
        "large_files_streamed": {"count": len(large_samples), "samples": large_samples},
        "results": results,
        "closure": {"closure_safe": closure_safe, "blockers": blockers},
        "scan_governance": {
            "mode": "FULL_IMPACT_SCAN" if args.formal_task else "AD_HOC_SEARCH",
            "status": "COMPLETE" if closure_safe else "FAILED",
            "task_id": args.task_id,
            "successful_run_count": successful_after,
            "max_successful_runs": FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS,
            "full_rescan_allowed": successful_after < FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS,
            "scan_state_ref": str(scan_state_path) if scan_state_path else None,
            "canonical_guard_ref": str(guard_path) if guard_path else None,
        },
    }

    if args.formal_task and scan_state_path and guard_path:
        state = {
            "scan_state_version": SCAN_STATE_VERSION,
            "task_id": args.task_id,
            "workspace_root": str(root),
            "authority_model": AUTHORITY_MODEL,
            "authority_root": AUTHORITY_ROOT,
            "scan_digest": scan_digest,
            "successful_run_count": successful_after,
            "max_successful_runs": FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS,
            "full_rescan_allowed": successful_after < FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS,
            "status": "COMPLETE" if closure_safe else "FAILED",
        }
        _write_scan_state(scan_state_path, state)
        if closure_safe:
            _write_scan_state(guard_path, state)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"authority={AUTHORITY_ROOT} scanned={scanned} matched={len(results)} "
            f"closure_safe={closure_safe} git_access=DISABLED"
        )
        for item in results[:SAMPLE_LIMIT]:
            print(item["path"])
    return 0 if closure_safe else 2


if __name__ == "__main__":
    raise SystemExit(main())
