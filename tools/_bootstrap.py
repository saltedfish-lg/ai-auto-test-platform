"""Root-aware bootstrap for formal direct-script developer CLIs.

The bootstrap only establishes repository import context. Repository discovery itself is
owned by ``platform_common.environment.find_repository_root`` so direct scripts and package
imports converge on the same root semantics.
"""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path(anchor: str | Path) -> Path:
    candidate = Path(anchor).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    common_source: Path | None = None
    for parent in (candidate, *candidate.parents):
        probe = parent / "packages" / "platform-common" / "src"
        if probe.is_dir():
            common_source = probe
            break
    if common_source is None:
        raise RuntimeError(f"REPOSITORY_IMPORT_CONTEXT_NOT_FOUND from {candidate}")
    common_text = str(common_source)
    if common_text not in sys.path:
        sys.path.insert(0, common_text)
    from platform_common.environment import find_repository_root

    root = find_repository_root(candidate)
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root
