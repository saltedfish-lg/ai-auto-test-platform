from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = (
    ROOT
    / ".agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("_snapshot_pruning_test", SNAPSHOT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs/authority").mkdir(parents=True)
    (repo / "docs/authority/rules.yaml").write_text("value: 1\n", encoding="utf-8")
    source = repo / "services/api/src/app.py"
    source.parent.mkdir(parents=True)
    source.write_text("def main():\n    return 1\n", encoding="utf-8")
    return repo


def test_snapshot_prunes_ignored_directories_before_descending(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    repo = _repo(tmp_path)
    ignored = repo / "node_modules/pkg/deep"
    ignored.mkdir(parents=True)
    for index in range(50):
        (ignored / f"ignored-{index}.js").write_text("ignored\n", encoding="utf-8")

    real_scandir = os.scandir
    visited: list[Path] = []

    def counting_scandir(path):
        visited.append(Path(path).resolve())
        return real_scandir(path)

    monkeypatch.setattr(module.os, "scandir", counting_scandir)
    files = list(module._iter_controlled_files(repo))

    assert all("node_modules" not in path.relative_to(repo).parts for path in files)
    ignored_root = (repo / "node_modules").resolve()
    assert all(path != ignored_root and ignored_root not in path.parents for path in visited)


def test_capture_enumerates_controlled_tree_once(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    repo = _repo(tmp_path)
    original = module._iter_controlled_files
    calls = 0

    def counted(root: Path):
        nonlocal calls
        calls += 1
        yield from original(root)

    monkeypatch.setattr(module, "_iter_controlled_files", counted)
    snapshot = module.capture_workspace(repo)

    assert calls == 1
    assert snapshot["snapshot_version"] == 4
    assert snapshot["file_count"] == 2
    assert snapshot["change_scope_provenance"] == "FILESYSTEM_SNAPSHOT_V4"


def test_reparse_or_symlink_directory_is_pruned(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    repo = _repo(tmp_path)
    linked = repo / "linked-cache"
    linked.mkdir()
    (linked / "should-not-enter.txt").write_text("x\n", encoding="utf-8")

    original = module._is_link_or_reparse

    def forced_reparse(path: Path) -> bool:
        if Path(path).name == "linked-cache":
            return True
        return original(path)

    monkeypatch.setattr(module, "_is_link_or_reparse", forced_reparse)
    files = list(module._iter_controlled_files(repo))

    assert all("linked-cache" not in path.relative_to(repo).parts for path in files)


def test_snapshot_v4_semantics_keep_controlled_files_and_exclude_cache_noise(tmp_path: Path) -> None:
    module = _module()
    repo = _repo(tmp_path)
    (repo / "outputs").mkdir()
    (repo / "outputs/runtime.txt").write_text("runtime\n", encoding="utf-8")
    cache = repo / ".pytest_cache/v/cache"
    cache.mkdir(parents=True)
    (cache / "nodeids").write_text("[]\n", encoding="utf-8")

    snapshot = module.capture_workspace(repo)
    files = set(snapshot["files"])

    # outputs is not part of the current Snapshot-v4 skip contract, so preserve it.
    assert "outputs/runtime.txt" in files
    assert not any(path.startswith(".pytest_cache/") for path in files)
    assert "docs/authority/rules.yaml" in files
    assert "services/api/src/app.py" in files
