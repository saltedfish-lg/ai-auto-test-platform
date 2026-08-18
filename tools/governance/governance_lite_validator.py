from __future__ import annotations

# Support both package imports and the documented direct-script CLI form.
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.governance'

import argparse
import fnmatch
import json
import re
import tempfile
import tomllib
from pathlib import Path

import yaml

from .project_profile import authority_config, command_tokens, domain_config, gate_config, reviewer_config, technology_config
from .required_gate_runner import formal_gate_ids

REQUIRED_CORE_AGENTS = {
    'default_coder.toml',
    'architecture_reviewer.toml',
    'product_sovereignty_reviewer.toml',
    'code_quality_reviewer.toml',
}
REQUIRED_CORE_SKILLS = {'context-efficiency', 'feature-orchestrator', 'product-sovereignty', 'code-quality'}
FORBIDDEN_ACTIVE = (
    'SIGNED_EXPLICIT_SLICE', 'Trust Anchor', 'Trust State', 'TRUST_STATE', 'TRUST_ANCHOR',
    'anti-rollback', 'Anti-Rollback', 'attestation', 'Attestation', 'producer trust', 'Producer Trust',
    'revocation state', 'Evidence Trust', 'evidence-trust-policy', 'external signature', 'Task Certificate',
    'Trust Bootstrap', 'Trust Generation', 'trusted head', 'Trusted Head',
)
PROJECT_HARDCODE_TOKENS = (
    'ai-auto-test-platform', 'apps/web', 'apps/api', 'mysql84', 'mysql 8.4', 'playwright', 'default admin', ' pda ',
)
GENERIC_ROOTS = ('.agents/skills', '.agents/agent-roles', '.codex/agents', 'tools/governance')
ONE_TIME_REPORT_GLOBS = ('GovernanceLite*报告*', 'GovernanceLite*清单*', 'GovernanceLite*遗留*')


def _text_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    paths = [base] if base.is_file() else [p for p in base.rglob('*') if p.is_file()]
    return [p for p in paths if '__pycache__' not in p.parts and p.suffix.lower() not in {'.pyc', '.pyo', '.zip'}]


def _cross_reference_errors(root: Path) -> list[str]:
    errors: list[str] = []; files: list[Path] = []
    for rel in ('AGENTS.md', 'README.md', '.governance', '.agents', '.codex'):
        files.extend(_text_files(root / rel))
    installed_agent_names = {p.stem for p in (root / '.codex/agents').glob('*.toml')}
    for f in files:
        try: txt = f.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError): continue
        for skill in re.findall(r'\$([a-z0-9][a-z0-9-]+)', txt):
            if not (root / '.agents/skills' / skill / 'SKILL.md').is_file():
                errors.append(f'{f.relative_to(root)}: missing skill {skill}')
        for agent in re.findall(r'\b([a-z][a-z0-9_]*(?:_reviewer|_coder))\b', txt):
            if agent not in installed_agent_names:
                errors.append(f'{f.relative_to(root)}: missing agent {agent}')
        patterns = (
            r'tools/governance/[A-Za-z0-9_-]+\.py', r'\.codex/agents/[A-Za-z0-9_-]+\.toml',
            r'\.agents/skills/[A-Za-z0-9_-]+/SKILL\.md', r'\.agents/skills/[A-Za-z0-9_-]+/references/[A-Za-z0-9_.-]+\.md',
            r'\.agents/agent-roles/[A-Za-z0-9_-]+\.md',
        )
        for pattern in patterns:
            for ref in re.findall(pattern, txt):
                if not (root / ref).is_file(): errors.append(f'{f.relative_to(root)}: dangling path {ref}')
    return sorted(set(errors))


