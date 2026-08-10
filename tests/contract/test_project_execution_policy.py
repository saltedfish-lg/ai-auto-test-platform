import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_root_agents_forbids_git_write_operations_by_default() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Git操作限制" in text
    assert "Git版本管理由用户负责" in text
    assert "当前任务中明确授权" in text
    for command in (
        "git add",
        "git commit",
        "git push",
        "git pull",
        "git checkout",
        "git switch",
        "git merge",
        "git rebase",
        "git reset",
        "git tag",
        "git remote",
    ):
        assert command in text
    assert ".git/**" in text
    assert "自动建分支、暂存、提交、推送或创建PR" in text


def test_all_custom_agents_explicitly_inherit_root_git_policy() -> None:
    agent_dir = ROOT / ".codex" / "agents"
    paths = sorted(agent_dir.glob("*.toml"))
    assert len(paths) == 12
    for path in paths:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        instructions = data["developer_instructions"]
        assert "继承根 AGENTS.md 的 Git 操作限制" in instructions
        assert "不得执行任何 Git 写操作" in instructions
