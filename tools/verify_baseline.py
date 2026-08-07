#!/usr/bin/env python3
"""Read-only verification for the frozen R4.1 package Manifest."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "baseline" / "R4.1"
MANIFEST = BASELINE / "MANIFEST.sha256"
EXPECTED_RELEASE = "PDBR-2026.08.06-R4.1"
MANIFEST_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify() -> dict[str, object]:
    expected: dict[str, str] = {}
    parse_errors: list[str] = []
    for raw_line in MANIFEST.read_text(encoding="utf-8").splitlines():
        match = MANIFEST_LINE.fullmatch(raw_line)
        if match is None:
            if raw_line.strip():
                parse_errors.append(raw_line)
            continue
        expected[match.group(2)] = match.group(1)

    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    for relative, expected_hash in expected.items():
        member = BASELINE / Path(relative)
        if not member.is_file():
            missing.append(relative)
        elif (actual_hash := sha256(member)) != expected_hash:
            mismatches.append({"path": relative, "expected": expected_hash, "actual": actual_hash})

    actual = {
        path.relative_to(BASELINE).as_posix()
        for path in BASELINE.rglob("*")
        if path.is_file() and path != MANIFEST
    }
    extra = sorted(actual.difference(expected))
    release_text = (
        BASELINE / "编码冻结基线" / "RELEASE" / "platform_design_baseline_release.yaml"
    ).read_text(encoding="utf-8")
    release_matches = f"release_id: {EXPECTED_RELEASE}" in release_text
    passed = not (parse_errors or missing or mismatches or extra) and release_matches
    return {
        "release_id": EXPECTED_RELEASE,
        "manifest_entries": len(expected),
        "actual_member_files": len(actual),
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "parse_errors": parse_errors,
        "release_matches": release_matches,
        "status": "PASS" if passed else "FAIL",
    }


def main() -> int:
    report = verify()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
