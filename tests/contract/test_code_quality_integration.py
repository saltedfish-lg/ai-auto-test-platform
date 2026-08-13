import hashlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents/skills/ai-auto-test-platform-code-quality"


def test_code_quality_skill_has_dual_modes_and_six_lanes() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "Implementation Standards Mode" in text
    assert "Review Mode" in text
    for lane in (
        "Structure / Thermo",
        "Hack / Shortcut",
        "Regression",
        "Testing",
        "Comments / Readability",
        "Maintainability",
    ):
        assert lane in text
    assert "350" in text


def test_code_quality_agent_is_read_only_and_inherits_git_policy() -> None:
    data = tomllib.loads(
        (ROOT / ".codex/agents/code_quality_reviewer.toml").read_text(encoding="utf-8")
    )
    assert data["name"] == "code_quality_reviewer"
    assert data["sandbox_mode"] == "read-only"
    assert "CODEX_GIT_ACCESS=DISABLED" in data["developer_instructions"]
    assert "不得执行任何 Git 命令" in data["developer_instructions"]
    assert "Review Mode" in data["developer_instructions"]


def test_code_quality_skill_manifest_is_complete() -> None:
    expected = {}
    for line in (SKILL / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    actual_files = sorted(
        p for p in SKILL.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256"
    )
    assert set(expected) == {p.relative_to(SKILL).as_posix() for p in actual_files}
    for path in actual_files:
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == expected[path.relative_to(SKILL).as_posix()]
        )


def test_implementers_use_quality_implementation_mode() -> None:
    for relative in (
        ".agents/skills/ai-auto-test-platform-backend/SKILL.md",
        ".agents/skills/ai-auto-test-platform-frontend/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "$ai-auto-test-platform-code-quality" in text
        assert "Implementation Standards Mode" in text


def test_orchestrator_and_final_review_integrate_quality_without_recursive_duplication() -> None:
    orchestrator = (
        ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md"
    ).read_text(encoding="utf-8")
    final_review = (ROOT / ".agents/skills/ai-auto-test-platform-code-review/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "code_quality_reviewer" in orchestrator
    assert "$ai-auto-test-platform-code-quality" in orchestrator
    assert "同一 workspace 状态和同一 scope" in final_review
    assert "不得无条件递归重复Review" in final_review
    assert "code_quality_reviewer" in final_review


def test_root_agents_define_comment_and_quality_policy() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "## 代码质量与注释规范" in text
    assert "Implementation Standards Mode" in text
    assert "Review Mode" in text
    assert "中文原因型注释" in text
    assert "第三人称或客观陈述" in text
    assert "不机械复述代码" in text
