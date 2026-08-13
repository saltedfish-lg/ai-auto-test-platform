import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/scripts/authority_write_guard.py"
CHECKPOINT = ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/scripts/task_checkpoint.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(GUARD), *args], text=True, capture_output=True, check=False)


def _cp_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CHECKPOINT), *args], text=True, capture_output=True, check=False)


def _checkpoint_module():
    spec = importlib.util.spec_from_file_location("_authority_test_checkpoint", CHECKPOINT)
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


def _cp(*args: str) -> subprocess.CompletedProcess[str]:
    if args and args[0] == "advance" and "VERIFICATION_COMPLETE" in args:
        repo = Path(args[args.index("--root") + 1])
        checkpoint = Path(args[args.index("--checkpoint") + 1])
        _attest_comment_gate(repo, checkpoint)
    return _cp_raw(*args)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validator(path: Path, exit_code: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"import sys\nprint('PASS' if {exit_code} == 0 else 'FAIL')\nsys.exit({exit_code})\n", encoding="utf-8")


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    authority = repo / "docs/authority"
    authority.mkdir(parents=True)
    target = authority / "rules.yaml"
    target.write_text("value: old\n", encoding="utf-8")
    _validator(repo / "tools/verify_authority.py")
    canonical = ROOT / "tools/authority_validation.py"
    (repo / "tools/authority_validation.py").write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    _validator(authority / "validation/validate_governance.py")
    _validator(authority / "validation/validate_all.py")
    _validator(authority / "validation/validate_auth_contract.py")
    projection = repo / "tools/authority_projection.py"
    projection.parent.mkdir(parents=True, exist_ok=True)
    projection.write_text("import sys\nprint('PASS')\nsys.exit(0)\n", encoding="utf-8")
    current_facts = repo / "tools/current_facts.py"
    current_facts.write_text("import sys\nprint('CURRENT_FACTS_CONSISTENT')\nsys.exit(0)\n", encoding="utf-8")
    referential = repo / "tools/authority_referential_integrity.py"
    referential.write_text("import sys\nprint('AUTHORITY_REFERENTIAL_INTEGRITY_PASS')\nsys.exit(0)\n", encoding="utf-8")
    openapi = repo / "tools/openapi_client.py"
    openapi.parent.mkdir(parents=True, exist_ok=True)
    openapi.write_text("import sys\nprint('PASS')\nsys.exit(0)\n", encoding="utf-8")
    return repo, target


def _authority_digest(repo: Path) -> str:
    completed = _run("digest", "--root", str(repo), "--authority-root", "docs/authority")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)["authority_digest"]


def _checkpoint_path(repo: Path, task: str) -> Path:
    return repo.parent / f"{task}.checkpoint.json"


def _ensure_checkpoint(repo: Path, task: str, checkpoint: Path | None = None) -> Path:
    cp = checkpoint or _checkpoint_path(repo, task)
    if not cp.exists():
        digest = _authority_digest(repo)
        created = _cp(
            "init", "--root", str(repo), "--out", str(cp), "--task-id", task,
            "--workspace-identity", "wid", "--authority-root", "docs/authority",
            "--authority-digest", digest, "--workspace-fingerprint", "fp0", "--pack-revision", "0",
        )
        assert created.returncode == 0, created.stdout + created.stderr
    return cp


