from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_SKILL = ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency"
SCANNER = CONTEXT_SKILL / "scripts/impact_scan.py"


def _verify_skill_manifest(skill_name: str) -> None:
    skill = ROOT / ".agents" / "skills" / skill_name
    manifest = skill / "MANIFEST.sha256"
    assert (skill / "SKILL.md").is_file()
    assert manifest.is_file()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative_path = line.split("  ", 1)
        target = skill / relative_path
        assert target.is_file(), relative_path
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected


def _run_scanner(repo: Path, *extra: str, check: bool = True, term: str = "needle") -> dict:
    completed = subprocess.run(
        [sys.executable, str(SCANNER), term, "--root", str(repo), "--json", *extra],
        check=check,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    payload["_returncode"] = completed.returncode
    return payload


def _write_fake_policy(repo: Path) -> None:
    policy = (
        repo
        / ".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml"
    )
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        """version: 3
search_scope:
  required_roots:
    - apps
    - docs/baseline/CURRENT
  optional_roots:
    - optional-root
  governance_roots:
    - .agents
    - .codex
""",
        encoding="utf-8",
    )


def test_context_efficiency_skill_is_integrated() -> None:
    _verify_skill_manifest("ai-auto-test-platform-context-efficiency")
    text = (CONTEXT_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "全局检索不缩水" in text
    assert "Pre-change Impact Closure" in text
    assert "Post-change Closure Verification" in text
    assert "IMPACT_EXPANSION" in text
    assert "流式扫描" in text
    assert "generic subagent" in text
    assert SCANNER.is_file()


def test_impact_scan_streams_large_current_authority_and_obeys_active_roots(tmp_path: Path) -> None:
    _write_fake_policy(tmp_path)
    (tmp_path / "docs/baseline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/baseline/CURRENT").write_text("R9\n", encoding="utf-8")
    current = tmp_path / "docs/baseline/R9"
    history = tmp_path / "docs/baseline/R8"
    current.mkdir(parents=True)
    history.mkdir(parents=True)
    (tmp_path / "apps").mkdir()
    (tmp_path / "noise").mkdir()

    # More than the old 4 MiB threshold, with the hit near the end.
    large = current / "authority.yaml"
    with large.open("w", encoding="utf-8") as handle:
        chunk = "x" * 96 + "\n"
        for _ in range(46000):
            handle.write(chunk)
        handle.write("needle: current-authority\n")

    (history / "old.yaml").write_text("needle: historical\n", encoding="utf-8")
    (tmp_path / "apps/main.py").write_text("needle = 'active-code'\n", encoding="utf-8")
    (tmp_path / "noise/not-active.txt").write_text("needle: noise\n", encoding="utf-8")

    payload = _run_scanner(tmp_path)
    paths = {item["path"] for item in payload["results"]}
    assert "docs/baseline/R9/authority.yaml" in paths
    assert "apps/main.py" in paths
    assert "docs/baseline/R8/old.yaml" not in paths
    assert "noise/not-active.txt" not in paths
    assert payload["scope"]["current_baseline"] == "R9"
    assert "optional-root" in payload["scope"]["missing_optional_roots"]
    assert payload["scope"]["closure_safe"] is True
    assert payload["large_files_streamed"]["count"] == 1
    assert "docs/baseline/R9/authority.yaml" in payload["large_files_streamed"]["samples"]
    assert payload["scan_errors"]["count"] == 0


def test_impact_scan_history_is_opt_in_and_dynamic_current_is_not_hardcoded(tmp_path: Path) -> None:
    _write_fake_policy(tmp_path)
    (tmp_path / "docs/baseline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/baseline/CURRENT").write_text("R77\n", encoding="utf-8")
    (tmp_path / "docs/baseline/R77").mkdir()
    (tmp_path / "docs/baseline/R76").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "docs/baseline/R77/new.yaml").write_text("needle: current\n", encoding="utf-8")
    (tmp_path / "docs/baseline/R76/old.yaml").write_text("needle: old\n", encoding="utf-8")

    default_payload = _run_scanner(tmp_path)
    default_paths = {item["path"] for item in default_payload["results"]}
    assert "docs/baseline/R77/new.yaml" in default_paths
    assert "docs/baseline/R76/old.yaml" not in default_paths

    history_payload = _run_scanner(tmp_path, "--include-history")
    history_paths = {item["path"] for item in history_payload["results"]}
    assert "docs/baseline/R77/new.yaml" in history_paths
    assert "docs/baseline/R76/old.yaml" in history_paths



