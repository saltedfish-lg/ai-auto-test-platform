from __future__ import annotations

import copy
from functools import lru_cache
import fnmatch
import shlex
from pathlib import Path
from typing import Any, Iterable

import yaml

PROFILE_DIR = '.governance'
PROFILE_FILES = (
    'project.yaml',
    'domains.yaml',
    'authorities.yaml',
    'gates.yaml',
    'reviewers.yaml',
    'policies.yaml',
    'technology.yaml',
)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return value if isinstance(value, dict) else {}


def _profile_signature(root: Path) -> tuple[tuple[str, int, int], ...]:
    base = root / PROFILE_DIR
    sig: list[tuple[str, int, int]] = []
    for name in PROFILE_FILES:
        path = base / name
        try:
            st = path.stat(); sig.append((name, int(st.st_mtime_ns), int(st.st_size)))
        except FileNotFoundError:
            sig.append((name, -1, -1))
    return tuple(sig)


@lru_cache(maxsize=32)
def _load_project_profile_cached(root_text: str, signature: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del signature
    root = Path(root_text)
    base = root / PROFILE_DIR
    out: dict[str, Any] = {'profile_dir': PROFILE_DIR}
    for name in PROFILE_FILES:
        out[name[:-5].replace('-', '_')] = _read_yaml(base / name)
    return out


def load_project_profile(root: Path) -> dict[str, Any]:
    """Load the optional project profile; cache is invalidated by file stat changes."""
    root = root.resolve()
    return _load_project_profile_cached(str(root), _profile_signature(root))


def profile_exists(root: Path) -> bool:
    return (root.resolve() / PROFILE_DIR / 'project.yaml').is_file()


def project_config(root: Path) -> dict[str, Any]:
    return load_project_profile(root).get('project', {})


def runtime_config(root: Path) -> dict[str, Any]:
    raw = project_config(root)
    value = raw.get('runtime') or {}
    return value if isinstance(value, dict) else {}


def policy_config(root: Path) -> dict[str, Any]:
    raw = load_project_profile(root).get('policies', {})
    value = raw.get('policies') or raw
    return value if isinstance(value, dict) else {}


def domain_config(root: Path) -> dict[str, dict[str, Any]]:
    raw = load_project_profile(root).get('domains', {})
    value = raw.get('domains') or {}
    return {str(k): v for k, v in value.items() if isinstance(v, dict)} if isinstance(value, dict) else {}


def authority_config(root: Path) -> dict[str, dict[str, Any]]:
    raw = load_project_profile(root).get('authorities', {})
    value = raw.get('authorities') or {}
    return {str(k): v for k, v in value.items() if isinstance(v, dict)} if isinstance(value, dict) else {}


def gate_config(root: Path) -> dict[str, dict[str, Any]]:
    raw = load_project_profile(root).get('gates', {})
    value = raw.get('gates') or {}
    return {str(k): v for k, v in value.items() if isinstance(v, dict)} if isinstance(value, dict) else {}


def reviewer_config(root: Path) -> dict[str, dict[str, Any]]:
    raw = load_project_profile(root).get('reviewers', {})
    value = raw.get('reviewers') or {}
    return {str(k): v for k, v in value.items() if isinstance(v, dict)} if isinstance(value, dict) else {}


def technology_config(root: Path) -> dict[str, Any]:
    raw = load_project_profile(root).get('technology', {})
    value = raw.get('technology') or raw
    return value if isinstance(value, dict) else {}


def match_any(rel: str, patterns: Iterable[str]) -> bool:
    rel = rel.replace('\\', '/')
    for pattern in patterns:
        pat = str(pattern).replace('\\', '/')
        if fnmatch.fnmatch(rel, pat):
            return True
        if pat.startswith('**/') and fnmatch.fnmatch(rel, pat[3:]):
            return True
    return False


def configured_request_signals(root: Path, key: str) -> dict[str, tuple[str, ...]]:
    policies = policy_config(root)
    raw = policies.get(key) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(name): tuple(str(x) for x in values or []) for name, values in raw.items()}


def configured_list(root: Path, key: str, default: Iterable[str] = ()) -> tuple[str, ...]:
    value = policy_config(root).get(key)
    if not isinstance(value, list):
        return tuple(default)
    return tuple(str(x) for x in value)


def configured_mapping(root: Path, key: str) -> dict[str, Any]:
    value = policy_config(root).get(key)
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def command_tokens(value: Any) -> list[str] | None:
    if isinstance(value, str) and value.strip():
        return shlex.split(value)
    if isinstance(value, list) and value and all(isinstance(x, (str, int, float)) for x in value):
        return [str(x) for x in value]
    return None


def format_command(tokens: list[str], *, root: Path, task_id: str, files: list[str]) -> list[str]:
    """Expand small, explicit placeholders without creating a workflow DSL."""
    rendered: list[str] = []
    for token in tokens:
        if token == '{files}':
            rendered.extend(files)
            continue
        rendered.append(token.format(root=str(root.resolve()), task_id=task_id))
    return rendered