def _profile_errors(root: Path) -> list[str]:
    errors: list[str] = []; base = root / '.governance'
    required = ('project.yaml', 'domains.yaml', 'authorities.yaml', 'gates.yaml', 'reviewers.yaml', 'policies.yaml', 'technology.yaml')
    for name in required:
        path = base / name
        if not path.is_file(): errors.append(f'.governance/{name}: missing')
        else:
            try:
                data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
                if not isinstance(data, dict): errors.append(f'.governance/{name}: root must be mapping')
            except Exception as exc: errors.append(f'.governance/{name}: YAML {exc}')
    if errors: return errors

    domains = domain_config(root); gates = gate_config(root); reviewers = reviewer_config(root); authorities = authority_config(root); tech = technology_config(root)
    formal = formal_gate_ids(root); available_gates = set(gates) | formal
    if not domains: errors.append('.governance/domains.yaml: no domains')
    if not gates: errors.append('.governance/gates.yaml: no gates')

    all_files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.tmp' not in p.parts}
    def exists_or_matches(value: str) -> bool:
        if any(ch in value for ch in '*?['): return any(fnmatch.fnmatch(f, value) for f in all_files)
        return (root / value).exists() or any(f.startswith(value.rstrip('/') + '/') for f in all_files)

    for name, cfg in domains.items():
        paths = cfg.get('paths') or []
        if not isinstance(paths, list) or not paths: errors.append(f'domain {name}: paths missing')
        kind = cfg.get('kind')
        if not isinstance(kind, str) or not kind.strip(): errors.append(f'domain {name}: kind missing')
        for gate in cfg.get('gates') or []:
            if str(gate) not in available_gates: errors.append(f'domain {name}: unknown gate {gate}')
        for route in cfg.get('routes') or []:
            if not isinstance(route, dict): errors.append(f'domain {name}: invalid route'); continue
            for gate in [*(route.get('gates') or []), *(route.get('engineering_gates') or [])]:
                if str(gate) not in available_gates: errors.append(f'domain {name}: route unknown gate {gate}')
        for value in [*(cfg.get('tests') or []), *(cfg.get('authorities') or []), *(cfg.get('authority_files') or [])]:
            if not exists_or_matches(str(value)): errors.append(f'domain {name}: dangling reference {value}')

    for name, cfg in authorities.items():
        paths = cfg.get('paths') or []
        if not isinstance(paths, list) or not paths: errors.append(f'authority {name}: paths missing')
        for value in paths:
            if not exists_or_matches(str(value)): errors.append(f'authority {name}: dangling path {value}')

    for name, cfg in gates.items():
        if not command_tokens(cfg.get('command')): errors.append(f'gate {name}: command invalid')

    valid_reviewers = {p.stem for p in (root / '.codex/agents').glob('*.toml')}
    for name in reviewers:
        if name not in valid_reviewers: errors.append(f'reviewer config references missing agent {name}')

    languages = tech.get('languages') or {}; adapters = tech.get('adapters') or {}
    if not isinstance(languages, dict) or not isinstance(adapters, dict): errors.append('technology: languages/adapters invalid')
    else:
        for lang, cfg in languages.items():
            if isinstance(cfg, dict) and str(cfg.get('adapter') or lang) not in adapters:
                errors.append(f'technology {lang}: unknown adapter {cfg.get("adapter")}')
    return errors


def _hardcode_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for rel in GENERIC_ROOTS:
        for path in _text_files(root / rel):
            if path.name == 'governance_lite_validator.py': continue
            try: text = path.read_text(encoding='utf-8', errors='ignore'); low = f' {text.lower()} '
            except OSError: continue
            for token in PROJECT_HARDCODE_TOKENS:
                if token in low:
                    errors.append(f'{path.relative_to(root)}: project hardcode {token.strip()}'); break
    return errors


