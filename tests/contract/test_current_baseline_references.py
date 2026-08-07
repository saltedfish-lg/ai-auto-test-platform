from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT = "R4.2"
RELEASE = "PDBR-2026.08.07-R4.2"
AUTHORITY = "AUTHORITY-MODEL-R4.2-001"

def test_current_navigation_and_active_tools_are_r4_2_aware() -> None:
    assert (ROOT / "docs/baseline/CURRENT").read_text(encoding="utf-8").strip() == CURRENT
    for relative in ("tools/dev.py", "tools/openapi_client.py", "tools/mysql84_gate.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "docs/baseline/R4.1" not in text

def test_current_runtime_contract_boundaries_use_r4_2() -> None:
    sources = (ROOT / "packages/contracts/src/platform_contracts/sources.py").read_text(encoding="utf-8")
    health = (ROOT / "services/api/src/platform_api/health.py").read_text(encoding="utf-8")
    assert RELEASE in sources
    assert RELEASE in health

def test_generated_client_is_from_current_release() -> None:
    for relative in ("apps/web/src/generated/types.ts", "apps/web/src/generated/client.ts"):
        assert RELEASE in (ROOT / relative).read_text(encoding="utf-8").splitlines()[0]

def test_active_core_skill_references_match_current_authority() -> None:
    refs = ROOT / ".agents/skills/ai-auto-test-platform-core/references"
    for path in refs.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert RELEASE in text
        assert AUTHORITY in text
        assert "PDBR-2026.08.06-R4.1" not in text
        assert "AUTHORITY-MODEL-R4.1-001" not in text

def test_p1_traceability_uses_current_r4_2_and_archives_r4_1_blocker() -> None:
    current = (ROOT / "docs/implementation/p1-auth-rbac-traceability.md").read_text(encoding="utf-8")
    history = ROOT / "docs/implementation/history/p1-auth-rbac-traceability-r4.1-blocked.md"
    assert history.exists()
    assert RELEASE in current
    assert AUTHORITY in current
    assert "READY_FOR_P1_IMPLEMENTATION" in current
    assert "docs/baseline/R4.2/**" in current
    assert "BLOCKED_BY_FORMAL_AUTH_CONTRACT_GAP" not in current
    assert "仅引用 `docs/baseline/R4.1/**`" not in current
    historical = history.read_text(encoding="utf-8")
    assert "历史证据，禁止作为当前P1实现事实源" in historical
    assert "PDBR-2026.08.06-R4.1" in historical
