from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

import yaml


_TEST_CALL_RE = re.compile(r"\b(?:test|it)\s*\(\s*(['\"])(?P<name>.+?)\1")
_JS_SIMPLE_SYMBOL_PATTERNS = (
    r"\b(?:export\s+default\s+|export\s+)?(?:async\s+)?function\s+{name}\b",
    r"\b(?:export\s+default\s+|export\s+)?class\s+{name}\b",
    r"\b(?:export\s+)?(?:const|let|var)\s+{name}\b",
    r"\b(?:export\s+)?(?:interface|type|enum)\s+{name}\b",
)
ID_KEY_RE = re.compile(r"(?:^id$|_id$)", re.I)

ANCHOR_CONTRACT_VERSION = 3
SUPPORTED_ANCHOR_KINDS = {
    "JSON_POINTER", "YAML_POINTER", "CANONICAL_ID", "HASHED_SPAN",
    "PYTHON_SYMBOL", "JS_TS_SYMBOL", "PYTEST_NODEID", "VITEST_CASE",
}


AnchorResolver = Callable[[Path, dict[str, Any], Path | None], bool]
_CUSTOM_RESOLVERS: dict[tuple[str, str], AnchorResolver] = {}


def register_anchor_resolver(domain: str, anchor_kind: str, resolver: AnchorResolver, *, replace: bool = False) -> None:
    """Register an extension resolver without changing the core validator.

    Domains are ``authority``, ``implementation`` or ``test``. Unknown anchor kinds remain
    fail-closed until a resolver is explicitly registered by the runtime/plugin layer.
    """
    normalized_domain = domain.strip().lower()
    normalized_kind = anchor_kind.strip().upper()
    if normalized_domain not in {"authority", "implementation", "test"}:
        raise ValueError(f"unsupported anchor resolver domain: {domain}")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", normalized_kind):
        raise ValueError(f"invalid anchor kind: {anchor_kind}")
    key = (normalized_domain, normalized_kind)
    if key in _CUSTOM_RESOLVERS and not replace:
        raise ValueError(f"anchor resolver already registered: {normalized_domain}:{normalized_kind}")
    _CUSTOM_RESOLVERS[key] = resolver


def unregister_anchor_resolver(domain: str, anchor_kind: str) -> None:
    _CUSTOM_RESOLVERS.pop((domain.strip().lower(), anchor_kind.strip().upper()), None)


def supported_anchor_kinds(domain: str | None = None) -> set[str]:
    result = set(SUPPORTED_ANCHOR_KINDS)
    if domain is None:
        result.update(kind for _, kind in _CUSTOM_RESOLVERS)
    else:
        normalized = domain.strip().lower()
        result.update(kind for (candidate, kind) in _CUSTOM_RESOLVERS if candidate == normalized)
    return result


def _extension_resolver(domain: str, kind: str, target_path: Path) -> AnchorResolver | None:
    registered = _CUSTOM_RESOLVERS.get((domain, kind))
    return registered


def _explicit_anchor_kind(ref: dict[str, Any]) -> str | None:
    value = ref.get("anchor_kind")
    if value is None:
        return None
    if not isinstance(value, str):
        return "UNSUPPORTED"
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", normalized):
        return "UNSUPPORTED"
    return normalized


def _authority_anchor_kind(ref: dict[str, Any], suffix: str) -> str:
    explicit = _explicit_anchor_kind(ref)
    if explicit is not None:
        return explicit
    if ref.get("json_pointer") is not None:
        return "JSON_POINTER"
    if ref.get("yaml_pointer") is not None:
        return "YAML_POINTER"
    if ref.get("id") is not None or ref.get("symbol") is not None:
        return "CANONICAL_ID" if suffix in {".yaml", ".yml", ".json"} else "HASHED_SPAN"
    return "HASHED_SPAN"


def _implementation_anchor_kind(ref: dict[str, Any], suffix: str) -> str:
    explicit = _explicit_anchor_kind(ref)
    if explicit is not None:
        return explicit
    symbol = ref.get("symbol")
    if symbol is None:
        return "HASHED_SPAN"
    if suffix == ".py":
        return "PYTHON_SYMBOL"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".vue", ".mjs", ".cjs"} and isinstance(symbol, str) and "." not in symbol:
        return "JS_TS_SYMBOL"
    return "HASHED_SPAN"


