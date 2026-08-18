
GOVERNANCE_TEST_GROUP = 'authority'

from pathlib import Path
import json,os,time
from tools.governance.authority_lock import acquire,release,cleanup_stale
from tools.governance.task_context import save_context,cleanup_task

def test_single_writer_blocks_second_task(tmp_path:Path):
 save_context(tmp_path,'a',{'affected_files':['docs/authority/x.yaml']}); save_context(tmp_path,'b',{'affected_files':['docs/authority/y.yaml']})
 acquire(tmp_path,'a','docs/authority/x.yaml')
 try:
  try: acquire(tmp_path,'b','docs/authority/y.yaml'); assert False,'second writer must block'
  except RuntimeError as exc: assert 'AUTHORITY_LOCK_BUSY' in str(exc)
 finally: release(tmp_path,'a'); cleanup_task(tmp_path,'a'); cleanup_task(tmp_path,'b')

def test_release_deletes_lock(tmp_path:Path):
 save_context(tmp_path,'a',{}); p=acquire(tmp_path,'a','docs/authority/x.yaml'); assert p.exists(); release(tmp_path,'a'); assert not p.exists(); cleanup_task(tmp_path,'a')

def test_lock_payload_is_minimal(tmp_path:Path):
 save_context(tmp_path,'a',{}); p=acquire(tmp_path,'a','docs/authority/x.yaml'); d=json.loads(p.read_text()); assert set(d)=={'task_id','pid','file','created_at','lock_instance_id'}; release(tmp_path,'a'); cleanup_task(tmp_path,'a')

def test_stale_dead_pid_lock_is_cleaned(tmp_path:Path):
 save_context(tmp_path,'dead',{}); p=tmp_path/'.tmp/agent-governance/authority.lock'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({'task_id':'dead','pid':99999999,'file':'x','created_at':'old'}))
 assert cleanup_stale(tmp_path) is True; assert not p.exists(); cleanup_task(tmp_path,'dead')