def _acquire(repo: Path, state: Path, task: str = "TASK-A", checkpoint: Path | None = None) -> subprocess.CompletedProcess[str]:
    cp = _ensure_checkpoint(repo, task, checkpoint)
    return _run("acquire", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--checkpoint", str(cp))


def _plan(repo: Path, target: Path, state: Path, replacement: Path, task: str = "TASK-A") -> subprocess.CompletedProcess[str]:
    change_set = state.parent / f"{task}-change.json"
    change_set.write_text(json.dumps({"operations": [{"path": "docs/authority/rules.yaml", "expected_sha256": _sha(target), "replacement_file": str(replacement), "sources": ["PRODUCT"]}]}), encoding="utf-8")
    return _run("plan", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--change-set", str(change_set))


def _validate(repo: Path, state: Path, task: str = "TASK-A") -> subprocess.CompletedProcess[str]:
    return _run("validate", "--root", str(repo), "--task-id", task, "--state-dir", str(state))


def _canonical_lock(repo: Path) -> Path:
    workspace_id = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / "ai-auto-test-platform" / "authority-write-locks" / f"{workspace_id}.lock.json"


def test_authority_runtime_state_must_be_outside_workspace(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    completed = _acquire(repo, repo / ".runtime/authority", "TASK-INSIDE")
    assert completed.returncode == 4
    assert "AUTHORITY_RUNTIME_STATE_INSIDE_WORKSPACE" in completed.stdout


def test_workspace_mutex_and_every_command_bind_to_canonical_state_dir(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state_a = tmp_path / "state-a"; state_b = tmp_path / "state-b"
    assert _acquire(repo, state_a, "TASK-A").returncode == 0
    assert _acquire(repo, state_b, "TASK-B").returncode == 3
    assert _acquire(repo, state_b, "TASK-A").returncode == 3
    wrong = _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state_b), "--final-status", "TASK_ABANDONED")
    assert wrong.returncode == 3 and "AUTHORITY_WRITE_STATE_DIR_MISMATCH" in wrong.stdout
    assert state_a.exists()
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state_a), "--final-status", "CLOSURE_COMPLETE").returncode == 0


