from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'validator'

import json,subprocess,sys,time
from pathlib import Path
import tomllib
from tools.governance.impact_scan import scan
from tools.governance.incremental_closure import expand
from tools.governance.task_context import load_context,cleanup_task,save_context,cleanup_stale,task_session
from tools.governance.authority_lock import acquire,release
from tools.governance.governance_lite_validator import validate
from tools.governance import required_gate_runner
ROOT=Path(__file__).resolve().parents[2]


def _write_domain_metadata(root: Path, rel: str, domains: list[str], gates: list[str]):
 p=root/rel/'.governance-domain.yaml'; p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text('schema_version: 2\nowner_identity: '+rel+'\nkind: implementation\ndomains:\n'+''.join(f'  - {d}\n' for d in domains)+'inherit: true\nengineering_gates:\n'+''.join(f'  - {g}\n' for g in gates),encoding='utf-8')

def test_exactly_four_core_skills_and_agents():
 assert {p.name for p in (ROOT/'.agents/skills').iterdir() if p.is_dir()}=={
  'context-efficiency','feature-orchestrator','product-sovereignty','code-quality'}
 assert {tomllib.loads(p.read_text(encoding='utf-8'))['name'] for p in (ROOT/'.codex/agents').glob('*.toml')}=={
  'default_coder','architecture_reviewer','product_sovereignty_reviewer','code_quality_reviewer'}

def test_case_a_low_risk_single_file_does_not_trigger_all_reviewers(tmp_path:Path):
 (tmp_path/'services/api').mkdir(parents=True); (tmp_path/'services/api/a.py').write_text('x=1')
 out=scan(tmp_path,'A','fix small backend bug',['services/api/a.py']); assert 'architecture_reviewer' not in out['review_triggers']; assert len(out['review_triggers'])<=1; cleanup_task(tmp_path,'A')

def test_case_b_cross_module_triggers_architecture_and_gates(tmp_path:Path):
 _write_domain_metadata(tmp_path,'services/api',['BACKEND'],['backend_test']); _write_domain_metadata(tmp_path,'apps/web',['FRONTEND'],['frontend_test'])
 for rel in ('services/api/a.py','apps/web/a.ts','docs/authority/编码权威事实/OPENAPI/openapi.yaml'):
  p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('x')
 out=scan(tmp_path,'B','backend frontend api change',['services/api/a.py','apps/web/a.ts','docs/authority/编码权威事实/OPENAPI/openapi.yaml']); assert 'architecture_reviewer' in out['review_triggers']; assert 'backend_test' in out['required_gates'] and 'frontend_test' in out['required_gates']; cleanup_task(tmp_path,'B')

def test_case_c_state_machine_change_triggers_product_sovereignty(tmp_path:Path):
 (tmp_path/'docs/authority').mkdir(parents=True); out=scan(tmp_path,'C','修改核心状态机规则',['docs/authority/state.yaml']); assert 'product_sovereignty_reviewer' in out['review_triggers']; cleanup_task(tmp_path,'C')

def test_case_d_new_dependency_uses_incremental_closure(tmp_path:Path):
 (tmp_path/'services/api').mkdir(parents=True); (tmp_path/'services/api/a.py').write_text('x')
 scan(tmp_path,'D','backend change',['services/api/a.py']); out=expand(tmp_path,'D',['packages/contracts/new.py']); assert out['incremental_revision']==1 and 'packages/contracts/new.py' in out['affected_files']; cleanup_task(tmp_path,'D')

def test_case_e_large_authority_uses_local_single_writer_lock(tmp_path:Path):
 save_context(tmp_path,'E',{}); p=acquire(tmp_path,'E','docs/authority/large.yaml'); assert p.exists(); release(tmp_path,'E'); assert not p.exists(); cleanup_task(tmp_path,'E')

def test_case_f_success_cleanup_removes_task_state(tmp_path:Path):
 save_context(tmp_path,'F',{'x':1}); cleanup_task(tmp_path,'F'); assert not (tmp_path/'.tmp/agent-governance/F').exists()

def test_case_g_failure_and_stale_cleanup(tmp_path:Path):
 save_context(tmp_path,'G',{'x':1,'task_pid':99999999,'task_status':'ACTIVE'}); p=tmp_path/'.tmp/agent-governance/G'; assert 'G' in cleanup_stale(tmp_path,86400); assert not p.exists()

def test_unknown_edge_expands_scope_instead_of_signed_slice(tmp_path:Path):
 (tmp_path/'services/api').mkdir(parents=True); (tmp_path/'services/api/a.py').write_text('x')
 scan(tmp_path,'U','backend change',['services/api/a.py']); a=expand(tmp_path,'U',[],unknown=True); assert a['scope_level']=='MODULE'; b=expand(tmp_path,'U',[],unknown=True); assert b['scope_level']=='REPOSITORY'; cleanup_task(tmp_path,'U')


def test_failure_cleanup_uses_finally(tmp_path:Path):
 try:
  with task_session(tmp_path,'FAIL',{'phase':'working'}):
   raise RuntimeError('synthetic failure')
 except RuntimeError:
  pass
 assert not (tmp_path/'.tmp/agent-governance/FAIL').exists()

def test_cancel_cleanup_uses_same_finally_path(tmp_path:Path):
 try:
  with task_session(tmp_path,'CANCEL',{'phase':'working'}):
   raise KeyboardInterrupt()
 except KeyboardInterrupt:
  pass
 assert not (tmp_path/'.tmp/agent-governance/CANCEL').exists()

def test_next_scan_cleans_stale_state(tmp_path:Path):
 save_context(tmp_path,'STALE',{'x':1,'task_pid':99999999,'task_status':'ACTIVE'}); stale=tmp_path/'.tmp/agent-governance/STALE'
 (tmp_path/'services/api').mkdir(parents=True); (tmp_path/'services/api/a.py').write_text('x')
 from tools.governance.task_governance import start,finish
 start(tmp_path,'NEW','small backend',['services/api/a.py'])
 assert not stale.exists(); finish(tmp_path,'NEW','ABORTED')


def test_required_gate_runner_executes_current_task_gate(tmp_path:Path, monkeypatch):
 _write_domain_metadata(tmp_path,'services/api',['BACKEND'],['backend_test'])
 (tmp_path/'services/api').mkdir(parents=True,exist_ok=True); (tmp_path/'services/api/a.py').write_text('x')
 (tmp_path/'.governance').mkdir(parents=True,exist_ok=True); (tmp_path/'.governance/gates.yaml').write_text('schema_version: 1\ngates:\n  backend_test:\n    command: [python, -c, "print(1)"]\n',encoding='utf-8')
 from tools.governance.task_governance import start,reconcile_task
 start(tmp_path,'RUN','small backend',['services/api/a.py'])
 reconcile_task(tmp_path,'RUN')
 monkeypatch.setitem(required_gate_runner.GATE_COMMANDS,'backend_test',[sys.executable,'-c','print("backend gate ok")'])
 report=required_gate_runner.run_required(tmp_path,'RUN',timeout=5)
 assert report['status']=='PASS' and report['results'][0]['status']=='PASS'
 cleanup_task(tmp_path,'RUN')

def test_governance_lite_validator_passes():
 out=validate(ROOT); assert out['status']=='PASS',out
