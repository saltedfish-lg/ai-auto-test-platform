from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"


def test_active_tools_use_single_living_authority() -> None:
    assert (ROOT / "docs/authority").is_dir()
    assert not (ROOT / "docs/baseline").exists()
    for relative in ("tools/dev.py", "tools/openapi_client.py", "tools/mysql84_gate.py", "tools/verify_authority.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "authority" in text
        if relative != "tools/verify_authority.py":
            assert "docs/baseline" not in text


def test_runtime_contract_sources_use_current_authority_not_release_snapshot() -> None:
    text = (ROOT / "packages/contracts/src/platform_contracts/sources.py").read_text(encoding="utf-8")
    assert AUTHORITY_MODEL in text
    assert "AuthoritySources" in text
    assert "BaselineSources" not in text
    assert "platform_design_baseline_release" not in text


def test_generated_client_is_from_current_authority() -> None:
    for relative in ("apps/web/src/generated/types.ts", "apps/web/src/generated/client.ts"):
        first = (ROOT / relative).read_text(encoding="utf-8").splitlines()[0]
        assert "current docs/authority OpenAPI" in first
    report = (ROOT / "apps/web/src/generated/generation-report.json").read_text(encoding="utf-8")
    assert AUTHORITY_MODEL in report


def test_active_core_skill_references_match_living_authority() -> None:
    skill = (ROOT / ".agents/skills/ai-auto-test-platform-core/SKILL.md").read_text(encoding="utf-8")
    rules = (ROOT / ".agents/skills/ai-auto-test-platform-core/schemas/skill-rules.yaml").read_text(encoding="utf-8")
    assert AUTHORITY_MODEL in skill and AUTHORITY_MODEL in rules
    assert "docs/authority" in skill and "docs/authority" in rules
    assert "versioned_baseline_copies" in rules
    assert "codex_git_access" in rules


def test_p1_traceability_uses_current_authority_only() -> None:
    current = (ROOT / "docs/implementation/p1-auth-rbac-traceability.md").read_text(encoding="utf-8")
    assert AUTHORITY_MODEL in current
    assert "docs/authority/**" in current
    assert "READY_FOR_P1_IMPLEMENTATION" in current
    assert "IMPLEMENTED_PENDING_RUNTIME_VALIDATION" in current
    assert "docs/baseline/" not in current
    assert not (ROOT / "docs/implementation/history").exists()


def test_bootstrap_uses_reproducible_npm_ci() -> None:
    text = (ROOT / "tools/dev.py").read_text(encoding="utf-8")
    assert 'npm("ci")' in text
    assert 'npm("install")' not in text


def test_mysql_runtime_gate_uses_living_authority_wording() -> None:
    first = (ROOT / "tests/integration/test_p1_auth_mysql.py").read_text(encoding="utf-8").splitlines()[0]
    assert "current Living Authority P1 auth boundary" in first
    assert "R4.3 candidate" not in first
