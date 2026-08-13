#!/usr/bin/env python3
"""Changed-symbol comment quality gate.

The gate consumes explicit Task change-scope evidence (changed symbols and/or changed
line ranges). It never treats "file changed" as permission to retroactively scan every
historical symbol in a large source file. Only complex/risk-bearing symbols that overlap
the current Task scope are evaluated, and acceptable comments must explain a reason,
invariant, or failure-prevention intent in Chinese rather than merely contain Chinese text.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import ast
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

EXIT_OK = 0
EXIT_POLICY = 2
EXIT_INVALID = 4

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
COMMENT_LINE_RE = re.compile(r"(?m)^\s*(#|//|/\*|\*)\s*(?P<body>.*)$")
REASON_MARKERS = (
    "避免", "防止", "确保", "保证", "否则", "因为", "为了", "以免", "从而", "因此",
    "用于防", "必须", "保持", "防护", "隔离", "回滚", "失效", "不变量",
)
GENERATED_PARTS = {"generated", "dist", "node_modules", ".venv", "venv"}
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue"}
BUSINESS_ROOTS = {"services", "packages", "workers", "runner", "apps"}
_WEB_SYMBOL_PARSER = None
_WORKSPACE_SNAPSHOT_MODULE = None
RISK_KEYWORDS = {
    "auth", "authorize", "permission", "rbac", "security", "secret", "password", "token",
    "transaction", "commit", "rollback", "idempot", "lock", "lease", "fencing", "concurr",
    "retry", "compens", "audit", "outbox", "state", "transition", "refresh", "replay",
    "runner", "worker", "scheduler", "session", "credential", "expected_version",
}


@dataclass
class Finding:
    path: str
    symbol: str
    reason: str
    start_line: int
    end_line: int

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "symbol": self.symbol,
            "reason": self.reason,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass
class ChangeScope:
    path: Path
    symbols: set[str] = field(default_factory=set)
    line_ranges: list[tuple[int, int]] = field(default_factory=list)


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _normalize_range(value: object) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("CHANGE_LINE_RANGE_INVALID")
    start, end = value
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise ValueError("CHANGE_LINE_RANGE_INVALID")
    return start, end


def _resolve_business_path(root: Path, raw: str) -> Path:
    p = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if not _inside(root, p):
        raise ValueError(f"PATH_OUTSIDE_WORKSPACE:{raw}")
    return p


def _merge_scope(scopes: dict[Path, ChangeScope], path: Path, symbols: Iterable[str], ranges: Iterable[tuple[int, int]]) -> None:
    scope = scopes.setdefault(path, ChangeScope(path=path))
    scope.symbols.update(s for s in symbols if s)
    scope.line_ranges.extend(ranges)


def _load_changes_file(root: Path, path: Path) -> dict[Path, ChangeScope]:
    if not path.is_file():
        raise ValueError("CHANGES_FILE_NOT_FOUND")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("CHANGES_FILE_INVALID_JSON") from exc
    scopes: dict[Path, ChangeScope] = {}

    # Preferred schema: {"changes": [{"path": ..., "symbols": [...], "line_ranges": [[s,e]]}]}
    if isinstance(data, dict) and isinstance(data.get("changes"), list):
        for item in data["changes"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("CHANGES_FILE_INVALID")
            symbols = item.get("symbols", item.get("changed_symbols", []))
            ranges = item.get("line_ranges", item.get("changed_line_ranges", []))
            if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
                raise ValueError("CHANGE_SYMBOLS_INVALID")
            if not isinstance(ranges, list):
                raise ValueError("CHANGE_LINE_RANGES_INVALID")
            _merge_scope(
                scopes,
                _resolve_business_path(root, item["path"]),
                symbols,
                [_normalize_range(r) for r in ranges],
            )
        return scopes

    # Task Context Pack-friendly schema: path-keyed changed_symbols / changed_line_ranges maps.
    if isinstance(data, dict):
        symbols_map = data.get("changed_symbols", {})
        ranges_map = data.get("changed_line_ranges", {})
        if isinstance(symbols_map, dict) or isinstance(ranges_map, dict):
            keys = set(symbols_map.keys() if isinstance(symbols_map, dict) else []) | set(ranges_map.keys() if isinstance(ranges_map, dict) else [])
            for raw in keys:
                if not isinstance(raw, str):
                    raise ValueError("CHANGES_FILE_INVALID")
                symbols = symbols_map.get(raw, []) if isinstance(symbols_map, dict) else []
                ranges = ranges_map.get(raw, []) if isinstance(ranges_map, dict) else []
                if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
                    raise ValueError("CHANGE_SYMBOLS_INVALID")
                if not isinstance(ranges, list):
                    raise ValueError("CHANGE_LINE_RANGES_INVALID")
                _merge_scope(scopes, _resolve_business_path(root, raw), symbols, [_normalize_range(r) for r in ranges])
            return scopes

    raise ValueError("CHANGES_FILE_INVALID")


def _workspace_snapshot_module():
    global _WORKSPACE_SNAPSHOT_MODULE
    if _WORKSPACE_SNAPSHOT_MODULE is not None:
        return _WORKSPACE_SNAPSHOT_MODULE
    snapshot = (
        Path(__file__).resolve().parents[2]
        / "ai-auto-test-platform-context-efficiency"
        / "scripts"
        / "workspace_snapshot.py"
    )
    spec = importlib.util.spec_from_file_location("_comment_gate_workspace_snapshot", snapshot)
    if spec is None or spec.loader is None:
        raise ValueError("WORKSPACE_SNAPSHOT_PROVIDER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    _WORKSPACE_SNAPSHOT_MODULE = module
    return module


def _checkpoint_checksum(data: dict[str, object]) -> str:
    payload = {k: v for k, v in data.items() if k != "checksum"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_checkpoint_start_evidence(root: Path, checkpoint: Path) -> tuple[str, str]:
    if not checkpoint.is_file():
        raise ValueError("TASK_CHECKPOINT_NOT_FOUND")
    if _inside(root, checkpoint):
        raise ValueError("TASK_CHECKPOINT_MUST_BE_EXTERNAL")
    try:
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("TASK_CHECKPOINT_INVALID_JSON") from exc
    if not isinstance(data, dict) or data.get("checksum") != _checkpoint_checksum(data):
        raise ValueError("TASK_CHECKPOINT_CORRUPTED")
    if data.get("workspace_root") != str(root.resolve()):
        raise ValueError("TASK_CHECKPOINT_WORKSPACE_MISMATCH")
    lifecycle_profile = data.get("lifecycle_profile", "FULL")
    if lifecycle_profile not in {"FULL", "LIGHTWEIGHT_LOCAL"}:
        raise ValueError("TASK_CHECKPOINT_LIFECYCLE_PROFILE_INVALID")
    stages = data.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("TASK_CHECKPOINT_CORRUPTED")
    initial = stages.get("TASK_INITIALIZED")
    if not isinstance(initial, dict):
        raise ValueError("TASK_CHECKPOINT_START_EVIDENCE_MISSING")
    evidence = initial.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("TASK_CHECKPOINT_START_EVIDENCE_MISSING")
    mechanical = evidence.get("mechanical_workspace_snapshot")
    if not isinstance(mechanical, dict):
        raise ValueError("TASK_CHECKPOINT_START_EVIDENCE_MISSING")
    digest = mechanical.get("snapshot_evidence_digest")
    if not isinstance(digest, str) or not digest:
        raise ValueError("TASK_CHECKPOINT_START_EVIDENCE_MISSING")
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("TASK_CHECKPOINT_TASK_ID_MISSING")
    return digest, task_id


def _load_task_delta(root: Path, path: Path, checkpoint: Path) -> tuple[dict[Path, ChangeScope], dict[str, str]]:
    if not path.is_file():
        raise ValueError("TASK_DELTA_NOT_FOUND")
    if _inside(root, path):
        raise ValueError("TASK_DELTA_MUST_BE_EXTERNAL")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("TASK_DELTA_INVALID_JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("TASK_DELTA_INVALID")
    task_start = data.get("task_start")
    supplied_current = data.get("current")
    supplied_delta = data.get("task_delta")
    if not isinstance(task_start, dict) or not isinstance(supplied_current, dict) or not isinstance(supplied_delta, dict):
        raise ValueError("TASK_DELTA_MECHANICAL_EVIDENCE_INCOMPLETE")

    snapshot_module = _workspace_snapshot_module()
    for snapshot, role in ((task_start, "TASK_START"), (supplied_current, "DELTA_CURRENT")):
        valid, reason = snapshot_module.validate_snapshot_evidence(snapshot)
        if not valid:
            raise ValueError(f"{role}_{reason or 'SNAPSHOT_INVALID'}")
        if Path(str(snapshot.get("root", ""))).resolve() != root.resolve():
            raise ValueError(f"{role}_WORKSPACE_MISMATCH")

    expected_start_digest, task_id = _load_checkpoint_start_evidence(root, checkpoint)
    if task_start.get("snapshot_evidence_digest") != expected_start_digest:
        raise ValueError("TASK_START_SNAPSHOT_NOT_BOUND_TO_CHECKPOINT")

    actual_current = snapshot_module.capture_workspace(root)
    valid, reason = snapshot_module.validate_snapshot_evidence(actual_current)
    if not valid:
        raise ValueError(reason or "CURRENT_SNAPSHOT_INVALID")
    if supplied_current.get("snapshot_evidence_digest") != actual_current.get("snapshot_evidence_digest"):
        raise ValueError("TASK_DELTA_STALE_REPLAY")

    recomputed = snapshot_module.compare_snapshots(task_start, actual_current)
    if recomputed.get("status") == "UNAVAILABLE":
        raise ValueError("TASK_DELTA_UNAVAILABLE")
    if supplied_delta != recomputed:
        raise ValueError("TASK_DELTA_RECOMPUTE_MISMATCH")
    if recomputed.get("change_scope_provenance") != "FILESYSTEM_SNAPSHOT_V4":
        raise ValueError("UNTRUSTED_CHANGE_SCOPE_EVIDENCE")

    symbols_map = recomputed.get("changed_symbols", {})
    ranges_map = recomputed.get("changed_line_ranges", {})
    if not isinstance(symbols_map, dict) or not isinstance(ranges_map, dict):
        raise ValueError("TASK_DELTA_SCOPE_INVALID")
    scopes: dict[Path, ChangeScope] = {}
    for raw in sorted(set(symbols_map) | set(ranges_map)):
        if not isinstance(raw, str):
            raise ValueError("TASK_DELTA_SCOPE_INVALID")
        symbols = symbols_map.get(raw, [])
        ranges = ranges_map.get(raw, [])
        if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
            raise ValueError("TASK_DELTA_SCOPE_INVALID")
        if not isinstance(ranges, list):
            raise ValueError("TASK_DELTA_SCOPE_INVALID")
        _merge_scope(scopes, _resolve_business_path(root, raw), symbols, [_normalize_range(r) for r in ranges])
    material = {
        "task_id": task_id,
        "task_start_snapshot_evidence_digest": expected_start_digest,
        "current_snapshot_evidence_digest": str(actual_current.get("snapshot_evidence_digest", "")),
        "workspace_fingerprint": str(actual_current.get("workspace_digest", "")),
        "task_delta_digest": str(recomputed.get("delta_digest", "")),
        "change_scope_digest": str(recomputed.get("change_scope_digest", "")),
        "task_delta_status": str(recomputed.get("status", "")),
    }
    return scopes, material


def _checkpoint_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "ai-auto-test-platform-feature-orchestrator"
        / "scripts"
        / "task_checkpoint.py"
    )
    spec = importlib.util.spec_from_file_location("_comment_gate_task_checkpoint", path)
    if spec is None or spec.loader is None:
        raise ValueError("TASK_CHECKPOINT_PROVIDER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _attest_formal_pass(root: Path, checkpoint: Path, material: dict[str, str]) -> None:
    module = _checkpoint_module()
    function = getattr(module, "_comment_quality_gate_pass", None)
    if not callable(function):
        raise ValueError("TASK_CHECKPOINT_COMMENT_GATE_API_UNAVAILABLE")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = int(function(argparse.Namespace(
            root=str(root),
            checkpoint=str(checkpoint),
            task_id=material["task_id"],
            task_start_snapshot_evidence_digest=material["task_start_snapshot_evidence_digest"],
            current_snapshot_evidence_digest=material["current_snapshot_evidence_digest"],
            workspace_fingerprint=material["workspace_fingerprint"],
            task_delta_digest=material["task_delta_digest"],
            change_scope_digest=material["change_scope_digest"],
            task_delta_status=material["task_delta_status"],
        )))
    if rc != 0:
        detail = output.getvalue().strip()
        raise ValueError(f"COMMENT_GATE_ATTESTATION_WRITE_FAILED:{detail or rc}")


def _parse_inline_scopes(root: Path, symbols: list[str], ranges: list[str]) -> dict[Path, ChangeScope]:
    scopes: dict[Path, ChangeScope] = {}
    for raw in symbols:
        if "::" not in raw:
            raise ValueError("CHANGED_SYMBOL_INVALID")
        path_text, symbol = raw.split("::", 1)
        if not path_text or not symbol:
            raise ValueError("CHANGED_SYMBOL_INVALID")
        _merge_scope(scopes, _resolve_business_path(root, path_text), [symbol], [])
    for raw in ranges:
        try:
            path_text, range_text = raw.rsplit(":", 1)
            start_text, end_text = range_text.split("-", 1)
            line_range = _normalize_range([int(start_text), int(end_text)])
        except (ValueError, TypeError) as exc:
            raise ValueError("CHANGED_RANGE_INVALID") from exc
        _merge_scope(scopes, _resolve_business_path(root, path_text), [], [line_range])
    return scopes


def _is_generated(path: Path, root: Path) -> bool:
    rel = path.resolve().relative_to(root.resolve())
    return any(part in GENERATED_PARTS for part in rel.parts) or path.name.endswith((".generated.ts", ".generated.py"))


def _is_business_source(path: Path, root: Path) -> bool:
    rel = path.resolve().relative_to(root.resolve())
    return bool(rel.parts) and rel.parts[0] in BUSINESS_ROOTS and "tests" not in rel.parts


def _contains_reason(text: str) -> bool:
    chinese_count = len(CHINESE_RE.findall(text))
    if chinese_count < 6:
        return False
    return any(marker in text for marker in REASON_MARKERS)


def _has_reason_comment(text: str) -> bool:
    for match in COMMENT_LINE_RE.finditer(text):
        if _contains_reason(match.group("body")):
            return True
    return False


def _python_comments(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return comments owned by one Python symbol without borrowing from a neighbour.

    Function-body comments are always owned by the function. A leading comment block is
    accepted only when it is directly attached to the declaration/decorator and has the
    same indentation as the declaration. This prevents an indented trailing comment in
    the previous function from satisfying the next function's gate.
    """
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    declaration_start = min([start, *[getattr(item, "lineno", start) for item in getattr(node, "decorator_list", [])]])
    declaration_line = lines[declaration_start - 1] if 0 < declaration_start <= len(lines) else ""
    declaration_indent = len(declaration_line) - len(declaration_line.lstrip(" \t"))

    leading: list[str] = []
    index = declaration_start - 2
    while index >= 0:
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            break
        indent = len(raw) - len(raw.lstrip(" \t"))
        if not stripped.startswith("#") or indent != declaration_indent:
            break
        leading.append(raw)
        index -= 1
    leading.reverse()

    body = lines[start - 1:min(len(lines), end)]
    return "\n".join([*leading, *body])


