from pathlib import Path
import hashlib
import importlib.util
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / ".agents/skills/ai-auto-test-platform-architecture"
CONTEXT = ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency"


def _verify_manifest(skill: Path) -> None:
    manifest = skill / "MANIFEST.sha256"
    expected = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    actual = sorted(
        p.relative_to(skill).as_posix()
        for p in skill.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256"
    )
    assert sorted(expected) == actual
    for relative, digest in expected.items():
        assert hashlib.sha256((skill / relative).read_bytes()).hexdigest() == digest


def test_architecture_skill_is_risk_triggered_not_always_on() -> None:
    _verify_manifest(ARCH)
    text = (ARCH / "SKILL.md").read_text(encoding="utf-8")
    for token in (
        "ARCH_LOW",
        "ARCH_MEDIUM",
        "ARCH_HIGH",
        "ARCH_NOT_REQUIRED",
        "ARCH_CHECK_PASS",
        "ARCH_DECISION_READY",
        "BLOCKED_BY_PRODUCT_DECISION",
        "ARCH_RECHECK_REQUIRED",
    ):
        assert token in text
    assert "不是产品经理" in text
    assert "ARCH_LOW 禁止为了“更稳”额外调用架构 Agent" in text


def test_solution_architect_is_read_only_and_product_sovereignty_is_preserved() -> None:
    data = tomllib.loads(
        (ROOT / ".codex/agents/solution_architect.toml").read_text(encoding="utf-8")
    )
    assert data["name"] == "solution_architect"
    assert data["sandbox_mode"] == "read-only"
    instructions = data["developer_instructions"]
    assert "ARCH_HIGH" in instructions
    assert "ARCH_LOW" in instructions
    assert "BLOCKED_BY_PRODUCT_DECISION" in instructions
    assert "不修改代码" in instructions
    assert "generic subagent" in instructions


def test_orchestrator_routes_architecture_by_risk() -> None:
    text = (
        ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "$ai-auto-test-platform-architecture" in text
    assert "ARCH_LOW" in text
    assert "ARCH_MEDIUM" in text
    assert "ARCH_HIGH" in text
    assert "solution_architect" in text
    assert "只有 ARCH_HIGH" in text
    assert "BLOCKED_BY_PRODUCT_DECISION" in text


def test_context_pack_has_architecture_and_tracked_deleted_slices() -> None:
    text = (CONTEXT / "references/task-context-pack.md").read_text(encoding="utf-8")
    assert "architecture:" in text
    assert "tracked_deleted:" in text


def test_git_tracked_deleted_is_exposed_without_git_writes(monkeypatch) -> None:
    scanner = CONTEXT / "scripts/impact_scan.py"
    spec = importlib.util.spec_from_file_location("impact_scan_contract", scanner)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class Completed:
        returncode = 0
        stdout = b".github/workflows/ci.yml\0"
        stderr = b""

    def fake_run(*args, **kwargs):
        return Completed()

    fake_root = ROOT
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    paths, error = module.collect_git_tracked_deleted(fake_root)
    assert error is None
    assert paths == [".github/workflows/ci.yml"]


def test_scanner_reports_tracked_deleted_ci_boundary_in_isolated_git_repo(tmp_path) -> None:
    # Build the minimum active scope expected by the scanner so this contract tests
    # scanner behavior rather than the source repository's current Git status.
    required_files = {
        "AGENTS.md": "governance\n",
        "package.json": '{"packageManager":"npm@11.12.1"}\n',
        "package-lock.json": "{}\n",
        "pyproject.toml": "[tool.ruff]\nline-length = 100\n",
        "requirements-dev.lock": "pytest==9.0.3\n",
        ".env.example": "ATP_EXAMPLE=1\n",
        ".editorconfig": "root = true\n",
        ".gitattributes": "* text=auto\n",
        ".gitignore": "__pycache__/\n",
        "docs/baseline/CURRENT": "R4.2\n",
    }
    for relative, content in required_files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for relative in ("apps", "services", "workers", "runner", "packages", "tests", "tools", "docs/baseline/R4.2"):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)

    ci = tmp_path / ".github/workflows/ci.yml"
    ci.parent.mkdir(parents=True, exist_ok=True)
    ci.write_text("name: ci\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", ".github/workflows/ci.yml"], check=True)
    ci.unlink()

    completed = subprocess.run(
        [
            sys.executable,
            str(CONTEXT / "scripts/impact_scan.py"),
            "packageManager",
            "--root",
            str(tmp_path),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    import json
    payload = json.loads(completed.stdout)
    git_workspace = payload["git_workspace"]
    assert git_workspace["tracked_deleted"] == [".github/workflows/ci.yml"]
    assert "impact evidence" in git_workspace["note"]
    assert any(item["path"] == "package.json" for item in payload["results"])
    assert payload["scope"]["closure_safe"] is True


def test_ui_ux_reviewer_environment_fallback_is_consistent() -> None:
    agent = tomllib.loads(
        (ROOT / ".codex/agents/ui_ux_reviewer.toml").read_text(encoding="utf-8")
    )["developer_instructions"]
    business = (
        ROOT / ".agents/skills/ai-auto-test-platform-business-ui-ux/SKILL.md"
    ).read_text(encoding="utf-8")
    ui_quality = (
        ROOT / ".agents/skills/ai-auto-test-platform-ui-quality/SKILL.md"
    ).read_text(encoding="utf-8")
    for token in (
        "BLOCKED_BY_ENVIRONMENT",
        "SOURCE_BASED_CURRENT_UI_BASELINE",
        "VISUAL_BASELINE_CONFIDENCE = LIMITED",
        "POST_CHANGE_BROWSER_VERIFY = REQUIRED",
    ):
        assert token in agent
        assert token in business
        assert token in ui_quality
    assert "禁止要求或伪造不存在的Before screenshot" in agent


def test_architecture_decision_is_reused_instead_of_reclassified() -> None:
    pack = (CONTEXT / "references/task-context-pack.md").read_text(encoding="utf-8")
    orchestrator = (ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md").read_text(encoding="utf-8")
    backend = (ROOT / ".agents/skills/ai-auto-test-platform-backend/SKILL.md").read_text(encoding="utf-8")
    architecture = (ARCH / "SKILL.md").read_text(encoding="utf-8")
    for token in ("architecture_decision:", "assessed_pack_revision", "freshness: CURRENT | STALE", "recheck_required"):
        assert token in pack
    for text in (orchestrator, backend, architecture):
        assert "freshness=CURRENT" in text
        assert "pack_revision" in text
    assert "禁止重复判级" in orchestrator
    assert "不得重复判级" in backend
    assert "不得再次判定 ARCH_RISK" in architecture
    for text in (pack, orchestrator, backend, architecture):
        assert "revision rebind" in text
        assert "assessed_pack_revision" in text
        assert "recheck_required=false" in text