def test_impact_scan_output_limit_keeps_full_index(tmp_path: Path) -> None:
    _write_fake_policy(tmp_path)
    (tmp_path / "docs/baseline").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/baseline/CURRENT").write_text("R1\n", encoding="utf-8")
    (tmp_path / "docs/baseline/R1").mkdir()
    (tmp_path / "apps").mkdir()
    for idx in range(4):
        (tmp_path / f"apps/file_{idx}.py").write_text(f"needle = {idx!r}\n", encoding="utf-8")
    index_path = tmp_path / "full-index.json"
    payload = _run_scanner(
        tmp_path,
        "--max-output-files",
        "1",
        "--index-out",
        str(index_path),
    )
    assert payload["matched_files"] == 4
    assert len(payload["results"]) == 1
    assert payload["truncated_results"] == 3
    full = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(full["results"]) == 4

def test_task_context_pack_requires_freshness_for_cross_module_work() -> None:
    text = (CONTEXT_SKILL / "references/task-context-pack.md").read_text(encoding="utf-8")
    for token in (
        "pack_revision",
        "baseline_manifest_hash",
        "changed_paths_digest",
        "freshness: CURRENT | STALE",
        "generated:",
        "state_event:",
        "observability_audit_artifact:",
        "delta refresh",
    ):
        assert token in text


