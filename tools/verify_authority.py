#!/usr/bin/env python3
from __future__ import annotations
import json,time
import sys
from pathlib import Path

# Direct-script bootstrap: establish repo-root package context before project imports.
_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))
from tools._bootstrap import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path(__file__)

import yaml
YAML_LOADER=getattr(yaml,'CSafeLoader',yaml.SafeLoader)
from tools.current_facts import check_current_fact_governance
from tools.governance.governance_lite_validator import validate as validate_lite

AUTHORITY=ROOT/'docs/authority'
CORE=[
 '产品总体需求与系统边界/产品总体需求与系统边界.yaml','用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml',
 '核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml','权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml',
 'AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml','数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml',
 '系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml']

def main()->int:
 errors=[]
 for rel in CORE:
  p=AUTHORITY/rel
  if not p.is_file(): errors.append(f'missing {rel}'); continue
  try:
   d=yaml.load(p.read_text(encoding='utf-8'),Loader=YAML_LOADER); m=(d or {}).get('metadata',{})
   if m.get('authority_model')!='SINGLE_LIVING_AUTHORITY': errors.append(f'{rel}: authority_model drift')
  except Exception as e: errors.append(f'{rel}: {e}')
 sd=yaml.load((AUTHORITY/'编码权威事实/SYSTEM_DESIGN.yaml').read_text(encoding='utf-8'),Loader=YAML_LOADER)
 if 'runtime_gate_contract' in sd: errors.append('SYSTEM_DESIGN still contains retired runtime_gate_contract')
 cat=sd.get('runtime_gate_catalog',{})
 for g in cat.get('gates',[]):
  if isinstance(g,dict) and any(k in g for k in ('status','last_execution_evidence','evidence_ref')): errors.append(f"runtime gate stores task result: {g.get('gate_id')}")
 errors.extend(check_current_fact_governance(ROOT))
 lite=validate_lite(ROOT)
 if lite['status']!='PASS': errors.extend('governance-lite: '+x for x in lite['errors'])
 out={'authority_model':'SINGLE_LIVING_AUTHORITY','executed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'PASS' if not errors else 'FAIL','error_count':len(errors),'errors':errors}
 print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
