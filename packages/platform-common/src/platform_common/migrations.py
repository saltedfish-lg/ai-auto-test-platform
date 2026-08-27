"""Current migration discovery shared by runtime and repository tooling.

Migration SQL remains owned by the Living Authority. This module only derives the ordered
current chain from Flyway-compatible filenames so callers never hard-code a migration head.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MIGRATION_RE = re.compile(r"^V(?P<version>\d+)__(?P<name>.+)\.sql$")


def discover_migrations(authority_root: Path) -> list[dict[str, Any]]:
    """Return the formal versioned migration chain in numeric order."""
    ddl_dir = authority_root / "编码权威事实" / "DATABASE_DDL"
    if not ddl_dir.is_dir():
        raise ValueError(f"migration authority directory not found: {ddl_dir}")
    found: list[dict[str, Any]] = []
    for path in ddl_dir.iterdir():
        if not path.is_file():
            continue
        match = MIGRATION_RE.fullmatch(path.name)
        if not match:
            continue
        found.append({"version": int(match.group("version")), "name": path.name, "path": path})
    found.sort(key=lambda item: item["version"])
    versions = [int(item["version"]) for item in found]
    if len(versions) != len(set(versions)):
        raise ValueError(f"duplicate migration versions: {versions}")
    if not found:
        raise ValueError(f"no formal migrations found under {ddl_dir}")
    return found


def current_migration_head(authority_root: Path) -> dict[str, Any]:
    """Return the current migration head derived from the formal Authority chain."""
    return discover_migrations(authority_root)[-1]
