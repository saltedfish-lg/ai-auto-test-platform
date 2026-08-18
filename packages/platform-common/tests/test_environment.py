from __future__ import annotations

import os
from pathlib import Path

from platform_common.environment import (
    find_repository_root,
    project_environment,
    redact_database_url,
    sanitize_database_error,
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".governance").mkdir()
    (tmp_path / "AGENTS.md").write_text("# test\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")
    return tmp_path


def test_repository_root_is_found_from_nested_anchor(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    nested = root / "services" / "api" / "src"
    nested.mkdir(parents=True)
    assert find_repository_root(nested) == root


def test_shell_environment_wins_over_root_dotenv(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".env").write_text("ATP_DATABASE_URL=from-dotenv\nONLY_DOTENV=yes\n", encoding="utf-8")
    merged = project_environment(root=root, base={"ATP_DATABASE_URL": "from-shell"})
    assert merged["ATP_DATABASE_URL"] == "from-shell"
    assert merged["ONLY_DOTENV"] == "yes"


def test_database_dsn_and_exception_are_redacted() -> None:
    dsn = "mysql+pymysql://root:p%40ss%23word@127.0.0.1:3306/mysql"
    redacted = redact_database_url(dsn)
    assert "p%40ss%23word" not in redacted
    assert ":***@" in redacted
    error = sanitize_database_error(f"failed: {dsn}", dsn)
    assert "p%40ss%23word" not in error
    assert dsn not in error