def _python_complexity(node: ast.AST, source: str) -> tuple[bool, str]:
    text = ast.get_source_segment(source, node) or ""
    lowered = text.lower()
    risk_hits = sorted(k for k in RISK_KEYWORDS if k in lowered)
    branches = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.Match, ast.With)) for n in ast.walk(node))
    calls = sum(isinstance(n, ast.Call) for n in ast.walk(node))
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    span = end - start + 1

    # Risk-domain words are weighting evidence, not an automatic complexity verdict.
    if risk_hits and ((branches >= 1 and calls >= 1) or calls >= 3 or span >= 12):
        return True, "risk-domain:" + ",".join(risk_hits[:6]) + f"/{branches}branches/{calls}calls/{span}lines"
    if branches >= 4:
        return True, f"control-flow-branches:{branches}"
    if span >= 28 and calls >= 5:
        return True, f"nontrivial-symbol:{span}lines/{calls}calls"
    return False, "simple"


def _ranges_overlap(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= range_end and range_start <= end for range_start, range_end in ranges)


def _python_functions(tree: ast.AST) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]:
    result: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = []

    def walk(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{child.name}"
                result.append((child, qualname))
                walk(child, f"{qualname}.")
            else:
                walk(child, prefix)

    walk(tree)
    return result


def _scan_python(path: Path, rel: str, scope: ChangeScope) -> tuple[list[Finding], list[str]]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Finding(rel, "<module>", f"PYTHON_PARSE_ERROR:{exc.msg}", exc.lineno or 1, exc.lineno or 1)], []
    lines = source.splitlines()
    findings: list[Finding] = []
    matched_symbols: set[str] = set()

    for node, qualname in _python_functions(tree):
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        symbol_match = any(s in {node.name, qualname} for s in scope.symbols)
        range_match = _ranges_overlap(start, end, scope.line_ranges)
        if not symbol_match and not range_match:
            continue
        if symbol_match:
            matched_symbols.update(s for s in scope.symbols if s in {node.name, qualname})
        complex_symbol, reason = _python_complexity(node, source)
        if not complex_symbol:
            continue
        doc = ast.get_docstring(node, clean=False) or ""
        context = _python_comments(lines, node)
        if _contains_reason(doc) or _has_reason_comment(context):
            continue
        findings.append(Finding(rel, qualname, reason, start, end))

    missing = sorted(scope.symbols - matched_symbols)
    return findings, missing


