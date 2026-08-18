from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "tools/governance/workspace-path-policy.yaml"


def load_policy(root: Path | None = None) -> dict:
    base = (root or ROOT).resolve()
    project_path = base / ".governance/workspace-path-policy.yaml"
    path = project_path if project_path.is_file() else base / "tools/governance/workspace-path-policy.yaml"
    if not path.is_file():
        path = DEFAULT_POLICY_PATH
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("policy_id") != "WORKSPACE_PATH_POLICY":
        raise ValueError("WORKSPACE_PATH_POLICY_INVALID")
    return payload


def policy_digest(policy: dict) -> str:
    raw = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _matches_category(rel: Path, category: dict) -> bool:
    parts = rel.parts
    directory_names = set(category.get("directory_names") or [])
    if any(part in directory_names for part in parts[:-1]):
        return True
    exact_names = set(category.get("exact_names") or [])
    if rel.name in exact_names:
        return True
    suffixes = set(category.get("suffixes") or [])
    if rel.suffix.lower() in {str(x).lower() for x in suffixes}:
        return True
    for pattern in category.get("name_patterns") or []:
        if fnmatch.fnmatch(rel.name, str(pattern)):
            return True
    rel_posix = rel.as_posix()
    for prefix in category.get("path_prefixes") or []:
        prefix = str(prefix).rstrip("/")
        if rel_posix == prefix or rel_posix.startswith(prefix + "/"):
            return True
    return False


def _normalized_relative(value: str | Path) -> Path:
    rel = Path(str(value).replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("WORKSPACE_PATH_OUTSIDE_ROOT")
    return Path(*[part for part in rel.parts if part not in ("", ".")])


def classify_relative_path(rel: str | Path, policy: dict) -> str:
    rel_path = _normalized_relative(rel)
    categories = policy.get("categories") or {}
    source_override = categories.get("SOURCE")
    if isinstance(source_override, dict) and _matches_category(rel_path, source_override):
        return "SOURCE"
    precedence = ["CACHE", "BUILD_OUTPUT", "RUNTIME_OUTPUT", "TRANSIENT", "SECRET", "FORMAL_EVIDENCE", "AUTHORITY", "GENERATED_REQUIRED"]
    for name in precedence:
        spec = categories.get(name)
        if isinstance(spec, dict) and _matches_category(rel_path, spec):
            return name
    return "SOURCE"


def classify_path(root: Path, path: Path, policy: dict | None = None) -> str:
    root = root.resolve()
    policy = policy or load_policy(root)
    lexical = path if path.is_absolute() else root / path
    try:
        rel = lexical.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise ValueError("WORKSPACE_PATH_OUTSIDE_ROOT") from exc
    return classify_relative_path(rel, policy)


def consumer_categories(policy: dict, consumer: str) -> set[str]:
    spec = (policy.get("consumers") or {}).get(consumer) or {}
    return set(spec.get("include_categories") or spec.get("allowed_categories") or [])


def consumer_allows_relative(root: Path, rel: str | Path, consumer: str, policy: dict | None = None) -> bool:
    policy = policy or load_policy(root)
    return classify_relative_path(rel, policy) in consumer_categories(policy, consumer)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        stat_result = os.lstat(path)
    except OSError:
        return True
    return os.path.islink(path) or bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def iter_policy_files(root: Path, consumer: str, policy: dict | None = None) -> Iterable[Path]:
    root = root.resolve()
    policy = policy or load_policy(root)
    include = consumer_categories(policy, consumer)
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept: list[str] = []
        for name in sorted(dirnames):
            candidate = current / name
            if _is_link_or_reparse(candidate):
                continue
            rel_probe = (candidate.relative_to(root) / "__policy_probe__")
            if classify_relative_path(rel_probe, policy) in include:
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = current / name
            if _is_link_or_reparse(path):
                continue
            rel = path.relative_to(root)
            if classify_relative_path(rel, policy) in include:
                yield path


def forbidden_persisted_paths(root: Path, policy: dict | None = None) -> list[str]:
    root = root.resolve()
    policy = policy or load_policy(root)
    forbidden = set(((policy.get("consumers") or {}).get("cleanup_validation") or {}).get("forbidden_persisted_categories") or [])
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        for name in list(dirnames):
            candidate = current / name
            if _is_link_or_reparse(candidate):
                dirnames.remove(name)
                continue
            rel_probe = candidate.relative_to(root) / "__policy_probe__"
            if classify_relative_path(rel_probe, policy) in forbidden:
                findings.append(candidate.relative_to(root).as_posix() + "/")
                dirnames.remove(name)
        for name in filenames:
            path = current / name
            if classify_relative_path(path.relative_to(root), policy) in forbidden:
                findings.append(path.relative_to(root).as_posix())
    return sorted(findings)
