#!/usr/bin/env python3
"""Crash-safe single-writer guard for controlled Living Authority updates.

The guard owns the authority-write transaction lifecycle. It never trusts caller-authored
validator PASS evidence: `validate` executes the formal validators itself and binds the
result to the exact Authority digest. Runtime state stays outside the workspace and is
cleaned only after a terminal, validated/rolled-back transaction.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_POLICY = 2
EXIT_REJECTED = 3
EXIT_INVALID = 4
FINAL_STATUSES = {"CLOSURE_COMPLETE", "TASK_ABORTED", "TASK_ABANDONED"}
CANONICAL_AUTHORITY_ROOT = "docs/authority"
IGNORED_AUTHORITY_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _validator_commands(root: Path) -> dict[str, list[str]]:
    path = root / "tools" / "authority_validation.py"
    spec = importlib.util.spec_from_file_location("_authority_guard_validator_commands", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AUTHORITY_VALIDATOR_DEFINITION_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    commands = module.validator_commands()
    if not isinstance(commands, dict) or not commands:
        raise RuntimeError("AUTHORITY_VALIDATOR_DEFINITION_INVALID")
    return {str(name): [str(arg) for arg in argv] for name, argv in commands.items()}


def _validator_timeout_seconds(root: Path) -> int:
    path = root / "tools" / "authority_validation.py"
    spec = importlib.util.spec_from_file_location("_authority_guard_validator_policy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AUTHORITY_VALIDATOR_DEFINITION_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, "validator_timeout_seconds", None)
    if not callable(function):
        raise RuntimeError("AUTHORITY_VALIDATOR_TIMEOUT_POLICY_UNAVAILABLE")
    return int(function(dict(os.environ)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _inside(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _canonical_authority_root(root: Path, value: str) -> Path:
    canonical = (root / CANONICAL_AUTHORITY_ROOT).resolve()
    requested = (root / value).resolve()
    if requested != canonical:
        raise ValueError("AUTHORITY_ROOT_OVERRIDE_FORBIDDEN")
    if not canonical.is_dir():
        raise ValueError("AUTHORITY_ROOT_INVALID")
    return canonical


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _json_write(path: Path, obj: Any) -> None:
    _atomic_write(path, (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fail(code: str, message: str, exit_code: int = EXIT_POLICY, **extra: Any) -> int:
    print(json.dumps({"status": "REJECTED", "error_code": code, "message": message, **extra}, ensure_ascii=False, indent=2))
    return exit_code


def _workspace_id(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:24]


def _canonical_lock(root: Path) -> Path:
    return Path(tempfile.gettempdir()) / "ai-auto-test-platform" / "authority-write-locks" / f"{_workspace_id(root)}.lock.json"




def _checkpoint_module() -> Any:
    """Load the checkpoint helper as a private module, never through its public CLI."""
    path = Path(__file__).resolve().with_name("task_checkpoint.py")
    spec = importlib.util.spec_from_file_location("_authority_guard_task_checkpoint", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AUTHORITY_CHECKPOINT_MODULE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checkpoint_private_call(function_name: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
    """Invoke Guard-only checkpoint mutation APIs in-process so no forgeable CLI exists."""
    module = _checkpoint_module()
    function = getattr(module, function_name)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = int(function(argparse.Namespace(**kwargs)))
    text = output.getvalue().strip()
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError:
        payload = {"status": "AUTHORITY_CHECKPOINT_PROTOCOL_ERROR", "message": text}
    return rc, payload


def _checkpoint_begin(
    root: Path,
    checkpoint: Path,
    task_id: str,
    transaction_id: str,
    authority_root: str,
    state_dir: Path,
    authority_digest_at_acquire: str,
) -> tuple[int, dict[str, Any]]:
    return _checkpoint_private_call(
        "_guard_authority_begin",
        root=str(root),
        checkpoint=str(checkpoint),
        task_id=task_id,
        transaction_id=transaction_id,
        authority_root=authority_root,
        state_dir=str(state_dir),
        authority_digest_at_acquire=authority_digest_at_acquire,
    )


def _checkpoint_terminal(
    root: Path,
    checkpoint: Path,
    task_id: str,
    transaction_id: str,
    state_dir: Path,
    final_status: str,
    *,
    had_change_set: bool,
    operation_count: int,
    validated_authority_digest: str | None,
    closure_authority_digest: str,
) -> tuple[int, dict[str, Any]]:
    return _checkpoint_private_call(
        "_guard_authority_terminal",
        root=str(root),
        checkpoint=str(checkpoint),
        task_id=task_id,
        transaction_id=transaction_id,
        state_dir=str(state_dir),
        final_status=final_status,
        had_change_set=had_change_set,
        operation_count=operation_count,
        validated_authority_digest=validated_authority_digest or "",
        closure_authority_digest=closure_authority_digest,
    )


def _checkpoint_failure(payload: dict[str, Any], fallback: str) -> int:
    return _fail(
        str(payload.get("status") or fallback),
        str(payload.get("message") or "Task checkpoint rejected Authority transaction state"),
        EXIT_REJECTED,
        checkpoint_payload=payload,
    )


def _publish_lock_no_clobber(lock: Path, owner: dict[str, Any]) -> None:
    """Publish a fully written lock atomically without exposing a partial canonical file."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=lock.name + ".", suffix=".candidate", dir=str(lock.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(owner, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.link(temp, lock)
    finally:
        temp.unlink(missing_ok=True)


def _recover_owned_lock_candidates(root: Path, task_id: str, state_dir: Path) -> list[str]:
    """Remove only orphan lock candidates that can be attributed to this recovery target."""
    lock = _canonical_lock(root)
    removed: list[str] = []
    if not lock.parent.is_dir():
        return removed
    pattern = lock.name + ".*.candidate"
    for candidate in lock.parent.glob(pattern):
        try:
            record = _load_json(candidate)
        except Exception:
            continue
        if (
            record.get("task_id") == task_id
            and record.get("workspace_root") == str(root.resolve())
            and record.get("state_dir")
            and _resolved(str(record.get("state_dir"))) == state_dir
        ):
            candidate.unlink(missing_ok=True)
            removed.append(str(candidate))
    return removed


def _state_file(state_dir: Path) -> Path:
    return state_dir / "write-state.json"


def _plan_file(state_dir: Path) -> Path:
    return state_dir / "change-set.json"


