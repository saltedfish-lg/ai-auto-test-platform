#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, sys, time, tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EVID=HERE/'evidence'; EVID.mkdir(exist_ok=True)
steps=[]
def run(name,cmd,allow_nonzero=False):
    with tempfile.TemporaryDirectory(prefix='r4_1_validation_') as td:
        out=Path(td)/'stdout'; err=Path(td)/'stderr'
        with out.open('w',encoding='utf-8') as fo, err.open('w',encoding='utf-8') as fe:
            p=subprocess.run([str(x) for x in cmd],cwd=HERE,text=True,stdout=fo,stderr=fe)
        stdout=out.read_text(encoding='utf-8',errors='replace')[-12000:]
        stderr=err.read_text(encoding='utf-8',errors='replace')[-12000:]
    steps.append({'name':name,'command':[str(x) for x in cmd],'returncode':p.returncode,'stdout_tail':stdout,'stderr_tail':stderr})
    if p.returncode and not allow_nonzero: raise SystemExit(p.returncode)
run('STATIC_CONTRACT_VALIDATION',[sys.executable,HERE/'validate_all.py','--root',ROOT,'--output',EVID/'static-validation.json'])
run('GOVERNANCE_CLEANUP_VALIDATION',[sys.executable,HERE/'validate_governance.py','--root',ROOT,'--output',EVID/'governance-validation.json'])
run('TYPESCRIPT_GENERATION',[sys.executable,HERE/'generate_ts_client.py','--root',ROOT,'--out',HERE/'generated'])
run('TYPESCRIPT_STRICT_COMPILE',['tsc','-p',HERE/'tsconfig.json'])
run('MYSQL84_RUNTIME_GATE',[sys.executable,HERE/'run_mysql84_gate.py','--root',ROOT,'--output',EVID/'mysql84-gate.json'],allow_nonzero=True)
report={'release_id':'PDBR-2026.08.06-R4.1','executed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'steps':steps,
        'static_status':'PASS' if all(x['returncode']==0 for x in steps[:4]) else 'FAIL',
        'mysql84_status':'NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE' if steps[4]['returncode'] else 'PASS',
        'implementation_release_readiness':'NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT'}
(EVID/'validation-run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
