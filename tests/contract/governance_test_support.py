from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools.governance.impact_scan import GENERIC_AUTO_REQUIRED_GATES, scan
from tools.governance.required_gate_runner import run_required
from tools.governance.task_context import cleanup_task, gate_results_path, load_context
from tools.governance.task_governance import finish, reconcile_task, resolve_product_decision, run_gates, start

ROOT = Path(__file__).resolve().parents[2]
STANDALONE = ROOT / 'agent-governance-lite'


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _project(root: Path, gates: dict[str, list[str]] | None = None, *, two_gates: bool = False) -> None:
    gates = gates or {
        'app_gate': [sys.executable, '-c', 'import sys; sys.exit(0)'],
        'code_quality_gate': [sys.executable, 'tools/governance/code_quality_gate.py', '--root', '.', '--task-id', '{task_id}'],
    }
    _write(root / '.governance/project.yaml', '''schema_version: 1
project:
  name: governance-fixture
runtime:
  use_legacy_domain_metadata: false
  allow_no_gates: false
''')
    domain_gates = '[app_gate, second_gate]' if two_gates else '[app_gate]'
    _write(root / '.governance/domains.yaml', f'''schema_version: 1
domains:
  APP:
    kind: implementation
    paths: ["src/**"]
    gates: {domain_gates}
''')
    gate_lines = ['schema_version: 1', 'gates:']
    for name, command in gates.items():
        gate_lines.append(f'  {name}:')
        gate_lines.append('    command: [' + ', '.join(json.dumps(x) for x in command) + ']')
    if two_gates and 'second_gate' not in gates:
        gate_lines += ['  second_gate:', f'    command: [{json.dumps(sys.executable)}, -c, "import sys; sys.exit(0)"]']
    _write(root / '.governance/gates.yaml', '\n'.join(gate_lines) + '\n')
    _write(root / '.governance/reviewers.yaml', '''schema_version: 1
reviewers:
  architecture_reviewer:
    trigger:
      risk: [ARCHITECTURE]
  product_sovereignty_reviewer:
    trigger:
      sovereignty_any: true
  code_quality_reviewer:
    trigger:
      risk: [CODE_QUALITY_HIGH_RISK]
''')
    _write(root / '.governance/authorities.yaml', 'schema_version: 1\nauthorities: {}\n')
    _write(root / '.governance/policies.yaml', '''schema_version: 1
policies:
  request_domain_signals:
    APP: [app]
''')
    _write(root / '.governance/technology.yaml', '''schema_version: 1
technology:
  languages:
    python:
      paths: ["**/*.py"]
      adapter: python
  adapters:
    python:
      checks: [no_unresolved_todo, python_syntax]
    generic:
      checks: [no_unresolved_todo]
''')
    _write(root / 'src/a.py', 'x = 1\n')


def _start_changed(root: Path, task: str, request: str = 'modify app') -> dict:
    ctx = start(root, task, request, ['src/a.py'])
    _write(root / 'src/a.py', 'x = 2\n')
    return ctx


def _abort_if_present(root: Path, task: str) -> None:
    if (root / '.tmp/agent-governance' / task).exists():
        finish(root, task, 'ABORTED')