def _generic_fixture_probe() -> tuple[bool, str | None]:
    from .impact_scan import scan
    from .task_context import cleanup_task
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir(); (root / 'src/main/java/demo').mkdir(parents=True); (root / 'ui/src').mkdir(parents=True)
            (root / 'src/main/java/demo/App.java').write_text('class App {}\n', encoding='utf-8'); (root / 'ui/src/main.tsx').write_text('export const x = 1\n', encoding='utf-8')
            (root / '.governance/project.yaml').write_text('schema_version: 1\nproject:\n  name: sample-cross-stack\n  type: monorepo\nruntime:\n  use_legacy_domain_metadata: false\n', encoding='utf-8')
            (root / '.governance/domains.yaml').write_text('''schema_version: 1
domains:
  SERVER:
    kind: implementation
    paths: ["src/main/java/**"]
    gates: [java_test]
  CLIENT:
    kind: implementation
    paths: ["ui/src/**"]
    gates: [ui_test]
''', encoding='utf-8')
            (root / '.governance/gates.yaml').write_text('''schema_version: 1
gates:
  java_test:
    command: [python, -c, "print(1)"]
  ui_test:
    command: [python, -c, "print(1)"]
''', encoding='utf-8')
            for name, content in {
                'authorities.yaml': 'schema_version: 1\nauthorities: {}\n', 'reviewers.yaml': 'schema_version: 1\nreviewers: {}\n',
                'policies.yaml': 'schema_version: 1\npolicies: {}\n', 'technology.yaml': 'schema_version: 1\ntechnology:\n  languages: {}\n  adapters: {}\n',
            }.items(): (root / '.governance' / name).write_text(content, encoding='utf-8')
            out = scan(root, 'GENERIC', 'cross module change', ['src/main/java/demo/App.java', 'ui/src/main.tsx'])
            ok = {'SERVER', 'CLIENT'} <= set(out['domains']) and {'java_test', 'ui_test'} <= set(out['required_gates']) and 'architecture_reviewer' in out['review_triggers']
            cleanup_task(root, 'GENERIC')
            return ok, None if ok else json.dumps(out, ensure_ascii=False)
    except Exception as exc:
        return False, repr(exc)


def _domain_request_only_probe() -> tuple[bool, str | None]:
    from .impact_scan import scan
    from .task_context import cleanup_task
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir(); (root / 'authority').mkdir()
            (root / 'authority/identity.yaml').write_text('rule: existing\n', encoding='utf-8')
            (root / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: request-only}\nruntime:\n  use_legacy_domain_metadata: false\n', encoding='utf-8')
            (root / '.governance/domains.yaml').write_text('''schema_version: 1
domains:
  PORTAL:
    kind: implementation
    paths: ["portal/**"]
    gates: [portal_check]
    reviewer_risks: [UI_RISK]
  IDENTITY:
    kind: authority
    paths: ["authority/**"]
    gates: [identity_check]
    authority_files: ["authority/identity.yaml"]
    reviewer_risks: [SECURITY_RISK]
''', encoding='utf-8')
            (root / '.governance/gates.yaml').write_text('''schema_version: 1
gates:
  portal_check: {command: [python, -c, "print(1)"]}
  identity_check: {command: [python, -c, "print(1)"]}
''', encoding='utf-8')
            (root / '.governance/reviewers.yaml').write_text('''schema_version: 1
reviewers:
  code_quality_reviewer:
    trigger:
      risk: [UI_RISK, SECURITY_RISK]
''', encoding='utf-8')
            (root / '.governance/authorities.yaml').write_text('''schema_version: 1
authorities:
  identity:
    domains: [IDENTITY]
    paths: [authority/identity.yaml]
''', encoding='utf-8')
            (root / '.governance/policies.yaml').write_text('''schema_version: 1
policies:
  request_domain_signals:
    PORTAL: [portal]
    IDENTITY: [login]
''', encoding='utf-8')
            (root / '.governance/technology.yaml').write_text('schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n', encoding='utf-8')
            out = scan(root, 'DOMAIN_ONLY', 'portal login change', [])
            ok = (
                out.get('scope_level') == 'DOMAIN'
                and {'PORTAL', 'IDENTITY'} <= set(out.get('domains', []))
                and {'portal_check', 'identity_check'} <= set(out.get('required_gates', []))
                and 'code_quality_reviewer' in out.get('review_triggers', [])
                and 'authority/identity.yaml' in out.get('authorities', [])
            )
            cleanup_task(root, 'DOMAIN_ONLY')
            return ok, None if ok else json.dumps(out, ensure_ascii=False)
    except Exception as exc:
        return False, repr(exc)


