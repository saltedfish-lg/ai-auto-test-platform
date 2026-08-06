#!/usr/bin/env python3
from pathlib import Path
import argparse,json,re,time,yaml
RID='PDBR-2026.08.06-R4.1'; AUTH='AUTHORITY-MODEL-R4.1-001'
CORE=[
'产品总体需求与系统边界/产品总体需求与系统边界.yaml',
'用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml',
'核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml',
'权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml',
'AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml',
'数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml',
'系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml']
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]); ap.add_argument('--output',type=Path); a=ap.parse_args()
 texts={r:(a.root/r).read_text(encoding='utf-8-sig') for r in CORE}; checks=[]; errors=[]; metrics={}
 def add(cid,ok,scanned,hits,locs=None):
  locs=locs or []; checks.append({'check_id':cid,'status':'PASS' if ok else 'FAIL','scanned_file_count':scanned,'hit_count':hits,'failure_locations':locs});
  if not ok: errors.extend(f'{cid}: {x}' for x in (locs or [str(hits)]))
 # Formal YAML/JSON parsing is executed by validate_all.py immediately before this validator.
 # Reuse that signed evidence instead of reparsing multi-megabyte YAML a second time.
 static_path=a.root/'编码冻结基线/RELEASE/validation/evidence/static-validation.json'
 parse=[]
 try:
  static=json.loads(static_path.read_text(encoding='utf-8'))
  if static.get('status')!='PASS' or static.get('error_count')!=0:
   parse.append(f'{static_path.relative_to(a.root)}: static validation not PASS')
 except Exception as e:
  parse.append(f'{static_path.relative_to(a.root)}:{e}')
 add('GOV-YAML-PARSE-EVIDENCE',not parse,len(CORE),len(parse),parse)
 for tok in ['coding_status: NEEDS_REFINEMENT','direct_code_input: false','core_scaffold_blocked: true']:
  loc=[f'{r}:{i}' for r,t in texts.items() for i,l in enumerate(t.splitlines(),1) if tok in l]
  add('GOV-FORBIDDEN-'+re.sub(r'[^A-Z0-9]+','_',tok.upper()).strip('_'),not loc,len(CORE),len(loc),loc[:100])
 # Closure counts are deterministic generated governance records.
 ai=texts[CORE[4]]; perm=texts[CORE[3]]; dom=texts[CORE[2]]
 counts={'ai_runner_closed':ai.count('closure_evidence:'),'permission_closed':perm.count('closure_evidence:'),'domain_stale_blockers_closed':dom.count('closure_evidence:')}
 add('GOV-AI-RUNNER-CLOSURE',counts['ai_runner_closed']==994,1,abs(counts['ai_runner_closed']-994),[f"closed={counts['ai_runner_closed']}"] if counts['ai_runner_closed']!=994 else [])
 add('GOV-PERMISSION-CLOSURE',counts['permission_closed']==41,1,abs(counts['permission_closed']-41),[f"closed={counts['permission_closed']}"] if counts['permission_closed']!=41 else [])
 add('GOV-DOMAIN-STALE-BLOCKERS',counts['domain_stale_blockers_closed']>=7,1,0 if counts['domain_stale_blockers_closed']>=7 else 1,[f"closed={counts['domain_stale_blockers_closed']}"] if counts['domain_stale_blockers_closed']<7 else [])
 metrics.update(counts)
 # Summary markers.
 required={CORE[4]:['needs_refinement_record_count: 0','direct_code_input: true'],CORE[3]:['needs_refinement_record_count: 0'],CORE[2]:['needs_refinement_record_count: 0','direct_code_input: true','open_decisions: []'],CORE[0]:['direct_code_input: true','current_package_has_frozen_design_release: true'],CORE[6]:['core_scaffold_blocked: false'],CORE[5]:['open_decisions: 0']}
 missing=[f'{r}:{m}' for r,ms in required.items() for m in ms if m not in texts[r]]
 for r,t in texts.items():
  if f'current_release_id: {RID}' not in t or 'pending_user_decisions: 0' not in t: missing.append(r+':current governance')
 add('GOV-CURRENT-STATUS-SUMMARIES',not missing,len(CORE),len(missing),missing)
 rx=re.compile(r'^\s*(statement|reason|authority_rule|recommended_direction|current_release_id|current_authority):.*PDBR-2026\.08\.06-R(?:2|3|4)(?!\.)')
 bad=[f'{r}:{i}:{l.strip()}' for r,t in texts.items() for i,l in enumerate(t.splitlines(),1) if rx.search(l)]
 add('GOV-CURRENT-AUTHORITY-NOT-SUPERSEDED',not bad,len(CORE),len(bad),bad[:100])
 # Current package member metadata must point to R4.1; R4 and earlier are allowed only as explicit parent/effective/historical provenance.
 meta_bad=[]
 domain=texts[CORE[2]]
 for i,l in enumerate(domain.splitlines(),1):
  if re.match(r'^\s*release_id:\s*PDBR-2026\.08\.06-R4\s*$',l): meta_bad.append(f'{CORE[2]}:{i}:stale member release_id')
 arch=texts[CORE[6]]
 if re.search(r'^r3_freeze_authority:',arch,re.M): meta_bad.append(f'{CORE[6]}:top-level r3_freeze_authority')
 if 'historical_provenance:\n  r3_freeze_authority:' not in arch: meta_bad.append(f'{CORE[6]}:missing historical R3 provenance')
 current_contracts=[
  '编码冻结基线/DATABASE_DDL/database-schema.yaml',
  '编码冻结基线/EVENT_CONTRACTS/event-registry.yaml',
  '编码冻结基线/STATE_OWNER_REGISTRY/state-owner-registry.yaml',
  '编码冻结基线/PERMISSION_CLOSURE/permission-closure.yaml',
  '编码冻结基线/NEEDS_REFINEMENT_CLOSURE/needs-refinement-closure.yaml',
  '编码冻结基线/ADR/ADR-register.yaml',
  '编码冻结基线/SYSTEM_DESIGN.yaml']
 for r in current_contracts:
  head='\n'.join((a.root/r).read_text(encoding='utf-8').splitlines()[:18])
  if f'release_id: {RID}' not in head: meta_bad.append(f'{r}:current release metadata')
  if 'parent_release_id: PDBR-2026.08.06-R4' not in head: meta_bad.append(f'{r}:parent release metadata')
 oa=(a.root/'编码冻结基线/OPENAPI/openapi.yaml').read_text(encoding='utf-8')
 if f'x-release-id: {RID}' not in '\n'.join(oa.splitlines()[:10]): meta_bad.append('编码冻结基线/OPENAPI/openapi.yaml:info.x-release-id')
 accm=json.loads((a.root/'编码冻结基线/ACCEPTANCE_CLOSURE/acceptance-closure.json').read_text(encoding='utf-8'))['metadata']
 if accm.get('release_id')!=RID or accm.get('parent_release_id')!='PDBR-2026.08.06-R4': meta_bad.append('编码冻结基线/ACCEPTANCE_CLOSURE/acceptance-closure.json:release chain')
 add('GOV-CURRENT-RELEASE-METADATA',not meta_bad,len(current_contracts)+3,len(meta_bad),meta_bad)
 auth=[]
 for r in ['系统技术架构技术选型与AGENTS/agents-rules.yaml','baseline-index.yaml','核心CodexSkill/ai-auto-test-platform-core/schemas/skill-rules.yaml','系统技术架构技术选型与AGENTS/AGENTS.md','BASELINE_INDEX.md','核心CodexSkill/ai-auto-test-platform-core/SKILL.md']:
  if AUTH not in (a.root/r).read_text(encoding='utf-8'): auth.append(r)
 add('GOV-AUTHORITY-MODEL-CONSISTENCY',not auth,6,len(auth),auth)
 nr=(a.root/'编码冻结基线/NEEDS_REFINEMENT_CLOSURE/needs-refinement-closure.yaml').read_text(encoding='utf-8'); gate=[]
 for marker in ['blocking_scope: DATABASE_MODULE_FORMAL_MERGE','blocks_code_initialization: false','blocks_database_module_formal_merge: true','blocking_scope: IMPLEMENTATION_RELEASE_READINESS','blocks_production_release: true']:
  if marker not in nr: gate.append(marker)
 if 'blocks_full_code_ready' in nr: gate.append('ambiguous blocks_full_code_ready')
 add('GOV-GATE-BLOCKING-SCOPE',not gate,1,len(gate),gate)
 acc=json.loads((a.root/'编码冻结基线/ACCEPTANCE_CLOSURE/acceptance-closure.json').read_text(encoding='utf-8'))['acceptance_closure']; passed=sum(x.get('status')=='PASSED' for x in acc); spec=sum(x.get('status')=='SPECIFIED' for x in acc)
 ab=[] if len(acc)==1691 and passed==0 and spec==1691 else [f'{len(acc)}/{spec}/{passed}']; add('GOV-ACCEPTANCE-HONEST-STATUS',not ab,1,len(ab),ab); metrics.update({'acceptance':len(acc),'specified':spec,'passed':passed})
 total=sum(1 for p in a.root.rglob('*') if p.is_file()); cb=[]
 for r,t in texts.items():
  for marker in [f'package_file_count_including_root_manifest: {total}',f'root_manifest_entry_count: {total-1}',f'package_inventory_entry_count: {total-2}']:
   if marker not in t: cb.append(f'{r}:{marker}')
 add('GOV-DYNAMIC-FILE-COUNTS',not cb,len(CORE),len(cb),cb); metrics['package_file_count_including_root_manifest']=total
 report={'release_id':RID,'validator':'validate_governance.py','executed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'PASS' if not errors else 'FAIL','metrics':metrics,'checks':checks,'error_count':len(errors),'errors':errors}
 raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n';
 if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(raw,encoding='utf-8')
 print(raw); return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