def test_stale_expected_sha_and_duplicate_target_are_rejected(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: new\n", encoding="utf-8")
    assert _acquire(repo, state).returncode == 0
    change = tmp_path / "bad.json"; op = {"path": "docs/authority/rules.yaml", "expected_sha256": "0" * 64, "replacement_file": str(replacement)}; change.write_text(json.dumps({"operations": [op]}), encoding="utf-8")
    assert "AUTHORITY_STALE_WRITE_CONFLICT" in _run("plan", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--change-set", str(change)).stdout
    good_op = {"path": "docs/authority/rules.yaml", "expected_sha256": _sha(target), "replacement_file": str(replacement)}; change.write_text(json.dumps({"operations": [good_op, good_op]}), encoding="utf-8")
    assert "AUTHORITY_CHANGE_SET_DUPLICATE_TARGET" in _run("plan", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--change-set", str(change)).stdout
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 0


def test_caller_authored_validation_evidence_is_forbidden_and_guard_executes_validators(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: new\n", encoding="utf-8")
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0; assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0
    fake = tmp_path / "fake.json"; fake.write_text(json.dumps({"gates": {"verify_authority": "PASS", "validate_governance": "PASS", "validate_all": "PASS"}}), encoding="utf-8")
    rejected = _run("mark-validated", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--validator-evidence", str(fake))
    assert rejected.returncode == 3 and "CALLER_SUPPLIED_VALIDATION_EVIDENCE_FORBIDDEN" in rejected.stdout
    accepted = _validate(repo, state); assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    payload = json.loads(accepted.stdout); assert payload["status"] == "VALIDATED"; assert (state / "validator-evidence.json").is_file()
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 0


def test_guard_validation_fails_when_real_validator_fails(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: new\n", encoding="utf-8")
    _validator(repo / "docs/authority/validation/validate_governance.py", 7)
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0; assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0
    failed = _validate(repo, state); assert failed.returncode == 3 and "AUTHORITY_VALIDATION_NOT_PASSED" in failed.stdout
    assert json.loads((state / "write-state.json").read_text())["status"] == "APPLIED_PENDING_VALIDATION"
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0
    assert target.read_text(encoding="utf-8") == "value: old\n"


def test_planned_or_unvalidated_write_cannot_be_closed_complete(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: new\n", encoding="utf-8")
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 3
    assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 3
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0


def test_rollback_refuses_external_edit_and_validation_staleness_blocks_closure(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: guard\n", encoding="utf-8")
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0; assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0
    target.write_text("value: external\n", encoding="utf-8")
    abandoned = _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "TASK_ABANDONED")
    assert abandoned.returncode == 3 and "AUTHORITY_ROLLBACK_STALE_CONFLICT" in abandoned.stdout
    assert target.read_text(encoding="utf-8") == "value: external\n"


def test_validated_write_rejects_post_validation_edit_and_cleanup_is_ephemeral(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: validated\n", encoding="utf-8")
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0; assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0; assert _validate(repo, state).returncode == 0
    target.write_text("value: changed-after-validation\n", encoding="utf-8")
    blocked = _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE")
    assert blocked.returncode == 3 and "AUTHORITY_CLOSURE_STALE_VALIDATION_CONFLICT" in blocked.stdout


def test_crash_safe_orphan_lock_and_cleaning_recovery(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; lock = _canonical_lock(repo); lock.parent.mkdir(parents=True, exist_ok=True)
    owner = {"schema_version": 3, "task_id": "TASK-A", "workspace_root": str(repo.resolve()), "workspace_identity": "x", "authority_root": "docs/authority", "state_dir": str(state.resolve()), "status": "LOCKED", "ever_planned": False}
    lock.write_text(json.dumps(owner), encoding="utf-8")
    recovered = _run("recover", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)); assert recovered.returncode == 0; assert not lock.exists()
    # CLEANING is recoverable even if state was already deleted; mutex is finalized last.
    owner["status"] = "CLEANING"; owner["ever_planned"] = True; lock.write_text(json.dumps(owner), encoding="utf-8")
    recovered = _run("recover", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)); assert recovered.returncode == 0; assert not lock.exists()


def test_interrupted_applying_can_reconcile_and_continue_same_task(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: prepared\n", encoding="utf-8")
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0
    plan = json.loads((state / "change-set.json").read_text()); target.write_bytes(Path(plan["operations"][0]["prepared_file"]).read_bytes())
    st = json.loads((state / "write-state.json").read_text()); st["status"] = "APPLYING"; (state / "write-state.json").write_text(json.dumps(st), encoding="utf-8")
    lock = _canonical_lock(repo); owner = json.loads(lock.read_text()); owner["status"] = "APPLYING"; lock.write_text(json.dumps(owner), encoding="utf-8")
    reconciled = _run("reconcile", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--strategy", "continue")
    assert reconciled.returncode == 0 and json.loads(reconciled.stdout)["status"] == "APPLIED_PENDING_VALIDATION"
    assert _validate(repo, state).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 0


def test_cp6_requires_guard_terminal_attestation_and_current_digest(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; task = "TASK-CP6"; cp = _checkpoint_path(repo, task)
    assert _acquire(repo, state, task, cp).returncode == 0
    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        assert _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--workspace-fingerprint", f"fp{i}", "--authority-digest", "auth", "--pack-revision", str(i)).returncode == 0
    blocked = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "fp6", "--authority-digest", _authority_digest(repo), "--pack-revision", "6")
    assert blocked.returncode == 3 and json.loads(blocked.stdout)["status"] == "AUTHORITY_WRITE_CLEANUP_REQUIRED"
    cleaned = _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE")
    assert cleaned.returncode == 0
    cleaned_payload = json.loads(cleaned.stdout)
    transaction_id = cleaned_payload["authority_transaction_id"]
    cp_after_cleanup = json.loads(cp.read_text(encoding="utf-8"))
    activity = cp_after_cleanup["authority_write"]
    assert activity["status"] == "CLOSURE_COMPLETE"
    assert activity["active_transaction_id"] is None
    assert activity["last_successful_transaction_id"] == transaction_id
    tx = activity["transactions"][-1]
    assert tx["transaction_id"] == transaction_id
    assert tx["closure_attestation"]["closure_authority_digest"] == _authority_digest(repo)
    closed = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "caller-value-is-ignored", "--authority-digest", "caller-value-is-ignored", "--pack-revision", "6")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    payload = json.loads(closed.stdout); assert payload["last_authority_transaction_id"] == transaction_id
    cp_data = json.loads(cp.read_text(encoding="utf-8")); evidence = cp_data["stages"]["CLOSURE_COMPLETE"]["evidence"]["authority_write"]
    assert evidence["status"] == "AUTHORITY_TRANSACTIONS_CLOSED"
    assert evidence["transaction_count"] == 1
    assert evidence["last_successful_transaction_id"] == transaction_id
    assert "closure_receipt" not in cleaned_payload


def test_abandoned_authority_transaction_cannot_advance_cp6(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; task = "TASK-ABANDONED"; cp = _checkpoint_path(repo, task)
    assert _acquire(repo, state, task, cp).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0
    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        assert _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--workspace-fingerprint", f"fp{i}", "--authority-digest", "auth", "--pack-revision", str(i)).returncode == 0
    blocked = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "fp6", "--authority-digest", _authority_digest(repo), "--pack-revision", "6")
    assert blocked.returncode == 3 and json.loads(blocked.stdout)["status"] == "AUTHORITY_NO_SUCCESSFUL_TRANSACTION"


def test_cp6_mechanically_detects_authority_write_not_used(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); cp = tmp_path / "cp.json"; task = "TASK-NO-AUTHORITY"
    digest = _authority_digest(repo)
    assert _cp("init", "--root", str(repo), "--out", str(cp), "--task-id", task, "--workspace-identity", "wid", "--authority-root", "docs/authority", "--authority-digest", digest, "--workspace-fingerprint", "fp0", "--pack-revision", "0").returncode == 0
    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        assert _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--workspace-fingerprint", f"fp{i}", "--authority-digest", "auth", "--pack-revision", str(i)).returncode == 0
    closed = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "fp6", "--authority-digest", digest, "--pack-revision", "6")
    assert closed.returncode == 0
    cp_data = json.loads(cp.read_text(encoding="utf-8")); assert cp_data["stages"]["CLOSURE_COMPLETE"]["evidence"]["authority_write"]["status"] == "AUTHORITY_WRITE_NOT_USED"


def test_authority_write_not_used_is_checkpoint_fact_not_caller_cli_claim(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; task = "TASK-NOT-USED-BYPASS"; cp = _checkpoint_path(repo, task)
    assert _acquire(repo, state, task, cp).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0
    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        assert _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--workspace-fingerprint", f"fp{i}", "--authority-digest", _authority_digest(repo), "--pack-revision", str(i)).returncode == 0
    claimed = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "fp6", "--authority-digest", _authority_digest(repo), "--pack-revision", "6", "--authority-write-not-used")
    assert claimed.returncode == 2
    assert "unrecognized arguments: --authority-write-not-used" in claimed.stderr
    blocked = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "fp6", "--authority-digest", _authority_digest(repo), "--pack-revision", "6")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "AUTHORITY_NO_SUCCESSFUL_TRANSACTION"


def test_same_task_can_open_multiple_sequential_authority_transactions_but_only_one_active(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); task = "TASK-MULTI-TX"; cp = _checkpoint_path(repo, task); first = tmp_path / "state-1"; second = tmp_path / "state-2"
    first_acquire = _acquire(repo, first, task, cp); assert first_acquire.returncode == 0
    tx1 = json.loads(first_acquire.stdout)["authority_transaction_id"]
    concurrent = _acquire(repo, second, task, cp)
    assert concurrent.returncode == 3
    assert json.loads(concurrent.stdout)["error_code"] in {"AUTHORITY_WRITE_STATE_DIR_MISMATCH", "AUTHORITY_TRANSACTION_ACTIVE"}
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(first), "--final-status", "CLOSURE_COMPLETE").returncode == 0

    second_acquire = _acquire(repo, second, task, cp); assert second_acquire.returncode == 0, second_acquire.stdout + second_acquire.stderr
    tx2 = json.loads(second_acquire.stdout)["authority_transaction_id"]
    assert tx2 != tx1
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(second), "--final-status", "CLOSURE_COMPLETE").returncode == 0

    cp_data = json.loads(cp.read_text(encoding="utf-8"))
    activity = cp_data["authority_write"]
    assert activity["active_transaction_id"] is None
    assert activity["last_successful_transaction_id"] == tx2
    assert [tx["sequence"] for tx in activity["transactions"]] == [1, 2]
    assert [tx["status"] for tx in activity["transactions"]] == ["CLOSURE_COMPLETE", "CLOSURE_COMPLETE"]

    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        assert _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--pack-revision", str(i)).returncode == 0
    closed = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--pack-revision", "6")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    evidence = json.loads(cp.read_text(encoding="utf-8"))["stages"]["CLOSURE_COMPLETE"]["evidence"]["authority_write"]
    assert evidence["transaction_count"] == 2
    assert evidence["successful_transaction_count"] == 2
    assert evidence["last_successful_transaction_id"] == tx2


def test_cp6_recomputes_current_authority_digest_after_cleanup(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; task = "TASK-ACTUAL-DIGEST"; cp = _checkpoint_path(repo, task)
    assert _acquire(repo, state, task, cp).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 0
    attested = json.loads(cp.read_text(encoding="utf-8"))["authority_write"]["transactions"][-1]["closure_attestation"]["closure_authority_digest"]
    target.write_text("value: external-after-cleanup\n", encoding="utf-8")
    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        assert _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--workspace-fingerprint", f"fp{i}", "--authority-digest", attested, "--pack-revision", str(i)).returncode == 0
    blocked = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--workspace-fingerprint", "fp6", "--authority-digest", attested, "--pack-revision", "6")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "AUTHORITY_CLOSURE_ATTESTATION_DIGEST_MISMATCH"


def test_changed_authority_closure_attestation_binds_validated_digest(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: new\n", encoding="utf-8")
    task = "TASK-ATTESTATION"; cp = _checkpoint_path(repo, task)
    assert _acquire(repo, state, task, cp).returncode == 0
    assert _plan(repo, target, state, replacement, task).returncode == 0
    assert _run("apply", "--root", str(repo), "--task-id", task, "--state-dir", str(state)).returncode == 0
    assert _validate(repo, state, task).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 0
    attestation = json.loads(cp.read_text(encoding="utf-8"))["authority_write"]["transactions"][-1]["closure_attestation"]
    assert attestation["had_change_set"] is True
    assert attestation["validated_authority_digest"] == attestation["closure_authority_digest"] == _authority_digest(repo)


def test_guard_validation_includes_auth_contract_and_openapi_client(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; replacement = tmp_path / "replacement.yaml"; replacement.write_text("value: new\n", encoding="utf-8")
    _validator(repo / "docs/authority/validation/validate_auth_contract.py", 7)
    assert _acquire(repo, state).returncode == 0; assert _plan(repo, target, state, replacement).returncode == 0; assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0
    failed = _validate(repo, state); assert failed.returncode == 3; assert json.loads(failed.stdout)["failed_gate"] == "validate_auth_contract"
    assert _run("cleanup", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0

    repo2, target2 = _repo(tmp_path / "second"); state2 = tmp_path / "state2"; replacement2 = tmp_path / "replacement2.yaml"; replacement2.write_text("value: new\n", encoding="utf-8")
    _validator(repo2 / "tools/openapi_client.py", 9)
    assert _acquire(repo2, state2, "TASK-B").returncode == 0; assert _plan(repo2, target2, state2, replacement2, "TASK-B").returncode == 0; assert _run("apply", "--root", str(repo2), "--task-id", "TASK-B", "--state-dir", str(state2)).returncode == 0
    failed2 = _validate(repo2, state2, "TASK-B"); assert failed2.returncode == 3; assert json.loads(failed2.stdout)["failed_gate"] == "openapi_client_check"
    assert _run("cleanup", "--root", str(repo2), "--task-id", "TASK-B", "--state-dir", str(state2), "--final-status", "TASK_ABANDONED").returncode == 0


def test_corrupted_preparing_lock_can_be_safely_recovered(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; state.mkdir(parents=True)
    record = {
        "schema_version": 3, "task_id": "TASK-A", "workspace_root": str(repo.resolve()),
        "workspace_identity": "x", "authority_root": "docs/authority", "state_dir": str(state.resolve()),
        "status": "PREPARING_LOCK", "ever_planned": False,
    }
    (state / "write-state.json").write_text(json.dumps(record), encoding="utf-8")
    lock = _canonical_lock(repo); lock.parent.mkdir(parents=True, exist_ok=True); lock.write_bytes(b"")
    acquire = _acquire(repo, state); assert acquire.returncode == 3 and "AUTHORITY_WRITE_LOCK_CORRUPTED_RECOVER_REQUIRED" in acquire.stdout
    recovered = _run("recover", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state))
    assert recovered.returncode == 0 and "CORRUPTED_PREPARING_LOCK_RECOVERED" in recovered.stdout
    assert not lock.exists() and not state.exists()


def test_checkpoint_guard_internal_authority_mutations_are_not_public_cli(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); cp = _ensure_checkpoint(repo, "TASK-PRIVATE"); state = tmp_path / "state"
    begin = _cp("authority-begin", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-PRIVATE", "--transaction-id", "forged", "--authority-root", "docs/authority", "--state-dir", str(state))
    terminal = _cp("authority-terminal", "--root", str(repo), "--checkpoint", str(cp), "--task-id", "TASK-PRIVATE", "--transaction-id", "forged", "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE")
    assert begin.returncode == 2 and "invalid choice" in begin.stderr
    assert terminal.returncode == 2 and "invalid choice" in terminal.stderr
    activity = json.loads(cp.read_text(encoding="utf-8"))["authority_write"]
    assert activity == {"ever_used": False, "status": "NOT_USED", "active_transaction_id": None, "next_sequence": 1, "transactions": []}


def test_no_change_transaction_rejects_external_authority_change_without_validation(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path); state = tmp_path / "state"; task = "TASK-NO-CHANGE-EXTERNAL"; cp = _checkpoint_path(repo, task)
    acquired = _acquire(repo, state, task, cp); assert acquired.returncode == 0
    before = json.loads((state / "write-state.json").read_text(encoding="utf-8"))["authority_digest_at_acquire"]
    target.write_text("value: external-during-transaction\n", encoding="utf-8")
    assert _authority_digest(repo) != before
    blocked = _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["error_code"] == "AUTHORITY_EXTERNAL_CHANGE_DURING_TRANSACTION"
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0


def test_authority_root_is_physically_fixed_to_docs_authority(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); cp = _checkpoint_path(repo, "TASK-ROOT")
    digest = _authority_digest(repo)
    bad_cp = _cp("init", "--root", str(repo), "--out", str(cp), "--task-id", "TASK-ROOT", "--workspace-identity", "wid", "--authority-root", "docs", "--authority-digest", digest, "--workspace-fingerprint", "fp0", "--pack-revision", "0")
    assert bad_cp.returncode == 2 and json.loads(bad_cp.stdout)["status"] == "INVALID_ARGUMENT"
    assert "AUTHORITY_ROOT_OVERRIDE_FORBIDDEN" in json.loads(bad_cp.stdout)["message"]
    cp = _ensure_checkpoint(repo, "TASK-ROOT")
    bad_acquire = _run("acquire", "--root", str(repo), "--task-id", "TASK-ROOT", "--state-dir", str(tmp_path / "state"), "--checkpoint", str(cp), "--authority-root", "docs")
    assert bad_acquire.returncode == 4 and json.loads(bad_acquire.stdout)["error_code"] == "AUTHORITY_ROOT_OVERRIDE_FORBIDDEN"
    bad_digest = _run("digest", "--root", str(repo), "--authority-root", "docs")
    assert bad_digest.returncode == 4 and json.loads(bad_digest.stdout)["error_code"] == "AUTHORITY_ROOT_OVERRIDE_FORBIDDEN"


def test_checkpoint_force_cannot_erase_abandoned_authority_history(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; task = "TASK-IMMUTABLE-CP"; cp = _checkpoint_path(repo, task)
    assert _acquire(repo, state, task, cp).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "TASK_ABANDONED").returncode == 0
    before = cp.read_bytes()
    digest = _authority_digest(repo)
    reset = _cp("init", "--root", str(repo), "--out", str(cp), "--task-id", task, "--workspace-identity", "wid", "--authority-root", "docs/authority", "--authority-digest", digest, "--workspace-fingerprint", "reset", "--pack-revision", "0", "--force")
    assert reset.returncode == 3
    assert json.loads(reset.stdout)["status"] == "CHECKPOINT_FORCE_RESET_FORBIDDEN"
    assert cp.read_bytes() == before
    assert json.loads(cp.read_text(encoding="utf-8"))["authority_write"]["status"] == "TASK_ABANDONED"


def test_recover_removes_only_owned_orphan_lock_candidate(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path); state = tmp_path / "state"; lock = _canonical_lock(repo); lock.parent.mkdir(parents=True, exist_ok=True)
    owned = lock.parent / f"{lock.name}.owned.candidate"
    other = lock.parent / f"{lock.name}.other.candidate"
    owned.write_text(json.dumps({"task_id": "TASK-A", "workspace_root": str(repo.resolve()), "state_dir": str(state.resolve())}), encoding="utf-8")
    other.write_text(json.dumps({"task_id": "TASK-B", "workspace_root": str(repo.resolve()), "state_dir": str((tmp_path / 'other').resolve())}), encoding="utf-8")
    recovered = _run("recover", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state))
    assert recovered.returncode == 0
    payload = json.loads(recovered.stdout)
    assert payload["status"] == "ORPHAN_CANDIDATES_CLEANED"
    assert not owned.exists()
    assert other.exists()
    other.unlink()

def test_orchestrator_documents_execution_proven_validation_and_crash_recovery() -> None:
    ref = (ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/references/authority-write-coordination.md").read_text(encoding="utf-8")
    orch = (ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md").read_text(encoding="utf-8")
    for token in ("AUTHORITY_PHYSICAL_WRITE_OWNER", "authority_write_guard.py validate", "authority_transaction_id", "reconcile", "recover", "mutex", "MUST_NOT_SURVIVE_COMPLETED_TASK = true"):
        assert token in ref or token in orch


def test_lightweight_local_cannot_acquire_authority_until_promoted_to_full(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    task = "TASK-LOCAL-AUTHORITY"
    cp = _checkpoint_path(repo, task)
    created = _cp(
        "init", "--root", str(repo), "--out", str(cp), "--task-id", task,
        "--workspace-identity", "wid", "--authority-root", "docs/authority",
        "--pack-revision", "0", "--lifecycle-profile", "LIGHTWEIGHT_LOCAL",
    )
    assert created.returncode == 0, created.stdout + created.stderr
    state = tmp_path / "local-state"
    rejected = _run("acquire", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--checkpoint", str(cp))
    assert rejected.returncode == 3
    assert json.loads(rejected.stdout)["error_code"] == "AUTHORITY_TRANSACTION_REQUIRES_FULL_CHECKPOINT"
    assert not state.exists()

    promoted = _cp("promote-local-to-full", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task)
    assert promoted.returncode == 0, promoted.stdout + promoted.stderr
    acquired = _run("acquire", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--checkpoint", str(cp))
    assert acquired.returncode == 0, acquired.stdout + acquired.stderr
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(state), "--final-status", "CLOSURE_COMPLETE").returncode == 0


def test_cp6_rejects_when_latest_sequential_authority_transaction_failed(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    task = "TASK-LATEST-TX-FAILED"
    cp = _checkpoint_path(repo, task)
    first = tmp_path / "state-success"
    second = tmp_path / "state-abandoned"

    assert _acquire(repo, first, task, cp).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(first), "--final-status", "CLOSURE_COMPLETE").returncode == 0
    assert _acquire(repo, second, task, cp).returncode == 0
    assert _run("cleanup", "--root", str(repo), "--task-id", task, "--state-dir", str(second), "--final-status", "TASK_ABANDONED").returncode == 0

    for i, stage in enumerate(["CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE", "VERIFICATION_COMPLETE"], start=1):
        advanced = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", stage, "--pack-revision", str(i))
        assert advanced.returncode == 0, advanced.stdout + advanced.stderr
    blocked = _cp("advance", "--root", str(repo), "--checkpoint", str(cp), "--task-id", task, "--stage", "CLOSURE_COMPLETE", "--pack-revision", "6")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "AUTHORITY_LATEST_TRANSACTION_NOT_SUCCESSFUL"


def test_guard_validation_includes_authority_referential_integrity(tmp_path: Path) -> None:
    repo, target = _repo(tmp_path)
    state = tmp_path / "state"
    replacement = tmp_path / "replacement.yaml"
    replacement.write_text("value: new\n", encoding="utf-8")
    _validator(repo / "tools/authority_referential_integrity.py", 11)
    assert _acquire(repo, state).returncode == 0
    assert _plan(repo, target, state, replacement).returncode == 0
    assert _run("apply", "--root", str(repo), "--task-id", "TASK-A", "--state-dir", str(state)).returncode == 0
    failed = _validate(repo, state)
    assert failed.returncode == 3
    assert json.loads(failed.stdout)["failed_gate"] == "authority_referential_integrity"
    assert _run(
        "cleanup",
        "--root",
        str(repo),
        "--task-id",
        "TASK-A",
        "--state-dir",
        str(state),
        "--final-status",
        "TASK_ABANDONED",
    ).returncode == 0
