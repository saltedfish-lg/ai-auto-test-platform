from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import ast
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .project_profile import command_tokens, format_command, match_any, technology_config
from .task_context import load_context, task_dir

TODO_RE = re.compile(r'\b(?:TODO|FIXME)\b', re.IGNORECASE)


def _language_for(rel: str, tech: dict[str, Any]) -> str | None:
    languages = tech.get('languages') or {}
    if not isinstance(languages, dict):
        return None
    for name, cfg in languages.items():
        if not isinstance(cfg, dict):
            continue
        if match_any(rel, [str(x) for x in cfg.get('paths') or []]):
            return str(cfg.get('adapter') or name)
    return None


def _checks_for(adapter: str | None, tech: dict[str, Any]) -> list[Any]:
    adapters = tech.get('adapters') or {}
    if not isinstance(adapters, dict):
        return ['no_unresolved_todo']
    cfg = adapters.get(adapter or 'generic') or adapters.get('generic') or {}
    if not isinstance(cfg, dict):
        return ['no_unresolved_todo']
    checks = cfg.get('checks') or []
    return list(checks) if isinstance(checks, list) else ['no_unresolved_todo']


def evaluate(root: Path, affected_files: list[str]) -> dict[str, Any]:
    root = root.resolve(); tech = technology_config(root); findings: list[dict[str, Any]] = []; executed: list[dict[str, Any]] = []
    existing = [rel for rel in sorted(set(affected_files)) if (root / rel).is_file()]
    by_adapter: dict[str, list[str]] = {}
    for rel in existing:
        adapter = _language_for(rel, tech) or 'generic'
        by_adapter.setdefault(adapter, []).append(rel)

    for adapter, files in sorted(by_adapter.items()):
        for check in _checks_for(adapter, tech):
            if check == 'no_unresolved_todo':
                for rel in files:
                    text = (root / rel).read_text(encoding='utf-8', errors='ignore')
                    for line_no, line in enumerate(text.splitlines(), 1):
                        if TODO_RE.search(line):
                            findings.append({'path': rel, 'line': line_no, 'check': check, 'reason': 'unresolved TODO/FIXME in current task file'})
                executed.append({'adapter': adapter, 'check': check, 'files': files})
            elif check == 'python_syntax':
                for rel in files:
                    if not rel.lower().endswith('.py'):
                        continue
                    try:
                        ast.parse((root / rel).read_text(encoding='utf-8'))
                    except SyntaxError as exc:
                        findings.append({'path': rel, 'line': exc.lineno or 1, 'check': check, 'reason': exc.msg})
                executed.append({'adapter': adapter, 'check': check, 'files': files})
            elif isinstance(check, dict):
                tokens = command_tokens(check.get('command'))
                if not tokens:
                    findings.append({'path': None, 'line': None, 'check': 'custom', 'reason': 'invalid custom command'})
                    continue
                cmd = format_command(tokens, root=root, task_id='', files=files)
                proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=int(check.get('timeout', 300)), check=False)
                executed.append({'adapter': adapter, 'check': 'custom', 'command': cmd, 'files': files, 'exit_code': proc.returncode})
                if proc.returncode != 0:
                    findings.append({'path': None, 'line': None, 'check': 'custom', 'reason': (proc.stderr or proc.stdout)[-1000:]})
            else:
                findings.append({'path': None, 'line': None, 'check': str(check), 'reason': 'unknown configured check'})

    return {
        'status': 'PASS' if not findings else 'FAIL',
        'checked_files': existing,
        'executed_checks': executed,
        'findings': findings,
    }


def run(root: Path, task_id: str) -> dict[str, Any]:
    ctx = load_context(root, task_id)
    result = evaluate(root, [str(x) for x in ctx.get('affected_files', [])])
    result['task_id'] = task_id
    result['executed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    out = task_dir(root, task_id) / 'code-quality-result.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.'); p.add_argument('--task-id', required=True); a = p.parse_args()
    result = run(Path(a.root), a.task_id); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
