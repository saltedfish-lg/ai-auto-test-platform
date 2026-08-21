from __future__ import annotations

import csv
import fnmatch
from functools import lru_cache
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from .context_loading import load_context_efficiency_config

_ID_VALUE = re.compile(r'\b[A-Z][A-Z0-9_]{1,24}-[A-Z0-9][A-Z0-9._-]*\b')
_CJK = re.compile(r'[\u3400-\u9fff]+')
_WORD = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.:/{}~-]*')
_ENDPOINT = re.compile(r'(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._~{}:-]+/)*[A-Za-z0-9._~{}:-]+')
_U_ESCAPE = re.compile(r'#U([0-9A-Fa-f]{4,6})')
_HTTP_METHODS = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'}
_SKIP_SECTIONS = {
    'metadata', 'independence_declaration', 'source_inventory_summary', 'source_documents',
    'coding_readiness', 'validation_summary', 'generation_manifest', 'conclusion',
}
_STOP = {
    'the','and','for','with','from','into','this','that','task','change','modify','update','fix','add','remove',
    '实现','修改','新增','删除','调整','修复','功能','规则','页面','代码','任务','需要','进行','当前','平台',
}
_INDEX_SCHEMA_VERSION = '3'
_MISSING = object()


def _decode_display_path(value: str) -> str:
    return _U_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), value)


def _match_any(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(rel, str(p).replace('\\', '/')) for p in patterns)


def _authority_files(root: Path) -> list[Path]:
    cfg = load_context_efficiency_config(root)['authority_index']
    extensions = {str(x).lower() for x in cfg.get('extensions') or []}
    excludes = [str(x) for x in cfg.get('exclude_patterns') or []]
    out: list[Path] = []
    for raw_root in cfg.get('source_roots') or []:
        base = root / str(raw_root)
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            rel = path.relative_to(root).as_posix()
            display = _decode_display_path(rel)
            if _match_any(rel, excludes) or _match_any(display, excludes):
                continue
            out.append(path)
    return sorted(set(out))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _signature(root: Path, files: list[Path]) -> tuple[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for path in files:
        st = path.stat()
        rel = path.relative_to(root).as_posix()
        content_sha256 = _sha256_file(path)
        row = {
            'path': rel,
            'size': int(st.st_size),
            'mtime_ns': int(st.st_mtime_ns),
            'sha256': content_sha256,
        }
        rows.append(row)
        # Path + content digest is authoritative for freshness. mtime is diagnostic only.
        digest.update(f'{rel}\0{st.st_size}\0{content_sha256}\n'.encode('utf-8'))
    return digest.hexdigest(), rows


def _cache_path(root: Path) -> Path:
    cfg = load_context_efficiency_config(root)['authority_index']
    return root / str(cfg.get('cache_path') or '.runtime/context-index/authority-index.sqlite3')


def _pointer_encode(value: str) -> str:
    return str(value).replace('~', '~0').replace('/', '~1')


def _pointer_decode(value: str) -> str:
    # RFC 6901 decoding order matters: ~1 first, then ~0.
    return str(value).replace('~1', '/').replace('~0', '~')


def _pointer(*segments: Any) -> str:
    return '/' + '/'.join(_pointer_encode(str(segment)) for segment in segments)


def _scalar_text(value: Any, *, max_chars: int = 1400) -> str:
    parts: list[str] = []
    used = 0

    def visit(item: Any) -> None:
        nonlocal used
        if used >= max_chars:
            return
        if isinstance(item, dict):
            for key, val in item.items():
                if str(key).lower() in {'release_id','version','current_version','source_basis','source_fact_ids'}:
                    continue
                visit(val)
        elif isinstance(item, list):
            for val in item[:24]:
                visit(val)
        elif isinstance(item, (str, int, float, bool)) and item is not None:
            text = str(item).strip()
            if text:
                clipped = text[:500]
                parts.append(clipped)
                used += len(clipped) + 3

    visit(value)
    return ' | '.join(parts)[:max_chars]


def _ids_in(value: Any, *, max_ids: int = 80) -> list[str]:
    found: list[str] = []

    def visit(item: Any) -> None:
        if len(found) >= max_ids:
            return
        if isinstance(item, dict):
            for val in item.values():
                visit(val)
        elif isinstance(item, list):
            for val in item:
                visit(val)
        elif isinstance(item, str):
            for match in _ID_VALUE.findall(item):
                if match not in found:
                    found.append(match)

    visit(value)
    return found


@lru_cache(maxsize=32)
def _identity_strategy_map(root_text: str) -> dict[str, Any]:
    # One index build runs against one immutable Project Profile snapshot. Caching avoids
    # tens of thousands of repeated YAML loads while the config remains the sole source.
    root = Path(root_text)
    strategies = load_context_efficiency_config(root).get('authority_index', {}).get('identity_strategies') or {}
    return dict(strategies) if isinstance(strategies, dict) else {}


def _identity_strategy(root: Path, path: Path, section: str) -> dict[str, list[str]]:
    strategies = _identity_strategy_map(str(root))
    basename = path.name
    if section == 'operations' and basename.lower().startswith('openapi'):
        raw = strategies.get('openapi.operations') or {}
    else:
        raw = strategies.get(basename) or {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        'primary': [str(x) for x in raw.get('primary') or []],
        'secondary': [str(x) for x in raw.get('secondary') or []],
        'composite': [str(x) for x in raw.get('composite') or []],
        'fallback': [str(x) for x in raw.get('fallback') or []],
    }


def _identity_value(record: dict[str, Any], key: str) -> str | None:
    lowered = {str(k).lower(): value for k, value in record.items()}
    value = lowered.get(str(key).lower())
    if isinstance(value, (str, int)) and str(value).strip():
        return str(value).strip()
    return None


def _identity_key_affinity(key: str, section: str) -> int:
    """Prefer an identity field whose lexical stem matches the record section.

    This avoids global business-key precedence (for example choosing a related lifecycle id
    as the identity of an object record) while staying entirely schema/domain agnostic.
    """
    def tokens(value: str) -> set[str]:
        raw=[part for part in re.split(r'[^a-z0-9]+', str(value).lower()) if part]
        out=set(raw)
        for part in list(raw):
            if part.endswith('ies') and len(part)>3:
                out.add(part[:-3]+'y')
            elif part.endswith('s') and len(part)>2:
                out.add(part[:-1])
        return out
    key_tokens=tokens(key)-{'id','code','key'}
    section_tokens=tokens(section)
    return len(key_tokens & section_tokens)


def _canonical_identity(root: Path, path: Path, section: str, record: dict[str, Any]) -> tuple[str | None, str | None, list[str]]:
    strategy = _identity_strategy(root, path, section)
    reference_ids: list[str] = []
    for key in strategy['secondary']:
        value = _identity_value(record, key)
        if value and value not in reference_ids:
            reference_ids.append(value)
    for key in strategy['primary']:
        value = _identity_value(record, key)
        if value:
            for composite_key in strategy['composite']:
                composite_value = _identity_value(record, composite_key)
                if composite_value and composite_value != value and composite_value not in reference_ids:
                    reference_ids.append(composite_value)
            return value, key, reference_ids
    # Generic fallback keys come from Project Profile. Business-specific identity names belong
    # in configuration, never in the Context Efficiency runtime algorithm.
    configured_keys = load_context_efficiency_config(root).get('authority_index', {}).get('canonical_identity_keys') or []
    lowered = {str(key).lower(): (str(key), value) for key, value in record.items()}
    candidates=[]
    for order,configured in enumerate(configured_keys):
        found = lowered.get(str(configured).lower())
        if not found:
            continue
        original_key,value=found
        if isinstance(value,(str,int)) and str(value).strip():
            candidates.append((_identity_key_affinity(original_key,section),-order,original_key,str(value).strip()))
    if candidates:
        _,_,original_key,value=max(candidates)
        return value,original_key,reference_ids
    return None, None, reference_ids


def _title(record: dict[str, Any]) -> str:
    for key in ('name','title','summary','statement','description','definition'):
        value = record.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()[:240]
    for key,value in record.items():
        normalized=str(key).lower()
        if normalized.endswith(('_name','_title','_summary','_statement','_description','_definition')) and isinstance(value,(str,int)) and str(value).strip():
            return str(value).strip()[:240]
    return ''


def _record_tuple(
    *,
    root: Path,
    path: Path,
    section: str,
    selector: str,
    record: dict[str, Any],
    structural_id: str | None = None,
) -> tuple[Any, ...]:
    rel = path.relative_to(root).as_posix()
    canonical_id, canonical_key, identity_references = _canonical_identity(root, path, section, record)
    references = _ids_in(record)
    for value in identity_references:
        if value not in references:
            references.append(value)
    if canonical_id and canonical_id in references:
        references.remove(canonical_id)
    domains: list[str] = []
    for key, value in record.items():
        if 'domain' not in str(key).lower():
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, (str, int)) and str(item).strip() not in domains:
                domains.append(str(item).strip())
    title = _title(record)
    locator_key = f'{rel}#{selector}'
    display_id = canonical_id or structural_id or ''
    search_text = ' | '.join(
        x for x in [display_id, structural_id or '', section, selector, title, _scalar_text(record)] if x
    )[:2200]
    identity_kind = 'CANONICAL' if canonical_id else ('STRUCTURAL' if structural_id else 'LOCATOR')
    return (
        canonical_id,
        canonical_key,
        structural_id,
        identity_kind,
        locator_key,
        section,
        selector,
        rel,
        _decode_display_path(rel),
        title,
        json.dumps(domains[:16], ensure_ascii=False),
        json.dumps(references, ensure_ascii=False),
        json.dumps(references, ensure_ascii=False),
        search_text,
    )


