#!/usr/bin/env python3
"""Task-level stage checkpoint and validated-resume helper.

The checkpoint is the task-lifecycle fact store. Authority write coordination binds a
Guard-owned sequential transaction history to this checkpoint so CP-6 can mechanically distinguish
"never used Authority write" from a failed/abandoned transaction without caller claims.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 5
ATTESTATION_SCHEMA_VERSION = 2
COMMENT_GATE_ATTESTATION_SCHEMA_VERSION = 1
CANONICAL_AUTHORITY_ROOT = "docs/authority"
LIFECYCLE_PROFILES = {"FULL", "LIGHTWEIGHT_LOCAL"}
STAGES = [
    "TASK_INITIALIZED",
    "CONTEXT_READY",
    "DECISIONS_READY",
    "IMPLEMENTATION_READY",
    "IMPLEMENTATION_COMPLETE",
    "VERIFICATION_COMPLETE",
    "CLOSURE_COMPLETE",
]
AUTHORITY_TERMINAL_STATUSES = {"CLOSURE_COMPLETE", "TASK_ABORTED", "TASK_ABANDONED"}
IGNORED_AUTHORITY_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXIT_INVALID = 2
EXIT_REJECTED = 3
EXIT_CORRUPTED = 4
_WORKSPACE_SNAPSHOT_MODULE: Any | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolved(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _canonical_authority_root(root: Path, value: str) -> Path:
    canonical = (root / CANONICAL_AUTHORITY_ROOT).resolve()
    requested = (root / value).resolve()
    if requested != canonical:
        raise ValueError("AUTHORITY_ROOT_OVERRIDE_FORBIDDEN")
    return canonical


def _workspace_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:24]


def _authority_write_lock(root: Path) -> Path:
    return Path(tempfile.gettempdir()) / "ai-auto-test-platform" / "authority-write-locks" / f"{_workspace_id(root)}.lock.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_digest(authority_root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted((p for p in authority_root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        rel_path = path.relative_to(authority_root)
        if any(part in IGNORED_AUTHORITY_PARTS for part in rel_path.parts) or path.suffix == ".pyc":
            continue
        hasher.update(rel_path.as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(_sha256_file(path).encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _workspace_snapshot_module() -> Any:
    global _WORKSPACE_SNAPSHOT_MODULE
    if _WORKSPACE_SNAPSHOT_MODULE is not None:
        return _WORKSPACE_SNAPSHOT_MODULE
    path = (
        Path(__file__).resolve().parents[2]
        / "ai-auto-test-platform-context-efficiency"
        / "scripts"
        / "workspace_snapshot.py"
    )
    spec = importlib.util.spec_from_file_location("_task_checkpoint_workspace_snapshot", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("WORKSPACE_SNAPSHOT_PROVIDER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _WORKSPACE_SNAPSHOT_MODULE = module
    return module


def _capture_current_facts(root: Path) -> tuple[dict[str, Any], str, str]:
    module = _workspace_snapshot_module()
    snapshot = module.capture_workspace(root)
    valid, reason = module.validate_snapshot_evidence(snapshot)
    if not valid:
        raise RuntimeError(reason or "WORKSPACE_SNAPSHOT_INVALID")
    workspace_digest = str(snapshot.get("workspace_digest"))
    authority_digest = _authority_digest((root / CANONICAL_AUTHORITY_ROOT).resolve())
    return snapshot, workspace_digest, authority_digest


def _mechanical_stage_evidence(user_evidence: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(user_evidence)
    evidence["mechanical_workspace_snapshot"] = {
        "snapshot_version": snapshot.get("snapshot_version"),
        "snapshot_evidence_digest": snapshot.get("snapshot_evidence_digest"),
        "workspace_digest": snapshot.get("workspace_digest"),
        "change_scope_provenance": snapshot.get("change_scope_provenance"),
    }
    return evidence


def _canonical_payload(data: dict[str, Any]) -> bytes:
    payload = {k: v for k, v in data.items() if k != "checksum"}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _checksum(data: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(data)).hexdigest()


def _seal(data: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(data)
    sealed["checksum"] = _checksum(sealed)
    return sealed


def _verify_checksum(data: dict[str, Any]) -> bool:
    return isinstance(data.get("checksum"), str) and data["checksum"] == _checksum(data)


def _attestation_checksum(data: dict[str, Any]) -> str:
    payload = {k: v for k, v in data.items() if k != "checksum"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _seal_attestation(data: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(data)
    sealed["checksum"] = _attestation_checksum(sealed)
    return sealed


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _fail(code: str, message: str, exit_code: int) -> int:
    _emit({"status": code, "message": message})
    return exit_code


def _validate_checkpoint_path(root: Path, path: Path) -> tuple[bool, str | None]:
    if _is_within(path, root):
        return False, "CHECKPOINT_INSIDE_WORKSPACE"
    return True, None


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    tmp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _stage_record(
    stage: str,
    workspace_fingerprint: str,
    authority_digest: str,
    pack_revision: int,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "COMPLETED",
        "completed_at": _utc_now(),
        "workspace_fingerprint": workspace_fingerprint,
        "authority_digest": authority_digest,
        "pack_revision": pack_revision,
        "evidence": evidence or {},
    }


def _parse_evidence(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("evidence JSON must be an object")
    return parsed


def _base_identity(args: argparse.Namespace) -> dict[str, Any]:
    root = _resolved(args.root)
    _canonical_authority_root(root, args.authority_root)
    return {
        "workspace_root": str(root),
        "workspace_identity": args.workspace_identity,
        "authority_root": CANONICAL_AUTHORITY_ROOT,
        "git_access": "DISABLED",
    }


def cmd_init(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    _canonical_authority_root(root, args.authority_root)
    out = _resolved(args.out)
    ok, error = _validate_checkpoint_path(root, out)
    if not ok:
        return _fail(error or "CHECKPOINT_PATH_INVALID", "checkpoint must be outside workspace", EXIT_INVALID)
    if getattr(args, "force", False):
        return _fail("CHECKPOINT_FORCE_RESET_FORBIDDEN", "existing Task checkpoint audit history is immutable; create a new task_id/checkpoint instead", EXIT_REJECTED)
    if out.exists():
        return _fail("CHECKPOINT_ALREADY_EXISTS", "checkpoint already exists and cannot be reset", EXIT_REJECTED)
    if args.pack_revision < 0:
        return _fail("PACK_REVISION_INVALID", "pack_revision must be non-negative", EXIT_INVALID)
    snapshot, workspace_digest, authority_digest = _capture_current_facts(root)
    now = _utc_now()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": args.task_id,
        **_base_identity(args),
        "lifecycle_profile": args.lifecycle_profile,
        "current_stage": "TASK_INITIALIZED",
        "authority_write": {"ever_used": False, "status": "NOT_USED", "active_transaction_id": None, "next_sequence": 1, "transactions": []},
        "code_quality": {"comment_gate": None},
        "stages": {
            "TASK_INITIALIZED": _stage_record(
                "TASK_INITIALIZED",
                workspace_digest,
                authority_digest,
                args.pack_revision,
                _mechanical_stage_evidence(_parse_evidence(args.evidence_json), snapshot),
            )
        },
        "created_at": now,
        "updated_at": now,
    }
    sealed = _seal(payload)
    _atomic_write(out, sealed)
    _emit({
        "status": "CHECKPOINT_CREATED",
        "checkpoint": str(out),
        "task_id": args.task_id,
        "current_stage": "TASK_INITIALIZED",
        "workspace_fingerprint": workspace_digest,
        "authority_digest": authority_digest,
        "checksum": sealed["checksum"],
    })
    return 0


def _load_valid_checkpoint(root: Path, path: Path) -> tuple[dict[str, Any] | None, int | None]:
    ok, error = _validate_checkpoint_path(root, path)
    if not ok:
        _fail(error or "CHECKPOINT_PATH_INVALID", "checkpoint must be outside workspace", EXIT_INVALID)
        return None, EXIT_INVALID
    if not path.is_file():
        _fail("CHECKPOINT_NOT_FOUND", "checkpoint does not exist", EXIT_REJECTED)
        return None, EXIT_REJECTED
    try:
        data = _load(path)
    except (OSError, json.JSONDecodeError) as exc:
        _fail("CHECKPOINT_CORRUPTED", f"cannot parse checkpoint: {exc}", EXIT_CORRUPTED)
        return None, EXIT_CORRUPTED
    if data.get("schema_version") != SCHEMA_VERSION or not _verify_checksum(data):
        _fail("CHECKPOINT_CORRUPTED", "schema/checksum validation failed", EXIT_CORRUPTED)
        return None, EXIT_CORRUPTED
    return data, None


def _validate_task_identity(root: Path, data: dict[str, Any], task_id: str) -> int | None:
    if data.get("task_id") != task_id:
        return _fail("TASK_ID_MISMATCH", "checkpoint belongs to another task", EXIT_REJECTED)
    if data.get("workspace_root") != str(root):
        return _fail("WORKSPACE_ROOT_MISMATCH", "checkpoint belongs to another workspace root", EXIT_REJECTED)
    return None


def _initial_snapshot_evidence_digest(data: dict[str, Any]) -> str | None:
    stages = data.get("stages")
    if not isinstance(stages, dict):
        return None
    initial = stages.get("TASK_INITIALIZED")
    if not isinstance(initial, dict):
        return None
    evidence = initial.get("evidence")
    if not isinstance(evidence, dict):
        return None
    mechanical = evidence.get("mechanical_workspace_snapshot")
    if not isinstance(mechanical, dict):
        return None
    value = mechanical.get("snapshot_evidence_digest")
    return value if isinstance(value, str) and value else None


def _comment_quality_gate_pass(args: argparse.Namespace) -> int:
    """Record a Comment Quality Gate PASS from the gate process itself.

    This is intentionally a private in-process mutation API. The public checkpoint CLI
    cannot manufacture Comment Gate evidence.
    """
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    identity_error = _validate_task_identity(root, data, args.task_id)
    if identity_error is not None:
        return identity_error
    expected_start = _initial_snapshot_evidence_digest(data)
    if not expected_start or expected_start != args.task_start_snapshot_evidence_digest:
        return _fail("COMMENT_GATE_TASK_START_MISMATCH", "Comment Gate task-start snapshot is not bound to CP-0", EXIT_REJECTED)
    _snapshot, actual_workspace, _authority = _capture_current_facts(root)
    if actual_workspace != args.workspace_fingerprint:
        return _fail("COMMENT_GATE_WORKSPACE_STALE", "workspace changed before Comment Gate attestation could be sealed", EXIT_REJECTED)
    code_quality = data.get("code_quality")
    if not isinstance(code_quality, dict):
        return _fail("CHECKPOINT_CORRUPTED", "code_quality record is invalid", EXIT_CORRUPTED)
    attestation = _seal_attestation({
        "schema_version": COMMENT_GATE_ATTESTATION_SCHEMA_VERSION,
        "gate": "CHANGED_COMPLEX_SYMBOL_COMMENT_GATE",
        "status": "PASS",
        "task_id": args.task_id,
        "task_start_snapshot_evidence_digest": args.task_start_snapshot_evidence_digest,
        "workspace_fingerprint": args.workspace_fingerprint,
        "current_snapshot_evidence_digest": args.current_snapshot_evidence_digest,
        "task_delta_digest": args.task_delta_digest,
        "change_scope_digest": args.change_scope_digest,
        "task_delta_status": args.task_delta_status,
        "finding_count": 0,
        "completed_at": _utc_now(),
        "generated_by": "comment_quality_gate",
    })
    code_quality["comment_gate"] = attestation
    data["code_quality"] = code_quality
    data["updated_at"] = _utc_now()
    sealed = _seal(data)
    _atomic_write(checkpoint, sealed)
    _emit({"status": "COMMENT_GATE_ATTESTED", "task_id": args.task_id, "workspace_fingerprint": args.workspace_fingerprint, "attestation_checksum": attestation["checksum"]})
    return 0


def _validate_comment_gate_for_current_workspace(data: dict[str, Any], workspace_digest: str) -> tuple[bool, str | None, dict[str, Any]]:
    code_quality = data.get("code_quality")
    if not isinstance(code_quality, dict):
        return False, "COMMENT_GATE_ATTESTATION_MISSING", {}
    attestation = code_quality.get("comment_gate")
    if not isinstance(attestation, dict):
        return False, "COMMENT_GATE_ATTESTATION_MISSING", {}
    if attestation.get("checksum") != _attestation_checksum(attestation):
        return False, "COMMENT_GATE_ATTESTATION_CORRUPTED", {}
    if attestation.get("schema_version") != COMMENT_GATE_ATTESTATION_SCHEMA_VERSION:
        return False, "COMMENT_GATE_ATTESTATION_SCHEMA_MISMATCH", {}
    if attestation.get("generated_by") != "comment_quality_gate" or attestation.get("status") != "PASS":
        return False, "COMMENT_GATE_ATTESTATION_INVALID", {}
    if attestation.get("task_id") != data.get("task_id"):
        return False, "COMMENT_GATE_ATTESTATION_TASK_MISMATCH", {}
    expected_start = _initial_snapshot_evidence_digest(data)
    if not expected_start or attestation.get("task_start_snapshot_evidence_digest") != expected_start:
        return False, "COMMENT_GATE_ATTESTATION_TASK_START_MISMATCH", {}
    if attestation.get("workspace_fingerprint") != workspace_digest:
        return False, "COMMENT_GATE_WORKSPACE_CHANGED_AFTER_PASS", {
            "attested_workspace_fingerprint": attestation.get("workspace_fingerprint"),
            "current_workspace_fingerprint": workspace_digest,
        }
    return True, None, {
        "status": "COMMENT_GATE_PASS",
        "attestation_checksum": attestation.get("checksum"),
        "workspace_fingerprint": workspace_digest,
        "task_delta_digest": attestation.get("task_delta_digest"),
        "change_scope_digest": attestation.get("change_scope_digest"),
    }


def _authority_transactions(activity: dict[str, Any]) -> list[dict[str, Any]]:
    transactions = activity.get("transactions")
    if not isinstance(transactions, list) or not all(isinstance(item, dict) for item in transactions):
        raise ValueError("AUTHORITY_TRANSACTION_HISTORY_CORRUPTED")
    return transactions


def _find_authority_transaction(activity: dict[str, Any], transaction_id: str) -> dict[str, Any] | None:
    for item in _authority_transactions(activity):
        if item.get("transaction_id") == transaction_id:
            return item
    return None


def _guard_authority_begin(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    identity_error = _validate_task_identity(root, data, args.task_id)
    if identity_error is not None:
        return identity_error
    if data.get("current_stage") == "CLOSURE_COMPLETE":
        return _fail("TASK_ALREADY_COMPLETE", "completed task cannot start an Authority transaction", EXIT_REJECTED)
    if data.get("lifecycle_profile", "FULL") != "FULL":
        return _fail(
            "AUTHORITY_TRANSACTION_REQUIRES_FULL_CHECKPOINT",
            "Authority transactions require FULL lifecycle; promote LIGHTWEIGHT_LOCAL before acquiring the Authority mutex",
            EXIT_REJECTED,
        )
    _canonical_authority_root(root, args.authority_root)
    if data.get("authority_root") != CANONICAL_AUTHORITY_ROOT:
        return _fail("AUTHORITY_ROOT_MISMATCH", "Task checkpoint must use the fixed docs/authority root", EXIT_REJECTED)
    state_dir = _resolved(args.state_dir)
    if _is_within(state_dir, root):
        return _fail("AUTHORITY_WRITE_STATE_DIR_INVALID", "Authority state directory must be outside workspace", EXIT_INVALID)
    activity = data.get("authority_write")
    if not isinstance(activity, dict):
        return _fail("CHECKPOINT_CORRUPTED", "authority_write record is invalid", EXIT_CORRUPTED)
    try:
        transactions = _authority_transactions(activity)
    except ValueError as exc:
        return _fail("CHECKPOINT_CORRUPTED", str(exc), EXIT_CORRUPTED)

    active_id = activity.get("active_transaction_id")
    if active_id:
        active = _find_authority_transaction(activity, str(active_id))
        same = bool(
            active
            and active.get("transaction_id") == args.transaction_id
            and active.get("status") == "ACTIVE"
            and active.get("authority_root") == CANONICAL_AUTHORITY_ROOT
            and active.get("canonical_state_dir") == str(state_dir)
            and active.get("authority_digest_at_acquire") == args.authority_digest_at_acquire
        )
        if same:
            _emit({"status": "AUTHORITY_TRANSACTION_RESUMED", "transaction_id": args.transaction_id, "sequence": active.get("sequence"), "checkpoint": str(checkpoint)})
            return 0
        return _fail(
            "AUTHORITY_TRANSACTION_ACTIVE",
            "another Authority transaction is already active for this Task; finish/recover it before opening the next sequential transaction",
            EXIT_REJECTED,
        )
    if _find_authority_transaction(activity, args.transaction_id) is not None:
        return _fail("AUTHORITY_TRANSACTION_ID_REUSED", "Authority transaction_id must be unique within the Task", EXIT_REJECTED)

    sequence = activity.get("next_sequence", 1)
    if not isinstance(sequence, int) or sequence < 1:
        return _fail("CHECKPOINT_CORRUPTED", "authority_write.next_sequence is invalid", EXIT_CORRUPTED)
    record = {
        "sequence": sequence,
        "transaction_id": args.transaction_id,
        "status": "ACTIVE",
        "authority_root": CANONICAL_AUTHORITY_ROOT,
        "canonical_state_dir": str(state_dir),
        "authority_digest_at_acquire": args.authority_digest_at_acquire,
        "started_at": _utc_now(),
        "generated_by": "authority_write_guard",
    }
    transactions.append(record)
    activity = dict(activity)
    activity.update({
        "ever_used": True,
        "status": "ACTIVE",
        "active_transaction_id": args.transaction_id,
        "next_sequence": sequence + 1,
        "transactions": transactions,
    })
    data["authority_write"] = activity
    data["updated_at"] = _utc_now()
    sealed = _seal(data)
    _atomic_write(checkpoint, sealed)
    _emit({"status": "AUTHORITY_TRANSACTION_RECORDED", "transaction_id": args.transaction_id, "sequence": sequence, "checkpoint": str(checkpoint), "checksum": sealed["checksum"]})
    return 0


def _guard_authority_terminal(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    identity_error = _validate_task_identity(root, data, args.task_id)
    if identity_error is not None:
        return identity_error
    activity = data.get("authority_write")
    if not isinstance(activity, dict) or not activity.get("ever_used"):
        return _fail("AUTHORITY_TRANSACTION_NOT_RECORDED", "Authority terminal state requires a Guard-recorded transaction", EXIT_REJECTED)
    try:
        transactions = _authority_transactions(activity)
    except ValueError as exc:
        return _fail("CHECKPOINT_CORRUPTED", str(exc), EXIT_CORRUPTED)
    transaction = _find_authority_transaction(activity, args.transaction_id)
    if transaction is None:
        return _fail("AUTHORITY_TRANSACTION_ID_MISMATCH", "terminal update does not match a recorded Authority transaction", EXIT_REJECTED)
    if transaction.get("canonical_state_dir") != str(_resolved(args.state_dir)):
        return _fail("AUTHORITY_WRITE_STATE_DIR_MISMATCH", "terminal update must use the recorded Authority state directory", EXIT_REJECTED)
    if args.final_status not in AUTHORITY_TERMINAL_STATUSES:
        return _fail("AUTHORITY_TERMINAL_STATUS_INVALID", "invalid Authority terminal status", EXIT_INVALID)
    if transaction.get("status") in AUTHORITY_TERMINAL_STATUSES:
        attestation = transaction.get("closure_attestation", {})
        if transaction.get("status") == args.final_status and isinstance(attestation, dict) and attestation.get("transaction_id") == args.transaction_id:
            _emit({"status": "AUTHORITY_TRANSACTION_TERMINAL_ALREADY_RECORDED", "transaction_id": args.transaction_id, "final_status": args.final_status})
            return 0
        return _fail("AUTHORITY_TRANSACTION_ALREADY_TERMINAL", "Authority transaction already has a different terminal state", EXIT_REJECTED)
    if activity.get("active_transaction_id") != args.transaction_id or transaction.get("status") != "ACTIVE":
        return _fail("AUTHORITY_TRANSACTION_STATE_INVALID", "only the currently ACTIVE Authority transaction may be terminalized", EXIT_REJECTED)
    if args.final_status == "CLOSURE_COMPLETE":
        if not args.closure_authority_digest:
            return _fail("AUTHORITY_CLOSURE_DIGEST_REQUIRED", "successful Authority closure requires the final Authority digest", EXIT_INVALID)
        if args.had_change_set and args.validated_authority_digest != args.closure_authority_digest:
            return _fail("AUTHORITY_CLOSURE_ATTESTATION_DIGEST_MISMATCH", "validated and closure Authority digests must match for a changed Authority", EXIT_REJECTED)
        if not args.had_change_set and transaction.get("authority_digest_at_acquire") != args.closure_authority_digest:
            return _fail("AUTHORITY_EXTERNAL_CHANGE_DURING_TRANSACTION", "a no-change Authority transaction may close only when the current digest equals the acquire digest", EXIT_REJECTED)
    attestation = _seal_attestation({
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "generated_by": "authority_write_guard",
        "task_id": args.task_id,
        "workspace_root": str(root),
        "workspace_identity": _workspace_id(root),
        "authority_root": transaction.get("authority_root"),
        "transaction_id": args.transaction_id,
        "sequence": transaction.get("sequence"),
        "canonical_state_dir": transaction.get("canonical_state_dir"),
        "authority_digest_at_acquire": transaction.get("authority_digest_at_acquire"),
        "final_status": args.final_status,
        "had_change_set": bool(args.had_change_set),
        "operation_count": int(args.operation_count),
        "validated_authority_digest": args.validated_authority_digest or None,
        "closure_authority_digest": args.closure_authority_digest or None,
        "created_at": _utc_now(),
    })
    transaction.update({
        "status": args.final_status,
        "completed_at": _utc_now(),
        "closure_attestation": attestation,
    })
    activity = dict(activity)
    activity.update({
        "status": args.final_status,
        "active_transaction_id": None,
        "last_transaction_id": args.transaction_id,
        "transactions": transactions,
    })
    if args.final_status == "CLOSURE_COMPLETE":
        activity["last_successful_transaction_id"] = args.transaction_id
    data["authority_write"] = activity
    data["updated_at"] = _utc_now()
    sealed = _seal(data)
    _atomic_write(checkpoint, sealed)
    _emit({
        "status": "AUTHORITY_TRANSACTION_TERMINAL_RECORDED",
        "transaction_id": args.transaction_id,
        "sequence": transaction.get("sequence"),
        "final_status": args.final_status,
        "attestation_checksum": attestation["checksum"],
        "checkpoint": str(checkpoint),
    })
    return 0


def _validate_authority_cleanup_before_closure(
    root: Path,
    task_id: str,
    checkpoint_data: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any]]:
    lock = _authority_write_lock(root)
    if lock.exists():
        return False, "AUTHORITY_WRITE_CLEANUP_REQUIRED", {}
    authority_root_value = str(checkpoint_data.get("authority_root", CANONICAL_AUTHORITY_ROOT))
    try:
        authority_root = _canonical_authority_root(root, authority_root_value)
    except ValueError as exc:
        return False, str(exc), {}
    actual_digest = _authority_digest(authority_root)
    activity = checkpoint_data.get("authority_write")
    if not isinstance(activity, dict):
        return False, "CHECKPOINT_CORRUPTED", {}
    if not activity.get("ever_used"):
        return True, None, {"status": "AUTHORITY_WRITE_NOT_USED", "transaction_count": 0, "current_authority_digest": actual_digest}
    try:
        transactions = _authority_transactions(activity)
    except ValueError:
        return False, "CHECKPOINT_CORRUPTED", {}
    if activity.get("active_transaction_id"):
        return False, "AUTHORITY_TRANSACTION_ACTIVE", {"active_transaction_id": activity.get("active_transaction_id")}
    if not transactions:
        return False, "AUTHORITY_TRANSACTION_HISTORY_CORRUPTED", {}

    successful: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for transaction in transactions:
        status = transaction.get("status")
        if status not in AUTHORITY_TERMINAL_STATUSES:
            return False, "AUTHORITY_TRANSACTION_NOT_TERMINAL", {"authority_transaction_id": transaction.get("transaction_id"), "authority_transaction_status": status}
        transaction_id = transaction.get("transaction_id")
        attestation = transaction.get("closure_attestation")
        if not isinstance(transaction_id, str) or not transaction_id or not isinstance(attestation, dict):
            return False, "AUTHORITY_CLOSURE_ATTESTATION_CORRUPTED", {}
        if attestation.get("schema_version") != ATTESTATION_SCHEMA_VERSION or attestation.get("generated_by") != "authority_write_guard":
            return False, "AUTHORITY_CLOSURE_ATTESTATION_CORRUPTED", {}
        if not isinstance(attestation.get("checksum"), str) or attestation.get("checksum") != _attestation_checksum(attestation):
            return False, "AUTHORITY_CLOSURE_ATTESTATION_CORRUPTED", {}
        expected_identity = {
            "task_id": task_id,
            "workspace_root": str(root),
            "workspace_identity": _workspace_id(root),
            "authority_root": authority_root_value,
            "transaction_id": transaction_id,
            "sequence": transaction.get("sequence"),
            "final_status": status,
        }
        if any(attestation.get(key) != expected for key, expected in expected_identity.items()):
            return False, "AUTHORITY_CLOSURE_ATTESTATION_IDENTITY_MISMATCH", {"authority_transaction_id": transaction_id}
        state_dir_value = attestation.get("canonical_state_dir")
        if not isinstance(state_dir_value, str) or not state_dir_value:
            return False, "AUTHORITY_CLOSURE_ATTESTATION_CORRUPTED", {}
        state_dir = _resolved(state_dir_value)
        if _is_within(state_dir, root):
            return False, "AUTHORITY_WRITE_STATE_DIR_INVALID", {}
        if state_dir.exists():
            return False, "AUTHORITY_WRITE_EPHEMERAL_STATE_SURVIVES", {"authority_transaction_id": transaction_id}
        closure_digest = attestation.get("closure_authority_digest")
        acquire_digest = attestation.get("authority_digest_at_acquire")
        if not isinstance(acquire_digest, str) or not acquire_digest:
            return False, "AUTHORITY_CLOSURE_ATTESTATION_CORRUPTED", {}
        if status == "CLOSURE_COMPLETE":
            if not isinstance(closure_digest, str) or not closure_digest:
                return False, "AUTHORITY_CLOSURE_ATTESTATION_CORRUPTED", {}
            if attestation.get("had_change_set") and attestation.get("validated_authority_digest") != closure_digest:
                return False, "AUTHORITY_CLOSURE_ATTESTATION_VALIDATION_MISMATCH", {"authority_transaction_id": transaction_id}
            if not attestation.get("had_change_set") and acquire_digest != closure_digest:
                return False, "AUTHORITY_EXTERNAL_CHANGE_DURING_TRANSACTION", {"authority_transaction_id": transaction_id}
            successful.append(transaction)
        summaries.append({
            "sequence": transaction.get("sequence"),
            "authority_transaction_id": transaction_id,
            "status": status,
            "attestation_checksum": attestation.get("checksum"),
            "had_change_set": bool(attestation.get("had_change_set")),
            "operation_count": int(attestation.get("operation_count", 0)),
            "closure_authority_digest": closure_digest,
        })

    if not successful:
        return False, "AUTHORITY_NO_SUCCESSFUL_TRANSACTION", {"transaction_count": len(transactions)}
    latest = transactions[-1]
    if latest.get("status") != "CLOSURE_COMPLETE":
        return False, "AUTHORITY_LATEST_TRANSACTION_NOT_SUCCESSFUL", {
            "last_transaction_id": latest.get("transaction_id"),
            "last_transaction_status": latest.get("status"),
            "last_successful_transaction_id": successful[-1].get("transaction_id"),
        }
    last_successful = successful[-1]
    derived_last_transaction_id = latest.get("transaction_id")
    derived_last_successful_transaction_id = last_successful.get("transaction_id")
    if derived_last_transaction_id != derived_last_successful_transaction_id:
        return False, "AUTHORITY_TRANSACTION_HISTORY_INCONSISTENT", {
            "last_transaction_id": derived_last_transaction_id,
            "last_successful_transaction_id": derived_last_successful_transaction_id,
        }
    if activity.get("last_transaction_id") != derived_last_transaction_id:
        return False, "AUTHORITY_TRANSACTION_SUMMARY_INCONSISTENT", {
            "summary_last_transaction_id": activity.get("last_transaction_id"),
            "derived_last_transaction_id": derived_last_transaction_id,
        }
    if activity.get("last_successful_transaction_id") != derived_last_successful_transaction_id:
        return False, "AUTHORITY_TRANSACTION_SUMMARY_INCONSISTENT", {
            "summary_last_successful_transaction_id": activity.get("last_successful_transaction_id"),
            "derived_last_successful_transaction_id": derived_last_successful_transaction_id,
        }
    last_attestation = last_successful["closure_attestation"]
    closure_digest = last_attestation.get("closure_authority_digest")
    if closure_digest != actual_digest:
        return False, "AUTHORITY_CLOSURE_ATTESTATION_DIGEST_MISMATCH", {
            "last_successful_transaction_id": last_successful.get("transaction_id"),
            "attested_authority_digest": closure_digest,
            "current_authority_digest": actual_digest,
        }
    evidence = {
        "status": "AUTHORITY_TRANSACTIONS_CLOSED",
        "transaction_count": len(transactions),
        "successful_transaction_count": len(successful),
        "last_successful_transaction_id": last_successful.get("transaction_id"),
        "last_successful_attestation_checksum": last_attestation.get("checksum"),
        "closure_authority_digest": closure_digest,
        "current_authority_digest": actual_digest,
        "transactions": summaries,
    }
    return True, None, evidence


def cmd_promote_local_to_full(args: argparse.Namespace) -> int:
    """Promote a LOCAL evidence anchor to the FULL lifecycle without losing CP-0 facts."""
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    identity_error = _validate_task_identity(root, data, args.task_id)
    if identity_error is not None:
        return identity_error
    if data.get("lifecycle_profile") == "FULL":
        _emit({"status": "CHECKPOINT_ALREADY_FULL", "checkpoint": str(checkpoint), "task_id": args.task_id})
        return 0
    if data.get("lifecycle_profile") != "LIGHTWEIGHT_LOCAL":
        return _fail("CHECKPOINT_LIFECYCLE_PROFILE_INVALID", "unsupported lifecycle profile", EXIT_CORRUPTED)
    if data.get("current_stage") != "TASK_INITIALIZED":
        return _fail("LOCAL_PROMOTION_STAGE_INVALID", "LIGHTWEIGHT_LOCAL may be promoted only from CP-0 TASK_INITIALIZED", EXIT_REJECTED)
    if data.get("local_completion"):
        return _fail("LOCAL_TASK_ALREADY_COMPLETE", "finalized LOCAL task cannot be promoted; create a new Task", EXIT_REJECTED)
    activity = data.get("authority_write", {})
    if not isinstance(activity, dict) or activity.get("ever_used"):
        return _fail("LOCAL_PROMOTION_AUTHORITY_STATE_INVALID", "LOCAL promotion requires an unused Authority transaction history", EXIT_REJECTED)
    snapshot, workspace_digest, authority_digest = _capture_current_facts(root)
    promotions = data.get("lifecycle_promotions", [])
    if not isinstance(promotions, list):
        return _fail("CHECKPOINT_CORRUPTED", "lifecycle_promotions is invalid", EXIT_CORRUPTED)
    promotions.append({
        "from": "LIGHTWEIGHT_LOCAL",
        "to": "FULL",
        "promoted_at": _utc_now(),
        "workspace_fingerprint": workspace_digest,
        "authority_digest": authority_digest,
        "mechanical_workspace_snapshot": _mechanical_stage_evidence({}, snapshot)["mechanical_workspace_snapshot"],
    })
    data["lifecycle_profile"] = "FULL"
    data["lifecycle_promotions"] = promotions
    data["updated_at"] = _utc_now()
    sealed = _seal(data)
    _atomic_write(checkpoint, sealed)
    _emit({
        "status": "LIGHTWEIGHT_LOCAL_PROMOTED_TO_FULL",
        "checkpoint": str(checkpoint),
        "task_id": args.task_id,
        "current_stage": data.get("current_stage"),
        "workspace_fingerprint": workspace_digest,
        "authority_digest": authority_digest,
        "checksum": sealed["checksum"],
    })
    return 0


def cmd_local_complete(args: argparse.Namespace) -> int:
    """Finalize a lightweight LOCAL evidence lifecycle without inventing CP-1..CP-6."""
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    identity_error = _validate_task_identity(root, data, args.task_id)
    if identity_error is not None:
        return identity_error
    if data.get("lifecycle_profile") != "LIGHTWEIGHT_LOCAL":
        return _fail("LOCAL_COMPLETE_REQUIRES_LIGHTWEIGHT_LOCAL", "local-complete applies only to LIGHTWEIGHT_LOCAL", EXIT_REJECTED)
    if data.get("current_stage") != "TASK_INITIALIZED":
        return _fail("LOCAL_COMPLETE_STAGE_INVALID", "LIGHTWEIGHT_LOCAL completion must remain anchored at CP-0", EXIT_REJECTED)
    activity = data.get("authority_write", {})
    if not isinstance(activity, dict) or activity.get("ever_used"):
        return _fail("LOCAL_COMPLETE_AUTHORITY_STATE_INVALID", "LIGHTWEIGHT_LOCAL cannot complete with Authority transaction history", EXIT_REJECTED)
    if data.get("local_completion"):
        _emit({"status": "LOCAL_EVIDENCE_ALREADY_COMPLETE", "checkpoint": str(checkpoint), "task_id": args.task_id})
        return 0
    snapshot, workspace_digest, authority_digest = _capture_current_facts(root)
    gate_ok, gate_reason, gate_evidence = _validate_comment_gate_for_current_workspace(data, workspace_digest)
    if not gate_ok:
        return _fail(gate_reason or "COMMENT_GATE_REQUIRED", "LIGHTWEIGHT_LOCAL completion requires a current Comment Quality Gate PASS", EXIT_REJECTED)
    data["local_completion"] = {
        "status": "LOCAL_EVIDENCE_COMPLETE",
        "completed_at": _utc_now(),
        "workspace_fingerprint": workspace_digest,
        "authority_digest": authority_digest,
        "evidence": {**_mechanical_stage_evidence(_parse_evidence(args.evidence_json), snapshot), "comment_quality_gate": gate_evidence},
    }
    data["updated_at"] = _utc_now()
    sealed = _seal(data)
    _atomic_write(checkpoint, sealed)
    _emit({
        "status": "LOCAL_EVIDENCE_COMPLETE",
        "checkpoint": str(checkpoint),
        "task_id": args.task_id,
        "workspace_fingerprint": workspace_digest,
        "authority_digest": authority_digest,
        "checksum": sealed["checksum"],
    })
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    identity_error = _validate_task_identity(root, data, args.task_id)
    if identity_error is not None:
        return identity_error
    if data.get("lifecycle_profile", "FULL") == "LIGHTWEIGHT_LOCAL":
        return _fail("LIGHTWEIGHT_LOCAL_STAGE_CHAIN_NOT_APPLICABLE", "LIGHTWEIGHT_LOCAL uses CP-0 only as a mechanical evidence anchor and does not run the full CP-0→CP-6 stage chain", EXIT_REJECTED)
    current = data.get("current_stage")
    if current not in STAGES:
        return _fail("CHECKPOINT_CORRUPTED", "unknown current stage", EXIT_CORRUPTED)
    current_index = STAGES.index(current)
    if current_index == len(STAGES) - 1:
        return _fail("TASK_ALREADY_COMPLETE", "closure checkpoint is already complete", EXIT_REJECTED)
    expected = STAGES[current_index + 1]
    if args.stage != expected:
        return _fail("INVALID_STAGE_TRANSITION", f"expected next stage {expected}, got {args.stage}", EXIT_REJECTED)
    previous_record = data.get("stages", {}).get(current, {})
    previous_revision = previous_record.get("pack_revision")
    if not isinstance(previous_revision, int):
        return _fail("CHECKPOINT_CORRUPTED", "current stage pack_revision is invalid", EXIT_CORRUPTED)
    if args.pack_revision < previous_revision:
        return _fail("PACK_REVISION_REGRESSION", f"pack_revision cannot decrease from {previous_revision} to {args.pack_revision}", EXIT_REJECTED)

    snapshot, workspace_digest, authority_digest = _capture_current_facts(root)

    stage_evidence = _mechanical_stage_evidence(_parse_evidence(args.evidence_json), snapshot)
    if args.stage == "VERIFICATION_COMPLETE":
        gate_ok, gate_reason, gate_evidence = _validate_comment_gate_for_current_workspace(data, workspace_digest)
        if not gate_ok:
            return _fail(gate_reason or "COMMENT_GATE_REQUIRED", "Verification requires a current Comment Quality Gate PASS bound to this workspace", EXIT_REJECTED)
        stage_evidence["comment_quality_gate"] = gate_evidence
    if args.stage == "CLOSURE_COMPLETE":
        verification = data.get("stages", {}).get("VERIFICATION_COMPLETE", {})
        verified_workspace = verification.get("workspace_fingerprint")
        if not isinstance(verified_workspace, str) or not verified_workspace:
            return _fail("VERIFICATION_WORKSPACE_FINGERPRINT_MISSING", "CP-6 requires the mechanically captured CP-5 workspace fingerprint", EXIT_CORRUPTED)
        if workspace_digest != verified_workspace:
            return _fail(
                "WORKSPACE_CHANGED_AFTER_VERIFICATION",
                "current workspace changed after CP-5; Verification must be rerun before CLOSURE_COMPLETE",
                EXIT_REJECTED,
            )
        gate_ok, gate_reason, gate_evidence = _validate_comment_gate_for_current_workspace(data, workspace_digest)
        if not gate_ok:
            return _fail(gate_reason or "COMMENT_GATE_REQUIRED", "Closure requires the same current Comment Quality Gate PASS used for Verification", EXIT_REJECTED)
        stage_evidence["comment_quality_gate"] = gate_evidence
        ok, reason, authority_evidence = _validate_authority_cleanup_before_closure(root, args.task_id, data)
        if not ok:
            details = authority_evidence if authority_evidence else None
            message = "Authority write transaction must prove successful cleanup and current Authority identity before CP-6 CLOSURE_COMPLETE"
            if details:
                message += f"; details={json.dumps(details, ensure_ascii=False, sort_keys=True)}"
            return _fail(reason or "AUTHORITY_WRITE_CLEANUP_REQUIRED", message, EXIT_REJECTED)
        stage_evidence["authority_write"] = authority_evidence

    data["stages"][args.stage] = _stage_record(
        args.stage,
        workspace_digest,
        authority_digest,
        args.pack_revision,
        stage_evidence,
    )
    data["current_stage"] = args.stage
    data["updated_at"] = _utc_now()
    sealed = _seal(data)
    _atomic_write(checkpoint, sealed)
    _emit({
        "status": "CHECKPOINT_ADVANCED",
        "checkpoint": str(checkpoint),
        "task_id": args.task_id,
        "current_stage": args.stage,
        "workspace_fingerprint": workspace_digest,
        "authority_digest": authority_digest,
        "pack_revision": args.pack_revision,
        "checksum": sealed["checksum"],
        "active_authority_transaction_id": data.get("authority_write", {}).get("active_transaction_id"),
        "last_authority_transaction_id": data.get("authority_write", {}).get("last_transaction_id"),
    })
    return 0


def cmd_resume_validate(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    _canonical_authority_root(root, args.authority_root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED

    expected_identity = {
        "workspace_root": str(root),
        "workspace_identity": args.workspace_identity,
        "authority_root": CANONICAL_AUTHORITY_ROOT,
    }
    mismatches = [key for key, expected in expected_identity.items() if data.get(key) != expected]
    if data.get("task_id") != args.task_id:
        mismatches.append("task_id")
    if mismatches:
        _emit({
            "status": "RESUME_REJECTED",
            "reason_code": "RESUME_IDENTITY_MISMATCH",
            "mismatches": sorted(set(mismatches)),
            "current_stage": data.get("current_stage"),
            "full_impact_scan_allowed": False,
        })
        return EXIT_REJECTED

    _snapshot, actual_workspace_fingerprint, actual_authority_digest = _capture_current_facts(root)
    current_stage = data["current_stage"]
    if data.get("lifecycle_profile", "FULL") == "LIGHTWEIGHT_LOCAL":
        initial = data.get("stages", {}).get("TASK_INITIALIZED", {})
        checkpoint_fingerprint = initial.get("workspace_fingerprint")
        checkpoint_authority_digest = initial.get("authority_digest")
        workspace_exact = checkpoint_fingerprint == actual_workspace_fingerprint
        authority_exact = checkpoint_authority_digest == actual_authority_digest
        completion = data.get("local_completion")
        if isinstance(completion, dict):
            complete_exact = (
                completion.get("workspace_fingerprint") == actual_workspace_fingerprint
                and completion.get("authority_digest") == actual_authority_digest
            )
            _emit({
                "status": "LOCAL_TASK_ALREADY_COMPLETE" if complete_exact else "LOCAL_TASK_COMPLETE_WORKSPACE_DRIFT",
                "resume_status": "LOCAL_COMPLETE" if complete_exact else "LOCAL_COMPLETE_DRIFT",
                "current_stage": "TASK_INITIALIZED",
                "next_stage": None,
                "current_workspace_fingerprint": actual_workspace_fingerprint,
                "current_authority_digest": actual_authority_digest,
                "required_action": "NONE" if complete_exact else "CREATE_NEW_TASK_FOR_POST_COMPLETION_CHANGES",
                "full_impact_scan_allowed": False,
            })
            return 0 if complete_exact else EXIT_REJECTED
        exact = workspace_exact and authority_exact
        _emit({
            "status": "LIGHTWEIGHT_LOCAL_RESUME_VALIDATED",
            "resume_status": "LOCAL_RESUME_EXACT" if exact else "LOCAL_RESUME_WITH_DELTA_REFRESH",
            "current_stage": "TASK_INITIALIZED",
            "next_stage": None,
            "checkpoint_workspace_fingerprint": checkpoint_fingerprint,
            "current_workspace_fingerprint": actual_workspace_fingerprint,
            "checkpoint_authority_digest": checkpoint_authority_digest,
            "current_authority_digest": actual_authority_digest,
            "authority_changed": not authority_exact,
            "full_impact_scan_allowed": False,
            "required_action": (
                "CONTINUE_LOCAL_COMMENT_GATE_THEN_LOCAL_COMPLETE_OR_PROMOTE_TO_FULL"
                if exact
                else "LOCAL_DELTA_REFRESH_THEN_COMMENT_GATE_OR_PROMOTE_TO_FULL"
            ),
        })
        return 0
    record = data["stages"].get(current_stage, {})
    checkpoint_fingerprint = record.get("workspace_fingerprint")
    checkpoint_authority_digest = record.get("authority_digest")
    workspace_exact = checkpoint_fingerprint == actual_workspace_fingerprint
    authority_exact = checkpoint_authority_digest == actual_authority_digest
    exact = workspace_exact and authority_exact

    if current_stage == "CLOSURE_COMPLETE":
        _emit({
            "status": "TASK_ALREADY_COMPLETE" if exact else "TASK_ALREADY_COMPLETE_CURRENT_WORKSPACE_ADVANCED",
            "resume_status": "RESUME_EXACT" if exact else "COMPLETED_TASK_WORKSPACE_DRIFT",
            "current_stage": current_stage,
            "next_stage": None,
            "checkpoint_workspace_fingerprint": checkpoint_fingerprint,
            "current_workspace_fingerprint": actual_workspace_fingerprint,
            "checkpoint_authority_digest": checkpoint_authority_digest,
            "current_authority_digest": actual_authority_digest,
            "authority_changed": not authority_exact,
            "required_action": "NONE" if exact else "CREATE_NEW_TASK_FOR_POST_COMPLETION_CHANGES",
            "full_impact_scan_allowed": False,
        })
        return 0

    next_stage = STAGES[STAGES.index(current_stage) + 1]
    if exact:
        resume_status = "RESUME_EXACT"
        required_action = "CONTINUE_NEXT_STAGE"
    else:
        resume_status = "RESUME_WITH_DELTA_REFRESH"
        required_action = (
            "AUTHORITY_DELTA_REFRESH_THEN_REVALIDATE_PRODUCT_AND_DOWNSTREAM"
            if not authority_exact
            else "DELTA_REFRESH_THEN_REVALIDATE_STAGE_INPUTS"
        )
    _emit({
        "status": "RESUME_VALIDATED",
        "resume_status": resume_status,
        "current_stage": current_stage,
        "next_stage": next_stage,
        "checkpoint_pack_revision": record.get("pack_revision"),
        "checkpoint_workspace_fingerprint": checkpoint_fingerprint,
        "current_workspace_fingerprint": actual_workspace_fingerprint,
        "checkpoint_authority_digest": checkpoint_authority_digest,
        "current_authority_digest": actual_authority_digest,
        "authority_changed": not authority_exact,
        "full_impact_scan_allowed": False,
        "required_action": required_action,
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Task-level stage checkpoint and validated resume helper")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create CP-0 TASK_INITIALIZED")
    init.add_argument("--root", required=True)
    init.add_argument("--out", required=True)
    init.add_argument("--task-id", required=True)
    init.add_argument("--workspace-identity", required=True)
    init.add_argument("--authority-root", default="docs/authority")
    init.add_argument("--authority-digest", help="deprecated compatibility input; ignored because mechanical current digest is authoritative")
    init.add_argument("--workspace-fingerprint", help="deprecated compatibility input; ignored because mechanical current workspace digest is authoritative")
    init.add_argument("--pack-revision", type=int, default=0)
    init.add_argument("--lifecycle-profile", choices=sorted(LIFECYCLE_PROFILES), default="FULL")
    init.add_argument("--evidence-json")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    advance = sub.add_parser("advance", help="atomically advance exactly one lifecycle stage")
    advance.add_argument("--root", required=True)
    advance.add_argument("--checkpoint", required=True)
    advance.add_argument("--task-id", required=True)
    advance.add_argument("--stage", choices=STAGES[1:], required=True)
    advance.add_argument("--workspace-fingerprint", help="deprecated compatibility input; ignored because mechanical current workspace digest is authoritative")
    advance.add_argument("--authority-digest", help="deprecated compatibility input; ignored because mechanical current digest is authoritative")
    advance.add_argument("--pack-revision", type=int, required=True)
    advance.add_argument("--evidence-json")
    advance.set_defaults(func=cmd_advance)

    promote = sub.add_parser("promote-local-to-full", help="promote a LIGHTWEIGHT_LOCAL CP-0 evidence anchor to FULL lifecycle")
    promote.add_argument("--root", required=True)
    promote.add_argument("--checkpoint", required=True)
    promote.add_argument("--task-id", required=True)
    promote.set_defaults(func=cmd_promote_local_to_full)

    local_complete = sub.add_parser("local-complete", help="finalize a LIGHTWEIGHT_LOCAL evidence lifecycle without CP-1..CP-6")
    local_complete.add_argument("--root", required=True)
    local_complete.add_argument("--checkpoint", required=True)
    local_complete.add_argument("--task-id", required=True)
    local_complete.add_argument("--evidence-json")
    local_complete.set_defaults(func=cmd_local_complete)

    resume = sub.add_parser("resume-validate", help="validate whether latest completed stage can be reused")
    resume.add_argument("--root", required=True)
    resume.add_argument("--checkpoint", required=True)
    resume.add_argument("--task-id", required=True)
    resume.add_argument("--workspace-identity", required=True)
    resume.add_argument("--authority-root", default="docs/authority")
    resume.add_argument("--current-authority-digest", help="deprecated compatibility input; ignored because resume recomputes current Authority digest")
    resume.add_argument("--current-workspace-fingerprint", help="deprecated compatibility input; ignored because resume recaptures current workspace")
    resume.set_defaults(func=cmd_resume_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (ValueError, TypeError) as exc:
        return _fail("INVALID_ARGUMENT", str(exc), EXIT_INVALID)


if __name__ == "__main__":
    raise SystemExit(main())
