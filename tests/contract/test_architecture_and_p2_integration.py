from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ARCH=ROOT/'.agents/skills/ai-auto-test-platform-architecture'
CONTEXT=ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency'
SNAPSHOT=CONTEXT/'scripts/workspace_snapshot.py'


def test_architecture_skill_is_risk_triggered_not_always_on()->None:
    text=(ARCH/'SKILL.md').read_text(encoding='utf-8')
    for token in ('ARCH_LOW','ARCH_MEDIUM','ARCH_HIGH','solution_architect','freshness=CURRENT','pack_revision'): assert token in text


def test_context_pack_reuses_architecture_decision_by_revision_rebind()->None:
    pack=(CONTEXT/'references/task-context-pack.md').read_text(encoding='utf-8')
    for token in ('architecture_decision:','assessed_pack_revision','freshness: CURRENT | STALE','recheck_required','revision rebind'): assert token in pack


def test_context_is_filesystem_only_and_has_no_git_dependency()->None:
    scan=(CONTEXT/'scripts/impact_scan.py').read_text(encoding='utf-8')
    snapshot=SNAPSHOT.read_text(encoding='utf-8')
    assert 'AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"' in scan
    assert 'git_access": "DISABLED"' in scan
    assert 'import subprocess' not in scan
    assert 'import subprocess' not in snapshot
    assert 'tracked_deleted' not in scan


def test_filesystem_snapshot_detects_added_modified_removed(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); (repo/'a.txt').write_text('a',encoding='utf-8'); (repo/'remove.txt').write_text('x',encoding='utf-8')
    start=tmp_path/'start.json'; delta=tmp_path/'delta.json'
    c=subprocess.run([sys.executable,str(SNAPSHOT),'capture','--root',str(repo),'--out',str(start)],capture_output=True,text=True,check=False); assert c.returncode==0
    (repo/'a.txt').write_text('b',encoding='utf-8'); (repo/'remove.txt').unlink(); (repo/'new.txt').write_text('n',encoding='utf-8')
    c=subprocess.run([sys.executable,str(SNAPSHOT),'delta','--root',str(repo),'--start',str(start),'--out',str(delta)],capture_output=True,text=True,check=False); assert c.returncode==0
    payload=json.loads(delta.read_text(encoding='utf-8'))['task_delta']
    assert payload['added']==['new.txt']; assert payload['removed']==['remove.txt']; assert payload['modified']==['a.txt']; assert payload['status']=='CHANGED'


def test_snapshot_artifacts_must_be_outside_workspace(tmp_path:Path)->None:
    repo=tmp_path/'repo'; repo.mkdir(); out=repo/'snapshot.json'
    c=subprocess.run([sys.executable,str(SNAPSHOT),'capture','--root',str(repo),'--out',str(out)],capture_output=True,text=True,check=False)
    assert c.returncode==2; assert json.loads(c.stdout)['reason_code']=='SNAPSHOT_OUTPUT_INSIDE_WORKSPACE'; assert not out.exists()