def test_business_ui_ux_skill_is_integrated() -> None:
    _verify_skill_manifest("ai-auto-test-platform-business-ui-ux")
    text = (
        ROOT / ".agents/skills/ai-auto-test-platform-business-ui-ux/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "UI_LOW" in text
    assert "UI_MEDIUM" in text
    assert "UI_HIGH" in text
    assert "Business UX Spec" in text
    assert "反机械化" in text
    assert "Pre-change Browser Baseline" in text
    assert "NOT_APPLICABLE_NEW_PAGE" in text
    archetypes = (
        ROOT
        / ".agents/skills/ai-auto-test-platform-business-ui-ux/references/page-archetypes.md"
    ).read_text(encoding="utf-8")
    assert "Authoring Workspace" in archetypes
    assert "AI Assisted Workspace" in archetypes
    assert "Operational Monitoring" in archetypes
    assert "Diagnosis / Analysis" in archetypes


def test_ui_high_before_after_and_custom_agent_fallback_are_orchestrated() -> None:
    for name in (
        "context_impact_analyst",
        "business_ui_ux_designer",
        "ui_ux_reviewer",
    ):
        data = tomllib.loads(
            (ROOT / ".codex" / "agents" / f"{name}.toml").read_text(encoding="utf-8")
        )
        assert data["name"] == name
        assert data["sandbox_mode"] == "read-only"

    orchestrator = (
        ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "Task Context Pack" in orchestrator
    assert "IMPACT_CLOSURE_PASS" in orchestrator
    assert "business_ui_ux_designer" in orchestrator
    assert "ui_ux_reviewer" in orchestrator
    assert "UI_HIGH" in orchestrator
    assert "BASELINE_CAPTURE" in orchestrator
    assert "CUSTOM_AGENT_ROUTING = FALLBACK_SERIAL" in orchestrator
    assert "generic subagent" in orchestrator

    ui_quality = (
        ROOT / ".agents/skills/ai-auto-test-platform-ui-quality/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "BASELINE_CAPTURE" in ui_quality
    assert "POST_CHANGE_VERIFY" in ui_quality
    assert "PRE_CHANGE_BASELINE = CAPTURED" in ui_quality


def test_frontend_uses_context_and_business_ui_gates() -> None:
    frontend = (
        ROOT / ".agents/skills/ai-auto-test-platform-frontend/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "$ai-auto-test-platform-context-efficiency" in frontend
    assert "$ai-auto-test-platform-business-ui-ux" in frontend
    assert "Element Plus 是组件库，不是信息架构" in frontend
    assert "PRE_CHANGE_BASELINE" in frontend
    assert "Post-change Impact Closure" in frontend



def test_impact_scan_covers_root_engineering_files_and_optional_github(tmp_path: Path) -> None:
    policy = tmp_path / ".agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(
        """version: 3
search_scope:
  required_roots:
    - package.json
    - pyproject.toml
    - .env.example
    - apps
    - docs/baseline/CURRENT
  optional_roots:
    - .github
    - db
  governance_roots:
    - .agents
    - .codex
""",
        encoding="utf-8",
    )
    (tmp_path / "docs/baseline/R1").mkdir(parents=True)
    (tmp_path / "docs/baseline/CURRENT").write_text("R1\n", encoding="utf-8")
    (tmp_path / "apps").mkdir()
    (tmp_path / "package.json").write_text('{"packageManager":"needle"}\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('line-length = "needle"\n', encoding="utf-8")
    (tmp_path / ".env.example").write_text("TOKEN=needle\n", encoding="utf-8")
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("name: needle\n", encoding="utf-8")

    payload = _run_scanner(tmp_path)
    paths = {item["path"] for item in payload["results"]}
    assert {"package.json", "pyproject.toml", ".env.example", ".github/workflows/ci.yml"} <= paths
    assert "db" in payload["scope"]["missing_optional_roots"]
    assert payload["scope"]["missing_required_roots"] == []
    assert payload["scope"]["closure_safe"] is True
    assert payload["_returncode"] == 0


def test_impact_scan_fails_closed_when_required_scope_or_current_is_missing(tmp_path: Path) -> None:
    _write_fake_policy(tmp_path)
    (tmp_path / "docs/baseline").mkdir(parents=True)
    (tmp_path / "docs/baseline/CURRENT").write_text("R404\n", encoding="utf-8")
    # apps and R404 are both missing: this must not look like a successful scan.
    payload = _run_scanner(tmp_path, check=False)
    assert payload["_returncode"] != 0
    assert payload["scope"]["scope_status"] == "INCOMPLETE"
    assert payload["scope"]["closure_safe"] is False
    assert "apps" in payload["scope"]["missing_required_roots"]
    assert "docs/baseline/R404" in payload["scope"]["missing_required_roots"]


def test_governance_roots_are_conditionally_expanded(tmp_path: Path) -> None:
    _write_fake_policy(tmp_path)
    (tmp_path / "docs/baseline/R1").mkdir(parents=True)
    (tmp_path / "docs/baseline/CURRENT").write_text("R1\n", encoding="utf-8")
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps/main.py").write_text("needle = 'business'\n", encoding="utf-8")
    # Policy itself exists under .agents and contains needle only in this test file.
    governance_file = tmp_path / ".agents/roles/example.md"
    governance_file.parent.mkdir(parents=True, exist_ok=True)
    governance_file.write_text("needle governance\n", encoding="utf-8")
    codex_file = tmp_path / ".codex/agents/example.toml"
    codex_file.parent.mkdir(parents=True, exist_ok=True)
    codex_file.write_text('description = "needle"\n', encoding="utf-8")

    normal = _run_scanner(tmp_path)
    normal_paths = {item["path"] for item in normal["results"]}
    assert "apps/main.py" in normal_paths
    assert ".agents/roles/example.md" not in normal_paths
    assert ".codex/agents/example.toml" not in normal_paths
    assert normal["scope"]["include_governance"] is False

    expanded = _run_scanner(tmp_path, "--include-governance")
    expanded_paths = {item["path"] for item in expanded["results"]}
    assert ".agents/roles/example.md" in expanded_paths
    assert ".codex/agents/example.toml" in expanded_paths
    assert expanded["scope"]["include_governance"] is True


def test_ui_high_environment_fallback_is_explicit() -> None:
    business = (ROOT / ".agents/skills/ai-auto-test-platform-business-ui-ux/SKILL.md").read_text(encoding="utf-8")
    ui_quality = (ROOT / ".agents/skills/ai-auto-test-platform-ui-quality/SKILL.md").read_text(encoding="utf-8")
    orchestrator = (ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md").read_text(encoding="utf-8")
    for token in (
        "PRE_CHANGE_BASELINE = BLOCKED_BY_ENVIRONMENT",
        "SOURCE_BASED_CURRENT_UI_BASELINE",
        "VISUAL_BASELINE_CONFIDENCE = LIMITED",
        "POST_CHANGE_BROWSER_VERIFY = REQUIRED",
    ):
        assert token in business
        assert token in ui_quality or token in orchestrator


def _write_full_minimum_scope(repo: Path) -> None:
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
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for relative in (
        "apps",
        "services",
        "workers",
        "runner",
        "packages",
        "tests",
        "tools",
        "docs/baseline/R4.2",
    ):
        (repo / relative).mkdir(parents=True, exist_ok=True)


def test_git_metadata_unavailable_never_claims_closure_safe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_full_minimum_scope(repo)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)

    import os

    env = os.environ.copy()
    env["PATH"] = ""
    for risk, required in (("LOCAL", False), ("CROSS_MODULE", True)):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCANNER),
                "packageManager",
                "--root",
                str(repo),
                "--risk",
                risk,
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        payload = json.loads(completed.stdout)
        assert completed.returncode == 2
        assert payload["scope"]["scope_status"] == "COMPLETE"
        assert payload["scope"]["closure_safe"] is False
        assert "git_metadata_unavailable" in payload["scope"]["closure_blockers"]
        assert payload["git_workspace"]["status"] == "UNAVAILABLE"
        assert payload["git_workspace"]["repository_present"] is True
        assert payload["git_workspace"]["required_by_task_risk"] is required
        assert payload["git_workspace"]["required_for_closure"] is True
        assert payload["git_workspace"]["blocking_for_closure"] is True
        assert payload["git_workspace"]["read_error"]


def test_no_git_repository_is_explicitly_not_applicable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_full_minimum_scope(repo)
    payload = _run_scanner(repo, term="packageManager")
    assert payload["git_workspace"]["status"] == "NOT_APPLICABLE"
    assert payload["git_workspace"]["repository_present"] is False
    assert payload["git_workspace"]["required_by_task_risk"] is False
    assert payload["git_workspace"]["required_for_closure"] is False
    assert payload["git_workspace"]["blocking_for_closure"] is False
    assert payload["scope"]["closure_safe"] is True


def test_workspace_snapshot_attributes_only_changes_since_task_start(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Contract Test",
            "-c",
            "user.email=contract@example.invalid",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )

    # Dirty state that predates the task.
    tracked.write_text("dirty-before-task\n", encoding="utf-8")
    old_untracked = repo / "old-untracked.txt"
    old_untracked.write_text("preexisting\n", encoding="utf-8")

    start_path = tmp_path / "task-start.json"
    start = subprocess.run(
        [
            sys.executable,
            str(snapshot_script),
            "capture",
            "--root",
            str(repo),
            "--out",
            str(start_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    start_payload = json.loads(start.stdout)
    assert start_payload["snapshot_version"] == 2
    assert start_payload["git_workspace"]["status"] == "COMPLETE"
    assert start_payload["repository_identity"]["identity_digest"]
    assert "tracked.txt" in start_payload["changed_paths"]
    assert "old-untracked.txt" in start_payload["untracked_paths"]

    # Current task changes an already-dirty tracked file and creates one new file.
    tracked.write_text("changed-by-current-task\n", encoding="utf-8")
    (repo / "new-task-file.txt").write_text("new\n", encoding="utf-8")

    delta = subprocess.run(
        [
            sys.executable,
            str(snapshot_script),
            "delta",
            "--root",
            str(repo),
            "--start",
            str(start_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(delta.stdout)
    task_delta = payload["task_delta"]
    assert task_delta["status"] == "CHANGED"
    assert "tracked.txt" in task_delta["categories"]["changed_paths"]["modified_since_start"]
    assert "new-task-file.txt" in task_delta["categories"]["untracked_paths"]["added"]
    assert "old-untracked.txt" not in task_delta["task_delta_paths"]
    assert {"tracked.txt", "new-task-file.txt"} <= set(task_delta["task_delta_paths"])


def test_task_context_pack_contains_task_start_current_and_task_delta() -> None:
    text = (CONTEXT_SKILL / "references/task-context-pack.md").read_text(encoding="utf-8")
    for token in (
        "task_start:",
        "snapshot_ref:",
        "current:",
        "task_delta:",
        "task_delta_paths:",
        "workspace_snapshot.py",
        "git_workspace_status: COMPLETE | NOT_APPLICABLE | UNAVAILABLE",
        "snapshot_version: 2",
        "repository_identity_digest:",
        "required_by_task_risk",
        "required_for_closure",
        "blocking_for_closure",
    ):
        assert token in text



def _init_snapshot_repo(repo: Path, content: str = "clean\n") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.name=Contract Test",
            "-c", "user.email=contract@example.invalid",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )


def test_workspace_snapshot_rejects_different_repository_root(tmp_path: Path) -> None:
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    _init_snapshot_repo(repo_a, "a\n")
    _init_snapshot_repo(repo_b, "b\n")
    start_path = tmp_path / "task-start-a.json"
    subprocess.run(
        [sys.executable, str(snapshot_script), "capture", "--root", str(repo_a), "--out", str(start_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [sys.executable, str(snapshot_script), "delta", "--root", str(repo_b), "--start", str(start_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["task_delta"]["status"] == "UNAVAILABLE"
    assert payload["task_delta"]["reason_code"] == "SNAPSHOT_ROOT_MISMATCH"
    assert payload["task_delta"]["task_delta_paths"] == []


def test_workspace_snapshot_rejects_unsupported_snapshot_version(tmp_path: Path) -> None:
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    repo = tmp_path / "repo"
    _init_snapshot_repo(repo)
    start_path = tmp_path / "task-start.json"
    subprocess.run(
        [sys.executable, str(snapshot_script), "capture", "--root", str(repo), "--out", str(start_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    start = json.loads(start_path.read_text(encoding="utf-8"))
    start["snapshot_version"] = 999
    start_path.write_text(json.dumps(start), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(snapshot_script), "delta", "--root", str(repo), "--start", str(start_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["task_delta"]["status"] == "UNAVAILABLE"
    assert payload["task_delta"]["reason_code"] == "SNAPSHOT_VERSION_MISMATCH"


def test_workspace_snapshot_rejects_replaced_repository_at_same_root(tmp_path: Path) -> None:
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    repo = tmp_path / "repo"
    _init_snapshot_repo(repo, "first\n")
    start_path = tmp_path / "task-start.json"
    subprocess.run(
        [sys.executable, str(snapshot_script), "capture", "--root", str(repo), "--out", str(start_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    git_dir = repo / ".git"
    backup = tmp_path / "old-git"
    git_dir.rename(backup)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)

    completed = subprocess.run(
        [sys.executable, str(snapshot_script), "delta", "--root", str(repo), "--start", str(start_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["task_delta"]["status"] == "UNAVAILABLE"
    assert payload["task_delta"]["reason_code"] == "SNAPSHOT_REPOSITORY_MISMATCH"



def _sha256_bytes(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_workspace_snapshot_preserves_real_git_index_bytes(tmp_path: Path) -> None:
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    repo = tmp_path / "repo"
    _init_snapshot_repo(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("dirty\n", encoding="utf-8")
    index_path_text = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "index"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    index_path = Path(index_path_text)
    if not index_path.is_absolute():
        index_path = (repo / index_path).resolve()
    before = _sha256_bytes(index_path)
    start_path = tmp_path / "task-start.json"
    subprocess.run(
        [sys.executable, str(snapshot_script), "capture", "--root", str(repo), "--out", str(start_path)],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        [sys.executable, str(snapshot_script), "delta", "--root", str(repo), "--start", str(start_path)],
        check=True, capture_output=True, text=True,
    )
    after = _sha256_bytes(index_path)
    assert after == before


def test_workspace_snapshot_rejects_artifact_output_inside_workspace(tmp_path: Path) -> None:
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    repo = tmp_path / "repo"
    _init_snapshot_repo(repo)
    forbidden = repo / "task-start.json"
    completed = subprocess.run(
        [sys.executable, str(snapshot_script), "capture", "--root", str(repo), "--out", str(forbidden)],
        check=False, capture_output=True, text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["status"] == "UNAVAILABLE"
    assert payload["reason_code"] == "SNAPSHOT_OUTPUT_INSIDE_WORKSPACE"
    assert not forbidden.exists()


def test_workspace_delta_rejects_output_inside_workspace(tmp_path: Path) -> None:
    snapshot_script = CONTEXT_SKILL / "scripts/workspace_snapshot.py"
    repo = tmp_path / "repo"
    _init_snapshot_repo(repo)
    start_path = tmp_path / "task-start.json"
    subprocess.run(
        [sys.executable, str(snapshot_script), "capture", "--root", str(repo), "--out", str(start_path)],
        check=True, capture_output=True, text=True,
    )
    forbidden = repo / "task-delta.json"
    completed = subprocess.run(
        [sys.executable, str(snapshot_script), "delta", "--root", str(repo), "--start", str(start_path), "--out", str(forbidden)],
        check=False, capture_output=True, text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["task_delta"]["reason_code"] == "SNAPSHOT_OUTPUT_INSIDE_WORKSPACE"
    assert not forbidden.exists()