def _load_workspace_web_symbols(text: str) -> dict[str, dict[str, object]]:
    """Reuse workspace_snapshot.py symbol boundaries so Gate and delta evidence share one parser."""
    global _WEB_SYMBOL_PARSER
    if _WEB_SYMBOL_PARSER is None:
        try:
            module = _workspace_snapshot_module()
        except ValueError as exc:
            raise RuntimeError("WORKSPACE_SNAPSHOT_SYMBOL_PARSER_UNAVAILABLE") from exc
        parser = getattr(module, "_web_symbols", None)
        if not callable(parser):
            raise RuntimeError("WORKSPACE_SNAPSHOT_SYMBOL_PARSER_UNAVAILABLE")
        _WEB_SYMBOL_PARSER = parser
    parsed = _WEB_SYMBOL_PARSER(text)
    return parsed if isinstance(parsed, dict) else {}


def _web_complexity(scoped: str, start: int, end: int) -> tuple[bool, str]:
    lowered = scoped.lower()
    risk_hits = sorted(k for k in RISK_KEYWORDS if k in lowered)
    branches = len(re.findall(r"\b(if|switch|catch|for|while)\b|\?\s*[^:]+:", scoped))
    calls = len(re.findall(r"\b[A-Za-z_$][\w$\.]*\s*\(", scoped))
    span = end - start + 1
    complex_scope = bool(risk_hits and ((branches >= 1 and calls >= 1) or calls >= 3 or span >= 16)) or branches >= 5 or (span >= 30 and calls >= 5)
    if not complex_scope:
        return False, "simple"
    reason = (
        "risk-domain:" + ",".join(risk_hits[:6]) + f"/{branches}branches/{calls}calls/{span}lines"
        if risk_hits
        else f"control-flow-branches:{branches}"
    )
    return True, reason


