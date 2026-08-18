from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for source in (
    ROOT / "packages/platform-common/src",
    ROOT / "services/api/src",
    ROOT / "workers/background/src",
    ROOT / "workers/scheduler/src",
    ROOT / "packages/observability/src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from platform_common.environment import (  # noqa: E402
    find_repository_root,
    project_environment,
    redact_database_url,
    sanitize_database_error,
)
from platform_api.config import ApiSettings  # noqa: E402
from platform_scheduler.config import SchedulerSettings  # noqa: E402
from platform_worker.config import WorkerSettings  # noqa: E402
from tools.database import check_connection  # noqa: E402
from tools.gates import auth_mysql_gate  # noqa: E402
from tools.governance import required_gate_runner  # noqa: E402
from tools.package_delivery import _forbidden_member  # noqa: E402


def _temp_repo(tmp_path: Path) -> Path:
    (tmp_path / ".governance").mkdir(exist_ok=True)
    (tmp_path / "AGENTS.md").write_text("# test\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")
    return tmp_path


def test_repository_dotenv_loads_from_nested_anchor_without_cwd_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temp_repo(tmp_path)
    nested = root / "services/api/src/module"
    nested.mkdir(parents=True)
    (root / ".env").write_text(
        "ATP_DATABASE_URL=mysql+pymysql://app:local@127.0.0.1:3306/app_db\n",
        encoding="utf-8",
    )
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    assert find_repository_root(nested) == root
    merged = project_environment(anchor=nested, base={})
    assert merged["ATP_DATABASE_URL"].endswith("/app_db")


def test_explicit_process_environment_wins_over_root_dotenv(tmp_path: Path) -> None:
    root = _temp_repo(tmp_path)
    (root / ".env").write_text("ATP_DATABASE_URL=dotenv-value\n", encoding="utf-8")
    merged = project_environment(root=root, base={"ATP_DATABASE_URL": "shell-value"})
    assert merged["ATP_DATABASE_URL"] == "shell-value"


def test_env_example_contains_both_formal_database_urls_without_real_secret() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ATP_DATABASE_URL=mysql+pymysql://<user>:<password>@" in text
    assert "ATP_MYSQL_ADMIN_URL=mysql+pymysql://<admin_user>:<admin_password>@" in text
    assert "REAL_PASSWORD" not in text


def test_real_dotenv_is_gitignored_and_forbidden_from_delivery() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    assert "!.env.example" in gitignore
    assert _forbidden_member(f"{ROOT.name}/.env") is True
    assert _forbidden_member(f"{ROOT.name}/.env.local") is True
    assert _forbidden_member(f"{ROOT.name}/.env.example") is False


def test_api_worker_scheduler_use_governed_application_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    governed = "mysql+pymysql://app:local@127.0.0.1:3306/governed"
    monkeypatch.setenv("PLATFORM_ENVIRONMENT", "test")
    monkeypatch.setenv("ATP_DATABASE_URL", governed)
    monkeypatch.setenv("PLATFORM_DATABASE_URL", "mysql+pymysql://legacy:local@127.0.0.1:3306/legacy")
    monkeypatch.setenv("ATP_JWT_KEY_RING_FILE", str(tmp_path / "jwt.json"))
    monkeypatch.setenv("ATP_AUTH_HMAC_MASTER_KEY_FILE", str(tmp_path / "hmac.json"))
    assert ApiSettings(_env_file=None).database_url == governed
    assert WorkerSettings(_env_file=None).database_url == governed
    assert SchedulerSettings(_env_file=None).database_url == governed


