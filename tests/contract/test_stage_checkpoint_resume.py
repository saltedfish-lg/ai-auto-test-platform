from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ORCH=ROOT/'.agents/skills/ai-auto-test-platform-feature-orchestrator'
CONTEXT=ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency'
HELPER=ORCH/'scripts/task_checkpoint.py'

def _run(*args:str):
    return subprocess.run([sys.executable,str(HELPER),*args],check=False,capture_output=True,text=True)

def _init(repo:Path, checkpoint:Path, *, fingerprint='fp-0', authority_digest='auth-1', workspace_identity='workspace-1'):
    return _run('init','--root',str(repo),'--out',str(checkpoint),'--task-id','TASK-RESUME-1','--workspace-identity',workspace_identity,'--authority-root','docs/authority','--authority-digest',authority_digest,'--workspace-fingerprint',fingerprint,'--pack-revision','0')

def _advance(repo:Path, checkpoint:Path, stage:str, fingerprint:str, revision:int, authority_digest='auth-1'):
    return _run('advance','--root',str(repo),'--checkpoint',str(checkpoint),'--task-id','TASK-RESUME-1','--stage',stage,'--workspace-fingerprint',fingerprint,'--authority-digest',authority_digest,'--pack-revision',str(revision))

def _resume(repo:Path, checkpoint:Path, fingerprint:str, *, workspace_identity='workspace-1', authority_digest='auth-1', authority_root='docs/authority'):
    return _run('resume-validate','--root',str(repo),'--checkpoint',str(checkpoint),'--task-id','TASK-RESUME-1','--workspace-identity',workspace_identity,'--authority-root',authority_root,'--current-workspace-fingerprint',fingerprint,'--current-authority-digest',authority_digest)

def test_checkpoint_must_be_outside_workspace(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=repo/'checkpoint.json'; c=_init(repo,cp)
    assert c.returncode==2; assert json.loads(c.stdout)['status']=='CHECKPOINT_INSIDE_WORKSPACE'; assert not cp.exists()

def test_checkpoint_is_atomic_checksummed_and_stage_progression_is_strict(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0
    data=json.loads(cp.read_text(encoding='utf-8')); assert data['schema_version']==2; assert data['current_stage']=='TASK_INITIALIZED'; assert len(data['checksum'])==64
    assert data['git_access']=='DISABLED'; assert data['authority_root']=='docs/authority'
    skipped=_advance(repo,cp,'DECISIONS_READY','fp-1',1); assert skipped.returncode==3; assert json.loads(skipped.stdout)['status']=='INVALID_STAGE_TRANSITION'

def test_resume_exact_reuses_latest_completed_stage(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0; assert _advance(repo,cp,'CONTEXT_READY','fp-context',1).returncode==0
    payload=json.loads(_resume(repo,cp,'fp-context').stdout); assert payload['resume_status']=='RESUME_EXACT'; assert payload['next_stage']=='DECISIONS_READY'; assert payload['full_impact_scan_allowed'] is False

def test_workspace_change_uses_delta_refresh_never_second_full_scan(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0; assert _advance(repo,cp,'CONTEXT_READY','fp-context',1).returncode==0
    payload=json.loads(_resume(repo,cp,'fp-changed').stdout); assert payload['resume_status']=='RESUME_WITH_DELTA_REFRESH'; assert payload['required_action']=='DELTA_REFRESH_THEN_REVALIDATE_STAGE_INPUTS'; assert payload['full_impact_scan_allowed'] is False

def test_authority_change_uses_delta_refresh_not_new_baseline(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0; assert _advance(repo,cp,'CONTEXT_READY','fp-context',1).returncode==0
    payload=json.loads(_resume(repo,cp,'fp-context',authority_digest='auth-2').stdout); assert payload['resume_status']=='RESUME_WITH_DELTA_REFRESH'; assert payload['authority_changed'] is True; assert payload['required_action']=='AUTHORITY_DELTA_REFRESH_THEN_REVALIDATE_PRODUCT_AND_DOWNSTREAM'; assert payload['full_impact_scan_allowed'] is False

def test_resume_rejected_on_workspace_identity_or_authority_root_change(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0
    c=_resume(repo,cp,'fp-0',workspace_identity='workspace-2'); assert c.returncode==3; assert 'workspace_identity' in json.loads(c.stdout)['mismatches']
    c=_resume(repo,cp,'fp-0',authority_root='docs/other'); assert c.returncode==3; assert 'authority_root' in json.loads(c.stdout)['mismatches']

def test_corrupted_checkpoint_fails_closed(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0
    data=json.loads(cp.read_text(encoding='utf-8')); data['current_stage']='CLOSURE_COMPLETE'; cp.write_text(json.dumps(data),encoding='utf-8')
    c=_resume(repo,cp,'fp-0'); assert c.returncode==4; assert json.loads(c.stdout)['status']=='CHECKPOINT_CORRUPTED'

def test_implementation_complete_resumes_at_verification(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); cp=tmp_path/'checkpoint.json'; assert _init(repo,cp).returncode==0
    for stage,fp,rev in [('CONTEXT_READY','fp-1',1),('DECISIONS_READY','fp-2',1),('IMPLEMENTATION_READY','fp-3',1),('IMPLEMENTATION_COMPLETE','fp-4',2)]: assert _advance(repo,cp,stage,fp,rev).returncode==0
    payload=json.loads(_resume(repo,cp,'fp-4').stdout); assert payload['resume_status']=='RESUME_EXACT'; assert payload['next_stage']=='VERIFICATION_COMPLETE'

def test_orchestrator_and_context_define_single_owner_and_validated_resume()->None:
    orch=(ORCH/'SKILL.md').read_text(encoding='utf-8'); ref=(ORCH/'references/task-checkpoint-resume.md').read_text(encoding='utf-8'); context=(CONTEXT/'SKILL.md').read_text(encoding='utf-8'); pack=(CONTEXT/'references/task-context-pack.md').read_text(encoding='utf-8'); policy=(CONTEXT/'schemas/context-policy.yaml').read_text(encoding='utf-8')
    for token in ('TASK_LIFECYCLE_OWNER','RESUME_EXACT','RESUME_WITH_DELTA_REFRESH','RESUME_REJECTED','CHECKPOINT_CORRUPTED','IMPLEMENTATION_COMPLETE','禁止 Full Scan #2'): assert token in orch or token in ref
    assert 'CONTEXT_STATE_PROVIDER' in context; assert 'task_lifecycle:' in pack; assert 'full_impact_scan_on_resume_allowed: false' in pack; assert 'full_impact_scan_on_resume: forbidden' in policy; assert 'per_agent_checkpoint_state: forbidden' in policy; assert 'codex_git_access: DISABLED' in policy
