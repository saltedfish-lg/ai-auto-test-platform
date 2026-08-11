#!/usr/bin/env python3
"""Generate or compare the TypeScript client from the current living authority."""
from __future__ import annotations
import argparse, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUTHORITY=ROOT/"docs"/"authority"
GENERATOR=AUTHORITY/"validation"/"generate_ts_client.py"
OUTPUT=ROOT/"apps"/"web"/"src"/"generated"
CHECK_OUTPUT=ROOT/".openapi-client-check"
GENERATED_FILES=("types.ts","client.ts","generation-report.json")

def _normalize_generated_files_to_lf(output: Path) -> None:
    for name in GENERATED_FILES:
        p=output/name
        if p.is_file(): p.write_bytes(p.read_bytes().replace(b"\r\n",b"\n").replace(b"\r",b"\n"))

def generate(output:Path)->None:
    subprocess.run([sys.executable,str(GENERATOR),"--root",str(AUTHORITY),"--out",str(output)],cwd=ROOT,check=True); _normalize_generated_files_to_lf(output)

def check()->int:
    if CHECK_OUTPUT.exists(): shutil.rmtree(CHECK_OUTPUT)
    try:
        generate(CHECK_OUTPUT)
        diff=[n for n in GENERATED_FILES if not (OUTPUT/n).is_file() or (OUTPUT/n).read_bytes()!=(CHECK_OUTPUT/n).read_bytes()]
    finally:
        if CHECK_OUTPUT.exists(): shutil.rmtree(CHECK_OUTPUT)
    if diff: print("Generated OpenAPI client differs: "+", ".join(diff)); return 1
    print("OpenAPI generated client check: PASS"); return 0

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("command",choices=("generate","check")); a=ap.parse_args()
    if a.command=="generate": generate(OUTPUT); return 0
    return check()
if __name__=="__main__": raise SystemExit(main())
