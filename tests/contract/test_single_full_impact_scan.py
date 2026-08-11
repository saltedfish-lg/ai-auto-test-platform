from __future__ import annotations
import json, subprocess, sys, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONTEXT=ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency'
ORCH=ROOT/'.agents/skills/ai-auto-test-platform-feature-orchestrator/SKILL.md'
PRODUCT=ROOT/'.agents/skills/ai-auto-test-platform-product-sovereignty/SKILL.md'
SCANNER=CONTEXT/'scripts/impact_scan.py'

def _make_repo(repo:Path, include_apps=True)->None:
    policy=repo/'.agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml'; policy.parent.mkdir(parents=True)
    policy.write_text('''version: 8\nsearch_scope:\n  required_roots:\n    - apps\n    - docs/authority\n  optional_roots: []\n  governance_roots:\n    - .agents\n    - .codex\n''',encoding='utf-8')
    (repo/'docs/authority').mkdir(parents=True)
    (repo/'docs/authority/fact.yaml').write_text('needle: authority\n',encoding='utf-8')
    if include_apps:
        (repo/'apps').mkdir(); (repo/'apps/main.py').write_text('needle=True\n',encoding='utf-8')

def _scan(repo:Path,state:Path,task='TASK-1'):
    return subprocess.run([sys.executable,str(SCANNER),'needle','--root',str(repo),'--risk','CROSS_MODULE','--formal-task','--task-id',task,'--scan-state',str(state),'--json'],capture_output=True,text=True,check=False)

def test_formal_task_allows_only_one_successful_full_impact_scan(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _make_repo(repo); state=tmp_path/'state.json'
    first=_scan(repo,state); assert first.returncode==0, first.stdout; p=json.loads(first.stdout); assert p['scan_governance']['successful_run_count']==1; assert p['scan_governance']['full_rescan_allowed'] is False
    second=_scan(repo,state); assert second.returncode==3; assert json.loads(second.stdout)['scan_governance']['error_code']=='IMPACT_SCAN_ALREADY_COMPLETED'
    alt=tmp_path/'alt.json'; third=_scan(repo,alt); assert third.returncode==3; assert not alt.exists()

def test_failed_scan_does_not_consume_success_quota(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _make_repo(repo,False); state=tmp_path/'state.json'
    failed=_scan(repo,state); assert failed.returncode==2; p=json.loads(failed.stdout); assert p['scan_governance']['successful_run_count']==0; assert p['scan_governance']['full_rescan_allowed'] is True
    (repo/'apps').mkdir(); (repo/'apps/main.py').write_text('needle=True',encoding='utf-8'); assert _scan(repo,state).returncode==0

def test_scan_state_must_be_outside_workspace(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); _make_repo(repo); c=_scan(repo,repo/'state.json'); assert c.returncode==3; assert json.loads(c.stdout)['scan_governance']['error_code']=='SCAN_STATE_INSIDE_WORKSPACE'

def test_orchestrator_declares_single_owner_and_incremental_closure_only()->None:
    text=ORCH.read_text(encoding='utf-8')
    for token in ('FULL_IMPACT_SCAN 唯一调度 Owner','FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS=1','IMPACT_SCAN_ALREADY_COMPLETED','MUST_CONSUME_TASK_CONTEXT_PACK','DELTA_REFRESH + TARGETED_REVERSE_LOOKUP','Full Scan #2'): assert token in text

def test_product_sovereignty_is_pack_consumer_not_scanner()->None:
    text=PRODUCT.read_text(encoding='utf-8')
    for token in ('MUST_CONSUME_TASK_CONTEXT_PACK','TASK_CONTEXT_PACK_REQUIRED','TARGETED_AUTHORITY_LOOKUP','不得执行 `impact_scan.py`','第二套 Impact Map'): assert token in text

def test_all_agents_and_roles_consume_shared_pack()->None:
    for p in sorted((ROOT/'.codex/agents').glob('*.toml')):
        ins=tomllib.loads(p.read_text(encoding='utf-8'))['developer_instructions']; assert 'MUST_CONSUME_TASK_CONTEXT_PACK' in ins; assert 'TASK_CONTEXT_PACK_REQUIRED' in ins
    for p in sorted((ROOT/'.agents/agent-roles').glob('*.md')):
        if p.name=='README.md': continue
        text=p.read_text(encoding='utf-8'); assert 'MUST_CONSUME_TASK_CONTEXT_PACK' in text; assert 'TASK_CONTEXT_PACK_REQUIRED' in text

def test_context_pack_forbids_rescan_when_stale()->None:
    text=(CONTEXT/'references/task-context-pack.md').read_text(encoding='utf-8')
    for token in ('successful_run_count: 0 | 1','max_successful_runs: 1','full_rescan_allowed: true | false','禁止重新执行 Full Impact Scan','TARGETED_REVERSE_LOOKUP','Full Scan #2'): assert token in text
