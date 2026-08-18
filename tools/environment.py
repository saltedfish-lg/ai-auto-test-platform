"""Developer-tool bridge to the project's single shared repository environment loader."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON_SOURCE = ROOT / "packages" / "platform-common" / "src"
if str(COMMON_SOURCE) not in sys.path:
    sys.path.insert(0, str(COMMON_SOURCE))

from platform_common.environment import (  # noqa: E402
    find_repository_root,
    get_env,
    load_project_environment,
    project_environment,
    redact_database_url,
    sanitize_database_error,
)

__all__ = [
    "find_repository_root",
    "get_env",
    "load_project_environment",
    "project_environment",
    "redact_database_url",
    "sanitize_database_error",
]
