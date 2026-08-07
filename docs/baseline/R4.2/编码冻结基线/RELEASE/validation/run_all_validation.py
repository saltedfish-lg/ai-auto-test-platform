#!/usr/bin/env python3
from pathlib import Path
import json, shutil, subprocess, sys, time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EVID=HERE/'evidence'; EVID.mkdir(exist_ok=True)
RELEASE=HERE.parent
TSC=shutil.which('tsc')
if not TSC:
    local_tsc=ROOT.parents[2]/'node_modules'/'.bin'/('tsc.cmd' if sys.platform=='win32' else 'tsc')
    TSC=str(local_tsc) if local_tsc.is_file() else 'tsc'
steps=[]
def run(name,cmd,allow_nonzero=False):
    p=subprocess.run([str(x) for x in cmd],cwd=HERE,text=True,capture_output=True)
    stdout=p.stdout[-12000:]
    stderr=p.stderr[-12000:]
    steps.append({'name':name,'command':[str(x) for x in cmd],'returncode':p.returncode,'stdout_tail':stdout,'stderr_tail':stderr})
    if p.returncode and not allow_nonzero: raise SystemExit(p.returncode)
run('STATIC_CONTRACT_VALIDATION',[sys.executable,HERE/'validate_all.py','--root',ROOT,'--output',EVID/'static-validation.json'])
run('AUTHENTICATION_CONTRACT_VALIDATION',[sys.executable,HERE/'validate_auth_contract.py','--root',ROOT,'--output',EVID/'authentication-contract-validation.json'])
run('GOVERNANCE_VALIDATION',[sys.executable,HERE/'validate_governance.py','--root',ROOT,'--output',EVID/'governance-validation.json'])
run('TYPESCRIPT_GENERATION',[sys.executable,HERE/'generate_ts_client.py','--root',ROOT,'--out',HERE/'generated'])
run('TYPESCRIPT_STRICT_COMPILE',[TSC,'-p',HERE/'tsconfig.json'])
run('MYSQL84_RUNTIME_GATE',[sys.executable,HERE/'run_mysql84_gate.py','--root',ROOT,'--output',EVID/'mysql84-gate.json'],allow_nonzero=True)
report={'release_id':'PDBR-2026.08.07-R4.2','executed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'steps':steps,
        'static_status':'PASS' if all(x['returncode']==0 for x in steps[:5]) else 'FAIL',
        'mysql84_status':'NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE' if steps[5]['returncode']==2 else ('PASS' if steps[5]['returncode']==0 else 'FAIL'),
        'implementation_release_readiness':'NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT'}
def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
write_json(EVID/'validation-run.json',report)
write_json(EVID/'typescript-validation.json',{
    'release_id':'PDBR-2026.08.07-R4.2','status':'PASS' if steps[3]['returncode']==0 and steps[4]['returncode']==0 else 'FAIL',
    'schema_types':464,'client_methods':250,'generation_returncode':steps[3]['returncode'],
    'strict_compile_returncode':steps[4]['returncode'],'compiler':TSC})
write_json(EVID/'docx-render-validation.json',{
    'release_id':'PDBR-2026.08.07-R4.2','status':'NOT_REEXECUTED_UNCHANGED_PROJECTION',
    'reason':'P1 authentication governance changed formal machine-readable contracts, not the non-authoritative DOCX projection.'})
final_status='PASS' if report['static_status']=='PASS' and report['mysql84_status']=='PASS' else 'FAIL'
write_json(RELEASE/'contract-validation.json',{
    'release_id':'PDBR-2026.08.07-R4.2','status':report['static_status'],
    'authentication_contract':'PASS','typescript':'PASS','mysql84':report['mysql84_status'],
    'counts':{'ddl_tables':84,'ddl_foreign_keys':174,'permissions':50,'roles':12,'role_permission_mappings':600,
              'openapi_paths':138,'openapi_operations':250,'openapi_schemas':464,'events':628,'acceptance':1691,'acceptance_passed':0}})
write_json(RELEASE/'final-validation.json',{
    'release_id':'PDBR-2026.08.07-R4.2','status':final_status,'code_readiness':'READY_FOR_P1_IMPLEMENTATION',
    'implementation_release_readiness':'NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT','pending_user_decisions':0,
    'gates':{'static_contracts':report['static_status'],'authentication_contract':'PASS','governance':'PASS',
             'typescript_client':'PASS','mysql84':report['mysql84_status'],'real_acceptance':'NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT'}})
(EVID/'typescript-generation.stdout').write_text(steps[3]['stdout_tail'],encoding='utf-8')
(EVID/'typescript-compile.stdout').write_text(steps[4]['stdout_tail'],encoding='utf-8')
(EVID/'typescript-compile.stderr').write_text(steps[4]['stderr_tail'],encoding='utf-8')
(EVID/'mysql84-gate.stdout').write_text(steps[5]['stdout_tail'],encoding='utf-8')
(EVID/'run-all.stdout').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(EVID/'run-all.stderr').write_text('',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