def _web_attached_comment_context(lines: list[str], start: int, end: int) -> str:
    """Return comments owned by one Web symbol without borrowing comments from a previous symbol."""
    body = lines[start - 1:end]
    leading: list[str] = []
    index = start - 2
    # Leading comments are attached only when the declaration is immediately preceded by a
    # contiguous comment block (blank lines break ownership). Encountering code/`}` stops
    # scanning, so a reason comment inside the previous function cannot satisfy this symbol.
    in_block = False
    while index >= 0:
        raw = lines[index]
        stripped = raw.strip()
        if not stripped:
            break
        if in_block:
            leading.append(raw)
            if "/*" in stripped:
                in_block = False
            index -= 1
            continue
        if stripped.startswith("//") or stripped.startswith("/*"):
            leading.append(raw)
            index -= 1
            continue
        if stripped.endswith("*/"):
            in_block = True
            leading.append(raw)
            index -= 1
            continue
        break
    leading.reverse()
    return "\n".join([*leading, *body])


def _symbol_candidates(symbols: dict[str, dict[str, object]], requested: str) -> list[tuple[str, dict[str, object]]]:
    if requested in symbols:
        return [(requested, symbols[requested])]
    leaf = requested.split(".")[-1]
    return [(name, meta) for name, meta in symbols.items() if name == leaf or name.startswith(leaf + "@")]


