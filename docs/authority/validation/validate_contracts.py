#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def main()->int:
    for name in ("validate_all.py","validate_governance.py","validate_auth_contract.py"):
        p=HERE/name
        if p.is_file():
            rc=subprocess.run([sys.executable,str(p),"--root",str(ROOT)],check=False).returncode
            if rc: return rc
    return 0
if __name__=="__main__": raise SystemExit(main())