def _iter_yaml_json_records(root: Path, path: Path, data: Any) -> Iterator[tuple[Any, ...]]:
    if not isinstance(data, dict):
        return
    for section, value in data.items():
        sec = str(section)
        if sec.lower() in _SKIP_SECTIONS:
            continue
        if isinstance(value, list):
            for idx, record in enumerate(value):
                if isinstance(record, dict):
                    yield _record_tuple(root=root, path=path, section=sec, selector=_pointer(sec, idx), record=record)
            continue
        if not isinstance(value, dict):
            continue
        if sec == 'paths':
            for route, path_item in value.items():
                if not isinstance(path_item, dict):
                    continue
                route_text = str(route)
                yield _record_tuple(
                    root=root,
                    path=path,
                    section='paths',
                    selector=_pointer('paths', route_text),
                    record=path_item,
                    structural_id=f'OPENAPI_PATH:{route_text}',
                )
                for method, operation in path_item.items():
                    method_name = str(method).lower()
                    if method_name in _HTTP_METHODS and isinstance(operation, dict):
                        yield _record_tuple(
                            root=root,
                            path=path,
                            section='operations',
                            selector=_pointer('paths', route_text, method_name),
                            record=operation,
                            structural_id=f'HTTP:{method_name.upper()} {route_text}',
                        )
            continue
        canonical_id, _, _ = _canonical_identity(root, path, sec, value)
        if canonical_id:
            yield _record_tuple(root=root, path=path, section=sec, selector=_pointer(sec), record=value)
            continue
        # Contract-style Authority often stores one semantic record as a mapping of
        # scalar/list properties (for example `credential:` or `refresh_session:`)
        # without a synthetic *_id. Preserve it as a stable fallback locator instead
        # of dropping it merely because it has no canonical ID.
        if any(not isinstance(item, dict) for item in value.values()):
            yield _record_tuple(root=root, path=path, section=sec, selector=_pointer(sec), record=value)
        for key, record in value.items():
            if isinstance(record, dict):
                yield _record_tuple(
                    root=root,
                    path=path,
                    section=sec,
                    selector=_pointer(sec, key),
                    record=record,
                )


def _iter_csv_records(root: Path, path: Path) -> Iterator[tuple[Any, ...]]:
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        for index, row in enumerate(csv.DictReader(fh)):
            record = {str(key): value for key, value in row.items() if key is not None}
            if record:
                yield _record_tuple(
                    root=root,
                    path=path,
                    section='rows',
                    selector=_pointer('rows', index),
                    record=record,
                    structural_id=f'CSV_ROW:{index + 2}',
                )


def _open_index(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(_cache_path(root))
    conn.row_factory = sqlite3.Row
    return conn


def _read_index_meta(cache: Path) -> tuple[str, dict[str, str], str | None]:
    if not cache.is_file():
        return 'MISSING', {}, None
    try:
        conn = sqlite3.connect(cache)
        try:
            quick = conn.execute('PRAGMA quick_check').fetchone()
            if not quick or str(quick[0]).lower() != 'ok':
                return 'INVALID', {}, 'SQLITE_QUICK_CHECK_FAILED'
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'meta', 'records', 'sources'} <= tables:
                return 'INVALID', {}, 'INDEX_SCHEMA_TABLE_MISSING'
            meta = {str(key): str(value) for key, value in conn.execute('SELECT key,value FROM meta')}
            return 'OK', meta, None
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return 'INVALID', {}, type(exc).__name__