def _test_anchor_kind(ref: dict[str, Any], suffix: str) -> str:
    explicit = _explicit_anchor_kind(ref)
    if explicit is not None:
        return explicit
    runner = str(ref.get("test_runner") or "").lower()
    if ref.get("test_nodeid"):
        if runner in {"vitest", "jest"} or suffix in {".ts", ".tsx", ".js", ".jsx", ".vue"}:
            return "VITEST_CASE"
        return "PYTEST_NODEID"
    if suffix == ".py" and ref.get("symbol"):
        return "PYTHON_SYMBOL"
    if ref.get("test_identifier") or ref.get("symbol"):
        return "VITEST_CASE"
    return "HASHED_SPAN"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _line_range_ok(path: Path, ref: dict[str, Any], *, require_hash_if_only_anchor: bool = False) -> bool:
    start = ref.get("line_start")
    if start is None:
        return not require_hash_if_only_anchor
    end = ref.get("line_end", start)
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        return False
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if end > len(lines):
        return False
    expected = ref.get("source_hash") or ref.get("anchor_hash")
    if require_hash_if_only_anchor and not isinstance(expected, str):
        return False
    if expected:
        excerpt = "\n".join(lines[start - 1 : end]).encode("utf-8")
        if hashlib.sha256(excerpt).hexdigest() != expected:
            return False
    return True


def _resolve_pointer(payload: Any, pointer: str) -> bool:
    if pointer == "":
        return True
    if not pointer.startswith("/"):
        return False
    current = payload
    for raw in pointer.split("/")[1:]:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and 0 <= int(part) < len(current):
            current = current[int(part)]
        else:
            return False
    return True


def _structured_id_matches(value: Any, identifier: str) -> int:
    matches = 0
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and ID_KEY_RE.search(key) and child == identifier:
                matches += 1
            matches += _structured_id_matches(child, identifier)
    elif isinstance(value, list):
        for child in value:
            matches += _structured_id_matches(child, identifier)
    return matches


def authority_anchor_exists(path: Path, ref: dict[str, Any]) -> bool:
    if not path.is_file() or not _line_range_ok(path, ref):
        return False
    suffix = path.suffix.lower()
    payload: Any | None = None
    if suffix in {".yaml", ".yml"}:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            return False
    elif suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False

    kind = _authority_anchor_kind(ref, suffix)
    if kind == "UNSUPPORTED":
        return False
    extension = _extension_resolver("authority", kind, path)
    if extension is not None:
        try:
            return bool(extension(path, ref, None))
        except Exception:
            return False
    if kind in {"JSON_POINTER", "YAML_POINTER"}:
        pointer = ref.get("json_pointer") if kind == "JSON_POINTER" else ref.get("yaml_pointer")
        return payload is not None and isinstance(pointer, str) and _resolve_pointer(payload, pointer)
    identifier = ref.get("id") or ref.get("symbol")
    if kind == "CANONICAL_ID":
        return payload is not None and isinstance(identifier, str) and bool(identifier) and _structured_id_matches(payload, identifier) == 1
    if kind == "HASHED_SPAN":
        needle = identifier if isinstance(identifier, str) and identifier else None
        return _hashed_span_contains(path, ref, needle)
    return False


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        result: list[str] = []
        for child in target.elts:
            result.extend(_target_names(child))
        return result
    return []


def _python_symbol_index(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return set()
    index: set[str] = set()

    def walk_body(body: list[ast.stmt], prefix: tuple[str, ...] = ()) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = ".".join((*prefix, node.name))
                index.add(qualified)
                # Also index leaf name for module-level declarations only; nested anchors should be qualified.
                if not prefix:
                    index.add(node.name)
                walk_body(node.body, (*prefix, node.name))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for name in _target_names(target):
                        qualified = ".".join((*prefix, name))
                        index.add(qualified)
                        if not prefix:
                            index.add(name)
            elif isinstance(node, ast.AnnAssign):
                for name in _target_names(node.target):
                    qualified = ".".join((*prefix, name))
                    index.add(qualified)
                    if not prefix:
                        index.add(name)
    walk_body(tree.body)
    return index


def _python_symbol_exists(path: Path, symbol: str) -> bool:
    normalized = symbol.removeprefix(path.stem + ".")
    return normalized in _python_symbol_index(path)


def _js_simple_symbol_exists(path: Path, symbol: str) -> bool:
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", symbol):
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    escaped = re.escape(symbol)
    return any(re.search(pattern.format(name=escaped), text) for pattern in _JS_SIMPLE_SYMBOL_PATTERNS)


def _hashed_span_contains(path: Path, ref: dict[str, Any], needle: str | None = None) -> bool:
    if not _line_range_ok(path, ref, require_hash_if_only_anchor=True):
        return False
    if needle is None:
        return True
    start, end = ref["line_start"], ref.get("line_end", ref["line_start"])
    excerpt = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[start - 1 : end])
    return needle in excerpt