def _final_reconciliation_bypass_probe() -> tuple[bool, str | None]:
    from .required_gate_runner import run_required
    from .task_context import cleanup_task, save_context, save_workspace_snapshot
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir()
            (root / '.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n', encoding='utf-8')
            save_workspace_snapshot(root, 'BYPASS')
            save_context(root, 'BYPASS', {'required_gates': ['check'], 'affected_files': [], 'final_reconciliation_status': 'NOT_RUN'})
            out = run_required(root, 'BYPASS', timeout=2)
            cleanup_task(root, 'BYPASS')
            ok = out.get('status') == 'BLOCKED' and out.get('reason') == 'FINAL_RECONCILIATION_REQUIRED'
            return ok, None if ok else json.dumps(out, ensure_ascii=False)
    except Exception as exc:
        return False, repr(exc)


def _no_configured_gate_probe() -> tuple[bool, str | None]:
    from .required_gate_runner import run_required
    from .task_context import cleanup_task, save_context, save_workspace_snapshot
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir()
            (root / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: no-gate}\nruntime:\n  allow_no_gates: false\n', encoding='utf-8')
            save_workspace_snapshot(root, 'NOGATE')
            save_context(root, 'NOGATE', {'required_gates': [], 'affected_files': [], 'final_reconciliation_status': 'PASS', 'actual_changed_files': []})
            out = run_required(root, 'NOGATE', timeout=2)
            cleanup_task(root, 'NOGATE')
            ok = out.get('status') == 'BLOCKED' and out.get('reason') == 'NO_CONFIGURED_GATE'
            return ok, None if ok else json.dumps(out, ensure_ascii=False)
    except Exception as exc:
        return False, repr(exc)



def _finish_gate_closure_probe() -> tuple[bool, str | None]:
    from .task_governance import finish, reconcile_task, start
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir(); (root / 'src').mkdir()
            (root / 'src/a.py').write_text('x=1\n', encoding='utf-8')
            (root / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: closure}\nruntime: {use_legacy_domain_metadata: false}\n', encoding='utf-8')
            (root / '.governance/domains.yaml').write_text('schema_version: 1\ndomains:\n  APP: {kind: implementation, paths: ["src/**"], gates: [check]}\n', encoding='utf-8')
            (root / '.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n', encoding='utf-8')
            for name, content in {
                'authorities.yaml': 'schema_version: 1\nauthorities: {}\n', 'reviewers.yaml': 'schema_version: 1\nreviewers: {}\n',
                'policies.yaml': 'schema_version: 1\npolicies: {}\n', 'technology.yaml': 'schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n',
            }.items(): (root / '.governance' / name).write_text(content, encoding='utf-8')
            start(root, 'FINISH', 'change', ['src/a.py']); (root / 'src/a.py').write_text('x=2\n', encoding='utf-8'); reconcile_task(root, 'FINISH')
            try:
                finish(root, 'FINISH', 'SUCCESS')
            except RuntimeError as exc:
                finish(root, 'FINISH', 'ABORTED')
                return str(exc) == 'REQUIRED_GATES_NOT_EXECUTED', str(exc)
            return False, 'SUCCESS bypassed required gates'
    except Exception as exc:
        return False, repr(exc)


def _gate_freshness_probe() -> tuple[bool, str | None]:
    from .task_governance import finish, run_gates, start
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir(); (root / 'src').mkdir()
            (root / 'src/a.py').write_text('x=1\n', encoding='utf-8')
            (root / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: freshness}\nruntime: {use_legacy_domain_metadata: false}\n', encoding='utf-8')
            (root / '.governance/domains.yaml').write_text('schema_version: 1\ndomains:\n  APP: {kind: implementation, paths: ["src/**"], gates: [check]}\n', encoding='utf-8')
            (root / '.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n', encoding='utf-8')
            for name, content in {
                'authorities.yaml': 'schema_version: 1\nauthorities: {}\n', 'reviewers.yaml': 'schema_version: 1\nreviewers: {}\n',
                'policies.yaml': 'schema_version: 1\npolicies: {}\n', 'technology.yaml': 'schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n',
            }.items(): (root / '.governance' / name).write_text(content, encoding='utf-8')
            start(root, 'FRESH', 'change', ['src/a.py']); (root / 'src/a.py').write_text('x=2\n', encoding='utf-8')
            if run_gates(root, 'FRESH', timeout=2).get('status') != 'PASS': return False, 'gate did not pass'
            (root / 'src/a.py').write_text('x=3\n', encoding='utf-8')
            try:
                finish(root, 'FRESH', 'SUCCESS')
            except RuntimeError as exc:
                finish(root, 'FRESH', 'ABORTED')
                return str(exc) == 'GATE_RESULT_STALE', str(exc)
            return False, 'stale gate result was reused'
    except Exception as exc:
        return False, repr(exc)


