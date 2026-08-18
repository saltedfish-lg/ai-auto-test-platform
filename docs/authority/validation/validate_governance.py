#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,sys,time
from pathlib import Path
from typing import Any
import yaml
YAML_LOADER=getattr(yaml,'CSafeLoader',yaml.SafeLoader)

REPO_ROOT=Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0, str(REPO_ROOT))
from tools._bootstrap import ensure_repo_root_on_path  # noqa: E402
REPO_ROOT = ensure_repo_root_on_path(__file__)
from tools.current_facts import check_current_fact_governance
from tools.governance.governance_lite_validator import validate as validate_lite

AUTHORITY_MODEL='SINGLE_LIVING_AUTHORITY'
CORE=[
 '产品总体需求与系统边界/产品总体需求与系统边界.yaml','用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml',
 '核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml','权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml',
 'AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml','数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml',
 '系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml']

def main()->int:
 p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--output',type=Path); a=p.parse_args(); root=a.root.resolve(); repo=root.parents[1]
 errors=[]; checks=[]
 def add(name,ok,detail): checks.append({'check':name,'status':'PASS' if ok else 'FAIL','detail':detail}); (not ok) and errors.append(f'{name}: {detail}')
 missing=[x for x in CORE if not (root/x).is_file()]; add('GOV-CORE-AUTHORITY',not missing,f'missing={missing}')
 parse=[]
 for rel in CORE:
  if not (root/rel).is_file(): continue
  try:
   d=yaml.load((root/rel).read_text(encoding='utf-8'),Loader=YAML_LOADER); m=(d or {}).get('metadata',{})
   if m.get('authority_model')!=AUTHORITY_MODEL: parse.append(f'{rel}: authority_model={m.get("authority_model")}')
  except Exception as e: parse.append(f'{rel}: {e}')
 add('GOV-LIVING-AUTHORITY',not parse,'; '.join(parse) or AUTHORITY_MODEL)
 sd=yaml.load((root/'编码权威事实/SYSTEM_DESIGN.yaml').read_text(encoding='utf-8'),Loader=YAML_LOADER)
 catalog=(sd or {}).get('runtime_gate_catalog',{}); gates=catalog.get('gates',[]) if isinstance(catalog,dict) else []
 bad=[g.get('gate_id') for g in gates if isinstance(g,dict) and any(k in g for k in ('status','last_execution_evidence','evidence_ref','rerun_reason'))]
 add('GOV-RUNTIME-RESULT-NOT-AUTHORITY',not bad,f'temporary-status-gates={bad}')
 cf=check_current_fact_governance(repo); add('GOV-CURRENT-FACTS',not cf,f'errors={cf[:20]}')
 lite=validate_lite(repo); add('GOV-AGENT-SKILL-LITE',lite['status']=='PASS',f"agents={lite['agent_count']}; skills={lite['skill_count']}; errors={lite['errors'][:10]}")
 report={'authority_model':AUTHORITY_MODEL,'executed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'PASS' if not errors else 'FAIL','checks':checks,'error_count':len(errors),'errors':errors}
 raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n'; print(raw,end='')
 if a.output: a.output.write_text(raw,encoding='utf-8')
 return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
