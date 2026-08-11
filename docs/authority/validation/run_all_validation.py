#!/usr/bin/env python3
"""Run current living-authority validators without producing release snapshots."""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path); args=ap.parse_args()
    steps=[]; failed=False
    for name in ('validate_all.py','validate_governance.py','validate_auth_contract.py'):
        p=HERE/name
        if not p.is_file(): continue
        proc=subprocess.run([sys.executable,str(p),'--root',str(ROOT)],text=True,capture_output=True)
        steps.append({'validator':name,'returncode':proc.returncode,'stdout_tail':proc.stdout[-4000:],'stderr_tail':proc.stderr[-2000:]})
        failed |= proc.returncode != 0
    report={'authority_model':'SINGLE_LIVING_AUTHORITY','authority_root':'docs/authority','executed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'FAIL' if failed else 'PASS','steps':steps}
    raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(raw,encoding='utf-8')
    print(raw); return 1 if failed else 0
if __name__=='__main__': raise SystemExit(main())
