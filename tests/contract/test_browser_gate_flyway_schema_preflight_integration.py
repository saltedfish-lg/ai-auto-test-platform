from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_api_starting_browser_gates_use_flyway_for_isolated_schema() -> None:
    for relative in (
        "tools/gates/auth_browser_gate.py",
        "tools/gates/project_acceptance_runtime.py",
        "tools/gates/model_configuration_browser_gate.py",
    ):
        source = _source(relative)
        assert 'run_flyway("migrate", target_database=database)' in source
        assert "_execute_script(database" not in source
        assert "FlywayBlocked" in source


def test_project_acceptance_does_not_disable_api_schema_preflight() -> None:
    source = _source("tools/gates/project_acceptance_runtime.py")
    assert '"ATP_SCHEMA_PREFLIGHT_MODE": "disabled"' not in source
