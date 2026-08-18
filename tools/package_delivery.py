#!/usr/bin/env python3
"""Create a clean source delivery ZIP from the controlled workspace.

The archive intentionally excludes dependency/build/runtime/cache output. Task-local runtime output is transient and excluded; Living Authority and source files are included.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.governance.workspace_path_policy import classify_path, iter_policy_files, load_policy


def iter_delivery_files(root: Path) -> Iterable[Path]:
    """Enumerate delivery members using the canonical WORKSPACE_PATH_POLICY."""
    yield from iter_policy_files(root.resolve(), "delivery_package", load_policy(root.resolve()))

def _forbidden_member(name: str) -> bool:
    # Archive members include the workspace root directory as their first segment.
    rel_parts = Path(name).parts[1:]
    if not rel_parts:
        return False
    pseudo_root = Path("/")
    pseudo_path = pseudo_root.joinpath(*rel_parts)
    # Use category names rather than a second local skip list.
    category = classify_path(pseudo_root, pseudo_path, load_policy(ROOT))
    allowed = set(load_policy(ROOT)["consumers"]["delivery_package"]["include_categories"])
    return category not in allowed

def verify_archive(path: Path) -> dict[str, object]:
    forbidden: list[str] = []
    non_utf8_unicode: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        infos = archive.infolist()
        for info in infos:
            if _forbidden_member(info.filename):
                forbidden.append(info.filename)
            if any(ord(ch) > 127 for ch in info.filename) and not (info.flag_bits & 0x800):
                non_utf8_unicode.append(info.filename)
    return {
        "status": "PASS" if not forbidden and not non_utf8_unicode and bad_crc is None else "FAIL",
        "entry_count": len(infos),
        "forbidden_entries": forbidden,
        "unicode_entries_without_utf8_flag": non_utf8_unicode,
        "crc_error": bad_crc,
    }


def create_archive(root: Path, output: Path) -> dict[str, object]:
    root = root.resolve()
    output = output.resolve()
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("PACKAGE_OUTPUT_INSIDE_WORKSPACE_FORBIDDEN")
    if output.exists():
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = root.name
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in iter_delivery_files(root):
            rel = path.relative_to(root).as_posix()
            archive.write(path, f"{prefix}/{rel}")
    result = verify_archive(output)
    result["output"] = str(output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    create.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = create_archive(args.root, args.output) if args.command == "create" else verify_archive(args.archive)
    except ValueError as exc:
        result = {"status": "BLOCKED", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else (2 if result["status"] == "BLOCKED" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
