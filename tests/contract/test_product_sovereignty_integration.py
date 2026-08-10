from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT / ".agents/skills/ai-auto-test-platform-product-sovereignty"
CONTEXT_PACK = ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency/references/task-context-pack.md"
ORCHESTRATOR = ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md"


def _verify_manifest(skill_dir: Path) -> None:
    manifest = skill_dir / "MANIFEST.sha256"
    assert manifest.is_file()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        payload = (skill_dir / rel).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest


def test_product_sovereignty_skill_manifest_and_no_manager_agent() -> None:
    _verify_manifest(PRODUCT)
    assert not (ROOT / ".codex/agents/product_manager.toml").exists()
    assert not (ROOT / ".codex/agents/product_decision_analyst.toml").exists()


def test_product_gate_preserves_user_product_sovereignty() -> None:
    text = (PRODUCT / "SKILL.md").read_text(encoding="utf-8")
    for token in (
        "PRODUCT_AUTHORITY_GATE",
        "PRODUCT_DECISION_NOT_REQUIRED",
        "PRODUCT_FACT_FOUND",
        "PRODUCT_DECISION_REQUIRED",
        "PRODUCT_CONFLICT_DETECTED",
        "PRODUCT_SCOPE_CHANGE",
        "recommendation != approval",
        "用户拥有产品批准权",
    ):
        assert token in text
    assert "不修改代码" in text
    assert "不新增 Product Manager Agent" in text


def test_product_decision_pack_cannot_self_approve() -> None:
    text = (PRODUCT / "references/product-decision-pack.md").read_text(encoding="utf-8")
    assert "recommendation_is_approval: false" in text
    assert "confirmed_by_user: false" in text
    assert "authority_update_required" in text
    assert "决策辅助制品，不是权威事实源" in text


def test_orchestrator_runs_product_gate_before_architecture_gate() -> None:
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    product_at = text.index("**产品主权门**")
    architecture_at = text.index("**架构风险门禁**")
    assert product_at < architecture_at
    assert "$ai-auto-test-platform-product-sovereignty" in text
    assert "PRODUCT_CONFLICT_DETECTED" in text
    assert "recommendation" in text.lower() or "推荐方案不等于用户批准" in text


def test_task_context_pack_has_reusable_product_authority_slice() -> None:
    text = CONTEXT_PACK.read_text(encoding="utf-8")
    for token in (
        "product_authority:",
        "assessed_pack_revision",
        "freshness: CURRENT | STALE",
        "user_decision_status: NOT_REQUIRED | PENDING | CONFIRMED",
        "decision_source: NONE | CURRENT_USER_REQUEST | PRIOR_USER_DECISION | DECISION_PACK_SELECTION",
        "authority_update_required: false",
        "workflow_state: READY_FOR_ARCHITECTURE | BLOCKED_BY_PRODUCT_DECISION | AUTHORITY_UPDATE_ONLY",
        "Product Authority 复用与失效规则",
    ):
        assert token in text
    assert "AI 推荐不得写成 `CONFIRMED`" in text


def test_architecture_and_engineering_autonomy_route_product_gaps_to_gate() -> None:
    architecture = (ROOT / ".agents/skills/ai-auto-test-platform-architecture/SKILL.md").read_text(encoding="utf-8")
    assert "$ai-auto-test-platform-product-sovereignty" in architecture
    for rel in (
        ".agents/skills/ai-auto-test-platform-backend/references/engineering-autonomy.md",
        ".agents/skills/ai-auto-test-platform-frontend/references/engineering-autonomy.md",
        ".agents/skills/ai-auto-test-platform-feature-orchestrator/references/engineering-autonomy.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "$ai-auto-test-platform-product-sovereignty" in text
        assert "推荐方案不等于批准" in text


def test_explicit_current_user_product_decision_does_not_repeat_pending() -> None:
    skill = (PRODUCT / "SKILL.md").read_text(encoding="utf-8")
    pack = (PRODUCT / "references/product-decision-pack.md").read_text(encoding="utf-8")
    context = CONTEXT_PACK.read_text(encoding="utf-8")
    assert "CURRENT_USER_REQUEST" in skill
    assert "禁止为了门禁形式再次要求确认" in skill
    assert "selected_option=USER_DEFINED" in skill
    assert "CURRENT_USER_REQUEST" in pack
    assert "selected_option=USER_DEFINED" in pack
    assert "禁止再次要求同一产品确认" in context


def test_confirmed_missing_fact_requires_authority_update() -> None:
    skill = (PRODUCT / "SKILL.md").read_text(encoding="utf-8")
    pack = (PRODUCT / "references/product-decision-pack.md").read_text(encoding="utf-8")
    context = CONTEXT_PACK.read_text(encoding="utf-8")
    assert "`PRODUCT_DECISION_REQUIRED + CONFIRMED` 默认意味着新增原缺失产品事实" in skill
    assert "`PRODUCT_DECISION_REQUIRED + CONFIRMED` 默认意味着新增原缺失产品事实" in pack
    assert "`PRODUCT_DECISION_REQUIRED + CONFIRMED` 表示为原缺失域**新增正式产品事实**" in context
    assert "authority_update_required=true" in skill


def test_confirmed_product_decision_allows_only_authority_update_before_architecture() -> None:
    skill = (PRODUCT / "SKILL.md").read_text(encoding="utf-8")
    orchestrator = ORCHESTRATOR.read_text(encoding="utf-8")
    context_skill = (ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency/SKILL.md").read_text(encoding="utf-8")
    for text in (skill, orchestrator, context_skill):
        assert "AUTHORITY_UPDATE_ONLY" in text
    assert "禁止 Architecture/Implementation" in orchestrator
    assert "禁止 Architecture/Implementation" in context_skill
    assert "重新执行产品门" in orchestrator
    assert "PRODUCT_FACT_FOUND" in orchestrator


def test_product_decision_state_machine_requires_fact_refresh_after_authority_sync() -> None:
    skill = (PRODUCT / "SKILL.md").read_text(encoding="utf-8")
    context = CONTEXT_PACK.read_text(encoding="utf-8")
    for token in ("PENDING", "CONFIRMED", "AUTHORITY_UPDATE_ONLY", "PRODUCT_FACT_FOUND", "READY_FOR_ARCHITECTURE"):
        assert token in skill
        assert token in context
    assert "`CONFIRMED` 只证明用户已经决定，不代表当前权威事实已经同步" in skill
