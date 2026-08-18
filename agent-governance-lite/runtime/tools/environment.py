"""Repository-root environment loading and database-secret redaction.

Local development uses one repository-root ``.env`` file. Process/shell variables always
win over values from that file. The helpers do not depend on the caller's current working
directory and never print or persist loaded secrets.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values

_REPOSITORY_FILE_MARKERS = ("AGENTS.md", "pyproject.toml")
_REPOSITORY_DIRECTORY_MARKERS = (".governance",)
_DATABASE_URL_PATTERN = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9+.-]*://[^\s:/@]+:)(?P<password>[^\s@]*)(?P<suffix>@[^\s]+)"
)


def find_repository_root(start: str | Path | None = None) -> Path:
    """Find the project root from a stable file/module anchor rather than the process cwd."""
    candidate = Path(start).expanduser().resolve() if start is not None else Path(__file__).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for root in (candidate, *candidate.parents):
        if all((root / name).is_file() for name in _REPOSITORY_FILE_MARKERS) and all(
            (root / name).is_dir() for name in _REPOSITORY_DIRECTORY_MARKERS
        ):
            return root
    raise RuntimeError(f"REPOSITORY_ROOT_NOT_FOUND from {candidate}")


def _root(root: str | Path | None, anchor: str | Path | None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    return find_repository_root(anchor)


def project_environment(
    *,
    root: str | Path | None = None,
    anchor: str | Path | None = None,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return ``repo/.env`` merged under an explicit process environment.

    Priority is ``base/os.environ`` > ``repo/.env``. Missing ``.env`` is valid.
    """
    repository_root = _root(root, anchor)
    merged = dict(os.environ if base is None else base)
    env_file = repository_root / ".env"
    if env_file.is_file():
        for key, value in dotenv_values(env_file).items():
            if key and value is not None and key not in merged:
                merged[key] = value
    return merged


def load_project_environment(
    *,
    root: str | Path | None = None,
    anchor: str | Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> Path:
    """Load missing repository ``.env`` values into the target process environment."""
    target = os.environ if environ is None else environ
    repository_root = _root(root, anchor)
    merged = project_environment(root=repository_root, base=target)
    for key, value in merged.items():
        target.setdefault(key, value)
    return repository_root


def get_env(
    name: str,
    *,
    root: str | Path | None = None,
    anchor: str | Path | None = None,
    default: str | None = None,
) -> str | None:
    """Read an environment variable after loading the repository-root ``.env`` once."""
    load_project_environment(root=root, anchor=anchor)
    return os.environ.get(name, default)


def redact_database_url(value: str | None) -> str:
    """Return a DSN safe for diagnostics while preserving non-secret routing information."""
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return _DATABASE_URL_PATTERN.sub(r"\g<prefix>***\g<suffix>", value)
    if not parsed.scheme or parsed.hostname is None:
        return _DATABASE_URL_PATTERN.sub(r"\g<prefix>***\g<suffix>", value)
    username = parsed.username or ""
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port is not None else ""
    auth = username
    if parsed.password is not None:
        auth += ":***"
    if auth:
        auth += "@"
    netloc = f"{auth}{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def sanitize_database_error(message: object, *secret_values: str | None) -> str:
    """Remove DSN credentials and known secret values from exception/CLI diagnostics."""
    sanitized = str(message)
    for raw in secret_values:
        if not raw:
            continue
        sanitized = sanitized.replace(raw, redact_database_url(raw))
        try:
            password = urlsplit(raw).password
        except ValueError:
            password = None
        if password:
            sanitized = sanitized.replace(password, "***")
    sanitized = _DATABASE_URL_PATTERN.sub(r"\g<prefix>***\g<suffix>", sanitized)
    return sanitized
