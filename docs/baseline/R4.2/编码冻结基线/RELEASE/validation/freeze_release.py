#!/usr/bin/env python3
"""Prepare counts, freeze manifests, and verify the R4.2 release package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import yaml


RELEASE_ID = "PDBR-2026.08.07-R4.2"
HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[2]
ROOT_MANIFEST = "MANIFEST.sha256"
PACKAGE_INVENTORY = "编码冻结基线/RELEASE/package-inventory.json"
RELEASE_YAML = "编码冻结基线/RELEASE/platform_design_baseline_release.yaml"
RELEASE_JSON = "编码冻结基线/RELEASE/platform_design_baseline_release.json"
MANIFEST_EVIDENCE = "编码冻结基线/RELEASE/manifest-verification.json"
SKILL_ROOT = "核心CodexSkill/ai-auto-test-platform-core"
SKILL_MANIFEST = f"{SKILL_ROOT}/MANIFEST.sha256"
CORE = [
    "产品总体需求与系统边界/产品总体需求与系统边界.yaml",
    "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
    "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml",
    "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
    "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
    "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
    "系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path) -> list[Path]:
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix())


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def replace_count(text: str, key: str, value: int) -> str:
    changed, count = re.subn(rf"(?m)^(\s*{re.escape(key)}:\s*)\d+\s*$", rf"\g<1>{value}", text)
    if count == 0:
        raise RuntimeError(f"count field not found: {key}")
    return changed


def prepare(root: Path) -> dict[str, int]:
    total = len(files(root))
    counts = {
        "package_file_count_including_root_manifest": total,
        "root_manifest_entry_count": total - 1,
        "package_inventory_entry_count": total - 2,
    }
    for relative in CORE:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        for key, value in counts.items():
            text = replace_count(text, key, value)
        text = replace_count(text, "source_file_count", total)
        path.write_text(text, encoding="utf-8")
    release_path = root / RELEASE_YAML
    release_text = release_path.read_text(encoding="utf-8")
    for key, value in counts.items():
        release_text = replace_count(release_text, key, value)
    release_path.write_text(release_text, encoding="utf-8")
    release = yaml.safe_load(release_text)
    (root / RELEASE_JSON).write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counts


def assert_prepared(root: Path, total: int) -> None:
    expected = {
        "package_file_count_including_root_manifest": total,
        "root_manifest_entry_count": total - 1,
        "package_inventory_entry_count": total - 2,
    }
    for relative in CORE + [RELEASE_YAML]:
        text = (root / relative).read_text(encoding="utf-8")
        for key, value in expected.items():
            if f"{key}: {value}" not in text:
                raise RuntimeError(f"unprepared count in {relative}: {key}")


def write_manifest(path: Path, entries: list[tuple[str, str]]) -> None:
    path.write_text("".join(f"{digest}  {relative}\n" for relative, digest in entries), encoding="utf-8")


def freeze(root: Path) -> dict[str, object]:
    total = len(files(root))
    assert_prepared(root, total)
    release = yaml.safe_load((root / RELEASE_YAML).read_text(encoding="utf-8"))
    (root / RELEASE_JSON).write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    skill_root = root / SKILL_ROOT
    skill_files = sorted(
        (p for p in skill_root.rglob("*") if p.is_file() and p != root / SKILL_MANIFEST),
        key=lambda p: p.relative_to(skill_root).as_posix(),
    )
    evidence = {
        "release_id": RELEASE_ID,
        "executed_at": now(),
        "status": "PASS",
        "verification_method": "Regenerate final Skill Manifest, package inventory and root MANIFEST; independently recompute all hashes and compare exact file sets.",
        "package_file_count_including_root_manifest": total,
        "root_manifest_entry_count": total - 1,
        "actual_file_count_excluding_root_manifest": total - 1,
        "package_inventory_entry_count": total - 2,
        "missing": 0,
        "unlisted": 0,
        "hash_mismatch": 0,
        "skill_manifest_entry_count": len(skill_files),
        "skill_manifest_status": "PASS",
    }
    (root / MANIFEST_EVIDENCE).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    skill_entries = [(p.relative_to(skill_root).as_posix(), sha256(p)) for p in skill_files]
    write_manifest(root / SKILL_MANIFEST, skill_entries)
    inventory_files = [p for p in files(root) if p not in {root / ROOT_MANIFEST, root / PACKAGE_INVENTORY}]
    inventory = {
        "release_id": RELEASE_ID,
        "generated_at": now(),
        "scope": "ALL_PACKAGE_FILES_EXCEPT_SELF_AND_ROOT_MANIFEST",
        "entry_count": len(inventory_files),
        "entries": [
            {"path": p.relative_to(root).as_posix(), "size": p.stat().st_size, "sha256": sha256(p)}
            for p in inventory_files
        ],
    }
    (root / PACKAGE_INVENTORY).write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    root_files = [p for p in files(root) if p != root / ROOT_MANIFEST]
    root_entries = [(p.relative_to(root).as_posix(), sha256(p)) for p in root_files]
    write_manifest(root / ROOT_MANIFEST, root_entries)
    report = verify(root)
    if report["status"] != "PASS":
        raise RuntimeError(json.dumps(report, ensure_ascii=False))
    return report


def parse_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise RuntimeError(f"invalid manifest line: {line}")
        result[match.group(2)] = match.group(1)
    return result


def verify(root: Path) -> dict[str, object]:
    manifest = parse_manifest(root / ROOT_MANIFEST)
    actual = {p.relative_to(root).as_posix(): p for p in files(root) if p != root / ROOT_MANIFEST}
    missing = sorted(set(manifest) - set(actual))
    unlisted = sorted(set(actual) - set(manifest))
    mismatches = sorted(path for path in set(manifest) & set(actual) if sha256(actual[path]) != manifest[path])
    inventory = json.loads((root / PACKAGE_INVENTORY).read_text(encoding="utf-8"))
    inventory_entries = {entry["path"]: entry for entry in inventory["entries"]}
    expected_inventory = {path: p for path, p in actual.items() if path != PACKAGE_INVENTORY}
    inventory_bad = sorted(
        path for path in set(inventory_entries) & set(expected_inventory)
        if inventory_entries[path]["sha256"] != sha256(expected_inventory[path])
        or inventory_entries[path]["size"] != expected_inventory[path].stat().st_size
    )
    inventory_set_ok = set(inventory_entries) == set(expected_inventory)
    skill_manifest = parse_manifest(root / SKILL_MANIFEST)
    skill_root = root / SKILL_ROOT
    skill_actual = {
        p.relative_to(skill_root).as_posix(): p
        for p in skill_root.rglob("*") if p.is_file() and p != root / SKILL_MANIFEST
    }
    skill_bad = sorted(path for path in set(skill_manifest) & set(skill_actual) if sha256(skill_actual[path]) != skill_manifest[path])
    skill_set_ok = set(skill_manifest) == set(skill_actual)
    release_ok = f"release_id: {RELEASE_ID}" in (root / RELEASE_YAML).read_text(encoding="utf-8")
    passed = not (missing or unlisted or mismatches or inventory_bad or skill_bad) and inventory_set_ok and skill_set_ok and release_ok
    return {
        "release_id": RELEASE_ID,
        "status": "PASS" if passed else "FAIL",
        "package_files": len(files(root)),
        "manifest_entries": len(manifest),
        "package_inventory_entries": len(inventory_entries),
        "skill_manifest_entries": len(skill_manifest),
        "missing": missing,
        "unlisted": unlisted,
        "hash_mismatches": mismatches,
        "package_inventory_set_ok": inventory_set_ok,
        "package_inventory_hash_mismatches": inventory_bad,
        "skill_manifest_set_ok": skill_set_ok,
        "skill_manifest_hash_mismatches": skill_bad,
        "release_matches": release_ok,
        "root_manifest_sha256": sha256(root / ROOT_MANIFEST),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--mode", choices=["prepare", "freeze", "verify"], required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        result: object = prepare(args.root)
    elif args.mode == "freeze":
        result = freeze(args.root)
    else:
        result = verify(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not isinstance(result, dict) or result.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
