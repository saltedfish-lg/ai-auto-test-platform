#!/usr/bin/env python3
"""Task-level stage checkpoint helper for validated Codex resume.

The checkpoint is deliberately independent of Git and versioned baseline
manifests. It persists only task lifecycle facts outside the workspace. The
single living authority is identified by its fixed root plus a content digest;
an authority digest change triggers delta refresh rather than creating a new
baseline version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
STAGES = [
    "TASK_INITIALIZED",
    "CONTEXT_READY",
    "DECISIONS_READY",
    "IMPLEMENTATION_READY",
    "IMPLEMENTATION_COMPLETE",
    "VERIFICATION_COMPLETE",
    "CLOSURE_COMPLETE",
]
EXIT_INVALID = 2
EXIT_REJECTED = 3
EXIT_CORRUPTED = 4


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
        if tmp.exists():
            tmp.unlink()


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
    return {
        "workspace_root": str(_resolved(args.root)),
        "workspace_identity": args.workspace_identity,
        "authority_root": args.authority_root,
        "git_access": "DISABLED",
    }


def cmd_init(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    out = _resolved(args.out)
    ok, error = _validate_checkpoint_path(root, out)
    if not ok:
        return _fail(error or "CHECKPOINT_PATH_INVALID", "checkpoint must be outside workspace", EXIT_INVALID)
    if out.exists() and not args.force:
        return _fail("CHECKPOINT_ALREADY_EXISTS", "checkpoint already exists", EXIT_REJECTED)
    now = _utc_now()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": args.task_id,
        **_base_identity(args),
        "current_stage": "TASK_INITIALIZED",
        "stages": {
            "TASK_INITIALIZED": _stage_record(
                "TASK_INITIALIZED",
                args.workspace_fingerprint,
                args.authority_digest,
                args.pack_revision,
                _parse_evidence(args.evidence_json),
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


def cmd_advance(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED
    if data.get("task_id") != args.task_id:
        return _fail("TASK_ID_MISMATCH", "checkpoint belongs to another task", EXIT_REJECTED)
    if data.get("workspace_root") != str(root):
        return _fail("WORKSPACE_ROOT_MISMATCH", "checkpoint belongs to another workspace root", EXIT_REJECTED)
    current = data.get("current_stage")
    if current not in STAGES:
        return _fail("CHECKPOINT_CORRUPTED", "unknown current stage", EXIT_CORRUPTED)
    current_index = STAGES.index(current)
    if current_index == len(STAGES) - 1:
        return _fail("TASK_ALREADY_COMPLETE", "closure checkpoint is already complete", EXIT_REJECTED)
    expected = STAGES[current_index + 1]
    if args.stage != expected:
        return _fail("INVALID_STAGE_TRANSITION", f"expected next stage {expected}, got {args.stage}", EXIT_REJECTED)
    data["stages"][args.stage] = _stage_record(
        args.stage,
        args.workspace_fingerprint,
        args.authority_digest,
        args.pack_revision,
        _parse_evidence(args.evidence_json),
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
        "checksum": sealed["checksum"],
    })
    return 0


def cmd_resume_validate(args: argparse.Namespace) -> int:
    root = _resolved(args.root)
    checkpoint = _resolved(args.checkpoint)
    data, exit_code = _load_valid_checkpoint(root, checkpoint)
    if data is None:
        return exit_code or EXIT_CORRUPTED

    expected_identity = {
        "workspace_root": str(root),
        "workspace_identity": args.workspace_identity,
        "authority_root": args.authority_root,
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

    current_stage = data["current_stage"]
    record = data["stages"].get(current_stage, {})
    checkpoint_fingerprint = record.get("workspace_fingerprint")
    checkpoint_authority_digest = record.get("authority_digest")
    workspace_exact = checkpoint_fingerprint == args.current_workspace_fingerprint
    authority_exact = checkpoint_authority_digest == args.current_authority_digest
    exact = workspace_exact and authority_exact

    if current_stage == "CLOSURE_COMPLETE" and exact:
        _emit({
            "status": "TASK_ALREADY_COMPLETE",
            "resume_status": "RESUME_EXACT",
            "current_stage": current_stage,
            "next_stage": None,
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
        "current_workspace_fingerprint": args.current_workspace_fingerprint,
        "checkpoint_authority_digest": checkpoint_authority_digest,
        "current_authority_digest": args.current_authority_digest,
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
    init.add_argument("--authority-digest", required=True)
    init.add_argument("--workspace-fingerprint", required=True)
    init.add_argument("--pack-revision", type=int, default=0)
    init.add_argument("--evidence-json")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    advance = sub.add_parser("advance", help="atomically advance exactly one lifecycle stage")
    advance.add_argument("--root", required=True)
    advance.add_argument("--checkpoint", required=True)
    advance.add_argument("--task-id", required=True)
    advance.add_argument("--stage", choices=STAGES[1:], required=True)
    advance.add_argument("--workspace-fingerprint", required=True)
    advance.add_argument("--authority-digest", required=True)
    advance.add_argument("--pack-revision", type=int, required=True)
    advance.add_argument("--evidence-json")
    advance.set_defaults(func=cmd_advance)

    resume = sub.add_parser("resume-validate", help="validate whether latest completed stage can be reused")
    resume.add_argument("--root", required=True)
    resume.add_argument("--checkpoint", required=True)
    resume.add_argument("--task-id", required=True)
    resume.add_argument("--workspace-identity", required=True)
    resume.add_argument("--authority-root", default="docs/authority")
    resume.add_argument("--current-authority-digest", required=True)
    resume.add_argument("--current-workspace-fingerprint", required=True)
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