def authority_index_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    cache = _cache_path(root)
    index_state, meta, index_error = _read_index_meta(cache)
    if index_state == 'MISSING':
        status = 'MISSING'
        signature = None
        source_rows: list[dict[str, Any]] = []
    elif index_state == 'INVALID':
        status = 'INVALID'
        signature = None
        source_rows = []
    else:
        try:
            files = _authority_files(root)
            signature, source_rows = _signature(root, files)
        except Exception as exc:
            return {
                'status': 'INVALID',
                'reason': 'AUTHORITY_SOURCE_READ_FAILED',
                'error': type(exc).__name__,
                'cache_path': cache.relative_to(root).as_posix(),
                'authority_is_source_of_truth': True,
                'index_is_authority': False,
                'build_command': 'python -m tools.context.authority_query --root . --rebuild-index',
            }
        if meta.get('schema_version') != _INDEX_SCHEMA_VERSION:
            status = 'INVALID'
            index_error = 'INDEX_SCHEMA_VERSION_MISMATCH'
        elif meta.get('source_signature') != signature:
            status = 'STALE'
        else:
            parse_errors = json.loads(meta.get('parse_errors', '[]'))
            status = 'PARTIAL' if parse_errors else 'READY'
    parse_errors = json.loads(meta.get('parse_errors', '[]')) if meta else []
    return {
        'status': status,
        'reason': index_error,
        'cache_path': cache.relative_to(root).as_posix(),
        'source_signature': signature,
        'record_count': int(meta.get('record_count', '0')) if meta else 0,
        'source_count': len(source_rows),
        'parse_errors': parse_errors,
        'authority_is_source_of_truth': True,
        'index_is_authority': False,
        'freshness_uses_content_digest': True,
        'build_command': 'python -m tools.context.authority_query --root . --rebuild-index',
    }