def _scan_web(path: Path, rel: str, scope: ChangeScope) -> tuple[list[Finding], list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        symbols = _load_workspace_web_symbols(text)
    except RuntimeError as exc:
        return [Finding(rel, "<module>", str(exc), 1, max(1, len(lines)))], []

    selected: dict[str, dict[str, object]] = {}
    matched_symbols: set[str] = set()
    for requested in sorted(scope.symbols):
        candidates = _symbol_candidates(symbols, requested)
        if len(candidates) == 1:
            name, meta = candidates[0]
            selected[name] = meta
            matched_symbols.add(requested)
        elif len(candidates) > 1 and requested in {name for name, _ in candidates}:
            name, meta = next((name, meta) for name, meta in candidates if name == requested)
            selected[name] = meta
            matched_symbols.add(requested)

    for name, meta in symbols.items():
        try:
            start = int(meta.get("start_line", 1))
            end = int(meta.get("end_line", start))
        except (TypeError, ValueError):
            continue
        if _ranges_overlap(start, end, scope.line_ranges):
            selected[name] = meta

    findings: list[Finding] = []
    covered_ranges: list[tuple[int, int]] = []
    for name, meta in sorted(selected.items(), key=lambda item: int(item[1].get("start_line", 1))):
        start = max(1, int(meta.get("start_line", 1)))
        end = min(len(lines), int(meta.get("end_line", start)))
        if end < start:
            continue
        covered_ranges.append((start, end))
        body = "\n".join(lines[start - 1:end])
        complex_symbol, reason = _web_complexity(body, start, end)
        if not complex_symbol:
            continue
        comment_context = _web_attached_comment_context(lines, start, end)
        if _has_reason_comment(comment_context):
            continue
        findings.append(Finding(rel, name, reason, start, end))

    # Preserve range-only diagnostics for top-level logic that is not owned by a parsed symbol.
    for range_start, range_end in scope.line_ranges:
        if any(_ranges_overlap(range_start, range_end, [(start, end)]) for start, end in covered_ranges):
            continue
        lo = max(1, range_start)
        hi = min(len(lines), range_end)
        if hi < lo:
            continue
        body = "\n".join(lines[lo - 1:hi])
        complex_scope, reason = _web_complexity(body, lo, hi)
        if not complex_scope:
            continue
        context = "\n".join(lines[max(0, lo - 4):hi])
        if not _has_reason_comment(context):
            findings.append(Finding(rel, f"lines:{lo}-{hi}", reason, lo, hi))

    missing = sorted(scope.symbols - matched_symbols)
    return findings, missing

def run(root: Path, scopes: Iterable[ChangeScope]) -> dict[str, object]:
    findings: list[Finding] = []
    checked: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    scope_errors: list[dict[str, object]] = []

    for scope in scopes:
        path = scope.path
        if not scope.symbols and not scope.line_ranges:
            scope_errors.append({"path": str(path), "error": "CHANGE_SCOPE_EVIDENCE_REQUIRED"})
            continue
        if not path.exists() or not path.is_file():
            skipped.append({"path": str(path), "reason": "NOT_A_FILE_OR_REMOVED"})
            continue
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            skipped.append({"path": rel, "reason": "NON_SOURCE"})
            continue
        if not _is_business_source(path, root):
            skipped.append({"path": rel, "reason": "NON_BUSINESS_SOURCE"})
            continue
        if _is_generated(path, root):
            skipped.append({"path": rel, "reason": "GENERATED_OR_BUILD_OUTPUT"})
            continue

        checked.append({
            "path": rel,
            "changed_symbols": sorted(scope.symbols),
            "changed_line_ranges": [list(r) for r in scope.line_ranges],
        })
        if path.suffix.lower() == ".py":
            local_findings, missing = _scan_python(path, rel, scope)
        else:
            local_findings, missing = _scan_web(path, rel, scope)
        findings.extend(local_findings)
        if missing:
            scope_errors.append({"path": rel, "error": "CHANGED_SYMBOL_NOT_FOUND", "symbols": missing})

    status = "ERROR" if scope_errors else ("FAIL" if findings else "PASS")
    return {
        "gate": "CHANGED_COMPLEX_SYMBOL_COMMENT_GATE",
        "scope": "TASK_CHANGED_SYMBOLS_OR_LINE_RANGES_ONLY",
        "policy": "REASON_COMMENTS_NOT_COMMENT_DENSITY",
        "status": status,
        "checked_scopes": checked,
        "skipped": skipped,
        "scope_errors": scope_errors,
        "findings": [f.as_dict() for f in findings],
        "finding_count": len(findings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reason-oriented comments for changed complex business symbols")
    parser.add_argument("--root", required=True)
    parser.add_argument("--task-delta", help="formal mode: workspace_snapshot.py delta output outside workspace")
    parser.add_argument("--checkpoint", help="formal mode: external Task Checkpoint that binds the task-start snapshot evidence")
    parser.add_argument("--diagnostic-scope", action="store_true", help="allow manually supplied scope only for diagnostics/tests")
    parser.add_argument("--changes-file")
    parser.add_argument("--changed-symbol", action="append", default=[], help="diagnostic only: path::symbol")
    parser.add_argument("--changed-range", action="append", default=[], help="diagnostic only: path:start-end")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "ERROR", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False))
        return EXIT_INVALID
    try:
        scopes: dict[Path, ChangeScope] = {}
        formal_attestation: dict[str, str] | None = None
        formal_mode = bool(args.task_delta)
        manual_scope_requested = bool(args.changes_file or args.changed_symbol or args.changed_range)
        if formal_mode and manual_scope_requested:
            raise ValueError("FORMAL_SCOPE_MUST_BE_MECHANICAL_ONLY")
        if formal_mode:
            if not args.checkpoint:
                raise ValueError("TASK_CHECKPOINT_REQUIRED_FOR_MECHANICAL_DELTA")
            loaded_scopes, formal_attestation = _load_task_delta(root, Path(args.task_delta).resolve(), Path(args.checkpoint).resolve())
            for path, scope in loaded_scopes.items():
                _merge_scope(scopes, path, scope.symbols, scope.line_ranges)
        else:
            if not args.diagnostic_scope:
                raise ValueError("MECHANICAL_TASK_DELTA_REQUIRED")
            if args.changes_file:
                for path, scope in _load_changes_file(root, Path(args.changes_file).resolve()).items():
                    _merge_scope(scopes, path, scope.symbols, scope.line_ranges)
            for path, scope in _parse_inline_scopes(root, args.changed_symbol, args.changed_range).items():
                _merge_scope(scopes, path, scope.symbols, scope.line_ranges)
        if not scopes:
            result = {
                "gate": "CHANGED_COMPLEX_SYMBOL_COMMENT_GATE",
                "scope": "MECHANICAL_TASK_DELTA" if formal_mode else "DIAGNOSTIC_SCOPE",
                "policy": "REASON_COMMENTS_NOT_COMMENT_DENSITY",
                "status": "PASS",
                "checked_scopes": [], "skipped": [], "scope_errors": [], "findings": [], "finding_count": 0,
                "reason": "NO_CHANGED_BUSINESS_SYMBOLS",
            }
            if formal_mode and formal_attestation is not None:
                _attest_formal_pass(root, Path(args.checkpoint).resolve(), formal_attestation)
            print(json.dumps(result, ensure_ascii=False, indent=2)); return EXIT_OK
    except ValueError as exc:
        print(json.dumps({"status": "ERROR", "error_code": str(exc)}, ensure_ascii=False, indent=2))
        return EXIT_INVALID

    result = run(root, scopes.values())
    if result["status"] == "PASS" and formal_mode and formal_attestation is not None:
        try:
            _attest_formal_pass(root, Path(args.checkpoint).resolve(), formal_attestation)
        except ValueError as exc:
            print(json.dumps({"status": "ERROR", "error_code": str(exc)}, ensure_ascii=False, indent=2))
            return EXIT_INVALID
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "PASS":
        return EXIT_OK
    if result["status"] == "ERROR":
        return EXIT_INVALID
    return EXIT_POLICY


if __name__ == "__main__":
    sys.exit(main())