def test_runtime_settings_disable_cwd_dotenv_and_call_shared_loader() -> None:
    for rel in (
        "services/api/src/platform_api/config.py",
        "workers/background/src/platform_worker/config.py",
        "workers/scheduler/src/platform_scheduler/config.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert 'env_file=None' in source
        assert "load_project_environment(anchor=Path(__file__))" in source


def test_auth_mysql_gate_reads_admin_url_from_root_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temp_repo(tmp_path)
    dsn = "mysql+pymysql://root:p%40ss%23word@127.0.0.1:3306/mysql"
    (root / ".env").write_text(f"ATP_MYSQL_ADMIN_URL={dsn}\n", encoding="utf-8")
    monkeypatch.delenv("ATP_MYSQL_ADMIN_URL", raising=False)
    monkeypatch.setattr(auth_mysql_gate, "ROOT", root)
    parsed = auth_mysql_gate._admin_url()
    assert parsed.username == "root"
    assert parsed.password == "p@ss#word"


def test_full_schema_gate_reads_admin_url_from_root_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temp_repo(tmp_path)
    dsn = "mysql+pymysql://admin:encoded%40pass@127.0.0.1:3306/mysql"
    (root / ".env").write_text(f"ATP_MYSQL_ADMIN_URL={dsn}\n", encoding="utf-8")
    monkeypatch.delenv("ATP_MYSQL_ADMIN_URL", raising=False)
    path = ROOT / "docs/authority/validation/run_mysql84_gate.py"
    spec = importlib.util.spec_from_file_location("full_schema_env_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", root)
    assert module._admin_url_from_environment() == dsn


def test_required_gate_subprocess_environment_merges_root_dotenv_with_shell_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _temp_repo(tmp_path)
    (root / ".governance/project.yaml").write_text(
        "schema_version: 1\nproject: {name: env-test}\nruntime: {}\n", encoding="utf-8"
    )
    (root / ".env").write_text(
        "ATP_DATABASE_URL=mysql+pymysql://app:dotenv@127.0.0.1:3306/app\n"
        "ATP_MYSQL_ADMIN_URL=mysql+pymysql://admin:dotenv@127.0.0.1:3306/mysql\n",
        encoding="utf-8",
    )
    shell_admin = "mysql+pymysql://admin:shell@127.0.0.1:3306/mysql"
    monkeypatch.setenv("ATP_MYSQL_ADMIN_URL", shell_admin)
    monkeypatch.delenv("ATP_DATABASE_URL", raising=False)
    env = required_gate_runner._gate_env(root)
    assert env["ATP_DATABASE_URL"].endswith("/app")
    assert env["ATP_MYSQL_ADMIN_URL"] == shell_admin


def test_database_dsn_redaction_and_percent_encoding_are_safe() -> None:
    dsn = "mysql+pymysql://root:p%40ss%23word@127.0.0.1:3306/mysql"
    parsed = check_connection._parse_dsn(dsn, require_database=True)
    assert parsed["password"] == "p@ss#word"
    redacted = redact_database_url(dsn)
    assert "p%40ss%23word" not in redacted
    assert ":***@" in redacted
    diagnostic = sanitize_database_error(f"connection failed for {dsn}", dsn)
    assert dsn not in diagnostic
    assert "p%40ss%23word" not in diagnostic


def test_database_preflight_never_serializes_raw_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    app = "mysql+pymysql://app:app-secret@127.0.0.1:3306/app"
    admin = "mysql+pymysql://root:admin-secret@127.0.0.1:3306/mysql"
    monkeypatch.setenv("ATP_DATABASE_URL", app)
    monkeypatch.setenv("ATP_MYSQL_ADMIN_URL", admin)
    monkeypatch.setattr(check_connection, "_check", lambda *_args, **_kwargs: ("DATABASE_CONNECTION_REFUSED", "connection refused"))
    payload = check_connection.run()
    rendered = repr(payload)
    assert "app-secret" not in rendered
    assert "admin-secret" not in rendered
    assert "***" in rendered


def test_full_schema_gate_keeps_destructive_validation_on_isolated_databases() -> None:
    source = (ROOT / "docs/authority/validation/run_mysql84_gate.py").read_text(encoding="utf-8")
    assert "atp_authority_empty_" in source
    assert "atp_authority_upgrade_" in source
    assert "DROP DATABASE IF EXISTS" in source
    assert "DROP DATABASE IF EXISTS `ai_auto_test_platform_dev`" not in source


def test_only_two_database_dsns_are_documented_as_formal_configuration() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "`ATP_DATABASE_URL`" in readme
    assert "`ATP_MYSQL_ADMIN_URL`" in readme
    assert "`PLATFORM_DATABASE_URL` 仅作为" in readme
    for forbidden in ("MYSQL_ROOT_URL", "DATABASE_ADMIN_URL", "SCHEMA_DATABASE_URL", "TEST_DATABASE_URL"):
        assert forbidden not in (ROOT / ".env.example").read_text(encoding="utf-8")


def test_required_gate_injects_dotenv_but_redacts_database_url_from_gate_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.contract.governance_test_support import _abort_if_present, _project
    from tools.governance.task_governance import reconcile_task, start

    secret = "mysql+pymysql://app:secret-value@127.0.0.1:3306/app"
    gate_command = [
        sys.executable,
        "-c",
        "import os; print(os.environ['ATP_DATABASE_URL'])",
    ]
    _project(tmp_path, gates={"app_gate": gate_command})
    (tmp_path / ".env").write_text(f"ATP_DATABASE_URL={secret}\n", encoding="utf-8")
    monkeypatch.delenv("ATP_DATABASE_URL", raising=False)
    start(tmp_path, "ENV_INJECTION", "modify app", ["src/a.py"])
    (tmp_path / "src/a.py").write_text("x = 2\n", encoding="utf-8")
    reconcile_task(tmp_path, "ENV_INJECTION")
    try:
        result = required_gate_runner.run_required(tmp_path, "ENV_INJECTION", timeout=5)
        assert result["status"] == "PASS", result
        rendered = repr(result)
        assert "secret-value" not in rendered
        assert "mysql+pymysql://app:***@127.0.0.1:3306/app" in rendered
    finally:
        _abort_if_present(tmp_path, "ENV_INJECTION")


def test_full_schema_gate_does_not_claim_admin_url_is_missing_after_dotenv_load() -> None:
    source = (ROOT / "docs/authority/validation/run_mysql84_gate.py").read_text(encoding="utf-8")
    assert "was loaded, but no MySQL client or Docker/Podman runtime is available" in source
    assert "is not configured and no Docker/Podman runtime is available" in source


def test_database_secrets_are_not_forwarded_to_unrelated_frontend_or_isolated_compose() -> None:
    browser_source = (ROOT / "tools/gates/auth_browser_gate.py").read_text(encoding="utf-8")
    schema_source = (ROOT / "docs/authority/validation/run_mysql84_gate.py").read_text(encoding="utf-8")

    assert 'web_environment.pop(ADMIN_URL_ENV, None)' in browser_source
    assert 'web_environment.pop(DATABASE_URL_ENV, None)' in browser_source
    assert 'compose_env.pop(ADMIN_URL_ENV, None)' in schema_source
    assert 'compose_env.pop("ATP_DATABASE_URL", None)' in schema_source
