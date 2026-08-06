#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
commands=[
 [sys.executable,str(HERE/'validate_all.py'),'--root',str(ROOT)],
 [sys.executable,str(HERE/'validate_governance.py'),'--root',str(ROOT)],
]
for cmd in commands:
 p=subprocess.run(cmd)
 if p.returncode: raise SystemExit(p.returncode)
raise SystemExit(0)
