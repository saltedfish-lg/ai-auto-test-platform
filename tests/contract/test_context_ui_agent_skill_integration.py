from __future__ import annotations
import json, subprocess, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONTEXT=ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency'
SCANNER=CONTEXT/'scripts/impact_scan.py'
SNAPSHOT=CONTEXT/'scripts/workspace_snapshot.py'
BUSINESS=ROOT/'.agents/skills/ai-auto-test-platform-business-ui-ux'
UIQ=ROOT/'.agents/skills/ai-auto-test-platform-ui-quality'

def _policy(repo:Path, *, governance=False)->None:
    p=repo/'.agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml'; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('''version: 8\nsearch_scope:\n  required_roots:\n    - apps\n    - docs/authority\n  optional_roots:\n    - .github\n  governance_roots:\n    - .agents\n    - .codex\n''',encoding='utf-8')

def _repo(repo:Path)->None:
    _policy(repo); (repo/'apps').mkdir(parents=True); (repo/'apps/main.py').write_text('needle=True\n',encoding='utf-8'); (repo/'docs/authority').mkdir(parents=True); (repo/'docs/authority/fact.yaml').write_text('needle: authority\n',encoding='utf-8')

def _scan(repo:Path,*extra:str):
    return subprocess.run([sys.executable,str(SCANNER),'needle','--root',str(repo),'--json',*extra],capture_output=True,text=True,check=False)

def test_context_policy_declares_single_living_authority_and_no_git()->None:
    text=(CONTEXT/'schemas/context-policy.yaml').read_text(encoding='utf-8')
    for token in ('SINGLE_LIVING_AUTHORITY','root: docs/authority','versioned_baseline_copies: forbidden','codex_git_access: DISABLED','FILESYSTEM_ONLY'): assert token in text

def test_scanner_searches_authority_and_source_broadly(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _repo(repo); c=_scan(repo); assert c.returncode==0, c.stdout
    payload=json.loads(c.stdout); paths={x['path'] for x in payload['results']}; assert 'apps/main.py' in paths; assert 'docs/authority/fact.yaml' in paths; assert payload['authority']['model']=='SINGLE_LIVING_AUTHORITY'; assert payload['git_access']=='DISABLED'

def test_scanner_fails_closed_when_living_authority_missing(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _policy(repo); (repo/'apps').mkdir(); c=_scan(repo); assert c.returncode==2; p=json.loads(c.stdout); assert p['closure']['closure_safe'] is False; assert 'docs/authority' in p['scope']['missing_required_roots'] or 'living_authority_missing' in p['closure']['blockers']

def test_governance_roots_are_conditionally_expanded(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _repo(repo); (repo/'.codex').mkdir(); (repo/'.codex/a.txt').write_text('needle',encoding='utf-8')
    no=_scan(repo); assert no.returncode==0; assert '.codex/a.txt' not in {x['path'] for x in json.loads(no.stdout)['results']}
    yes=_scan(repo,'--include-governance'); assert yes.returncode==0; assert '.codex/a.txt' in {x['path'] for x in json.loads(yes.stdout)['results']}

def test_large_authority_file_is_streamed_not_silently_skipped(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _repo(repo); large=repo/'docs/authority/large.yaml'; large.write_text(('x: filler\n'*500000)+'needle: yes\n',encoding='utf-8')
    c=_scan(repo); assert c.returncode==0; p=json.loads(c.stdout); assert 'docs/authority/large.yaml' in p['large_files_streamed']['samples']

def test_workspace_snapshot_is_filesystem_only_and_external(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); (repo/'a.txt').write_text('a',encoding='utf-8'); out=tmp_path/'snap.json'
    c=subprocess.run([sys.executable,str(SNAPSHOT),'capture','--root',str(repo),'--out',str(out)],capture_output=True,text=True,check=False); assert c.returncode==0
    p=json.loads(out.read_text(encoding='utf-8')); assert p['snapshot_version']==3; assert p['git_access']=='DISABLED'; assert p['workspace_identity']['identity_mode']=='FILESYSTEM_ONLY'

def test_workspace_snapshot_delta_is_task_scoped(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); (repo/'a.txt').write_text('a',encoding='utf-8'); start=tmp_path/'s.json'; out=tmp_path/'d.json'
    subprocess.run([sys.executable,str(SNAPSHOT),'capture','--root',str(repo),'--out',str(start)],check=True,capture_output=True,text=True); (repo/'a.txt').write_text('b',encoding='utf-8')
    subprocess.run([sys.executable,str(SNAPSHOT),'delta','--root',str(repo),'--start',str(start),'--out',str(out)],check=True,capture_output=True,text=True); d=json.loads(out.read_text(encoding='utf-8'))['task_delta']; assert d['task_delta_paths']==['a.txt']; assert d['status']=='CHANGED'

def test_task_context_pack_contains_authority_snapshot_expert_and_resume_slices()->None:
    text=(CONTEXT/'references/task-context-pack.md').read_text(encoding='utf-8')
    for token in ('authority:','model: SINGLE_LIVING_AUTHORITY','workspace_fingerprint:','snapshot_version: 3','task_delta_paths:','product_authority:','architecture_decision:','expert_selection:','task_lifecycle:'): assert token in text

def test_business_ui_ux_skill_is_risk_triggered_and_business_first()->None:
    text=(BUSINESS/'SKILL.md').read_text(encoding='utf-8')
    for token in ('UI_LOW','UI_MEDIUM','UI_HIGH','WHO','WHY','WHAT','FREQUENCY','RISK','PRIORITY','STATE','FLOW','Business UX Spec'): assert token in text
    assert '默认不单独启动 Designer Agent' in text

def test_ui_high_baseline_capture_has_environment_fallback_without_fake_before()->None:
    text=(BUSINESS/'SKILL.md').read_text(encoding='utf-8'); q=(UIQ/'SKILL.md').read_text(encoding='utf-8')
    for token in ('BASELINE_CAPTURE','BLOCKED_BY_ENVIRONMENT','SOURCE_BASED_CURRENT_UI_BASELINE','VISUAL_BASELINE_CONFIDENCE = LIMITED','POST_CHANGE_BROWSER_VERIFY = REQUIRED'): assert token in text and token in q
    assert '禁止伪造' in text

def test_business_ui_specialist_is_dual_mode_and_ui_verifier_remains_separate()->None:
    specialist=tomllib.loads((ROOT/'.codex/agents/business_ui_ux_specialist.toml').read_text(encoding='utf-8'))['developer_instructions']; verifier=tomllib.loads((ROOT/'.codex/agents/ui_verifier.toml').read_text(encoding='utf-8'))['developer_instructions']
    assert 'DESIGN_MODE' in specialist and 'REVIEW_MODE' in specialist; assert '真实浏览器' in verifier or 'browser' in verifier.lower()

def test_all_agents_use_shared_pack_not_full_repository_reexploration()->None:
    for p in (ROOT/'.codex/agents').glob('*.toml'):
        ins=tomllib.loads(p.read_text(encoding='utf-8'))['developer_instructions']; assert 'MUST_CONSUME_TASK_CONTEXT_PACK' in ins, p.name
