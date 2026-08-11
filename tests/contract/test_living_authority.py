from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_single_living_authority_has_no_versioned_baseline_tree_or_manifest() -> None:
    assert (ROOT / "docs/authority").is_dir()
    assert not (ROOT / "docs/baseline").exists()
    for name in ("MANIFEST.sha256", "baseline-index.yaml", "BASELINE_INDEX.md"):
        assert not list((ROOT / "docs/authority").rglob(name))
    assert not (ROOT / "docs/authority/编码权威事实/RELEASE").exists()


def test_verify_authority_passes_without_git_or_release_manifest() -> None:
    completed = subprocess.run([sys.executable, "tools/verify_authority.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PASS"
    assert payload["authority_model"] == "SINGLE_LIVING_AUTHORITY"
    assert payload["git_access"] == "DISABLED"


def test_top_level_responsibility_directories_are_not_python_packages() -> None:
    for directory in ("apps", "services", "workers", "runner", "packages", "tests", "tools"):
        assert not (ROOT / directory / "__init__.py").exists()

CORE_AUTHORITY = (
    "产品总体需求与系统边界/产品总体需求与系统边界.yaml",
    "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
    "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml",
    "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
    "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
    "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
    "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml",
)
ACTIVE_DOCUMENT_STATUS = "ACTIVE_CONTROLLED_MUTABLE_AUTHORITY"


def test_core_documents_identify_as_controlled_mutable_current_authority() -> None:
    authority = ROOT / "docs/authority"
    for relative in CORE_AUTHORITY:
        head = "\n".join((authority / relative).read_text(encoding="utf-8").splitlines()[:40])
        assert "  authority_model: SINGLE_LIVING_AUTHORITY" in head
        assert f"  document_status: {ACTIVE_DOCUMENT_STATUS}" in head


def test_current_authority_has_no_active_release_manifest_or_frozen_baseline_dependency() -> None:
    authority = ROOT / "docs/authority"
    governed = (*CORE_AUTHORITY, "系统技术架构技术选型与AGENTS/agents-rules.yaml")
    forbidden = (
        "manifest_ref: MANIFEST.sha256",
        "current release manifest",
        "根级发布清单",
        "RELEASE_AND_MANIFEST",
        "FULL_BASELINE_CODEX_INPUT",
        "当前发布是正式冻结代码输入",
        "technical_status: FROZEN",
        "AUTHORITY-MODEL-R4.2-001",
        "Release只决定成员和版本",
        "预置角色默认模板仍待正式冻结",
        "FULL_CODE_READY: 仅在冻结设计发布中",
    )
    for relative in governed:
        text = (authority / relative).read_text(encoding="utf-8")
        lowered = text.lower()
        for token in forbidden:
            assert token.lower() not in lowered, f"{relative}: {token}"


def test_agent_rules_model_living_authority_integrity_not_release_manifest_ownership() -> None:
    import yaml

    payload = yaml.safe_load(
        (ROOT / "docs/authority/系统技术架构技术选型与AGENTS/agents-rules.yaml").read_text(encoding="utf-8")
    )
    assert payload["rules"]["technical_status"] == "CURRENT_AUTHORITY"
    assert payload["authority_model"]["model_id"] == "AUTHORITY-MODEL-LIVING-001"
    authorities = {item["authority"] for item in payload["authority_model"]["responsibilities"]}
    assert "LIVING_AUTHORITY_INTEGRITY" in authorities
    assert "RELEASE_AND_MANIFEST" not in authorities


def test_verify_authority_legacy_semantic_scan_is_fail_closed(tmp_path: Path) -> None:
    import importlib.util

    module_path = ROOT / "tools/verify_authority.py"
    spec = importlib.util.spec_from_file_location("verify_authority_contract", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    authority = tmp_path / "authority"
    authority.mkdir()
    sample = authority / "sample.yaml"
    sample.write_text(
        "closure_evidence:\n  manifest_ref: MANIFEST.sha256\n  verification_rule: At least the current release manifest was resolved.\n",
        encoding="utf-8",
    )
    errors = module.find_legacy_active_semantics(authority, ["sample.yaml"])
    assert errors
    assert any("MANIFEST.sha256" in error or "current release manifest" in error for error in errors)
