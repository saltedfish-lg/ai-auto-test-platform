from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / ".codex" / "agents"

EXPECTED = {
    "frontend_implementer": "workspace-write",
    "backend_implementer": "workspace-write",
    "contract_guardian": "read-only",
    "database_integrity_reviewer": "read-only",
    "security_rbac_reviewer": "read-only",
    "ui_verifier": "workspace-write",
    "independent_code_reviewer": "read-only",
}

def test_project_custom_agents_are_valid_and_permission_scoped() -> None:
    loaded = {}
    for path in sorted(AGENTS.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert data["name"]
        assert data["description"]
        assert data["developer_instructions"]
        loaded[data["name"]] = data["sandbox_mode"]
    assert loaded == EXPECTED