def _product_decision_block_probe() -> tuple[bool, str | None]:
    from .required_gate_runner import run_required
    from .task_governance import finish, reconcile_task, start
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / '.governance').mkdir(); (root / 'src').mkdir()
            (root / 'src/a.py').write_text('x=1\n', encoding='utf-8')
            (root / '.governance/project.yaml').write_text('schema_version: 1\nproject: {name: product}\nruntime: {use_legacy_domain_metadata: false}\n', encoding='utf-8')
            (root / '.governance/domains.yaml').write_text('schema_version: 1\ndomains:\n  APP: {kind: implementation, paths: ["src/**"], gates: [check]}\n', encoding='utf-8')
            (root / '.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  check: {command: [python, -c, "print(1)"]}\n', encoding='utf-8')
            (root / '.governance/reviewers.yaml').write_text('schema_version: 1\nreviewers:\n  product_sovereignty_reviewer:\n    trigger: {sovereignty_any: true}\n', encoding='utf-8')
            (root / '.governance/authorities.yaml').write_text('schema_version: 1\nauthorities: {}\n', encoding='utf-8')
            (root / '.governance/policies.yaml').write_text('schema_version: 1\npolicies: {}\n', encoding='utf-8')
            (root / '.governance/technology.yaml').write_text('schema_version: 1\ntechnology: {languages: {}, adapters: {}}\n', encoding='utf-8')
            ctx = start(root, 'PRODUCT', '新增角色并改为允许删除', ['src/a.py']); (root / 'src/a.py').write_text('x=2\n', encoding='utf-8'); reconcile_task(root, 'PRODUCT')
            out = run_required(root, 'PRODUCT', timeout=2)
            ok = ctx.get('product_decision_status') == 'REQUIRED' and out.get('status') == 'BLOCKED' and out.get('reason') == 'PRODUCT_DECISION_REQUIRED'
            finish(root, 'PRODUCT', 'ABORTED')
            return ok, None if ok else json.dumps({'ctx': ctx, 'gate': out}, ensure_ascii=False)
    except Exception as exc:
        return False, repr(exc)

