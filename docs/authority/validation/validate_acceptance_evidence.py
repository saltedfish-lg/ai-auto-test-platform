#!/usr/bin/env python3
"""Validate mechanical integrity of PASSED/VERIFIED Acceptance evidence.

This gate does not decide whether a business assertion is semantically correct. It prevents
status-only closure by requiring every PASSED Acceptance to have one portable, direct mapping
entry whose referenced implementation/tests/runtime evidence are mechanically resolvable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402
REPO_ROOT = ensure_repo_root_on_path(__file__)
from tools.governance.source_anchors import authority_anchor_exists, implementation_anchor_exists, test_anchor_exists, pytest_nodeid_exists, vitest_case_exists  # noqa: E402

AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
DEFAULT_MAPPING_REL = "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-evidence-mapping.json"
ABSOLUTE_WINDOWS = re.compile(r"^[A-Za-z]:[\\/]")


def _is_absolute_reference(value: str) -> bool:
    return value.startswith("/") or bool(ABSOLUTE_WINDOWS.match(value))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: root must be an object")
    return value


def _resolve_repo_ref(repo_root: Path, value: str) -> Path | None:
    if not value or _is_absolute_reference(value):
        return None
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return candidate


def _validate_test_execution_evidence(repo_root: Path, test_path: Path, test_nodeid: str, *, test_runner: str | None = None) -> list[str]:
    errors: list[str] = []
    if test_runner == "pytest" and not pytest_nodeid_exists(repo_root, test_nodeid):
        errors.append(f"pytest nodeid does not resolve: {test_nodeid}")
    elif test_runner == "vitest" and not vitest_case_exists(test_path, test_nodeid):
        errors.append(f"vitest case does not resolve: {test_nodeid}")
    return errors


def validate(root: Path) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    root = root.resolve()
    repo_root = root.parents[1]
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def add(name: str, passed: bool, detail: str, issues: list[str] | None = None) -> None:
        issue_list = issues or []
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail, "errors": issue_list})
        if not passed:
            errors.extend(f"{name}: {issue}" for issue in issue_list or [detail])

    acceptance_path = root / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json"
    try:
        acceptance = _load_json(acceptance_path)
        items = acceptance.get("acceptance_closure", [])
        if not isinstance(items, list):
            raise ValueError("acceptance_closure must be a list")
    except Exception as exc:
        add("ACC-EVIDENCE-AUTHORITY-LOAD", False, "acceptance authority load failed", [str(exc)])
        return checks, errors, {"passed_acceptance": 0, "mapped_acceptance": 0}

    ids = [item.get("acceptance_id") for item in items if isinstance(item, dict)]
    duplicate_ids = sorted({value for value in ids if isinstance(value, str) and ids.count(value) > 1})
    add("ACC-EVIDENCE-UNIQUE-IDS", not duplicate_ids, f"acceptance_ids={len(ids)}", [f"duplicate {x}" for x in duplicate_ids])

    passed = {
        str(item["acceptance_id"]): item
        for item in items
        if isinstance(item, dict) and item.get("status") == "PASSED"
    }
    incoherent = [
        str(item.get("acceptance_id"))
        for item in items
        if isinstance(item, dict)
        and ((item.get("status") == "PASSED") != (item.get("evidence_status") == "VERIFIED"))
    ]
    add("ACC-EVIDENCE-STATUS-COHERENCE", not incoherent, f"passed={len(passed)}", incoherent)

    integrity = acceptance.get("metadata", {}).get("acceptance_evidence_integrity", {})
    mapping_rel = integrity.get("portable_mapping_path", DEFAULT_MAPPING_REL)
    if _is_absolute_reference(str(mapping_rel)):
        add("ACC-EVIDENCE-MAPPING-POLICY", False, "mapping path must be portable", [str(mapping_rel)])
        mapping_rel = DEFAULT_MAPPING_REL
    else:
        add(
            "ACC-EVIDENCE-MAPPING-POLICY",
            integrity.get("validator") == "docs/authority/validation/validate_acceptance_evidence.py"
            and integrity.get("absolute_local_paths_are_not_portable_evidence") is True
            and integrity.get("runtime_result_policy") == "CURRENT_TASK_ONLY_NOT_AUTHORITY",
            f"mapping={mapping_rel}",
            [] if integrity else ["acceptance_evidence_integrity metadata missing"],
        )

    mapping_path = root / str(mapping_rel)
    if not passed:
        add(
            "ACC-EVIDENCE-DIRECT-MAPPING",
            True,
            "no PASSED acceptance exists; portable mapping is not required until a PASSED/VERIFIED transition is proposed",
        )
        mapped_count = 0
    else:
        map_errors: list[str] = []
        mapped_count = 0
        if not mapping_path.is_file():
            map_errors.append(f"PASSED acceptance requires portable mapping: {mapping_rel}")
        else:
            try:
                mapping = _load_json(mapping_path)
                if mapping.get("schema_version") != 3:
                    map_errors.append(f"mapping schema_version must be 3, got {mapping.get('schema_version')}")
                if mapping.get("authority_model") != AUTHORITY_MODEL:
                    map_errors.append("mapping authority_model mismatch")
                mapping_items = mapping.get("items", [])
                if not isinstance(mapping_items, list):
                    raise ValueError("mapping items must be a list")
                by_id: dict[str, list[dict[str, Any]]] = {}
                for entry in mapping_items:
                    if not isinstance(entry, dict) or not isinstance(entry.get("acceptance_id"), str):
                        map_errors.append("mapping contains item without acceptance_id")
                        continue
                    by_id.setdefault(entry["acceptance_id"], []).append(entry)
                extras = sorted(set(by_id) - set(passed))
                if extras:
                    map_errors.append(f"mapping contains non-PASSED acceptance ids: {extras[:20]}")
                for acceptance_id, item in passed.items():
                    entries = by_id.get(acceptance_id, [])
                    if len(entries) != 1:
                        map_errors.append(f"{acceptance_id}: expected exactly one mapping entry, got {len(entries)}")
                        continue
                    mapped_count += 1
                    entry = entries[0]
                    if entry.get("final_status") != "PASSED":
                        map_errors.append(f"{acceptance_id}: mapping final_status must be PASSED")
                    authority_refs = entry.get("authority_refs")
                    if not isinstance(authority_refs, list) or not authority_refs:
                        map_errors.append(f"{acceptance_id}: authority_refs missing")
                    else:
                        for ref in authority_refs:
                            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
                                map_errors.append(f"{acceptance_id}: authority_refs must use portable path + anchor objects")
                                continue
                            resolved = _resolve_repo_ref(repo_root, ref["path"])
                            if resolved is None or not resolved.is_file():
                                map_errors.append(f"{acceptance_id}: authority path missing/non-portable: {ref.get('path')}")
                                continue
                            if not authority_anchor_exists(resolved, ref):
                                map_errors.append(f"{acceptance_id}: authority anchor does not mechanically resolve: {ref.get('path')}")
                    impl_refs = entry.get("implementation_refs")
                    if not isinstance(impl_refs, list) or not impl_refs:
                        map_errors.append(f"{acceptance_id}: implementation_refs missing")
                    else:
                        for ref in impl_refs:
                            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
                                map_errors.append(f"{acceptance_id}: invalid implementation ref")
                                continue
                            resolved = _resolve_repo_ref(repo_root, ref["path"])
                            if resolved is None or not resolved.is_file():
                                map_errors.append(f"{acceptance_id}: implementation path missing/non-portable: {ref.get('path')}")
                                continue
                            if not implementation_anchor_exists(resolved, ref):
                                map_errors.append(f"{acceptance_id}: implementation anchor does not mechanically resolve: {ref.get('path')}")
                    evidence = entry.get("direct_evidence")
                    if not isinstance(evidence, list) or not evidence:
                        map_errors.append(f"{acceptance_id}: direct_evidence missing")
                        continue
                    for ref in evidence:
                        if not isinstance(ref, dict) or ref.get("result") != "PASS" or not ref.get("assertion"):
                            map_errors.append(f"{acceptance_id}: each direct_evidence item requires result=PASS and a specific assertion")
                            continue
                        kind = ref.get("kind")
                        if kind == "TEST":
                            path_value = ref.get("path")
                            if not isinstance(path_value, str):
                                map_errors.append(f"{acceptance_id}: TEST evidence path missing")
                                continue
                            resolved = _resolve_repo_ref(repo_root, path_value)
                            if resolved is None or not resolved.is_file():
                                map_errors.append(f"{acceptance_id}: TEST evidence path missing/non-portable: {path_value}")
                                continue
                            if not test_anchor_exists(repo_root, resolved, ref):
                                map_errors.append(f"{acceptance_id}: TEST anchor/nodeid does not mechanically resolve: {path_value}")
                            test_nodeid = ref.get("test_nodeid")
                            if not isinstance(test_nodeid, str) or not test_nodeid:
                                map_errors.append(f"{acceptance_id}: TEST evidence requires test_nodeid")
                            else:
                                map_errors.extend(f"{acceptance_id}: {e}" for e in _validate_test_execution_evidence(repo_root, resolved, test_nodeid, test_runner=ref.get("test_runner")))
                        elif kind == "RUNTIME_GATE":
                            gate_id = ref.get("gate_id")
                            if not isinstance(gate_id, str):
                                map_errors.append(f"{acceptance_id}: RUNTIME_GATE requires gate_id")
                                continue
                            design = yaml.safe_load((root / "编码权威事实/SYSTEM_DESIGN.yaml").read_text(encoding="utf-8"))
                            known = {x.get("gate_id") for x in (design.get("runtime_gate_catalog") or {}).get("gates", []) if isinstance(x, dict)}
                            if gate_id not in known:
                                map_errors.append(f"{acceptance_id}: unknown runtime gate_id {gate_id}")
                        else:
                            map_errors.append(f"{acceptance_id}: unsupported direct evidence kind {kind!r}")
            except Exception as exc:
                map_errors.append(str(exc))
        add("ACC-EVIDENCE-DIRECT-MAPPING", not map_errors, f"passed={len(passed)} mapped={mapped_count}", map_errors[:200])

    projection_errors: list[str] = []
    safety_path = root / "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml"
    try:
        safety = yaml.safe_load(safety_path.read_text(encoding="utf-8"))
        conclusion = safety.get("conclusion", {}) if isinstance(safety, dict) else {}
        p1 = safety.get("p1_authentication_security_contract", {}) if isinstance(safety, dict) else {}
        if "acceptance_passed" in conclusion:
            projection_errors.append("data-safety conclusion must not duplicate volatile acceptance_passed")
        if conclusion.get("acceptance_passed_source") != "tools/current_facts.py#acceptance.passed_count":
            projection_errors.append("data-safety acceptance_passed_source must delegate to tools/current_facts.py")
        if "acceptance_status" in p1:
            projection_errors.append("data-safety P1 contract must not duplicate volatile acceptance_status")
        expected_status_source = "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json#acceptance_closure.status"
        if p1.get("acceptance_status_source") != expected_status_source:
            projection_errors.append("data-safety P1 acceptance_status_source must delegate to ACCEPTANCE_CLOSURE")
    except Exception as exc:
        projection_errors.append(str(exc))
    add("ACC-EVIDENCE-NO-DUPLICATED-STATUS-PROJECTION", not projection_errors, "volatile acceptance status has one canonical owner", projection_errors)

    metrics = {"acceptance_total": len(items), "passed_acceptance": len(passed), "mapped_acceptance": mapped_count}
    return checks, errors, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks, errors, metrics = validate(args.root)
    report = {
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
        "validator": "validate_acceptance_evidence.py",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS" if not errors else "FAIL",
        "metrics": metrics,
        "checks": checks,
        "error_count": len(errors),
        "errors": errors,
    }
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