def _evidence_file(state_dir: Path) -> Path:
    return state_dir / "validator-evidence.json"


def _validate_state_dir(root: Path, state_dir: Path) -> tuple[bool, str | None]:
    return (False, "AUTHORITY_RUNTIME_STATE_INSIDE_WORKSPACE") if _inside(root, state_dir) else (True, None)


def _lock_owner(lock: Path) -> dict[str, Any] | None:
    if not lock.exists():
        return None
    try:
        return _load_json(lock)
    except Exception:
        return {"task_id": "<CORRUPTED>", "status": "CORRUPTED"}


def _write_lock(lock: Path, owner: dict[str, Any]) -> None:
    _json_write(lock, owner)


def _sync_status(lock: Path, owner: dict[str, Any], state_path: Path, state: dict[str, Any], status: str, **extra: Any) -> None:
    state.update({"status": status, **extra, "updated_at": _now()})
    _json_write(state_path, state)
    owner.update({"status": status, **{k: v for k, v in extra.items() if k in {"ever_planned", "final_status"}}, "updated_at": _now()})
    _write_lock(lock, owner)


def _authority_digest(authority_root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted((p for p in authority_root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        rel_path = path.relative_to(authority_root)
        if any(part in IGNORED_AUTHORITY_PARTS for part in rel_path.parts) or path.suffix == ".pyc":
            continue
        hasher.update(rel_path.as_posix().encode("utf-8")); hasher.update(b"\0")
        hasher.update(_sha256_file(path).encode("ascii")); hasher.update(b"\n")
    return hasher.hexdigest()


def _owner_authority_root(root: Path, owner: dict[str, Any]) -> Path:
    return _canonical_authority_root(root, str(owner.get("authority_root", CANONICAL_AUTHORITY_ROOT)))


def _require_lock(root: Path, task_id: str, state_dir: Path, *, require_state: bool = True) -> tuple[Path | None, dict[str, Any] | None, int | None]:
    ok, reason = _validate_state_dir(root, state_dir)
    if not ok:
        return None, None, _fail(reason or "STATE_DIR_INVALID", "authority runtime state must be outside workspace", EXIT_INVALID)
    lock = _canonical_lock(root); owner = _lock_owner(lock)
    if owner is None:
        return None, None, _fail("AUTHORITY_WRITE_LOCK_NOT_HELD", "authority write lock is not held", EXIT_REJECTED)
    if owner.get("task_id") != task_id:
        return None, owner, _fail("AUTHORITY_WRITE_LOCKED_BY_OTHER_TASK", "another task owns the workspace-level authority write lock", EXIT_REJECTED, owner_task_id=owner.get("task_id"))
    canonical = _resolved(owner.get("state_dir", "")) if owner.get("state_dir") else None
    if canonical is None or canonical != state_dir:
        return None, owner, _fail("AUTHORITY_WRITE_STATE_DIR_MISMATCH", "command must use the canonical state directory recorded by the workspace lock", EXIT_REJECTED, canonical_state_dir=str(canonical) if canonical else None, provided_state_dir=str(state_dir))
    if owner.get("workspace_root") != str(root.resolve()):
        return None, owner, _fail("AUTHORITY_WRITE_WORKSPACE_MISMATCH", "lock belongs to another workspace root", EXIT_REJECTED)
    if require_state and not _state_file(state_dir).is_file():
        return None, owner, _fail("AUTHORITY_WRITE_STATE_LOST", "workspace lock exists but canonical write-state is missing; run recover", EXIT_REJECTED, lock_status=owner.get("status"))
    return lock, owner, None


def _initial_record(
    root: Path,
    authority_root: Path,
    state_dir: Path,
    task_id: str,
    checkpoint: Path,
    transaction_id: str,
    authority_digest_at_acquire: str,
) -> dict[str, Any]:
    return {
        "schema_version": 5,
        "task_id": task_id,
        "workspace_root": str(root),
        "workspace_identity": _workspace_id(root),
        "authority_root": authority_root.relative_to(root).as_posix(),
        "state_dir": str(state_dir),
        "checkpoint": str(checkpoint),
        "authority_transaction_id": transaction_id,
        "authority_digest_at_acquire": authority_digest_at_acquire,
        "status": "PREPARING_LOCK",
        "ever_planned": False,
        "created_at": _now(),
        "updated_at": _now(),
        "auto_steal": False,
        "ephemeral": True,
    }


def cmd_acquire(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    state_dir = _resolved(args.state_dir)
    checkpoint = _resolved(args.checkpoint)
    if not root.is_dir():
        return _fail("WORKSPACE_ROOT_INVALID", "workspace root is invalid", EXIT_INVALID)
    try:
        authority_root = _canonical_authority_root(root, args.authority_root)
    except ValueError as exc:
        return _fail(str(exc), "Authority root is fixed to docs/authority", EXIT_INVALID)
    ok, error = _validate_state_dir(root, state_dir)
    if not ok:
        return _fail(error or "STATE_DIR_INVALID", "authority runtime state must be outside workspace", EXIT_INVALID)
    if _inside(root, checkpoint):
        return _fail("CHECKPOINT_INSIDE_WORKSPACE", "Task checkpoint must remain outside workspace", EXIT_INVALID)

    lock = _canonical_lock(root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    existing = _lock_owner(lock)
    if existing:
        if existing.get("status") == "CORRUPTED":
            return _fail("AUTHORITY_WRITE_LOCK_CORRUPTED_RECOVER_REQUIRED", "canonical authority lock is corrupted; run recover with the original PREPARING_LOCK state if available", EXIT_REJECTED)
        if existing.get("task_id") != args.task_id:
            return _fail("AUTHORITY_WRITE_LOCKED_BY_OTHER_TASK", "another task owns the workspace-level authority write lock", EXIT_REJECTED, owner_task_id=existing.get("task_id"))
        if _resolved(existing.get("state_dir", "")) != state_dir:
            return _fail("AUTHORITY_WRITE_STATE_DIR_MISMATCH", "same task must resume the canonical authority-write state directory", EXIT_REJECTED)
        if _resolved(existing.get("checkpoint", "")) != checkpoint:
            return _fail("AUTHORITY_CHECKPOINT_MISMATCH", "same Authority transaction must resume the checkpoint recorded by the workspace lock", EXIT_REJECTED)
        transaction_id = str(existing.get("authority_transaction_id") or "")
        if not transaction_id:
            return _fail("AUTHORITY_TRANSACTION_ID_MISSING", "canonical lock has no Authority transaction identity", EXIT_REJECTED)
        if existing.get("status") == "CLEANING" and not state_dir.exists():
            lock.unlink(missing_ok=True)
            print(json.dumps({"status": "CLEANUP_RECOVERED", "task_id": args.task_id, "authority_transaction_id": transaction_id, "lock_exists": lock.exists()}, ensure_ascii=False, indent=2))
            return EXIT_OK
        if not _state_file(state_dir).is_file():
            if existing.get("status") in {"LOCKED", "PREPARING_LOCK"} and not existing.get("ever_planned", True):
                return _fail("AUTHORITY_WRITE_STATE_LOST_RECOVER_REQUIRED", "safe orphan lock requires recover so the Task checkpoint transaction can be terminalized consistently", EXIT_REJECTED, lock_status=existing.get("status"))
            return _fail("AUTHORITY_WRITE_STATE_LOST_UNRECOVERABLE", "lock has transactional history but canonical state is missing", EXIT_REJECTED, lock_status=existing.get("status"))
        state = _load_json(_state_file(state_dir))
        if state.get("status") == "CLEANING":
            shutil.rmtree(state_dir, ignore_errors=True)
            lock.unlink(missing_ok=True)
            print(json.dumps({"status": "CLEANUP_RECOVERED", "task_id": args.task_id, "authority_transaction_id": transaction_id, "lock_exists": lock.exists(), "state_dir_exists": state_dir.exists()}, ensure_ascii=False, indent=2))
            return EXIT_OK
        acquire_digest = str(existing.get("authority_digest_at_acquire") or state.get("authority_digest_at_acquire") or "")
        if not acquire_digest:
            return _fail("AUTHORITY_ACQUIRE_DIGEST_MISSING", "Authority transaction is missing its acquire-time digest", EXIT_REJECTED)
        cp_rc, cp_payload = _checkpoint_begin(root, checkpoint, args.task_id, transaction_id, CANONICAL_AUTHORITY_ROOT, state_dir, acquire_digest)
        if cp_rc != 0:
            return _checkpoint_failure(cp_payload, "AUTHORITY_CHECKPOINT_BIND_FAILED")
        if state.get("status") == "PREPARING_LOCK" and existing.get("status") == "LOCKED":
            state.update({"status": "LOCKED", "acquired_at": existing.get("acquired_at", _now()), "updated_at": _now()})
            _json_write(_state_file(state_dir), state)
        print(json.dumps({"status": "RESUMED", "task_id": args.task_id, "authority_transaction_id": transaction_id, "write_status": state.get("status"), "lock": str(lock), "state_dir": str(state_dir), "checkpoint": str(checkpoint)}, ensure_ascii=False, indent=2))
        return EXIT_OK

    prior: dict[str, Any] | None = None
    if state_dir.exists():
        sf = _state_file(state_dir)
        if not sf.is_file():
            return _fail("AUTHORITY_ORPHAN_STATE_INVALID", "state directory exists without write-state", EXIT_REJECTED)
        prior = _load_json(sf)
        if prior.get("task_id") != args.task_id or prior.get("status") not in {"PREPARING_LOCK", "CLEANING"}:
            return _fail("AUTHORITY_ORPHAN_STATE_REQUIRES_RECOVER", "existing state directory is not safe to reuse", EXIT_REJECTED, write_status=prior.get("status"))
        if prior.get("status") == "CLEANING":
            shutil.rmtree(state_dir)
            prior = None
        elif _resolved(prior.get("checkpoint", "")) != checkpoint:
            return _fail("AUTHORITY_CHECKPOINT_MISMATCH", "orphan PREPARING_LOCK state belongs to another checkpoint", EXIT_REJECTED)

    state_dir.mkdir(parents=True, exist_ok=True)
    transaction_id = str(prior.get("authority_transaction_id")) if prior else uuid.uuid4().hex
    if prior and not transaction_id:
        return _fail("AUTHORITY_TRANSACTION_ID_MISSING", "orphan PREPARING_LOCK state has no transaction identity", EXIT_REJECTED)
    authority_digest_at_acquire = str(prior.get("authority_digest_at_acquire") or "") if prior else ""
    if not authority_digest_at_acquire:
        authority_digest_at_acquire = _authority_digest(authority_root)
    record = prior or _initial_record(root, authority_root, state_dir, args.task_id, checkpoint, transaction_id, authority_digest_at_acquire)
    record["authority_root"] = CANONICAL_AUTHORITY_ROOT
    record["authority_digest_at_acquire"] = authority_digest_at_acquire
    _json_write(_state_file(state_dir), record)
    lock_record = dict(record)
    lock_record.update({"status": "LOCKED", "acquired_at": _now()})
    try:
        _publish_lock_no_clobber(lock, lock_record)
    except FileExistsError:
        owner = _lock_owner(lock) or {}
        code = "AUTHORITY_WRITE_LOCK_CORRUPTED_RECOVER_REQUIRED" if owner.get("status") == "CORRUPTED" else "AUTHORITY_WRITE_LOCKED_BY_OTHER_TASK"
        return _fail(code, "authority lock raced with another task or requires recovery", EXIT_REJECTED, owner_task_id=owner.get("task_id"))

    cp_rc, cp_payload = _checkpoint_begin(root, checkpoint, args.task_id, transaction_id, CANONICAL_AUTHORITY_ROOT, state_dir, authority_digest_at_acquire)
    if cp_rc != 0:
        lock.unlink(missing_ok=True)
        shutil.rmtree(state_dir, ignore_errors=True)
        return _checkpoint_failure(cp_payload, "AUTHORITY_CHECKPOINT_BIND_FAILED")
    record.update({"status": "LOCKED", "acquired_at": lock_record["acquired_at"], "updated_at": _now()})
    _json_write(_state_file(state_dir), record)
    print(json.dumps({"status": "ACQUIRED", "task_id": args.task_id, "authority_transaction_id": transaction_id, "lock": str(lock), "state_dir": str(state_dir), "checkpoint": str(checkpoint)}, ensure_ascii=False, indent=2))
    return EXIT_OK


def _normalize_plan(root: Path, authority_root: Path, state_dir: Path, source: dict[str, Any]) -> dict[str, Any]:
    operations = source.get("operations")
    if not isinstance(operations, list) or not operations: raise ValueError("AUTHORITY_CHANGE_SET_EMPTY")
    seen: set[str] = set(); normalized: list[dict[str, Any]] = []; before_dir = state_dir / "before"; prepared_dir = state_dir / "prepared"
    shutil.rmtree(before_dir, ignore_errors=True); shutil.rmtree(prepared_dir, ignore_errors=True); before_dir.mkdir(parents=True); prepared_dir.mkdir(parents=True)
    for index, item in enumerate(operations):
        if not isinstance(item, dict): raise ValueError("AUTHORITY_CHANGE_SET_INVALID_OPERATION")
        relative, expected, replacement_file = item.get("path"), item.get("expected_sha256"), item.get("replacement_file")
        if not all(isinstance(x, str) for x in (relative, expected, replacement_file)): raise ValueError("AUTHORITY_CHANGE_SET_INVALID_OPERATION")
        if relative in seen: raise ValueError(f"AUTHORITY_CHANGE_SET_DUPLICATE_TARGET:{relative}")
        seen.add(relative); target = (root / relative).resolve()
        if not _inside(authority_root, target) or not target.is_file(): raise ValueError(f"AUTHORITY_TARGET_INVALID:{relative}")
        actual = _sha256_file(target)
        if actual != expected: raise ValueError(f"AUTHORITY_STALE_WRITE_CONFLICT:{relative}")
        replacement = _resolved(replacement_file)
        if not replacement.is_file(): raise ValueError(f"AUTHORITY_REPLACEMENT_NOT_FOUND:{relative}")
        if _inside(root, replacement): raise ValueError(f"AUTHORITY_REPLACEMENT_MUST_BE_EPHEMERAL:{relative}")
        token = hashlib.sha256(relative.encode()).hexdigest()[:12]; before_path = before_dir / f"{index:04d}-{token}.before"; prepared_path = prepared_dir / f"{index:04d}-{token}.prepared"
        _atomic_write(before_path, target.read_bytes()); _atomic_write(prepared_path, replacement.read_bytes())
        normalized.append({"path": relative, "expected_sha256": expected, "before_sha256": actual, "before_file": str(before_path), "prepared_file": str(prepared_path), "prepared_sha256": _sha256_file(prepared_path), "sources": item.get("sources", []) if isinstance(item.get("sources", []), list) else []})
    return {"schema_version": 3, "created_at": _now(), "operations": normalized, "ephemeral": True}


def cmd_plan(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir); lock, owner, error = _require_lock(root, args.task_id, state_dir)
    if error is not None: return error
    state_path = _state_file(state_dir); state = _load_json(state_path)
    if state.get("status") != "LOCKED": return _fail("AUTHORITY_WRITE_INVALID_STATE", "planning requires LOCKED state", EXIT_REJECTED, write_status=state.get("status"))
    source_path = _resolved(args.change_set)
    if not source_path.is_file() or _inside(root, source_path): return _fail("AUTHORITY_CHANGE_SET_MUST_BE_EPHEMERAL", "input change-set must exist outside workspace", EXIT_INVALID)
    try: plan = _normalize_plan(root, _owner_authority_root(root, owner or {}), state_dir, _load_json(source_path))
    except (ValueError, json.JSONDecodeError) as exc: return _fail(str(exc).split(":", 1)[0], str(exc), EXIT_REJECTED)
    _json_write(_plan_file(state_dir), plan); _sync_status(lock, owner or {}, state_path, state, "PLANNED", ever_planned=True, planned_at=_now(), operation_count=len(plan["operations"]))
    print(json.dumps({"status": "PLANNED", "operation_count": len(plan["operations"]), "coalesced_targets": [o["path"] for o in plan["operations"]]}, ensure_ascii=False, indent=2)); return EXIT_OK


def _safe_rollback_plan(root: Path, plan: dict[str, Any]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for item in plan.get("operations", []):
        target = (root / item["path"]).resolve(); before = _resolved(item["before_file"])
        if not before.is_file() or not target.is_file(): conflicts.append({"path": item["path"], "reason": "ROLLBACK_MATERIAL_MISSING"}); continue
        current = _sha256_file(target); before_sha = item["before_sha256"]; guard_sha = item["prepared_sha256"]
        if current == before_sha: continue
        if current != guard_sha:
            conflicts.append({"path": item["path"], "reason": "AUTHORITY_ROLLBACK_STALE_CONFLICT", "current_sha256": current, "guard_resulting_sha256": guard_sha}); continue
        _atomic_write(target, before.read_bytes())
    return conflicts


def _verify_prepared(plan: dict[str, Any]) -> str | None:
    for item in plan.get("operations", []):
        prepared = _resolved(item["prepared_file"])
        if not prepared.is_file() or _sha256_file(prepared) != item["prepared_sha256"]: return item["path"]
    return None


def _finalize_applied(root: Path, plan_path: Path, state_path: Path, lock: Path, owner: dict[str, Any], state: dict[str, Any], plan: dict[str, Any]) -> int:
    results = []
    for item in plan.get("operations", []):
        target = (root / item["path"]).resolve(); resulting = _sha256_file(target)
        if resulting != item["prepared_sha256"]: return _fail("AUTHORITY_APPLY_RESULT_MISMATCH", "atomic write result does not match prepared content", EXIT_REJECTED, path=item["path"])
        item["resulting_sha256"] = resulting; results.append({"path": item["path"], "resulting_sha256": resulting})
    _json_write(plan_path, plan); _sync_status(lock, owner, state_path, state, "APPLIED_PENDING_VALIDATION", applied_at=_now(), results=results)
    print(json.dumps({"status": "APPLIED_PENDING_VALIDATION", "results": results}, ensure_ascii=False, indent=2)); return EXIT_OK


def cmd_apply(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir); lock, owner, error = _require_lock(root, args.task_id, state_dir)
    if error is not None: return error
    state_path, plan_path = _state_file(state_dir), _plan_file(state_dir); state = _load_json(state_path)
    if not plan_path.is_file(): return _fail("AUTHORITY_CHANGE_SET_NOT_PLANNED", "no prepared change-set exists", EXIT_REJECTED)
    if state.get("status") != "PLANNED": return _fail("AUTHORITY_WRITE_INVALID_STATE", "apply requires PLANNED state; use reconcile after interrupted APPLYING", EXIT_REJECTED, write_status=state.get("status"))
    plan = _load_json(plan_path)
    for item in plan.get("operations", []):
        target = (root / item["path"]).resolve()
        if not target.is_file() or _sha256_file(target) != item["expected_sha256"]: return _fail("AUTHORITY_STALE_WRITE_CONFLICT", "authority target changed after plan; DELTA_REFRESH is required", EXIT_REJECTED, path=item["path"])
    corrupt = _verify_prepared(plan)
    if corrupt: return _fail("PREPARED_CONTENT_CORRUPTED", "prepared authority replacement was modified", EXIT_REJECTED, path=corrupt)
    _sync_status(lock, owner or {}, state_path, state, "APPLYING", applying_at=_now())
    try:
        for item in plan.get("operations", []): _atomic_write((root / item["path"]).resolve(), _resolved(item["prepared_file"]).read_bytes())
    except Exception as exc:
        conflicts = _safe_rollback_plan(root, plan)
        if conflicts:
            _sync_status(lock, owner or {}, state_path, state, "ROLLBACK_CONFLICT", error=str(exc), rollback_conflicts=conflicts); return _fail("AUTHORITY_APPLY_FAILED_ROLLBACK_CONFLICT", str(exc), EXIT_REJECTED, rollback_conflicts=conflicts)
        _sync_status(lock, owner or {}, state_path, state, "LOCKED", error=str(exc), rolled_back_at=_now()); shutil.rmtree(state_dir / "before", ignore_errors=True); shutil.rmtree(state_dir / "prepared", ignore_errors=True); plan_path.unlink(missing_ok=True)
        return _fail("AUTHORITY_APPLY_FAILED_ROLLED_BACK", str(exc), EXIT_REJECTED)
    return _finalize_applied(root, plan_path, state_path, lock, owner or {}, state, plan)


def cmd_reconcile(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir); lock, owner, error = _require_lock(root, args.task_id, state_dir)
    if error is not None: return error
    state_path, plan_path = _state_file(state_dir), _plan_file(state_dir); state = _load_json(state_path)
    if state.get("status") != "APPLYING" or not plan_path.is_file(): return _fail("AUTHORITY_RECONCILE_NOT_REQUIRED", "reconcile only handles interrupted APPLYING state", EXIT_REJECTED, write_status=state.get("status"))
    plan = _load_json(plan_path); classifications: dict[str, str] = {}; conflicts = []
    for item in plan.get("operations", []):
        target = (root / item["path"]).resolve()
        if not target.is_file(): conflicts.append({"path": item["path"], "reason": "TARGET_MISSING"}); continue
        current = _sha256_file(target)
        if current == item["before_sha256"]: classifications[item["path"]] = "BEFORE"
        elif current == item["prepared_sha256"]: classifications[item["path"]] = "PREPARED"
        else: conflicts.append({"path": item["path"], "reason": "THIRD_PARTY_SHA", "current_sha256": current})
    if conflicts:
        _sync_status(lock, owner or {}, state_path, state, "ROLLBACK_CONFLICT", reconcile_conflicts=conflicts); return _fail("AUTHORITY_RECONCILE_STALE_CONFLICT", "interrupted apply contains third-party authority edits", EXIT_REJECTED, conflicts=conflicts)
    if args.strategy == "rollback":
        rb = _safe_rollback_plan(root, plan)
        if rb: return _fail("AUTHORITY_ROLLBACK_STALE_CONFLICT", "reconcile rollback refused", EXIT_REJECTED, conflicts=rb)
        shutil.rmtree(state_dir / "before", ignore_errors=True); shutil.rmtree(state_dir / "prepared", ignore_errors=True); plan_path.unlink(missing_ok=True); _sync_status(lock, owner or {}, state_path, state, "LOCKED", reconciled_at=_now())
        print(json.dumps({"status": "RECONCILED_TO_LOCKED", "strategy": "rollback"}, ensure_ascii=False, indent=2)); return EXIT_OK
    corrupt = _verify_prepared(plan)
    if corrupt: return _fail("PREPARED_CONTENT_CORRUPTED", "prepared authority replacement was modified", EXIT_REJECTED, path=corrupt)
    for item in plan.get("operations", []):
        if classifications.get(item["path"]) == "BEFORE": _atomic_write((root / item["path"]).resolve(), _resolved(item["prepared_file"]).read_bytes())
    return _finalize_applied(root, plan_path, state_path, lock, owner or {}, state, plan)


def _run_validator(root: Path, name: str, argv: list[str], timeout_seconds: int) -> dict[str, Any]:
    command = [sys.executable, *argv]; env = dict(os.environ); env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = _now()
    try:
        cp = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False, timeout=timeout_seconds)
        stdout, stderr, exit_code = cp.stdout or "", cp.stderr or "", cp.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""; stderr = exc.stderr if isinstance(exc.stderr, str) else ""; exit_code = 124
        stderr = (stderr + "\nVALIDATOR_TIMEOUT").strip()
    return {"name": name, "status": "PASS" if exit_code == 0 else "FAIL", "exit_code": exit_code, "command": command, "timeout_seconds": timeout_seconds, "started_at": started, "finished_at": _now(), "stdout_sha256": _sha256_bytes(stdout.encode()), "stderr_sha256": _sha256_bytes(stderr.encode()), "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}


def cmd_validate(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir); lock, owner, error = _require_lock(root, args.task_id, state_dir)
    if error is not None: return error
    state_path, plan_path = _state_file(state_dir), _plan_file(state_dir); state = _load_json(state_path)
    if state.get("status") != "APPLIED_PENDING_VALIDATION" or not plan_path.is_file(): return _fail("AUTHORITY_WRITE_NOT_READY_FOR_VALIDATION", "authority changes must be fully applied before validation", EXIT_REJECTED, write_status=state.get("status"))
    plan = _load_json(plan_path)
    for item in plan.get("operations", []):
        target = (root / item["path"]).resolve(); expected = item.get("resulting_sha256", item["prepared_sha256"])
        if not target.is_file() or _sha256_file(target) != expected: return _fail("AUTHORITY_VALIDATION_STALE_WRITE_CONFLICT", "authority changed after apply", EXIT_REJECTED, path=item["path"])
    authority_root = _owner_authority_root(root, owner or {}); before_digest = _authority_digest(authority_root); results = []
    try:
        validator_timeout_seconds = _validator_timeout_seconds(root)
    except (RuntimeError, ValueError) as exc:
        return _fail("AUTHORITY_VALIDATOR_TIMEOUT_POLICY_INVALID", str(exc), EXIT_INVALID)
    for name, argv in _validator_commands(root).items():
        result = _run_validator(root, name, argv, validator_timeout_seconds); results.append(result)
        if result["status"] != "PASS":
            evidence = {"schema_version": 1, "task_id": args.task_id, "authority_digest_before": before_digest, "authority_digest_after": _authority_digest(authority_root), "status": "FAIL", "gates": results, "created_at": _now(), "generated_by": "authority_write_guard"}; _json_write(_evidence_file(state_dir), evidence)
            return _fail("AUTHORITY_VALIDATION_NOT_PASSED", "formal authority validator failed", EXIT_REJECTED, failed_gate=name, validator_exit_code=result["exit_code"])
    after_digest = _authority_digest(authority_root)
    if before_digest != after_digest: return _fail("AUTHORITY_VALIDATION_MUTATED_AUTHORITY", "authority changed while validators were running", EXIT_REJECTED, before_digest=before_digest, after_digest=after_digest)
    stale = []
    for item in plan.get("operations", []):
        target = (root / item["path"]).resolve(); expected = item.get("resulting_sha256", item["prepared_sha256"])
        if not target.is_file() or _sha256_file(target) != expected: stale.append(item["path"])
    if stale: return _fail("AUTHORITY_VALIDATION_STALE_WRITE_CONFLICT", "authority target changed while validators were running", EXIT_REJECTED, paths=stale)
    evidence = {"schema_version": 1, "task_id": args.task_id, "authority_digest_before": before_digest, "authority_digest_after": after_digest, "status": "PASS", "gates": results, "created_at": _now(), "generated_by": "authority_write_guard"}; _json_write(_evidence_file(state_dir), evidence)
    _sync_status(lock, owner or {}, state_path, state, "VALIDATED", validated_at=_now(), validated_authority_digest=after_digest, validator_evidence_sha256=_sha256_file(_evidence_file(state_dir)))
    print(json.dumps({"status": "VALIDATED", "task_id": args.task_id, "authority_digest": after_digest, "gates": {x["name"]: x["status"] for x in results}, "evidence": str(_evidence_file(state_dir))}, ensure_ascii=False, indent=2)); return EXIT_OK


def cmd_mark_validated(args: argparse.Namespace) -> int:
    return _fail("CALLER_SUPPLIED_VALIDATION_EVIDENCE_FORBIDDEN", "formal validation must use `authority_write_guard.py validate`; caller-authored PASS evidence is not trusted", EXIT_REJECTED)


def cmd_rollback(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir); lock, owner, error = _require_lock(root, args.task_id, state_dir)
    if error is not None: return error
    state_path, plan_path = _state_file(state_dir), _plan_file(state_dir); state = _load_json(state_path)
    if not plan_path.is_file() or state.get("status") not in {"APPLYING", "APPLIED_PENDING_VALIDATION", "VALIDATED", "ROLLBACK_CONFLICT"}: return _fail("AUTHORITY_ROLLBACK_NOT_REQUIRED", "current authority-write state has no applied changes to rollback", EXIT_REJECTED, write_status=state.get("status"))
    conflicts = _safe_rollback_plan(root, _load_json(plan_path))
    if conflicts:
        _sync_status(lock, owner or {}, state_path, state, "ROLLBACK_CONFLICT", rollback_conflicts=conflicts, rollback_conflict_at=_now()); return _fail("AUTHORITY_ROLLBACK_STALE_CONFLICT", "authority changed after guard write; rollback refused", EXIT_REJECTED, conflicts=conflicts)
    shutil.rmtree(state_dir / "before", ignore_errors=True); shutil.rmtree(state_dir / "prepared", ignore_errors=True); plan_path.unlink(missing_ok=True); _evidence_file(state_dir).unlink(missing_ok=True)
    _sync_status(lock, owner or {}, state_path, state, "LOCKED", rollback_at=_now(), results=[], rollback_conflicts=[])
    print(json.dumps({"status": "ROLLED_BACK_TO_LOCKED", "task_id": args.task_id}, ensure_ascii=False, indent=2)); return EXIT_OK


def _begin_cleaning(lock: Path, owner: dict[str, Any], state_path: Path, state: dict[str, Any], final_status: str) -> None:
    _sync_status(lock, owner, state_path, state, "CLEANING", final_status=final_status, cleaning_at=_now())


def _finish_cleaning(lock: Path, state_dir: Path) -> None:
    if state_dir.exists(): shutil.rmtree(state_dir)
    lock.unlink(missing_ok=True)  # mutex is released last


def cmd_cleanup(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    state_dir = _resolved(args.state_dir)
    lock, owner, error = _require_lock(root, args.task_id, state_dir)
    if error is not None:
        return error
    if args.final_status not in FINAL_STATUSES:
        return _fail("AUTHORITY_CLEANUP_STATUS_INVALID", "cleanup only accepts terminal task states", EXIT_INVALID)
    state_path, plan_path = _state_file(state_dir), _plan_file(state_dir)
    state = _load_json(state_path)
    plan_exists = plan_path.is_file()
    authority_root = _owner_authority_root(root, owner or {})
    if args.final_status == "CLOSURE_COMPLETE":
        if plan_exists and state.get("status") != "VALIDATED":
            return _fail("AUTHORITY_CLOSURE_REQUIRES_VALIDATED_WRITE", "completed task cannot discard an unvalidated authority write", EXIT_REJECTED, write_status=state.get("status"))
        if not plan_exists and state.get("status") != "LOCKED":
            return _fail("AUTHORITY_CLOSURE_STATE_INVALID", "authority lifecycle is inconsistent for closure", EXIT_REJECTED, write_status=state.get("status"))
        if not plan_exists:
            acquire_digest = str(state.get("authority_digest_at_acquire") or (owner or {}).get("authority_digest_at_acquire") or "")
            current_digest = _authority_digest(authority_root)
            if not acquire_digest:
                return _fail("AUTHORITY_ACQUIRE_DIGEST_MISSING", "no-change Authority transaction lacks acquire-time digest", EXIT_REJECTED)
            if current_digest != acquire_digest:
                return _fail("AUTHORITY_EXTERNAL_CHANGE_DURING_TRANSACTION", "Authority changed outside this no-change Guard transaction; DELTA_REFRESH and formal validation are required", EXIT_REJECTED, authority_digest_at_acquire=acquire_digest, current_authority_digest=current_digest)
        if plan_exists:
            plan = _load_json(plan_path)
            stale = []
            for item in plan.get("operations", []):
                target = (root / item["path"]).resolve()
                expected = item.get("resulting_sha256", item["prepared_sha256"])
                if not target.is_file() or _sha256_file(target) != expected:
                    stale.append(item["path"])
            current_digest = _authority_digest(authority_root)
            if stale or current_digest != state.get("validated_authority_digest"):
                return _fail("AUTHORITY_CLOSURE_STALE_VALIDATION_CONFLICT", "authority changed after validation", EXIT_REJECTED, stale_targets=stale, current_authority_digest=current_digest, validated_authority_digest=state.get("validated_authority_digest"))
    elif plan_exists and state.get("status") in {"APPLYING", "APPLIED_PENDING_VALIDATION", "VALIDATED", "ROLLBACK_CONFLICT"}:
        conflicts = _safe_rollback_plan(root, _load_json(plan_path))
        if conflicts:
            _sync_status(lock, owner or {}, state_path, state, "ROLLBACK_CONFLICT", rollback_conflicts=conflicts)
            return _fail("AUTHORITY_ROLLBACK_STALE_CONFLICT", "cleanup refused because rollback would overwrite external edits", EXIT_REJECTED, conflicts=conflicts)

    plan = _load_json(plan_path) if plan_exists else None
    closure_digest = _authority_digest(authority_root)
    if args.final_status == "CLOSURE_COMPLETE" and plan_exists and closure_digest != state.get("validated_authority_digest"):
        return _fail("AUTHORITY_CLOSURE_STALE_VALIDATION_CONFLICT", "Authority digest changed before terminal attestation", EXIT_REJECTED, current_authority_digest=closure_digest, validated_authority_digest=state.get("validated_authority_digest"))
    confirmation_digest = _authority_digest(authority_root)
    if confirmation_digest != closure_digest:
        return _fail("AUTHORITY_CLOSURE_DIGEST_UNSTABLE", "Authority changed while preparing terminal attestation", EXIT_REJECTED, first_digest=closure_digest, second_digest=confirmation_digest)

    checkpoint_value = (owner or {}).get("checkpoint") or state.get("checkpoint")
    transaction_id = str((owner or {}).get("authority_transaction_id") or state.get("authority_transaction_id") or "")
    if not checkpoint_value or not transaction_id:
        return _fail("AUTHORITY_CHECKPOINT_BINDING_MISSING", "Authority transaction lacks checkpoint/transaction identity", EXIT_REJECTED)
    checkpoint = _resolved(str(checkpoint_value))
    cp_rc, cp_payload = _checkpoint_terminal(
        root,
        checkpoint,
        args.task_id,
        transaction_id,
        state_dir,
        args.final_status,
        had_change_set=plan_exists,
        operation_count=len(plan.get("operations", [])) if plan else 0,
        validated_authority_digest=state.get("validated_authority_digest"),
        closure_authority_digest=closure_digest,
    )
    if cp_rc != 0:
        return _checkpoint_failure(cp_payload, "AUTHORITY_CHECKPOINT_TERMINAL_FAILED")

    _begin_cleaning(lock, owner or {}, state_path, state, args.final_status)
    _finish_cleaning(lock, state_dir)
    print(json.dumps({
        "status": "CLEANED",
        "final_status": args.final_status,
        "authority_transaction_id": transaction_id,
        "closure_authority_digest": closure_digest,
        "checkpoint": str(checkpoint),
        "state_dir_exists": state_dir.exists(),
        "lock_exists": lock.exists(),
        "ephemeral_state_survives": state_dir.exists() or lock.exists(),
    }, ensure_ascii=False, indent=2))
    return EXIT_OK


def _terminalize_unplanned_binding(root: Path, record: dict[str, Any], state_dir: Path) -> tuple[bool, dict[str, Any] | None]:
    checkpoint_value = record.get("checkpoint")
    transaction_id = str(record.get("authority_transaction_id") or "")
    if not checkpoint_value or not transaction_id:
        # Crash happened before Task Checkpoint binding was durably recorded.
        return True, None
    try:
        authority_root = _owner_authority_root(root, record)
    except ValueError:
        return False, {"status": "AUTHORITY_ROOT_INVALID", "message": "cannot terminalize orphan transaction with invalid Authority root"}
    rc, payload = _checkpoint_terminal(
        root,
        _resolved(str(checkpoint_value)),
        str(record.get("task_id")),
        transaction_id,
        state_dir,
        "TASK_ABORTED",
        had_change_set=False,
        operation_count=0,
        validated_authority_digest=None,
        closure_authority_digest=_authority_digest(authority_root),
    )
    if rc == 0 or payload.get("status") == "AUTHORITY_TRANSACTION_NOT_RECORDED":
        return True, payload
    return False, payload


def cmd_recover(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir)
    removed_candidates = _recover_owned_lock_candidates(root, args.task_id, state_dir)
    lock = _canonical_lock(root); owner = _lock_owner(lock)
    if owner is not None and owner.get("status") == "CORRUPTED":
        sf = _state_file(state_dir)
        if sf.is_file():
            try:
                state = _load_json(sf)
            except Exception:
                state = {}
            safe_preparing = (
                state.get("task_id") == args.task_id
                and state.get("workspace_root") == str(root.resolve())
                and _resolved(state.get("state_dir", "")) == state_dir
                and state.get("status") == "PREPARING_LOCK"
                and not state.get("ever_planned", True)
            )
            if safe_preparing:
                terminalized, payload = _terminalize_unplanned_binding(root, state, state_dir)
                if not terminalized:
                    return _checkpoint_failure(payload or {}, "AUTHORITY_CHECKPOINT_TERMINAL_FAILED")
                lock.unlink(missing_ok=True)
                shutil.rmtree(state_dir, ignore_errors=True)
                print(json.dumps({"status": "CORRUPTED_PREPARING_LOCK_RECOVERED", "lock_exists": lock.exists(), "state_dir_exists": state_dir.exists()}, ensure_ascii=False, indent=2)); return EXIT_OK
        return _fail("AUTHORITY_WRITE_LOCK_CORRUPTED_MANUAL_REVIEW", "corrupted canonical lock cannot be safely attributed to this task", EXIT_REJECTED)
    if owner is None:
        if state_dir.exists():
            sf = _state_file(state_dir)
            if sf.is_file():
                orphan_state = _load_json(sf)
                if orphan_state.get("task_id") == args.task_id and orphan_state.get("status") in {"PREPARING_LOCK", "CLEANING"}:
                    if orphan_state.get("status") == "PREPARING_LOCK":
                        terminalized, payload = _terminalize_unplanned_binding(root, orphan_state, state_dir)
                        if not terminalized:
                            return _checkpoint_failure(payload or {}, "AUTHORITY_CHECKPOINT_TERMINAL_FAILED")
                    shutil.rmtree(state_dir); print(json.dumps({"status": "ORPHAN_STATE_CLEANED"}, indent=2)); return EXIT_OK
            return _fail("AUTHORITY_ORPHAN_STATE_REQUIRES_MANUAL_REVIEW", "state exists without canonical lock and is not known-safe", EXIT_REJECTED)
        print(json.dumps({"status": "ORPHAN_CANDIDATES_CLEANED" if removed_candidates else "NOTHING_TO_RECOVER", "removed_lock_candidates": removed_candidates}, ensure_ascii=False, indent=2)); return EXIT_OK
    if owner.get("task_id") != args.task_id or _resolved(owner.get("state_dir", "")) != state_dir:
        return _fail("AUTHORITY_WRITE_LOCKED_BY_OTHER_TASK", "recover may only operate on the canonical owner task/state", EXIT_REJECTED, owner_task_id=owner.get("task_id"))
    sf = _state_file(state_dir)
    state_status = _load_json(sf).get("status") if sf.is_file() else None
    if owner.get("status") == "CLEANING" or state_status == "CLEANING":
        if state_dir.exists(): shutil.rmtree(state_dir)
        lock.unlink(missing_ok=True); print(json.dumps({"status": "CLEANUP_RECOVERED", "lock_exists": lock.exists(), "state_dir_exists": state_dir.exists()}, indent=2)); return EXIT_OK
    if not sf.is_file():
        if owner.get("status") in {"LOCKED", "PREPARING_LOCK"} and not owner.get("ever_planned", True):
            terminalized, payload = _terminalize_unplanned_binding(root, owner, state_dir)
            if not terminalized:
                return _checkpoint_failure(payload or {}, "AUTHORITY_CHECKPOINT_TERMINAL_FAILED")
            lock.unlink(missing_ok=True); print(json.dumps({"status": "SAFE_ORPHAN_LOCK_RELEASED", "lock_exists": lock.exists()}, indent=2)); return EXIT_OK
        return _fail("AUTHORITY_WRITE_STATE_LOST_UNRECOVERABLE", "transactional lock survived but state material is missing", EXIT_REJECTED, lock_status=owner.get("status"))
    state = _load_json(sf)
    if state.get("status") == "APPLYING":
        # Reconciliation is explicit so callers can choose continue or rollback.
        return _fail("AUTHORITY_APPLY_RECONCILE_REQUIRED", "interrupted APPLYING state requires reconcile --strategy continue|rollback", EXIT_REJECTED)
    print(json.dumps({"status": "RECOVERABLE_STATE_PRESENT", "write_status": state.get("status"), "next_action": "resume normal command flow"}, ensure_ascii=False, indent=2)); return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    root = _resolved(args.root); state_dir = _resolved(args.state_dir); lock = _canonical_lock(root); owner = _lock_owner(lock); canonical = _resolved(owner.get("state_dir", "")) if owner and owner.get("state_dir") else None
    print(json.dumps({"status": "PRESENT" if state_dir.exists() or lock.exists() else "ABSENT", "lock": owner, "write_state": _load_json(_state_file(state_dir)) if _state_file(state_dir).is_file() else None, "change_set_present": _plan_file(state_dir).is_file(), "state_dir_matches_lock": canonical == state_dir if canonical else None, "ephemeral": True}, ensure_ascii=False, indent=2)); return EXIT_OK


def cmd_digest(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    try:
        authority_root = _canonical_authority_root(root, args.authority_root)
    except ValueError as exc:
        return _fail(str(exc), "Authority root is fixed to docs/authority", EXIT_INVALID)
    print(json.dumps({"status": "PASS", "authority_root": CANONICAL_AUTHORITY_ROOT, "authority_digest": _authority_digest(authority_root)}, ensure_ascii=False, indent=2)); return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crash-safe single-writer Living Authority coordination guard"); sub = parser.add_subparsers(dest="command", required=True)
    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", required=True); p.add_argument("--task-id", required=True); p.add_argument("--state-dir", required=True)
    acquire = sub.add_parser("acquire"); common(acquire); acquire.add_argument("--authority-root", default="docs/authority"); acquire.add_argument("--checkpoint", required=True); acquire.set_defaults(func=cmd_acquire)
    plan = sub.add_parser("plan"); common(plan); plan.add_argument("--change-set", required=True); plan.set_defaults(func=cmd_plan)
    apply = sub.add_parser("apply"); common(apply); apply.set_defaults(func=cmd_apply)
    reconcile = sub.add_parser("reconcile"); common(reconcile); reconcile.add_argument("--strategy", choices=("continue", "rollback"), default="continue"); reconcile.set_defaults(func=cmd_reconcile)
    validate = sub.add_parser("validate"); common(validate); validate.set_defaults(func=cmd_validate)
    mark = sub.add_parser("mark-validated"); common(mark); mark.add_argument("--validator-evidence", required=False); mark.set_defaults(func=cmd_mark_validated)
    rollback = sub.add_parser("rollback"); common(rollback); rollback.set_defaults(func=cmd_rollback)
    cleanup = sub.add_parser("cleanup"); common(cleanup); cleanup.add_argument("--final-status", required=True, choices=sorted(FINAL_STATUSES)); cleanup.set_defaults(func=cmd_cleanup)
    recover = sub.add_parser("recover"); common(recover); recover.set_defaults(func=cmd_recover)
    status = sub.add_parser("status"); common(status); status.set_defaults(func=cmd_status)
    digest = sub.add_parser("digest"); digest.add_argument("--root", required=True); digest.add_argument("--authority-root", default="docs/authority"); digest.set_defaults(func=cmd_digest)
    return parser


def main() -> int:
    args = build_parser().parse_args(); return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