def implementation_anchor_exists(path: Path, ref: dict[str, Any]) -> bool:
    if not path.is_file() or not _line_range_ok(path, ref):
        return False
    symbol = ref.get("symbol")
    suffix = path.suffix.lower()
    kind = _implementation_anchor_kind(ref, suffix)
    if kind == "UNSUPPORTED":
        return False
    extension = _extension_resolver("implementation", kind, path)
    if extension is not None:
        try:
            return bool(extension(path, ref, None))
        except Exception:
            return False
    if kind == "PYTHON_SYMBOL":
        return isinstance(symbol, str) and bool(symbol) and suffix == ".py" and _python_symbol_exists(path, symbol)
    if kind == "JS_TS_SYMBOL":
        return isinstance(symbol, str) and bool(symbol) and "." not in symbol and _js_simple_symbol_exists(path, symbol)
    if kind == "HASHED_SPAN":
        needle = symbol.split(".")[-1] if isinstance(symbol, str) and symbol else None
        return _hashed_span_contains(path, ref, needle)
    return False


def pytest_nodeid_exists(repo_root: Path, nodeid: str) -> bool:
    parts = nodeid.split("::")
    if len(parts) < 2:
        return False
    path = (repo_root / parts[0]).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError:
        return False
    if not path.is_file() or path.suffix != ".py":
        return False
    chain = [re.sub(r"\[.*\]$", "", part) for part in parts[1:]]
    return ".".join(chain) in _python_symbol_index(path)


def _vitest_case_count(path: Path, identifier: str) -> int:
    if not path.is_file() or not identifier:
        return 0
    text = path.read_text(encoding="utf-8", errors="replace")
    return sum(1 for match in _TEST_CALL_RE.finditer(text) if match.group("name") == identifier)


def vitest_case_exists(path: Path, identifier: str) -> bool:
    # Name-only Vitest anchors are accepted only when unambiguous.
    return _vitest_case_count(path, identifier) == 1


def test_anchor_exists(repo_root: Path, path: Path, ref: dict[str, Any]) -> bool:
    if not path.is_file() or not _line_range_ok(path, ref):
        return False
    suffix = path.suffix.lower()
    kind = _test_anchor_kind(ref, suffix)
    if kind == "UNSUPPORTED":
        return False
    extension = _extension_resolver("test", kind, path)
    if extension is not None:
        try:
            return bool(extension(path, ref, repo_root.resolve()))
        except Exception:
            return False
    nodeid = ref.get("test_nodeid")
    identifier = ref.get("test_identifier") or ref.get("symbol")
    if kind == "PYTEST_NODEID":
        return isinstance(nodeid, str) and bool(nodeid) and pytest_nodeid_exists(repo_root, nodeid)
    if kind == "PYTHON_SYMBOL":
        return suffix == ".py" and isinstance(identifier, str) and bool(identifier) and _python_symbol_exists(path, identifier)
    if kind == "VITEST_CASE":
        if not isinstance(identifier, str) or not identifier:
            identifier = nodeid.split("::")[-1] if isinstance(nodeid, str) and nodeid else ""
        if not identifier:
            return False
        count = _vitest_case_count(path, identifier)
        if count == 1:
            return True
        return count > 1 and _hashed_span_contains(path, ref, identifier)
    if kind == "HASHED_SPAN":
        needle = identifier if isinstance(identifier, str) and identifier else None
        return _hashed_span_contains(path, ref, needle)
    return False

