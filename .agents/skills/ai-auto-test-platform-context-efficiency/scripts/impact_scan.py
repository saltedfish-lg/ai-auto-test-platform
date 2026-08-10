#!/usr/bin/env python3
"""Compact repository-wide impact scanner.

Search breadth is governed by context-policy.yaml. The scanner resolves the
current baseline dynamically, includes root engineering facts, streams large
text files line by line, conditionally expands governance roots, and emits only
compact hit metadata so Codex can search broadly without loading broadly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "test-results",
}
LARGE_FILE_BYTES = 4 * 1024 * 1024
SAMPLE_LIMIT = 20
DEFAULT_REQUIRED_ROOTS = (
    "AGENTS.md", "package.json", "package-lock.json", "pyproject.toml",
    "requirements-dev.lock", ".env.example", ".editorconfig",
    ".gitattributes", ".gitignore", "apps", "services", "workers",
    "runner", "packages", "tests", "tools", "docs/baseline/CURRENT",
)
DEFAULT_OPTIONAL_ROOTS = ("db", ".github")
DEFAULT_GOVERNANCE_ROOTS = (".agents", ".codex")


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
    """Read scope lists without adding a YAML runtime dependency."""
    policy = root / ".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml"
    if not policy.is_file():
        return (
            list(DEFAULT_REQUIRED_ROOTS),
            list(DEFAULT_OPTIONAL_ROOTS),
            list(DEFAULT_GOVERNANCE_ROOTS),
        )
    try:
        lines = policy.read_text(encoding="utf-8").splitlines()
    except OSError:
        return (
            list(DEFAULT_REQUIRED_ROOTS),
            list(DEFAULT_OPTIONAL_ROOTS),
            list(DEFAULT_GOVERNANCE_ROOTS),
        )
    required = _load_policy_list(lines, "required_roots") or list(DEFAULT_REQUIRED_ROOTS)
    optional = _load_policy_list(lines, "optional_roots") or list(DEFAULT_OPTIONAL_ROOTS)
    governance = _load_policy_list(lines, "governance_roots") or list(DEFAULT_GOVERNANCE_ROOTS)
    return required, optional, governance



def collect_git_tracked_deleted(root: Path) -> tuple[list[str], str | None]:
    """Return tracked paths deleted from the working tree using read-only Git metadata."""
    if not (root / ".git").exists():
        return [], None
    try:
        git_env = os.environ.copy()
        git_env["GIT_OPTIONAL_LOCKS"] = "0"
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--deleted", "-z"],
            check=False,
            env=git_env,
            capture_output=True,
            text=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        return [], f"git ls-files --deleted exited {completed.returncode}: {stderr}"
    paths = [
        item.decode("utf-8", errors="replace")
        for item in completed.stdout.split(b"\0")
        if item
    ]
    return sorted(set(paths)), None


def resolve_current_baseline(root: Path) -> tuple[str | None, Path | None]:
    marker = root / "docs/baseline/CURRENT"
    if not marker.is_file():
        return None, None
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None, None
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        return value or None, None
    candidate = root / "docs/baseline" / value
    return value, candidate if candidate.is_dir() else None


def resolve_search_roots(
    root: Path, include_history: bool, include_governance: bool
) -> tuple[list[Path], list[str], list[str], str | None]:
    required, optional, governance = load_search_policy(root)
    current_name, current_dir = resolve_current_baseline(root)
    resolved: list[Path] = []
    missing_required: list[str] = []
    missing_optional: list[str] = []

    def add_entry(item: str, required_entry: bool) -> None:
        missing = missing_required if required_entry else missing_optional
        if item == "docs/baseline/CURRENT":
            marker = root / item
            if marker.is_file():
                resolved.append(marker)
            else:
                missing.append(item)
            if current_dir is not None:
                resolved.append(current_dir)
            else:
                missing.append(f"docs/baseline/{current_name or '<unresolved-current>'}")
            return
        candidate = root / item
        if candidate.exists():
            resolved.append(candidate)
        else:
            missing.append(item)

    for item in required:
        add_entry(item, True)
    for item in optional:
        add_entry(item, False)
    if include_governance:
        for item in governance:
            # Governance roots are required only when explicitly requested.
            add_entry(item, True)

    if include_history:
        history_root = root / "docs/baseline"
        if history_root.is_dir():
            resolved.append(history_root)
        else:
            missing_optional.append("docs/baseline")

    unique: list[Path] = []
    seen: set[Path] = set()
    for item in resolved:
        try:
            key = item.resolve()
        except OSError:
            key = item.absolute()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique, missing_required, missing_optional, current_name


def iter_files(search_roots: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for base in search_roots:
        if base.is_file():
            candidates = (base,)
        elif base.is_dir():
            candidates = base.rglob("*")
        else:
            continue
        for path in candidates:
            if not path.is_file() or is_skipped(path):
                continue
            try:
                key = path.resolve()
            except OSError:
                key = path.absolute()
            if key in seen:
                continue
            seen.add(key)
            yield path


def classify_path(relative: str, current_baseline: str | None) -> str:
    current_prefix = f"docs/baseline/{current_baseline}/" if current_baseline else ""
    if relative == "AGENTS.md":
        return "governance-core"
    if relative.startswith(".agents/") or relative.startswith(".codex/"):
        return "governance-expanded"
    if relative.startswith(".github/"):
        return "ci"
    if relative in {
        "package.json", "package-lock.json", "pyproject.toml", "requirements-dev.lock",
        ".env.example", ".editorconfig", ".gitattributes", ".gitignore",
    }:
        return "engineering-config"
    if relative == "docs/baseline/CURRENT":
        return "authority-marker"
    if current_prefix and relative.startswith(current_prefix):
        return "authority"
    for prefix, group in (
        ("apps/", "frontend"), ("services/", "backend"), ("workers/", "workers"),
        ("runner/", "runner"), ("packages/", "packages"), ("tests/", "tests"),
        ("tools/", "tools"), ("db/", "database"), ("docs/baseline/", "baseline-history"),
    ):
        if relative.startswith(prefix):
            return group
    return "other"


def scan_file(
    path: Path,
    root: Path,
    raw_terms: list[str],
    patterns: list[re.Pattern[str]],
    snippets_per_file: int,
) -> tuple[dict[str, object] | None, str | None]:
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"

    total = 0
    matched_terms: set[str] = set()
    line_hits: list[dict[str, object]] = []
    try:
        with handle:
            for index, line in enumerate(handle, start=1):
                current = [
                    raw for raw, pattern in zip(raw_terms, patterns, strict=True)
                    if pattern.search(line)
                ]
                if not current:
                    continue
                total += 1
                matched_terms.update(current)
                if len(line_hits) < snippets_per_file:
                    compact = " ".join(line.strip().split())[:180]
                    line_hits.append({"line": index, "snippet": compact})
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"

    if not total:
        return None, None
    return {
        "path": path.relative_to(root).as_posix(),
        "hits": total,
        "terms": sorted(matched_terms),
        "samples": line_hits,
    }, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("terms", nargs="+", help="literal or regex search terms")
    parser.add_argument("--root", default=".")
    parser.add_argument("--regex", action="store_true")
    parser.add_argument(
        "--risk",
        choices=("LOCAL", "CROSS_MODULE", "HIGH_RISK"),
        default="LOCAL",
        help="task impact risk; CROSS_MODULE/HIGH_RISK require complete Git metadata when a repository is present",
    )
    parser.add_argument(
        "--require-git-metadata",
        action="store_true",
        help="require readable Git metadata for CI/dependency/build/deploy/env/tooling-sensitive tasks",
    )
    parser.add_argument("--include-history", action="store_true")
    parser.add_argument(
        "--include-governance",
        action="store_true",
        help="expand .agents/.codex for Agent/Skill/Orchestrator/Codex-governance tasks",
    )
    parser.add_argument("--snippets-per-file", type=int, default=2)
    parser.add_argument(
        "--max-output-files", type=int, default=0,
        help="limit printed result rows only; scanning still covers the full active scope",
    )
    parser.add_argument(
        "--index-out",
        help="optional JSON path for the full result index when printed output is limited",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    patterns = [
        re.compile(term if args.regex else re.escape(term), re.IGNORECASE)
        for term in args.terms
    ]
    search_roots, missing_required, missing_optional, current_baseline = resolve_search_roots(
        root, args.include_history, args.include_governance
    )
    tracked_deleted, git_workspace_error = collect_git_tracked_deleted(root)
    git_repository_present = (root / ".git").exists()
    if not git_repository_present:
        git_workspace_status = "NOT_APPLICABLE"
    elif git_workspace_error:
        git_workspace_status = "UNAVAILABLE"
    else:
        git_workspace_status = "COMPLETE"
    git_metadata_required_by_task_risk = args.require_git_metadata or args.risk in {"CROSS_MODULE", "HIGH_RISK"}
    # If this workspace is a Git repository, readable Git metadata is always required
    # before declaring impact closure safe. Task risk controls whether the task itself
    # explicitly requires Git evidence; closure completeness is a separate invariant.
    git_metadata_required_for_closure = git_repository_present

    results: list[dict[str, object]] = []
    scanned = 0
    binary_skipped = 0
    binary_samples: list[str] = []
    large_file_count = 0
    large_file_samples: list[str] = []
    error_count = 0
    error_samples: list[str] = []
    group_scanned: Counter[str] = Counter()

    for path in iter_files(search_roots):
        relative = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError as exc:
            error_count += 1
            _sample_append(error_samples, f"{relative}: {type(exc).__name__}: {exc}")
            continue
        if is_probably_binary(path):
            binary_skipped += 1
            _sample_append(binary_samples, relative)
            continue
        if size > LARGE_FILE_BYTES:
            large_file_count += 1
            _sample_append(large_file_samples, relative)

        scanned += 1
        group_scanned[classify_path(relative, current_baseline)] += 1
        result, error = scan_file(path, root, args.terms, patterns, max(0, args.snippets_per_file))
        if error:
            error_count += 1
            _sample_append(error_samples, f"{relative}: {error}")
        elif result is not None:
            results.append(result)

    results.sort(key=lambda item: (-int(item["hits"]), str(item["path"])))
    matched_groups = Counter(classify_path(str(item["path"]), current_baseline) for item in results)
    scope_complete = not missing_required and error_count == 0 and current_baseline is not None
    # If a Git repository is present but its metadata cannot be read, tracked-deleted
    # evidence is incomplete. Never claim closure_safe from incomplete evidence.
    git_evidence_complete = git_workspace_status != "UNAVAILABLE"
    closure_safe = scope_complete and git_evidence_complete
    scope_status = "COMPLETE" if scope_complete else "INCOMPLETE"
    closure_blockers: list[str] = []
    if not scope_complete:
        closure_blockers.append("incomplete_required_scope")
    if not git_evidence_complete:
        closure_blockers.append("git_metadata_unavailable")

    payload: dict[str, object] = {
        "scope": {
            "scope_status": scope_status,
            "closure_safe": closure_safe,
            "current_baseline": current_baseline,
            "include_history": args.include_history,
            "include_governance": args.include_governance,
            "task_risk": args.risk,
            "git_metadata_required_by_task_risk": git_metadata_required_by_task_risk,
            "git_metadata_required_for_closure": git_metadata_required_for_closure,
            "closure_blockers": closure_blockers,
            "active_roots": [path.relative_to(root).as_posix() for path in search_roots],
            "missing_required_roots": missing_required,
            "missing_optional_roots": missing_optional,
        },
        "scanned_text_files": scanned,
        "matched_files": len(results),
        "group_summary": {
            "scanned": dict(sorted(group_scanned.items())),
            "matched": dict(sorted(matched_groups.items())),
        },
        "large_files_streamed": {
            "threshold_bytes": LARGE_FILE_BYTES,
            "count": large_file_count,
            "samples": large_file_samples,
        },
        "skipped_files": {"binary_count": binary_skipped, "binary_samples": binary_samples},
        "scan_errors": {"count": error_count, "samples": error_samples},
        "git_workspace": {
            "status": git_workspace_status,
            "repository_present": git_repository_present,
            "required_by_task_risk": git_metadata_required_by_task_risk,
            "required_for_closure": git_metadata_required_for_closure,
            "blocking_for_closure": git_metadata_required_for_closure and git_workspace_status == "UNAVAILABLE",
            "tracked_deleted_count": len(tracked_deleted),
            "tracked_deleted": tracked_deleted,
            "read_error": git_workspace_error,
            "note": (
                "tracked-but-deleted paths are impact evidence even when their working-tree content is absent; "
                "if a repository is present but Git metadata is UNAVAILABLE, required_for_closure=true and closure_safe=false. "
                "required_by_task_risk is a separate signal for CROSS_MODULE/HIGH_RISK or explicit CI/dependency/build/deploy/env/tooling-sensitive tasks."
            ),
        },
        "results": results,
    }

    if args.index_out:
        index_path = Path(args.index_out)
        if not index_path.is_absolute():
            index_path = root / index_path
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    visible_results = results
    truncated = 0
    if args.max_output_files > 0 and len(results) > args.max_output_files:
        visible_results = results[: args.max_output_files]
        truncated = len(results) - len(visible_results)

    if args.json:
        visible_payload = dict(payload)
        visible_payload["results"] = visible_results
        visible_payload["truncated_results"] = truncated
        if truncated and not args.index_out:
            visible_payload["warning"] = (
                "printed results were truncated; rerun without --max-output-files or use --index-out "
                "before declaring impact closure"
            )
        print(json.dumps(visible_payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"scope_status={scope_status} closure_safe={str(closure_safe).lower()} "
            f"current_baseline={current_baseline or '<unresolved>'} scanned={scanned} "
            f"matched_files={len(results)} large_streamed={large_file_count} "
            f"binary_skipped={binary_skipped} scan_errors={error_count} "
            f"git_status={git_workspace_status} tracked_deleted={len(tracked_deleted)}"
        )
        if missing_required:
            print(f"missing_required_roots={','.join(missing_required)}")
        if missing_optional:
            print(f"missing_optional_roots={','.join(missing_optional)}")
        print("matched_groups=" + ",".join(f"{group}:{count}" for group, count in sorted(matched_groups.items())))
        for item in visible_results:
            samples = item["samples"]
            locs = ",".join(str(sample["line"]) for sample in samples)
            print(f"{int(item['hits']):>4}  {item['path']}  lines={locs}  terms={','.join(item['terms'])}")
        if truncated:
            suffix = f"; full_index={args.index_out}" if args.index_out else ""
            print(
                f"truncated_results={truncated}{suffix}; "
                "do not declare impact closure from truncated output alone"
            )

    # Fail closed: incomplete required scope, unreadable active text, or unavailable
    # Git metadata in an existing repository means impact closure cannot be declared.
    return 0 if closure_safe else 2


if __name__ == "__main__":
    raise SystemExit(main())
