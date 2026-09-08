#!/usr/bin/env python3
"""Fail closed when normal Web forms expose relation IDs or raw runtime enums.

The gate intentionally allows read-only IDs inside technical/diagnostic sections.  It
only rejects editable Element Plus inputs and raw enum text rendered directly by a
mustache expression or literal status tag.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB_ROOTS = (ROOT / "apps/web/src/views", ROOT / "apps/web/src/components")
RELATION_FIELDS = {
    "project_id",
    "environment_id",
    "business_terminal_id",
    "test_account_id",
    "runner_id",
    "runtime_policy_revision_id",
    "owner_user_id",
    "execution_attempt_id",
    "execution_slot_id",
    "login_strategy_id",
    "runner_resource_identity",
    "owner_execution_identity",
}
RAW_ENUMS = {
    "ACTIVE",
    "DISABLED",
    "ONLINE",
    "OFFLINE",
    "HEALTHY",
    "UNHEALTHY",
    "UNKNOWN",
    "COMPATIBLE",
    "INCOMPATIBLE",
    "UPGRADE_REQUIRED",
    "IDLE",
    "BUSY",
    "AVAILABLE",
    "OCCUPIED",
    "PUBLISHED",
    "READY",
    "IN_USE",
    "RELEASED",
    "EXPIRED",
    "PASS",
    "FAIL",
    "SUCCESS",
    "FAILED",
    "RUNNING",
    "CANCELLED",
    "CONFIGURED",
    "VALID",
    "PENDING",
}
DISALLOWED_FORM_LABELS = {
    "ExecutionAttempt ID",
    "Environment ID",
    "BusinessTerminal ID",
    "TestAccount ID",
    "Runner ID",
    "Project ID",
    "Owner Execution Identity",
    "Runner Resource Identity",
}


def _vue_files() -> list[Path]:
    return sorted(path for root in WEB_ROOTS for path in root.rglob("*.vue"))




def _mask_technical_sections(text: str) -> str:
    pattern = re.compile(
        r'<el-collapse-item\b(?=[^>]*title="[^"]*(?:技术|诊断)[^"]*")[^>]*>.*?</el-collapse-item>',
        re.S,
    )
    def mask(match: re.Match[str]) -> str:
        value = match.group(0)
        return "".join("\n" if char == "\n" else " " for char in value)
    return pattern.sub(mask, text)


def collect_violations() -> list[str]:
    violations: list[str] = []
    input_pattern = re.compile(r"<el-input\b[^>]*?(?:/?>)", re.S)
    model_pattern = re.compile(r'v-model(?::[^=]+)?="([^"]+)"')
    attr_pattern = re.compile(r'(?:label|placeholder|aria-label)="([^"]+)"')
    mustache_pattern = re.compile(r"\{\{([^{}]+)\}\}")

    for path in _vue_files():
        raw_text = path.read_text(encoding="utf-8")
        text = _mask_technical_sections(raw_text)
        relative = path.relative_to(ROOT).as_posix()

        for match in input_pattern.finditer(text):
            tag = match.group(0)
            model_match = model_pattern.search(tag)
            if model_match:
                expression = model_match.group(1)
                if any(re.search(rf"(?:^|\.){re.escape(field)}$", expression) for field in RELATION_FIELDS):
                    line = text.count("\n", 0, match.start()) + 1
                    violations.append(f"{relative}:{line}: editable relation identity {expression}")
            for attribute in attr_pattern.findall(tag):
                if attribute in DISALLOWED_FORM_LABELS:
                    line = text.count("\n", 0, match.start()) + 1
                    violations.append(f"{relative}:{line}: editable technical label {attribute}")

        for match in mustache_pattern.finditer(text):
            expression = " ".join(match.group(1).split())
            if not re.search(r"(?:status|state)$|(?:status|state)\b", expression):
                continue
            if any(helper in expression for helper in ("statusLabel(", "enumLabel(")):
                continue
            # Ternary/comparison expressions are presentation logic rather than direct raw display.
            if any(token in expression for token in ("===", "!==", "?", ":")):
                continue
            line = text.count("\n", 0, match.start()) + 1
            violations.append(f"{relative}:{line}: raw state/status expression {expression}")

        for enum in RAW_ENUMS:
            pattern = re.compile(rf">\s*{re.escape(enum)}\s*<")
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{relative}:{line}: raw enum text {enum}")

    return sorted(set(violations))


def main() -> int:
    violations = collect_violations()
    if violations:
        print("WEB_UI_BUSINESS_SEMANTICS_GATE=FAIL")
        for item in violations:
            print(item)
        return 1
    print("WEB_UI_BUSINESS_SEMANTICS_GATE=PASS")
    print(f"scanned_vue_files={len(_vue_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
