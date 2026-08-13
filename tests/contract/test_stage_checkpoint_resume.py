from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORCH = ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator"
CONTEXT = ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency"
HELPER = ORCH / "scripts/task_checkpoint.py"


def _raw_run(*args: str):
    return subprocess.run([sys.executable, str(HELPER), *args], check=False, capture_output=True, text=True)


def _checkpoint_module():
    spec = importlib.util.spec_from_file_location("_stage_test_checkpoint", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _attest_comment_gate(repo: Path, checkpoint: Path) -> None:
    module = _checkpoint_module()
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    start = data["stages"]["TASK_INITIALIZED"]["evidence"]["mechanical_workspace_snapshot"]["snapshot_evidence_digest"]
    snapshot, workspace_digest, _ = module._capture_current_facts(repo)
    rc = module._comment_quality_gate_pass(argparse.Namespace(
        root=str(repo), checkpoint=str(checkpoint), task_id=data["task_id"],
        task_start_snapshot_evidence_digest=start,
        current_snapshot_evidence_digest=snapshot["snapshot_evidence_digest"],
        workspace_fingerprint=workspace_digest, task_delta_digest="TEST_DELTA",
        change_scope_digest="TEST_SCOPE", task_delta_status="CHANGED",
    ))
    assert rc == 0


def _run(*args: str):
    if args and args[0] == "advance" and "VERIFICATION_COMPLETE" in args:
        root = Path(args[args.index("--root") + 1])
        checkpoint = Path(args[args.index("--checkpoint") + 1])
        _attest_comment_gate(root, checkpoint)
    return _raw_run(*args)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs/authority").mkdir(parents=True)
    (repo / "docs/authority/rules.yaml").write_text("value: 1\n", encoding="utf-8")
    source = repo / "services/api/src/state.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    return repo


def _init(repo: Path, checkpoint: Path, *, workspace_identity: str = "workspace-1"):
    return _run(
        "init", "--root", str(repo), "--out", str(checkpoint), "--task-id", "TASK-RESUME-1",
        "--workspace-identity", workspace_identity, "--authority-root", "docs/authority", "--pack-revision", "0",
    )


def _advance(repo: Path, checkpoint: Path, stage: str, revision: int):
    return _run(
        "advance", "--root", str(repo), "--checkpoint", str(checkpoint), "--task-id", "TASK-RESUME-1",
        "--stage", stage, "--pack-revision", str(revision),
    )


def _resume(repo: Path, checkpoint: Path, *, workspace_identity: str = "workspace-1", authority_root: str = "docs/authority", extra: list[str] | None = None):
    args = [
        "resume-validate", "--root", str(repo), "--checkpoint", str(checkpoint), "--task-id", "TASK-RESUME-1",
        "--workspace-identity", workspace_identity, "--authority-root", authority_root,
    ]
    if extra:
        args.extend(extra)
    return _run(*args)


def test_checkpoint_must_be_outside_workspace(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = repo / "checkpoint.json"; c = _init(repo, cp)
    assert c.returncode == 2; assert json.loads(c.stdout)["status"] == "CHECKPOINT_INSIDE_WORKSPACE"; assert not cp.exists()


def test_checkpoint_is_atomic_checksummed_and_stage_progression_is_strict(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0
    data = json.loads(cp.read_text(encoding="utf-8")); assert data["schema_version"] == 5; assert data["current_stage"] == "TASK_INITIALIZED"; assert len(data["checksum"]) == 64
    assert data["git_access"] == "DISABLED"; assert data["authority_root"] == "docs/authority"
    mechanical = data["stages"]["TASK_INITIALIZED"]["evidence"]["mechanical_workspace_snapshot"]
    assert mechanical["workspace_digest"] == data["stages"]["TASK_INITIALIZED"]["workspace_fingerprint"]
    assert len(mechanical["snapshot_evidence_digest"]) == 64
    skipped = _advance(repo, cp, "DECISIONS_READY", 1); assert skipped.returncode == 3; assert json.loads(skipped.stdout)["status"] == "INVALID_STAGE_TRANSITION"


def test_resume_exact_reuses_latest_completed_stage(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0; assert _advance(repo, cp, "CONTEXT_READY", 1).returncode == 0
    payload = json.loads(_resume(repo, cp).stdout); assert payload["resume_status"] == "RESUME_EXACT"; assert payload["next_stage"] == "DECISIONS_READY"; assert payload["full_impact_scan_allowed"] is False


def test_workspace_change_uses_mechanical_delta_refresh_even_if_caller_replays_old_values(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0; assert _advance(repo, cp, "CONTEXT_READY", 1).returncode == 0
    recorded = json.loads(cp.read_text(encoding="utf-8"))["stages"]["CONTEXT_READY"]
    (repo / "services/api/src/state.py").write_text("VALUE = 2\n", encoding="utf-8")
    payload = json.loads(_resume(repo, cp, extra=["--current-workspace-fingerprint", recorded["workspace_fingerprint"], "--current-authority-digest", recorded["authority_digest"]]).stdout)
    assert payload["resume_status"] == "RESUME_WITH_DELTA_REFRESH"
    assert payload["current_workspace_fingerprint"] != recorded["workspace_fingerprint"]
    assert payload["required_action"] == "DELTA_REFRESH_THEN_REVALIDATE_STAGE_INPUTS"
    assert payload["full_impact_scan_allowed"] is False


def test_authority_change_uses_mechanical_delta_refresh_not_new_baseline(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0; assert _advance(repo, cp, "CONTEXT_READY", 1).returncode == 0
    (repo / "docs/authority/rules.yaml").write_text("value: 2\n", encoding="utf-8")
    payload = json.loads(_resume(repo, cp).stdout); assert payload["resume_status"] == "RESUME_WITH_DELTA_REFRESH"; assert payload["authority_changed"] is True; assert payload["required_action"] == "AUTHORITY_DELTA_REFRESH_THEN_REVALIDATE_PRODUCT_AND_DOWNSTREAM"; assert payload["full_impact_scan_allowed"] is False


def test_resume_rejected_on_workspace_identity_or_authority_root_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0
    c = _resume(repo, cp, workspace_identity="workspace-2"); assert c.returncode == 3; assert "workspace_identity" in json.loads(c.stdout)["mismatches"]
    c = _resume(repo, cp, authority_root="docs/other"); assert c.returncode == 2; assert json.loads(c.stdout)["status"] == "INVALID_ARGUMENT"; assert "AUTHORITY_ROOT_OVERRIDE_FORBIDDEN" in json.loads(c.stdout)["message"]


def test_corrupted_checkpoint_fails_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0
    data = json.loads(cp.read_text(encoding="utf-8")); data["current_stage"] = "CLOSURE_COMPLETE"; cp.write_text(json.dumps(data), encoding="utf-8")
    c = _resume(repo, cp); assert c.returncode == 4; assert json.loads(c.stdout)["status"] == "CHECKPOINT_CORRUPTED"


def test_implementation_complete_resumes_at_verification(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0
    for stage, rev in [("CONTEXT_READY", 1), ("DECISIONS_READY", 1), ("IMPLEMENTATION_READY", 1), ("IMPLEMENTATION_COMPLETE", 2)]:
        assert _advance(repo, cp, stage, rev).returncode == 0
    payload = json.loads(_resume(repo, cp).stdout); assert payload["resume_status"] == "RESUME_EXACT"; assert payload["next_stage"] == "VERIFICATION_COMPLETE"


def test_pack_revision_cannot_regress(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0
    assert _advance(repo, cp, "CONTEXT_READY", 3).returncode == 0
    rejected = _advance(repo, cp, "DECISIONS_READY", 2)
    assert rejected.returncode == 3
    assert json.loads(rejected.stdout)["status"] == "PACK_REVISION_REGRESSION"


def test_cp6_rejects_workspace_change_after_verification(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "checkpoint.json"; assert _init(repo, cp).returncode == 0
    for stage, rev in [("CONTEXT_READY", 1), ("DECISIONS_READY", 1), ("IMPLEMENTATION_READY", 1), ("IMPLEMENTATION_COMPLETE", 2), ("VERIFICATION_COMPLETE", 2)]:
        assert _advance(repo, cp, stage, rev).returncode == 0
    (repo / "services/api/src/state.py").write_text("VALUE = 999\n", encoding="utf-8")
    rejected = _advance(repo, cp, "CLOSURE_COMPLETE", 2)
    assert rejected.returncode == 3
    assert json.loads(rejected.stdout)["status"] == "WORKSPACE_CHANGED_AFTER_VERIFICATION"



def test_lightweight_local_checkpoint_is_cp0_evidence_anchor_not_full_stage_chain(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "local-checkpoint.json"
    created = _run(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-LOCAL-1",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
        "--pack-revision", "0", "--lifecycle-profile", "LIGHTWEIGHT_LOCAL",
    )
    assert created.returncode == 0, created.stdout + created.stderr
    data = json.loads(cp.read_text(encoding="utf-8"))
    assert data["lifecycle_profile"] == "LIGHTWEIGHT_LOCAL"
    assert data["current_stage"] == "TASK_INITIALIZED"
    assert data["stages"]["TASK_INITIALIZED"]["evidence"]["mechanical_workspace_snapshot"]["snapshot_evidence_digest"]
    rejected = _run(
        "advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-1",
        "--stage", "CONTEXT_READY", "--pack-revision", "1",
    )
    assert rejected.returncode == 3
    assert json.loads(rejected.stdout)["status"] == "LIGHTWEIGHT_LOCAL_STAGE_CHAIN_NOT_APPLICABLE"

def test_orchestrator_and_context_define_single_owner_and_validated_resume() -> None:
    orch = (ORCH / "SKILL.md").read_text(encoding="utf-8"); ref = (ORCH / "references/task-checkpoint-resume.md").read_text(encoding="utf-8"); context = (CONTEXT / "SKILL.md").read_text(encoding="utf-8"); pack = (CONTEXT / "references/task-context-pack.md").read_text(encoding="utf-8"); policy = (CONTEXT / "schemas/context-policy.yaml").read_text(encoding="utf-8")
    for token in ("TASK_LIFECYCLE_OWNER", "RESUME_EXACT", "RESUME_WITH_DELTA_REFRESH", "RESUME_REJECTED", "CHECKPOINT_CORRUPTED", "IMPLEMENTATION_COMPLETE", "禁止 Full Scan #2", "机械重算"):
        assert token in orch or token in ref
    assert "CONTEXT_STATE_PROVIDER" in context; assert "task_lifecycle:" in pack; assert "full_impact_scan_on_resume_allowed: false" in pack; assert "full_impact_scan_on_resume: forbidden" in policy; assert "per_agent_checkpoint_state: forbidden" in policy; assert "codex_git_access: DISABLED" in policy


def test_lightweight_local_resume_never_points_to_full_stage_chain(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "local-checkpoint.json"
    created = _run(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-LOCAL-RESUME",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
        "--pack-revision", "0", "--lifecycle-profile", "LIGHTWEIGHT_LOCAL",
    )
    assert created.returncode == 0
    resumed = _run(
        "resume-validate", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-RESUME",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
    )
    payload = json.loads(resumed.stdout)
    assert resumed.returncode == 0
    assert payload["status"] == "LIGHTWEIGHT_LOCAL_RESUME_VALIDATED"
    assert payload["next_stage"] is None
    assert "LOCAL" in payload["required_action"]


def test_lightweight_local_can_be_promoted_to_full_without_losing_cp0(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "local-promote.json"
    created = _run(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-LOCAL-PROMOTE",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
        "--pack-revision", "0", "--lifecycle-profile", "LIGHTWEIGHT_LOCAL",
    )
    assert created.returncode == 0
    before = json.loads(cp.read_text(encoding="utf-8"))
    cp0_digest = before["stages"]["TASK_INITIALIZED"]["workspace_fingerprint"]
    promoted = _run(
        "promote-local-to-full", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-PROMOTE",
    )
    assert promoted.returncode == 0, promoted.stdout + promoted.stderr
    after = json.loads(cp.read_text(encoding="utf-8"))
    assert after["lifecycle_profile"] == "FULL"
    assert after["current_stage"] == "TASK_INITIALIZED"
    assert after["stages"]["TASK_INITIALIZED"]["workspace_fingerprint"] == cp0_digest
    assert after["lifecycle_promotions"][-1]["from"] == "LIGHTWEIGHT_LOCAL"
    advanced = _run(
        "advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-PROMOTE",
        "--stage", "CONTEXT_READY", "--pack-revision", "1",
    )
    assert advanced.returncode == 0, advanced.stdout + advanced.stderr


def test_lightweight_local_has_explicit_terminal_evidence_without_cp1_to_cp6(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "local-complete.json"
    assert _run(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-LOCAL-COMPLETE",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
        "--pack-revision", "0", "--lifecycle-profile", "LIGHTWEIGHT_LOCAL",
    ).returncode == 0
    _attest_comment_gate(repo, cp)
    completed = _run(
        "local-complete", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-COMPLETE",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    data = json.loads(cp.read_text(encoding="utf-8"))
    assert data["current_stage"] == "TASK_INITIALIZED"
    assert data["local_completion"]["status"] == "LOCAL_EVIDENCE_COMPLETE"
    resumed = _run(
        "resume-validate", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-COMPLETE",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
    )
    payload = json.loads(resumed.stdout)
    assert resumed.returncode == 0
    assert payload["status"] == "LOCAL_TASK_ALREADY_COMPLETE"
    assert payload["next_stage"] is None


def test_local_complete_requires_comment_gate_attestation(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "local-gate-required.json"
    created = _raw_run(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-LOCAL-GATE",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority",
        "--pack-revision", "0", "--lifecycle-profile", "LIGHTWEIGHT_LOCAL",
    )
    assert created.returncode == 0
    blocked = _raw_run("local-complete", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-LOCAL-GATE")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "COMMENT_GATE_ATTESTATION_MISSING"


def test_full_verification_requires_current_comment_gate_and_rejects_post_gate_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "full-gate-required.json"
    assert _raw_run(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-FULL-GATE",
        "--workspace-identity", "workspace-1", "--authority-root", "docs/authority", "--pack-revision", "0",
    ).returncode == 0
    for stage in ("CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE"):
        assert _raw_run("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-FULL-GATE", "--stage", stage, "--pack-revision", "1").returncode == 0
    blocked = _raw_run("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-FULL-GATE", "--stage", "VERIFICATION_COMPLETE", "--pack-revision", "1")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "COMMENT_GATE_ATTESTATION_MISSING"
    _attest_comment_gate(repo, cp)
    (repo / "services/api/src/state.py").write_text("VALUE = 999\n", encoding="utf-8")
    stale = _raw_run("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-FULL-GATE", "--stage", "VERIFICATION_COMPLETE", "--pack-revision", "1")
    assert stale.returncode == 3
    assert json.loads(stale.stdout)["status"] == "COMMENT_GATE_WORKSPACE_CHANGED_AFTER_PASS"


def test_completed_full_task_resume_is_terminal_even_after_workspace_drift(tmp_path: Path) -> None:
    repo = _repo(tmp_path); cp = tmp_path / "completed-drift.json"
    assert _init(repo, cp).returncode == 0
    for stage, rev in [("CONTEXT_READY", 1), ("DECISIONS_READY", 1), ("IMPLEMENTATION_READY", 1), ("IMPLEMENTATION_COMPLETE", 1), ("VERIFICATION_COMPLETE", 1), ("CLOSURE_COMPLETE", 1)]:
        assert _advance(repo, cp, stage, rev).returncode == 0
    (repo / "services/api/src/state.py").write_text("VALUE = 42\n", encoding="utf-8")
    resumed = _resume(repo, cp)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    payload = json.loads(resumed.stdout)
    assert payload["status"] == "TASK_ALREADY_COMPLETE_CURRENT_WORKSPACE_ADVANCED"
    assert payload["resume_status"] == "COMPLETED_TASK_WORKSPACE_DRIFT"
    assert payload["next_stage"] is None
    assert payload["required_action"] == "CREATE_NEW_TASK_FOR_POST_COMPLETION_CHANGES"