def build_authority_index(root: Path, *, force: bool = False) -> dict[str, Any]:
    root = root.resolve()
    _identity_strategy_map.cache_clear()
    files = _authority_files(root)
    signature, source_rows = _signature(root, files)
    cache = _cache_path(root)
    index_state, meta, _ = _read_index_meta(cache)
    if not force and index_state == 'OK' and meta.get('source_signature') == signature and meta.get('schema_version') == _INDEX_SCHEMA_VERSION:
        parse_errors = json.loads(meta.get('parse_errors', '[]'))
        return {
            'kind': 'DERIVED_AUTHORITY_LOCATOR_INDEX',
            'status': 'PARTIAL' if parse_errors else 'READY',
            'source_signature': signature,
            'record_count': int(meta.get('record_count', '0')),
            'parse_errors': parse_errors,
            'cache_path': cache.relative_to(root).as_posix(),
            'cache_hit': True,
        }
    cache.parent.mkdir(parents=True, exist_ok=True)
    temp = cache.with_suffix(cache.suffix + '.tmp')
    temp.unlink(missing_ok=True)
    conn = sqlite3.connect(temp)
    parse_errors: list[dict[str, str]] = []
    record_count = 0
    indexed_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    source_by_path = {row['path']: dict(row) for row in source_rows}
    try:
        conn.executescript('''
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE sources (
              path TEXT PRIMARY KEY,
              size INTEGER NOT NULL,
              mtime_ns INTEGER NOT NULL,
              sha256 TEXT NOT NULL,
              parser TEXT NOT NULL,
              parse_status TEXT NOT NULL,
              parse_error TEXT,
              indexed_at TEXT NOT NULL
            );
            CREATE TABLE records (
              row_id INTEGER PRIMARY KEY,
              canonical_record_id TEXT,
              canonical_id_key TEXT,
              structural_id TEXT,
              identity_kind TEXT NOT NULL,
              locator_key TEXT NOT NULL UNIQUE,
              section TEXT NOT NULL,
              selector TEXT NOT NULL,
              path TEXT NOT NULL,
              display_path TEXT NOT NULL,
              title TEXT NOT NULL,
              domains_json TEXT NOT NULL,
              references_json TEXT NOT NULL,
              reference_ids_json TEXT NOT NULL,
              search_text TEXT NOT NULL
            );
            CREATE INDEX idx_records_canonical_id ON records(canonical_record_id);
            CREATE INDEX idx_records_structural_id ON records(structural_id);
            CREATE INDEX idx_records_path ON records(path);
            CREATE INDEX idx_records_display_path ON records(display_path);
        ''')
        insert_sql = '''INSERT INTO records(
            canonical_record_id,canonical_id_key,structural_id,identity_kind,locator_key,section,selector,path,display_path,title,domains_json,references_json,reference_ids_json,search_text
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        for path in files:
            rel = path.relative_to(root).as_posix()
            parser = path.suffix.lower().lstrip('.')
            parse_status = 'PASS'
            parse_error: str | None = None
            try:
                if path.suffix.lower() in {'.yaml', '.yml'}:
                    iterator = _iter_yaml_json_records(root, path, yaml.safe_load(path.read_text(encoding='utf-8')))
                elif path.suffix.lower() == '.json':
                    iterator = _iter_yaml_json_records(root, path, json.loads(path.read_text(encoding='utf-8')))
                elif path.suffix.lower() == '.csv':
                    iterator = _iter_csv_records(root, path)
                else:
                    continue
                batch: list[tuple[Any, ...]] = []
                for row in iterator:
                    batch.append(row)
                    record_count += 1
                    if len(batch) >= 500:
                        conn.executemany(insert_sql, batch)
                        batch.clear()
                if batch:
                    conn.executemany(insert_sql, batch)
            except Exception as exc:
                parse_status = 'ERROR'
                parse_error = type(exc).__name__
                parse_errors.append({'path': rel, 'error': parse_error})
            source = source_by_path[rel]
            conn.execute(
                'INSERT INTO sources(path,size,mtime_ns,sha256,parser,parse_status,parse_error,indexed_at) VALUES (?,?,?,?,?,?,?,?)',
                (rel, source['size'], source['mtime_ns'], source['sha256'], parser, parse_status, parse_error, indexed_at),
            )
        meta_rows = {
            'schema_version': _INDEX_SCHEMA_VERSION,
            'kind': 'DERIVED_AUTHORITY_LOCATOR_INDEX',
            'source_signature': signature,
            'record_count': str(record_count),
            'parse_errors': json.dumps(parse_errors, ensure_ascii=False),
            'generated_at': indexed_at,
            'authority_is_source_of_truth': 'true',
            'index_is_authority': 'false',
        }
        conn.executemany('INSERT INTO meta(key,value) VALUES (?,?)', meta_rows.items())
        conn.commit()
    finally:
        conn.close()
    temp.replace(cache)
    return {
        'kind': 'DERIVED_AUTHORITY_LOCATOR_INDEX',
        'status': 'PARTIAL' if parse_errors else 'READY',
        'source_signature': signature,
        'record_count': record_count,
        'parse_errors': parse_errors,
        'cache_path': cache.relative_to(root).as_posix(),
        'cache_hit': False,
    }


def _query_terms(text: str) -> list[str]:
    terms: list[str] = []
    for token in _WORD.findall(text.lower()):
        if len(token) >= 3 and token not in _STOP and token not in terms:
            terms.append(token)
    for seq in _CJK.findall(text):
        if seq in _STOP:
            continue
        if 2 <= len(seq) <= 8 and seq not in terms:
            terms.append(seq)
        for size in (2, 4, 3):
            if len(seq) < size:
                continue
            for index in range(len(seq) - size + 1):
                token = seq[index:index + size]
                if token not in _STOP and token not in terms:
                    terms.append(token)
                if len(terms) >= 40:
                    return terms
    return terms[:40]


def _authority_route_map(root: Path, domains: Iterable[str], authority_paths: Iterable[str]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    profile = root / '.governance/authorities.yaml'
    wanted_domains = {str(x).upper() for x in domains}
    explicit_paths = {str(x).replace('\\', '/') for x in authority_paths}
    groups: dict[str, set[str]] = {}
    group_domains: dict[str, set[str]] = {}
    try:
        raw = yaml.safe_load(profile.read_text(encoding='utf-8')) or {}
    except Exception:
        raw = {}
    configs = raw.get('authorities') or {}
    if isinstance(configs, dict):
        for name, config in configs.items():
            if not isinstance(config, dict):
                continue
            config_domains = {str(x).upper() for x in config.get('domains') or []}
            paths = {str(x).replace('\\', '/') for x in config.get('paths') or []}
            relevant = bool(wanted_domains & config_domains) or bool(explicit_paths & paths)
            if relevant:
                groups[str(name)] = paths
                group_domains[str(name)] = config_domains
    covered = set().union(*groups.values()) if groups else set()
    for path in sorted(explicit_paths - covered):
        groups[f'path:{path}'] = {path}
        group_domains[f'path:{path}'] = set()
    return groups, group_domains


def _path_route_metadata(path: str, groups: dict[str, set[str]], group_domains: dict[str, set[str]]) -> tuple[str | None, list[str]]:
    for group, paths in groups.items():
        if path in paths:
            return group, sorted(group_domains.get(group, set()))
    return None, []


def _row_to_ref(row: sqlite3.Row, *, authority_group: str | None = None, authority_domains: list[str] | None = None) -> dict[str, Any]:
    canonical = row['canonical_record_id']
    structural = row['structural_id']
    return {
        'record_id': canonical or structural,
        'canonical_record_id': canonical,
        'canonical_id_key': row['canonical_id_key'],
        'structural_id': structural,
        'identity_kind': row['identity_kind'],
        'fallback_locator': row['locator_key'],
        'section': row['section'],
        'selector': row['selector'],
        'path': row['path'],
        'display_path': row['display_path'],
        'title': row['title'],
        'domains': json.loads(row['domains_json']),
        'references': json.loads(row['references_json']),
        'reference_ids': json.loads(row['reference_ids_json']),
        'authority_group': authority_group,
        'authority_domains': list(authority_domains or []),
    }


def _candidate_rows(conn: sqlite3.Connection, *, selected_paths: set[str], explicit_ids: list[str], terms: list[str], wanted_domains: set[str]) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[str] = []
    if selected_paths:
        sub: list[str] = []
        for path in sorted(selected_paths):
            sub.extend(['path = ?', 'display_path = ?'])
            params.extend([path, path])
        clauses.append('(' + ' OR '.join(sub) + ')')
    else:
        sub = []
        for record_id in explicit_ids:
            sub.extend(['canonical_record_id = ?', 'structural_id = ?'])
            params.extend([record_id, record_id])
        for term in terms[:12]:
            sub.append('search_text LIKE ?')
            params.append('%' + term + '%')
        for domain in sorted(wanted_domains)[:8]:
            sub.append('lower(domains_json) LIKE ?')
            params.append('%' + domain.lower() + '%')
        if sub:
            clauses.append('(' + ' OR '.join(sub) + ')')
    sql = '''SELECT canonical_record_id,canonical_id_key,structural_id,identity_kind,locator_key,section,selector,path,display_path,title,domains_json,references_json,reference_ids_json,search_text FROM records'''
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    sql += ' LIMIT 20000'
    return list(conn.execute(sql, params))


def _section_intent_bonus(request: str, section: str) -> int:
    """Small domain-agnostic bonus when request terms directly match a section locator.

    Section intent is deliberately lexical.  Business meaning belongs to Authority/routing
    metadata, not to Context Efficiency runtime branches.
    """
    sec = str(section or '').lower().replace('_', ' ').replace('-', ' ')
    if not sec:
        return 0
    matches = [term for term in _query_terms(request) if str(term).lower().replace('_', ' ') in sec]
    return min(90, 18 * len(matches))


def _record_matches_domain_intent(candidate: dict[str, Any], domain: str) -> bool:
    domain_upper = str(domain).upper()
    route_domains = {str(x).upper() for x in (candidate.get('authority_domains') or [])}
    record_domains = {str(x).upper() for x in (candidate.get('domains') or [])}
    return domain_upper in route_domains or domain_upper in record_domains


def _choose_diverse(
    scored: list[tuple[int, str, dict[str, Any]]],
    *,
    limit: int,
    authority_groups: dict[str, set[str]],
    routed_paths: set[str],
    authority_backed_domains: set[str],
    min_per_authority: int,
    min_per_domain: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    chosen_keys: set[tuple[str, str]] = set()

    def take(candidate: dict[str, Any]) -> bool:
        key = (str(candidate['path']), str(candidate['selector']))
        if key in chosen_keys or len(chosen) >= limit:
            return False
        chosen.append(candidate); chosen_keys.add(key); return True

    # Exact record/endpoint hits always win.
    for _, _, candidate in scored:
        reasons = candidate.get('relevance_reasons') or []
        if 'EXPLICIT_ENDPOINT' in reasons or 'EXPLICIT_ID' in reasons:
            take(candidate)

    # File-level recall is stronger than group/domain quotas. Every routed Authority
    # file gets a chance to contribute one real record before relevance competition.
    for path in sorted(routed_paths):
        for _, _, candidate in scored:
            if str(candidate.get('path')) == path and take(candidate):
                break

    for group in authority_groups:
        count = sum(1 for item in chosen if item.get('authority_group') == group)
        for _, _, candidate in scored:
            if count >= min_per_authority:
                break
            if candidate.get('authority_group') == group and take(candidate):
                count += 1

    for domain in sorted(authority_backed_domains):
        count = 0
        for _, _, candidate in scored:
            if _record_matches_domain_intent(candidate, domain) and take(candidate):
                count += 1
                if count >= min_per_domain:
                    break
        if count < min_per_domain:
            for _, _, candidate in scored:
                candidate_domains = {str(x).upper() for x in (candidate.get('domains') or []) + (candidate.get('authority_domains') or [])}
                if domain.upper() in candidate_domains and take(candidate):
                    count += 1
                    if count >= min_per_domain:
                        break

    section_counts: dict[str, int] = {}
    for _, _, candidate in scored:
        section = str(candidate.get('section') or '')
        reasons = candidate.get('relevance_reasons') or []
        if section_counts.get(section, 0) >= 4 and not ({'EXPLICIT_ID','EXPLICIT_ENDPOINT'} & set(reasons)):
            continue
        if take(candidate):
            section_counts[section] = section_counts.get(section, 0) + 1
        if len(chosen) >= limit:
            break

    represented_groups = {str(x.get('authority_group')) for x in chosen if x.get('authority_group')}
    represented_files = {str(x.get('path')) for x in chosen if x.get('path')}
    represented_domains: set[str] = set()
    for item in chosen:
        represented_domains.update(str(x).upper() for x in (item.get('domains') or []) + (item.get('authority_domains') or []))
    return chosen, {
        'authority_group_quota': min_per_authority,
        'authority_file_quota': 1,
        'domain_quota': min_per_domain,
        'represented_authority_groups': sorted(represented_groups),
        'unrepresented_authority_groups': [group for group in authority_groups if group not in represented_groups],
        'represented_authority_files': sorted(represented_files),
        'unrepresented_authority_files': sorted(path for path in routed_paths if path not in represented_files),
        'authority_backed_domains': sorted(authority_backed_domains),
        'missing_domains': [domain for domain in sorted(authority_backed_domains) if domain not in represented_domains],
    }


def _requires_full_relationship_cardinality(request: str) -> bool:
    text=request.lower()
    # Generic cardinality intent: when the user explicitly asks for all/every/complete members
    # of a relationship, enumerate direct matches regardless of the business domain.
    universal_terms=(
        '所有','全部','每个','每一','完整','全量','逐一','哪些',
        ' all ','all ','every ','each ','complete ','full ','which ',
    )
    return any(term in f' {text} ' for term in universal_terms)


def _literal_identity_in_request(identity: str, request: str) -> bool:
    identity=str(identity or '').strip()
    if not identity:
        return False
    pattern=r'(?<![A-Za-z0-9_])'+re.escape(identity)+r'(?![A-Za-z0-9_])'
    return re.search(pattern, request, flags=re.IGNORECASE) is not None


def _relationship_closure(
    routed_refs: list[dict[str, Any]],
    scored: list[tuple[int, str, dict[str, Any]]],
    *,
    explicit_ids: list[str],
    request: str = '',
    max_depth: int = 2,
) -> dict[str, Any]:
    """Build a small deterministic relationship closure over already-routed Authority records.

    The closure is not a graph service. It only follows schema-aware canonical_record_id and
    reference_ids already present in the local Authority index.
    """
    by_key = {(str(ref.get('path') or ''), str(ref.get('selector') or '')): ref for ref in routed_refs}
    canonical_paths: dict[str, set[str]] = {}
    for ref in routed_refs:
        canonical = str(ref.get('canonical_record_id') or '')
        if canonical:
            canonical_paths.setdefault(canonical, set()).add(str(ref.get('path') or ''))

    anchors: list[str] = []
    anchor_reasons: dict[str, list[str]] = {}
    explicit_set = {str(x) for x in explicit_ids if str(x)}

    def add_anchor(ref: dict[str, Any]) -> bool:
        canonical = str(ref.get('canonical_record_id') or '')
        if not canonical or canonical in anchors:
            return False
        reasons = {str(x) for x in ref.get('relevance_reasons') or []}
        anchors.append(canonical)
        anchor_reasons[canonical] = sorted(reasons)
        return True

    # Only explicit/literal identities are strong anchors. Generic relevance and domain
    # matches remain weak candidates and must never silently narrow a broad task.
    for _, _, ref in scored:
        canonical = str(ref.get('canonical_record_id') or '')
        structural = str(ref.get('structural_id') or '')
        reasons = {str(x) for x in ref.get('relevance_reasons') or []}
        if canonical and (
            canonical in explicit_set
            or structural in explicit_set
            or _literal_identity_in_request(canonical, request)
            or _literal_identity_in_request(structural, request)
            or {'EXPLICIT_ID', 'EXPLICIT_ENDPOINT'} & reasons
        ):
            add_anchor(ref)

    weak_candidates=[]
    if not anchors:
        for _, _, ref in scored:
            canonical=str(ref.get('canonical_record_id') or '')
            reasons={str(x) for x in ref.get('relevance_reasons') or []}
            if canonical and {'REQUEST_TERM','DOMAIN','SECTION_INTENT'} & reasons and canonical not in weak_candidates:
                weak_candidates.append(canonical)
            if len(weak_candidates)>=8:
                break

    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()
    edges: list[dict[str, Any]] = []
    visited_ids: set[str] = set()
    frontier = list(anchors)
    reference_origin_paths: dict[str, set[str]] = {}
    full_cardinality_required = _requires_full_relationship_cardinality(request)

    def add_ref(ref: dict[str, Any], *, relationship_id: str, relationship_kind: str) -> None:
        key = (str(ref.get('path') or ''), str(ref.get('selector') or ''))
        if key in selected_keys:
            return
        copied = dict(ref)
        copied['relevance_score'] = max(int(copied.get('relevance_score') or 0), 950 if relationship_kind == 'SAME_CANONICAL_ID' else 900)
        reasons = list(copied.get('relevance_reasons') or [])
        marker = 'RELATIONSHIP_' + relationship_kind
        if marker not in reasons:
            reasons.insert(0, marker)
        copied['relevance_reasons'] = reasons
        selected.append(copied); selected_keys.add(key)
        edges.append({
            'relationship_id': relationship_id,
            'kind': relationship_kind,
            'path': copied.get('path'),
            'selector': copied.get('selector'),
            'canonical_record_id': copied.get('canonical_record_id'),
        })

    for depth in range(max_depth):
        if not frontier:
            break
        next_frontier: list[str] = []
        for relationship_id in frontier:
            if relationship_id in visited_ids:
                continue
            visited_ids.add(relationship_id)
            same = [ref for ref in routed_refs if str(ref.get('canonical_record_id') or '') == relationship_id or str(ref.get('structural_id') or '') == relationship_id]
            origin_paths = reference_origin_paths.get(relationship_id, set())
            referenced = [
                ref for ref in routed_refs
                if relationship_id in {str(x) for x in ref.get('reference_ids') or []}
                and str(ref.get('path') or '') not in origin_paths
            ]
            # Default to one representative relationship record per routed file.  When the
            # request explicitly asks for complete cardinality, enumerate every direct match
            # with the same generic algorithm, regardless of business domain.
            for relationship_kind, matches in (('SAME_CANONICAL_ID', same), ('REFERENCE_ID', referenced)):
                per_path: set[str] = set()
                for ref in sorted(matches, key=lambda item: (str(item.get('path') or ''), str(item.get('selector') or ''))):
                    path = str(ref.get('path') or '')
                    enumerate_all = full_cardinality_required and relationship_kind == 'REFERENCE_ID'
                    if path in per_path and not enumerate_all:
                        continue
                    per_path.add(path)
                    add_ref(ref, relationship_id=relationship_id, relationship_kind=relationship_kind)
                    for reference_id in ref.get('reference_ids') or []:
                        candidate = str(reference_id)
                        if not candidate or candidate in visited_ids or candidate in next_frontier:
                            continue
                        # Propagate only references that have an actual relationship target inside routed Authorities.
                        has_target = any(
                            str(other.get('canonical_record_id') or '') == candidate
                            or str(other.get('structural_id') or '') == candidate
                            or candidate in {str(x) for x in other.get('reference_ids') or []}
                            for other in routed_refs
                        )
                        if has_target:
                            reference_origin_paths.setdefault(candidate, set()).add(path)
                            next_frontier.append(candidate)
        frontier = next_frontier

    return {
        'anchor_ids': anchors,
        'anchor_reasons': anchor_reasons,
        'anchor_mode': 'STRONG_ANCHOR' if anchors else 'NO_SPECIFIC_ANCHOR',
        'weak_candidate_ids': weak_candidates,
        'relationship_refs': selected,
        'relationship_edges': edges,
        'relationship_ids_visited': sorted(visited_ids),
        'cardinality_mode': 'FULL_REQUIRED' if full_cardinality_required else 'REPRESENTATIVE_ALLOWED',
        'complete_semantics': 'RELATIONSHIP_PATH_RESOLVED',
    }


def _routed_file_ref(path: str, groups: dict[str, set[str]], group_domains: dict[str, set[str]]) -> dict[str, Any]:
    group, domains = _path_route_metadata(path, groups, group_domains)
    return {
        'record_id': None, 'canonical_record_id': None, 'canonical_id_key': None, 'structural_id': None,
        'identity_kind': 'ROUTED_FILE_REF', 'fallback_locator': path, 'section': None, 'selector': None,
        'path': path, 'display_path': _decode_display_path(path), 'title': '', 'domains': [], 'references': [],
        'reference_ids': [], 'authority_group': group, 'authority_domains': domains, 'ref_only': True,
        'relevance_score': 0, 'relevance_reasons': ['ROUTED_AUTHORITY_FILE_MINIMUM_RECALL'],
    }


def query_authority_result(
    root: Path,
    *,
    request: str,
    domains: Iterable[str] = (),
    authority_paths: Iterable[str] = (),
    max_records: int | None = None,
    build_if_missing: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    state = authority_index_status(root)
    if state['status'] in {'MISSING', 'STALE', 'INVALID'} and build_if_missing:
        build_authority_index(root, force=state['status'] != 'MISSING')
        state = authority_index_status(root)
    if state['status'] not in {'READY', 'PARTIAL'}:
        return {'status': state['status'], 'refs': [], 'index': state, 'diagnostics': {}}
    cfg = load_context_efficiency_config(root)
    loading = cfg['context_loading']
    limit = max(0, int(max_records or loading['authority']['initial_records']))
    explicit_ids = list(dict.fromkeys(_ID_VALUE.findall(request)))
    explicit_ids.extend(token for token in _WORD.findall(request) if token.startswith('HTTP:') or token.startswith('OPENAPI_PATH:'))
    explicit_endpoints = list(dict.fromkeys(_ENDPOINT.findall(request)))
    explicit_ids = list(dict.fromkeys(explicit_ids + explicit_endpoints))
    terms = _query_terms(request)
    wanted_domains = {str(x).upper() for x in domains}
    groups, group_domains = _authority_route_map(root, domains, authority_paths)
    selected_paths = set().union(*groups.values()) if groups else set()
    conn = _open_index(root)
    try:
        rows = _candidate_rows(
            conn,
            selected_paths=selected_paths,
            explicit_ids=explicit_ids,
            terms=terms,
            wanted_domains={x.lower() for x in wanted_domains},
        )
        scored: list[tuple[int, str, dict[str, Any]]] = []
        routed_refs: list[dict[str, Any]] = []
        for row in rows:
            group, authority_domains = _path_route_metadata(str(row['path']), groups, group_domains)
            ref = _row_to_ref(row, authority_group=group, authority_domains=authority_domains)
            routed_refs.append(ref)
            identities = {str(x) for x in (ref.get('canonical_record_id'), ref.get('structural_id'), ref.get('fallback_locator')) if x}
            search = str(row['search_text']).lower()
            references = {str(x) for x in ref['references']}
            score = 0
            reasons: list[str] = []
            endpoint_hits = [value for value in explicit_endpoints if value in identities or value.lower() in search]
            exact_hits = [value for value in explicit_ids if value in identities or value.lower() in search]
            literal_identity_hits = [value for value in identities if _literal_identity_in_request(value, request)]
            if endpoint_hits:
                score += 1200
                reasons.append('EXPLICIT_ENDPOINT')
            elif exact_hits or literal_identity_hits:
                score += 1000
                reasons.append('EXPLICIT_ID')
            ref_hits = [value for value in explicit_ids if value in references]
            if ref_hits:
                score += 180 * len(ref_hits)
                reasons.append('REFERENCES_EXPLICIT_ID')
            if group:
                score += 80
                reasons.append('ROUTED_AUTHORITY')
            candidate_domains = {str(x).upper() for x in ref['domains']} | {str(x).upper() for x in authority_domains}
            domain_hits = wanted_domains & candidate_domains
            if domain_hits:
                score += 90 + 10 * len(domain_hits)
                reasons.append('DOMAIN')
            matched = [term for term in terms if term.lower() in search]
            if matched:
                score += sum(min(18, max(2, len(term))) for term in matched)
                reasons.append('REQUEST_TERM')
            intent_bonus = _section_intent_bonus(request, str(ref.get('section') or ''))
            if intent_bonus:
                score += intent_bonus
                reasons.append('SECTION_INTENT')
            if score <= 0:
                continue
            ref['relevance_score'] = score
            ref['relevance_reasons'] = reasons
            scored.append((score, f"{ref['path']}::{ref['selector']}", ref))
        scored.sort(key=lambda row: (-row[0], row[1]))
        authority_backed_domains = wanted_domains & set().union(*group_domains.values()) if group_domains else set()
        baseline, recall = _choose_diverse(
            scored,
            limit=limit,
            authority_groups=groups,
            routed_paths=selected_paths,
            authority_backed_domains=authority_backed_domains,
            min_per_authority=max(0, int(loading.get('minimum_records_per_authority', 1))),
            min_per_domain=max(0, int(loading.get('minimum_records_per_domain', 1))),
        )
        closure = _relationship_closure(routed_refs, scored, explicit_ids=explicit_ids, request=request)
        relationship_refs = list(closure.get('relationship_refs') or [])
        core_minimum_refs: list[dict[str, Any]] = []
        for path in sorted(selected_paths):
            best = next((dict(candidate) for _, _, candidate in scored if str(candidate.get('path') or '') == path), None)
            if best is None:
                continue
            reasons = list(best.get('relevance_reasons') or [])
            if 'CORE_AUTHORITY_MINIMUM' not in reasons:
                reasons.insert(0, 'CORE_AUTHORITY_MINIMUM')
            best['relevance_reasons'] = reasons
            core_minimum_refs.append(best)
        # Relationship closure is selected before generic Top-N. initial_records is only the
        # normal first-batch target. Relationship and routed-core minimum facts are correctness-
        # driven and may exceed that target without turning it into a hard context budget.
        chosen: list[dict[str, Any]] = []
        chosen_keys: set[tuple[str, str]] = set()
        for candidate in relationship_refs:
            key = (str(candidate.get('path') or ''), str(candidate.get('selector') or ''))
            if key in chosen_keys:
                continue
            chosen.append(candidate); chosen_keys.add(key)
        for candidate in core_minimum_refs:
            key = (str(candidate.get('path') or ''), str(candidate.get('selector') or ''))
            if key in chosen_keys:
                continue
            chosen.append(candidate); chosen_keys.add(key)
        for candidate in baseline:
            key = (str(candidate.get('path') or ''), str(candidate.get('selector') or ''))
            if key in chosen_keys or len(chosen) >= max(limit, len(relationship_refs) + len(core_minimum_refs)):
                continue
            chosen.append(candidate); chosen_keys.add(key)
        unresolved_relationship_refs = [
            ref for ref in relationship_refs
            if (str(ref.get('path') or ''), str(ref.get('selector') or '')) not in chosen_keys
        ]
        # If routed files outnumber the record budget, preserve them as compact refs rather than silently dropping them.
        represented_before_refs = {str(ref.get('path') or '') for ref in chosen if ref.get('path')}
        file_ref_paths = sorted(path for path in selected_paths if path not in represented_before_refs)
        chosen.extend(_routed_file_ref(path, groups, group_domains) for path in file_ref_paths)
        parse_error_paths = {str(item.get('path')) for item in state.get('parse_errors') or []}
        routed_parse_errors = sorted(path for path in selected_paths if path in parse_error_paths)
        status = 'TRUNCATED' if file_ref_paths else 'READY'
        final_represented_files = {str(ref.get('path')) for ref in chosen if ref.get('path')}
        final_unrepresented_files = sorted(path for path in selected_paths if path not in final_represented_files)
        final_represented_groups = {str(ref.get('authority_group')) for ref in chosen if ref.get('authority_group')}
        final_unrepresented_groups = sorted(group for group in groups if group not in final_represented_groups)
        final_represented_domains: set[str] = set()
        for ref in chosen:
            final_represented_domains.update(str(x).upper() for x in (ref.get('domains') or []) + (ref.get('authority_domains') or []))
        final_missing_domains = sorted(domain for domain in authority_backed_domains if domain not in final_represented_domains)
        if state['status'] == 'PARTIAL' or routed_parse_errors or final_unrepresented_files or final_unrepresented_groups or final_missing_domains:
            status = 'PARTIAL'
        relationship_complete = not unresolved_relationship_refs
        if not relationship_complete and status == 'READY':
            status = 'TRUNCATED'
        relationship_keys = {(str(ref.get('path') or ''), str(ref.get('selector') or '')) for ref in relationship_refs}
        selected_relationship_count = sum(
            1 for ref in chosen
            if (str(ref.get('path') or ''), str(ref.get('selector') or '')) in relationship_keys
        )
        diagnostics = {
            **recall,
            'represented_domains': sorted(final_represented_domains),
            'missing_domains': final_missing_domains,
            'relationship_closure': {
                'anchor_ids': list(closure.get('anchor_ids') or []),
                'anchor_reasons': dict(closure.get('anchor_reasons') or {}),
                'anchor_mode': str(closure.get('anchor_mode') or 'NO_SPECIFIC_ANCHOR'),
                'weak_candidate_ids': list(closure.get('weak_candidate_ids') or []),
                'complete': relationship_complete,
                'complete_semantics': str(closure.get('complete_semantics') or 'RELATIONSHIP_PATH_RESOLVED'),
                'cardinality_mode': str(closure.get('cardinality_mode') or 'REPRESENTATIVE_ALLOWED'),
                'selected_relationship_count': selected_relationship_count,
                'candidate_relationship_count': len(relationship_refs),
                'missing_relationships': [
                    {'path': ref.get('path'), 'selector': ref.get('selector'), 'canonical_record_id': ref.get('canonical_record_id'), 'reference_ids': ref.get('reference_ids')}
                    for ref in unresolved_relationship_refs
                ],
                'candidate_refs': [
                    {'path': ref.get('path'), 'selector': ref.get('selector'), 'canonical_record_id': ref.get('canonical_record_id'), 'reference_ids': ref.get('reference_ids')}
                    for ref in relationship_refs
                ],
                'edges': list(closure.get('relationship_edges') or []),
            },
            'represented_authority_files': sorted(final_represented_files),
            'unrepresented_authority_files': final_unrepresented_files,
            'represented_authority_groups': sorted(final_represented_groups),
            'unrepresented_authority_groups': final_unrepresented_groups,
            'routed_authority_groups': {name: sorted(paths) for name, paths in groups.items()},
            'routed_parse_error_sources': routed_parse_errors,
            'direct_read_required': routed_parse_errors,
            'candidate_count': len(scored),
            'selected_count': len(chosen),
            'max_records': limit,
        }
        return {'status': status, 'refs': chosen, 'index': state, 'diagnostics': diagnostics}
    finally:
        conn.close()


def query_authority(
    root: Path,
    *,
    request: str,
    domains: Iterable[str] = (),
    authority_paths: Iterable[str] = (),
    max_records: int | None = None,
    build_if_missing: bool = True,
) -> list[dict[str, Any]]:
    return query_authority_result(
        root,
        request=request,
        domains=domains,
        authority_paths=authority_paths,
        max_records=max_records,
        build_if_missing=build_if_missing,
    )['refs']


def refs_by_id(
    root: Path,
    record_id: str,
    *,
    authority_paths: Iterable[str] = (),
    selector: str | None = None,
) -> list[dict[str, Any]]:
    root = root.resolve()
    state = authority_index_status(root)
    if state['status'] in {'MISSING', 'STALE', 'INVALID'}:
        build_authority_index(root, force=state['status'] != 'MISSING')
    conn = _open_index(root)
    selected = {str(x).replace('\\', '/') for x in authority_paths}
    try:
        rows = list(conn.execute(
            '''SELECT canonical_record_id,canonical_id_key,structural_id,identity_kind,locator_key,section,selector,path,display_path,title,domains_json,references_json,reference_ids_json,search_text
               FROM records WHERE canonical_record_id=? OR structural_id=? OR locator_key=? OR reference_ids_json LIKE ? ORDER BY path, selector''',
            (record_id, record_id, record_id, '%\"' + record_id.replace('%','') + '\"%'),
        ))
        direct_refs = []
        referenced_refs = []
        for row in rows:
            ref = _row_to_ref(row)
            if record_id in {str(ref.get('canonical_record_id') or ''), str(ref.get('structural_id') or ''), str(ref.get('fallback_locator') or '')}:
                direct_refs.append(ref)
            elif record_id in {str(x) for x in ref.get('reference_ids') or []}:
                referenced_refs.append(ref)
        refs = direct_refs if direct_refs else referenced_refs
        if selected:
            refs = [ref for ref in refs if ref['path'] in selected or ref['display_path'] in selected]
        if selector is not None:
            refs = [ref for ref in refs if ref['selector'] == selector]
        ambiguous = len(refs) > 1
        for ref in refs:
            ref['ambiguous'] = ambiguous
            ref['candidate_count'] = len(refs)
        return refs
    finally:
        conn.close()


def _load_source(root: Path, path: str, source_cache: dict[str, Any]) -> Any:
    if path in source_cache:
        return source_cache[path]
    source = root / path
    if source.suffix.lower() in {'.yaml', '.yml'}:
        value = yaml.safe_load(source.read_text(encoding='utf-8'))
    elif source.suffix.lower() == '.json':
        value = json.loads(source.read_text(encoding='utf-8'))
    elif source.suffix.lower() == '.csv':
        with source.open('r', encoding='utf-8-sig', newline='') as fh:
            value = {'rows': list(csv.DictReader(fh))}
    else:
        value = None
    source_cache[path] = value
    return value


def _resolve_selector(data: Any, selector: str) -> Any:
    if not isinstance(selector, str) or not selector.startswith('/'):
        raise ValueError('INVALID_SELECTOR')
    current = data
    for raw_part in selector[1:].split('/'):
        part = _pointer_decode(raw_part)
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise ValueError('INVALID_SELECTOR') from exc
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
        elif isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
        else:
            return _MISSING
    return current


def authority_preview(refs: list[dict[str, Any]], *, max_chars: int | None = None) -> dict[str, Any]:
    """Return the first precise locator batch. This is a loading batch, never a Task quota."""
    limit = None if max_chars is None else max(0, int(max_chars))
    used=0; items=[]
    for ref in refs:
        compact={
            'record_id':ref.get('record_id'),'canonical_record_id':ref.get('canonical_record_id'),'identity_kind':ref.get('identity_kind'),
            'fallback_locator':ref.get('fallback_locator'),'section':ref.get('section'),'title':ref.get('title'),'path':ref.get('display_path') or ref.get('path'),
            'selector':ref.get('selector'),'authority_group':ref.get('authority_group'),'relevance_score':ref.get('relevance_score'),'relevance_reasons':ref.get('relevance_reasons'),
            'references':list(ref.get('references') or [])[:12],
        }
        chars=len(json.dumps(compact,ensure_ascii=False,separators=(',',':')))
        if limit is not None and items and used+chars>limit: break
        items.append(compact); used+=chars
    truncated=len(items)<len(refs); record_count=sum(1 for item in items if item.get('identity_kind')!='ROUTED_FILE_REF'); ref_only_count=len(items)-record_count
    if not refs: status='NO_RECORDS'
    elif record_count==0 and ref_only_count: status='REF_ONLY'
    elif truncated: status='TRUNCATED'
    else: status='PASS'
    return {'status':status,'strategy':'DETERMINISTIC_AUTHORITY_RECORD_LOCATOR','authority_is_source_of_truth':True,'preview_is_authority':False,
            'batch_chars':limit,'used_chars':used,'record_count':record_count,'ref_only_count':ref_only_count,'truncated':truncated,'records':items,
            'expansion_mode':'ADAPTIVE_ON_DEMAND_BY_CANONICAL_ID_OR_LOCATOR'}


def expand_authority_refs(root: Path, refs: list[dict[str, Any]], *, max_chars: int | None = None, max_record_chars: int | None = None) -> dict[str, Any]:
    """Expand exact Authority refs. max_chars/max_record_chars bound one response batch only, never future reads."""
    root=root.resolve(); state=authority_index_status(root)
    if state['status'] in {'MISSING','STALE','INVALID'}: build_authority_index(root, force=state['status']!='MISSING')
    total_limit=None if max_chars is None else max(0,int(max_chars)); record_limit=None if max_record_chars is None else max(0,int(max_record_chars))
    used=0; slices=[]; errors=[]; source_cache={}; ref_only_count=0
    for ref in refs:
        if ref.get('ref_only') or ref.get('identity_kind')=='ROUTED_FILE_REF': ref_only_count+=1; continue
        if total_limit is not None and slices and used>=total_limit: break
        path=str(ref.get('path') or ''); selector=str(ref.get('selector') or ''); source=root/path
        if not path or not source.is_file(): errors.append({'path':path,'selector':selector,'status':'NOT_FOUND','reason':'AUTHORITY_SOURCE_NOT_FOUND'}); continue
        try: value=_resolve_selector(_load_source(root,path,source_cache),selector)
        except ValueError: errors.append({'path':path,'selector':selector,'status':'INVALID_SELECTOR','reason':'SELECTOR_PARSE_FAILED'}); continue
        except Exception as exc: errors.append({'path':path,'selector':selector,'status':'ERROR','reason':type(exc).__name__}); continue
        if value is _MISSING: errors.append({'path':path,'selector':selector,'status':'NOT_FOUND','reason':'SELECTOR_RECORD_NOT_FOUND'}); continue
        serialized=json.dumps(value,ensure_ascii=False,separators=(',',':'),default=str); allowed=len(serialized)
        if record_limit is not None: allowed=min(allowed,record_limit)
        if total_limit is not None: allowed=min(allowed,max(0,total_limit-used))
        if allowed<=0: break
        full=len(serialized)<=allowed; content=value if full else serialized[:max(0,allowed-1)]+'…'; chars=len(serialized) if full else len(content)
        rid=ref.get('record_id'); locator=ref.get('fallback_locator') or f'{path}#{selector}'
        slices.append({'record_id':rid,'canonical_record_id':ref.get('canonical_record_id'),'identity_kind':ref.get('identity_kind'),'fallback_locator':locator,
                       'section':ref.get('section'),'selector':selector,'path':path,'display_path':ref.get('display_path'),'relevance_score':ref.get('relevance_score'),
                       'relevance_reasons':ref.get('relevance_reasons'),'content':content,'content_chars':chars,'full_record':full,
                       'expand_command':(f'python -m tools.context.authority_query --root . --id {json.dumps(str(rid))} --expand' if rid and ref.get('canonical_record_id') else f'python -m tools.context.authority_query --root . --authority-path {json.dumps(path)} --selector {json.dumps(selector)} --expand')})
        used+=chars
    expandable=max(0,len(refs)-ref_only_count); truncated=len(slices)<expandable or any(not x['full_record'] for x in slices)
    if not refs: status='NO_RECORDS'
    elif errors:
        statuses={str(x['status']) for x in errors}
        if not slices and statuses=={'INVALID_SELECTOR'}: status='INVALID_SELECTOR'
        elif not slices and statuses=={'NOT_FOUND'}: status='NOT_FOUND'
        elif not slices and 'ERROR' in statuses: status='ERROR'
        else: status='PARTIAL'
    elif not slices and ref_only_count: status='REF_ONLY'
    elif not slices: status='NO_RECORDS'
    elif truncated: status='TRUNCATED'
    else: status='PASS'
    return {'status':status,'strategy':'ADAPTIVE_AUTHORITY_EXPANSION','authority_is_source_of_truth':True,'record_count':len(slices),'ref_only_count':ref_only_count,
            'batch_chars':total_limit,'used_chars':used,'truncated':truncated,'records':slices,'errors':errors,'can_continue_expanding':True}
