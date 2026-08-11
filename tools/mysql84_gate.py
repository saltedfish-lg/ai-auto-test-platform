#!/usr/bin/env python3
"""Explicit entrypoint for the current living-authority MySQL 8.4 runtime gate."""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUTHORITY=ROOT/"docs"/"authority"
VALIDATION=AUTHORITY/"validation"

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--execute",action="store_true",help="Rerun the real MySQL 8.4 gate against current authority contracts."); a=ap.parse_args()
    if not a.execute:
        print("AUTHORITY_MODEL = SINGLE_LIVING_AUTHORITY")
        print("MYSQL_8_4_RUNTIME_GATE = NOT_EXECUTED_THIS_RUN")
        print("Use --execute to rerun the real MySQL 8.4 gate in the current environment.")
        return 0
    c=subprocess.run([sys.executable,str(VALIDATION/"run_mysql84_gate.py"),"--root",str(AUTHORITY),"--compose",str(VALIDATION/"mysql84-compose.yml")],cwd=ROOT,check=False)
    return c.returncode
if __name__=="__main__": raise SystemExit(main())