def _standalone_errors(root: Path) -> list[str]:
    base = root / 'agent-governance-lite'; errors: list[str] = []
    if (base / 'templates/project-profile/.agent').exists():
        errors.append('agent-governance-lite: legacy .agent template remains')
    if not base.is_dir():
        # Installed Standalone mode: distribution templates are no longer required,
        # but the copied Runtime/Agents/Skills/Profile must remain self-validating.
        installed_required = [
            'tools/environment.py',
            'tools/governance/impact_scan.py',
            'tools/governance/incremental_closure.py',
            'tools/governance/final_reconciliation.py',
            'tools/governance/required_gate_runner.py',
            'tools/governance/task_governance.py',
            'tools/governance/governance_lite_validator.py',
            'tools/governance/governance_contract_test.py',
            'tools/governance/git_readonly_adapter.py',
            'tools/governance/workspace_writer_lock.py',
            'tools/governance/process_identity.py',
            'tools/governance/workspace-path-policy.yaml',
        ]
        for rel in installed_required:
            if not (root / rel).is_file(): errors.append(f'{rel}: missing from installed standalone')
        runtime_text = '\n'.join(p.read_text(encoding='utf-8', errors='ignore') for p in (root / 'tools/governance').glob('*.py') if p.name != 'governance_lite_validator.py')
        if 'docs/authority/' in runtime_text:
            errors.append('tools/governance: fixed docs/authority path remains in installed standalone')
        return errors
    required = [
        'README.md',
        'requirements.txt',
        'templates/AGENTS.governance-snippet.md',
        *[f'agents/{name}' for name in sorted(REQUIRED_CORE_AGENTS)],
        *[f'skills/{name}/SKILL.md' for name in sorted(REQUIRED_CORE_SKILLS)],
        'runtime/tools/environment.py',
        'runtime/tools/governance/impact_scan.py',
        'runtime/tools/governance/incremental_closure.py',
        'runtime/tools/governance/final_reconciliation.py',
        'runtime/tools/governance/required_gate_runner.py',
        'runtime/tools/governance/task_governance.py',
        'runtime/tools/governance/governance_lite_validator.py',
        'runtime/tools/governance/governance_contract_test.py',
        'runtime/tools/governance/git_readonly_adapter.py',
        'runtime/tools/governance/workspace_writer_lock.py',
        'runtime/tools/governance/process_identity.py',
        'runtime/tools/governance/workspace-path-policy.yaml',
        *[f'templates/project-profile/.governance/{name}' for name in ('project.yaml','domains.yaml','authorities.yaml','gates.yaml','reviewers.yaml','policies.yaml','technology.yaml','workspace-path-policy.yaml')],
    ]
    for rel in required:
        if not (base / rel).is_file(): errors.append(f'agent-governance-lite/{rel}: missing')
    if errors:
        return errors
    for name in REQUIRED_CORE_AGENTS:
        installed = root / '.codex/agents' / name
        if not installed.is_file():
            continue  # Missing Core is reported by the Generic Validator core subset check.
        if (base / 'agents' / name).read_text(encoding='utf-8') != installed.read_text(encoding='utf-8'):
            errors.append(f'agent-governance-lite/agents/{name}: drift')
    for name in REQUIRED_CORE_SKILLS:
        if (base / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8') != (root / '.agents/skills' / name / 'SKILL.md').read_text(encoding='utf-8'):
            errors.append(f'agent-governance-lite/skills/{name}: drift')
    try:
        from .impact_scan import GENERIC_AUTO_REQUIRED_GATES
        standalone_gates = yaml.safe_load((base / 'templates/project-profile/.governance/gates.yaml').read_text(encoding='utf-8')) or {}
        gate_names = set((standalone_gates.get('gates') or {}).keys())
        missing = set(GENERIC_AUTO_REQUIRED_GATES) - gate_names
        if missing: errors.append(f'agent-governance-lite: missing generic auto gates {sorted(missing)}')
        for required_gate in ('governance_lite_validator', 'governance_contract_test'):
            if required_gate not in gate_names:
                errors.append(f'agent-governance-lite: missing governance self-protection gate {required_gate}')
        standalone_domains = yaml.safe_load((base / 'templates/project-profile/.governance/domains.yaml').read_text(encoding='utf-8')) or {}
        governance = (standalone_domains.get('domains') or {}).get('GOVERNANCE') or {}
        governance_paths = {str(x) for x in governance.get('paths') or []}
        governance_gates = {str(x) for x in governance.get('gates') or []}
        for required_path in ('AGENTS.md', '.governance/**', '.agents/**', '.codex/**', 'tools/governance/**', 'agent-governance-lite/**'):
            if required_path not in governance_paths:
                errors.append(f'agent-governance-lite: GOVERNANCE domain missing path {required_path}')
        for required_gate in ('governance_lite_validator', 'governance_contract_test'):
            if required_gate not in governance_gates:
                errors.append(f'agent-governance-lite: GOVERNANCE domain missing gate {required_gate}')
    except Exception as exc:
        errors.append(f'agent-governance-lite: gate registry parse failed {exc}')
    runtime_text = '\n'.join(p.read_text(encoding='utf-8', errors='ignore') for p in (base / 'runtime/tools/governance').glob('*.py') if p.name != 'governance_lite_validator.py')
    if 'docs/authority/' in runtime_text:
        errors.append('agent-governance-lite/runtime: fixed docs/authority path remains')
    for runtime_dir, label in ((root / 'tools/governance', 'tools/governance'), (base / 'runtime/tools/governance', 'agent-governance-lite/runtime')):
        if not runtime_dir.is_dir():
            continue
        for candidate in runtime_dir.glob('*.py'):
            if candidate.name in {'process_identity.py', 'governance_lite_validator.py'}:
                continue
            text = candidate.read_text(encoding='utf-8', errors='ignore')
            if 'os.kill(' in text:
                errors.append(f'{label}/{candidate.name}: direct os.kill liveness probe forbidden; use process_identity')
    req = (base / 'requirements.txt').read_text(encoding='utf-8', errors='ignore')
    if 'PyYAML' not in req: errors.append('agent-governance-lite/requirements.txt: PyYAML missing')
    snippet = (base / 'templates/AGENTS.governance-snippet.md').read_text(encoding='utf-8', errors='ignore')
    for token in ('Full Impact Scan', 'Incremental Closure', 'Product Sovereignty', 'Required Gates', 'Git is user-owned'):
        if token.lower() not in snippet.lower(): errors.append(f'AGENTS governance snippet: missing {token}')
    return errors



def _versioned_governance_test_naming_errors(root: Path) -> list[str]:
    """Reject release/patch naming while allowing capability terms such as final_reconciliation."""
    import ast
    errors: list[str] = []
    base = root / 'tests' / 'contract'
    if not base.is_dir():
        return errors
    file_bad = re.compile(r'(?:^|[_-])(r\d+|finalfixed\d*|fixed\d*|closure)(?:[_-]|$)', re.IGNORECASE)
    func_bad = re.compile(r'(?:^|_)(r\d+|finalfixed\d*|fixed\d*|closure)(?:_|$)', re.IGNORECASE)
    for path in sorted(base.glob('test_governance_*.py')):
        stem = path.stem
        if file_bad.search(stem):
            errors.append(f'{path.relative_to(root)}: versioned governance test filename')
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith('test_'):
                continue
            name = node.name
            bad = bool(re.search(r'(?:^|_)(r\d+|finalfixed\d*|fixed\d*)(?:_|$)', name, re.IGNORECASE))
            if re.search(r'(?:^|_)closure(?:_|$)', name, re.IGNORECASE) and 'incremental_closure' not in name:
                bad = True
            if name.startswith('test_final_') and not (
                name.startswith('test_final_reconciliation') or name.startswith('test_final_workspace_reconciliation')
            ):
                bad = True
            if bad:
                errors.append(f'{path.relative_to(root)}::{name}: versioned governance test function name')
    return errors

def validate(root: Path) -> dict:
    root = root.resolve(); errors: list[str] = []
    legacy_profile = root / '.agent'
    current_profile = root / '.governance'
    if legacy_profile.exists():
        if current_profile.exists():
            errors.append('LEGACY_GOVERNANCE_DIRECTORY_PRESENT: .agent and .governance cannot coexist; remove legacy .agent')
        else:
            errors.append('DEPRECATED_AGENT_PROFILE_DIRECTORY: rename .agent/ to .governance/')
    agents = {p.name for p in (root / '.codex/agents').glob('*.toml')}; skills_root = root / '.agents/skills'; skills = {p.name for p in skills_root.iterdir() if p.is_dir()} if skills_root.is_dir() else set()
    missing_core_agents = REQUIRED_CORE_AGENTS - agents
    missing_core_skills = REQUIRED_CORE_SKILLS - skills
    if missing_core_agents: errors.append(f'missing core agents={sorted(missing_core_agents)}')
    if missing_core_skills: errors.append(f'missing core skills={sorted(missing_core_skills)}')

    for ap in (root / '.codex/agents').glob('*.toml'):
        try: data = tomllib.loads(ap.read_text(encoding='utf-8'))
        except Exception as exc: errors.append(f'{ap.relative_to(root)}: TOML {exc}'); continue
        if data.get('name') != ap.stem: errors.append(f'{ap.relative_to(root)}: name mismatch')
        if data.get('sandbox_mode') not in {'workspace-write', 'read-only'}: errors.append(f'{ap.relative_to(root)}: sandbox_mode invalid')
    for skill in sorted(REQUIRED_CORE_SKILLS):
        sp = root / '.agents/skills' / skill / 'SKILL.md'
        if not sp.is_file(): continue
        head = '\n'.join(sp.read_text(encoding='utf-8').splitlines()[:8])
        if not re.search(rf'(?m)^name:\s*{re.escape(skill)}\s*$', head): errors.append(f'{sp.relative_to(root)}: frontmatter name mismatch')

    errors.extend(_cross_reference_errors(root)); errors.extend(_profile_errors(root)); errors.extend(_hardcode_errors(root)); errors.extend(_versioned_governance_test_naming_errors(root))
    for rel in GENERIC_ROOTS:
        for f in _text_files(root / rel):
            if f.name == 'governance_lite_validator.py': continue
            try: txt = f.read_text(encoding='utf-8', errors='ignore')
            except OSError: continue
            for token in FORBIDDEN_ACTIVE:
                if token.lower() in txt.lower(): errors.append(f'{f.relative_to(root)}: forbidden active governance token {token}'); break

    for pattern in ONE_TIME_REPORT_GLOBS:
        for path in root.glob(pattern): errors.append(f'{path.name}: one-time governance report remains in runtime root')
    fixture_ok, fixture_error = _generic_fixture_probe()
    if not fixture_ok: errors.append(f'generic fixture failed: {fixture_error}')
    domain_ok, domain_error = _domain_request_only_probe()
    if not domain_ok: errors.append(f'domain request-only fixture failed: {domain_error}')
    bypass_ok, bypass_error = _final_reconciliation_bypass_probe()
    if not bypass_ok: errors.append(f'final reconciliation bypass probe failed: {bypass_error}')
    no_gate_ok, no_gate_error = _no_configured_gate_probe()
    if not no_gate_ok: errors.append(f'no-configured-gate probe failed: {no_gate_error}')
    finish_gate_ok, finish_gate_error = _finish_gate_closure_probe()
    if not finish_gate_ok: errors.append(f'finish-gate closure probe failed: {finish_gate_error}')
    freshness_ok, freshness_error = _gate_freshness_probe()
    if not freshness_ok: errors.append(f'gate freshness probe failed: {freshness_error}')
    product_block_ok, product_block_error = _product_decision_block_probe()
    if not product_block_ok: errors.append(f'product decision block probe failed: {product_block_error}')
    standalone_errors = _standalone_errors(root)
    errors.extend(standalone_errors)

    return {
        'status': 'PASS' if not errors else 'FAIL',
        'validation_scope': 'AGENT_SKILL_PROFILE_RUNTIME_STRUCTURE',
        'semantic_complete': False,
        'contract_tests_required': True,
        'error_count': len(errors), 'errors': sorted(set(errors)), 'agent_count': len(agents), 'skill_count': len(skills),
        'core_agent_count': len(REQUIRED_CORE_AGENTS & agents), 'core_skill_count': len(REQUIRED_CORE_SKILLS & skills),
        'project_profile': 'PASS' if not _profile_errors(root) else 'FAIL', 'generic_fixture': 'PASS' if fixture_ok else 'FAIL',
        'domain_request_only_fixture': 'PASS' if domain_ok else 'FAIL',
        'final_reconciliation_bypass': 'PASS' if bypass_ok else 'FAIL',
        'no_configured_gate_guard': 'PASS' if no_gate_ok else 'FAIL',
        'finish_required_gate_closure': 'PASS' if finish_gate_ok else 'FAIL',
        'gate_freshness': 'PASS' if freshness_ok else 'FAIL',
        'product_decision_block': 'PASS' if product_block_ok else 'FAIL',
        'standalone_template': 'PASS' if not standalone_errors else 'FAIL',
    }


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument('--root', default='.'); a = p.parse_args(); out = validate(Path(a.root)); print(json.dumps(out, ensure_ascii=False, indent=2)); return 0 if out['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
