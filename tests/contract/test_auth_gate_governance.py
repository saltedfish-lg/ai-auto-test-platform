from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.gates import auth_mysql_gate

ROOT = Path(__file__).resolve().parents[2]


class _FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, *_args: object) -> None:
        self.statements.append(statement)

    def fetchone(self) -> tuple[str]:
        return ("8.4.6",)


class _FakeConnection:
    def __init__(self) -> None:
        self.fake_cursor = _FakeCursor()

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return self.fake_cursor


def _result(output: str) -> dict[str, object]:
    # Gate stdout is a complete machine-readable JSON document; formatting
    # (compact vs. indented) is not part of the governance contract.
    return json.loads(output.strip())


def _configure_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    migration_failure: bool = False,
) -> list[str]:
    removed: list[str] = []
    monkeypatch.setenv(
        auth_mysql_gate.ADMIN_URL_ENV,
        "mysql+pymysql://root:synthetic-secret@127.0.0.1:3306/mysql",
    )
    monkeypatch.setattr(sys, "argv", ["auth_mysql_gate.py"])
    monkeypatch.setattr(auth_mysql_gate, "_connection", lambda _database=None: _FakeConnection())
    monkeypatch.setattr(
        auth_mysql_gate,
        "_execute_script",
        (
            (lambda _database, _path: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
            if migration_failure
            else (lambda _database, _path: None)
        ),
    )
    monkeypatch.setattr(auth_mysql_gate, "_seed_legacy_idempotency_record", lambda _db: None)
    monkeypatch.setattr(
        auth_mysql_gate.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        auth_mysql_gate,
        "_drop_isolated_database",
        lambda database: removed.append(database),
    )
    return removed


def test_authentication_gate_database_names_are_unique_and_bounded() -> None:
    names = {auth_mysql_gate._new_database_name() for _ in range(100)}

    assert len(names) == 100
    assert all(name.startswith("ai_auto_test_platform_gate_auth_") for name in names)
    assert all(len(name) <= 64 for name in names)
    assert all(name != "ai_auto_test_platform_dev" for name in names)


def test_missing_admin_environment_is_blocked_without_a_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(auth_mysql_gate.ADMIN_URL_ENV, raising=False)
    monkeypatch.setattr(sys, "argv", ["auth_mysql_gate.py"])

    assert auth_mysql_gate.main() == 2
    output = capsys.readouterr().out
    payload = _result(output)
    assert payload["gate_id"] == auth_mysql_gate.GATE_STATUS_NAME
    assert payload["result"] == "BLOCKED"
    assert "mysql+pymysql://" not in output


def test_successful_gate_uses_and_cleans_the_isolated_database(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    removed = _configure_fake_runtime(monkeypatch)

    assert auth_mysql_gate.main() == 0
    output = capsys.readouterr().out
    payload = _result(output)
    assert payload["gate_id"] == auth_mysql_gate.GATE_STATUS_NAME
    assert payload["result"] == "PASS"
    assert payload["cleanup_status"]["temporary_database_removed"] is True
    assert payload["cleanup_status"]["success"] is True
    assert len(removed) == 1 and removed[0].startswith(auth_mysql_gate.DATABASE_PREFIX)
    assert "synthetic-secret" not in output
    assert "mysql+pymysql://" not in output


def test_failure_still_cleans_the_database_and_sanitizes_the_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    removed = _configure_fake_runtime(monkeypatch, migration_failure=True)

    assert auth_mysql_gate.main() == 1
    output = capsys.readouterr().out
    payload = _result(output)
    assert payload["gate_id"] == auth_mysql_gate.GATE_STATUS_NAME
    assert payload["result"] == "FAIL"
    assert payload["cleanup_status"]["temporary_database_removed"] is True
    assert payload["cleanup_status"]["success"] is True
    assert payload["error_type"] == "RuntimeError"
    assert len(removed) == 1 and removed[0].startswith(auth_mysql_gate.DATABASE_PREFIX)
    assert "synthetic-secret" not in output
    assert "synthetic failure" not in output


def test_active_runtime_paths_have_no_retired_stage_bound_names() -> None:
    legacy_tokens = (
        "ATP_P1_MYSQL_ADMIN_URL",
        "ATP_P1_TEST_DATABASE_URL",
        "tools/p1_auth_mysql_gate.py",
        "tools/p1_browser_gate.py",
        "P1_AUTH_MYSQL_GATE",
        "P1_BROWSER_GATE",
        "P1_AUTH_MYSQL_RUNTIME_GATE",
        "P1_BROWSER_RUNTIME_GATE",
    )
    active_roots = (
        ROOT / "docs" / "authority",
        ROOT / "docs" / "implementation",
        ROOT / "services",
        ROOT / "tools",
        ROOT / "apps" / "web" / "e2e",
        ROOT / "tests" / "integration",
    )
    findings: list[str] = []
    this_file = Path(__file__).resolve()
    for active_root in active_roots:
        for path in active_root.rglob("*"):
            if not path.is_file() or path.resolve() == this_file:
                continue
            if path.suffix.lower() not in {".py", ".yaml", ".yml", ".json", ".md", ".ts"}:
                continue
            text = path.read_text(encoding="utf-8")
            findings.extend(
                f"{path.relative_to(ROOT).as_posix()}: {token}"
                for token in legacy_tokens
                if token in text
            )

    assert findings == []
    assert not (ROOT / "tools" / "p1_auth_mysql_gate.py").exists()
    assert not (ROOT / "tools" / "p1_browser_gate.py").exists()


def test_gate_sources_use_capability_paths_and_status_names() -> None:
    mysql_source = (ROOT / "tools/gates/auth_mysql_gate.py").read_text(encoding="utf-8")
    browser_source = (ROOT / "tools/gates/auth_browser_gate.py").read_text(encoding="utf-8")

    assert 'ADMIN_URL_ENV = "ATP_MYSQL_ADMIN_URL"' in mysql_source
    assert 'DATABASE_URL_ENV = "ATP_DATABASE_URL"' in mysql_source
    assert 'GATE_STATUS_NAME = "AUTH_MYSQL_RUNTIME_GATE"' in mysql_source
    assert 'GATE_STATUS_NAME = "AUTH_BROWSER_RUNTIME_GATE"' in browser_source
    assert '"ATP_AUTH_HMAC_MASTER_KEY_FILE": str(hmac_key_ring_file)' in browser_source
    assert "chromium.executablePath()" in browser_source
    assert "CURRENT_PLAYWRIGHT_BROWSER_NOT_INSTALLED" in browser_source
    assert 'glob("ms-playwright/chromium-*' not in browser_source
    assert "--no-sandbox" not in browser_source
