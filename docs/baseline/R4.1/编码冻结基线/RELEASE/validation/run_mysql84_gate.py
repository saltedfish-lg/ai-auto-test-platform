#!/usr/bin/env python3
from pathlib import Path
import argparse, json, shutil, subprocess, time

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[3])
    ap.add_argument("--compose",type=Path,default=Path(__file__).resolve().parent/"mysql84-compose.yml")
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    docker=shutil.which("docker")
    podman=shutil.which("podman")
    mysql=shutil.which("mysql")
    executed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    report={"release_id":"PDBR-2026.08.06-R4.1","gate":"MYSQL84_EMPTY_DATABASE_EXECUTION",
            "blocking_scope":"DATABASE_MODULE_FORMAL_MERGE","executed_at":executed_at,
            "details":{"docker":docker,"podman":podman,"mysql_client":mysql},
            "required_steps":["empty database","V3 migration","V4 seed first run","V4 seed second run",
                              "foreign key rejection","unique key rejection","check constraint rejection",
                              "illegal state rejection","idempotency and optimistic-lock schema checks"]}
    engine=docker or podman
    if not engine:
        report.update({"status":"NOT_EXECUTED_ENVIRONMENT_UNAVAILABLE",
                       "note":"No MySQL 8.4 server/container runtime detected. This result is intentionally not PASS."})
        rc=2
    else:
        cmd=[engine,"compose","-f",str(args.compose),"up","--abort-on-container-exit","--exit-code-from","validator"]
        p=subprocess.run(cmd,cwd=args.compose.parent,text=True,capture_output=True)
        cleanup=subprocess.run([engine,"compose","-f",str(args.compose),"down","-v"],cwd=args.compose.parent,text=True,capture_output=True)
        report.update({"status":"PASS" if p.returncode==0 else "FAIL","command":cmd,"returncode":p.returncode,
                       "stdout":p.stdout[-20000:],"stderr":p.stderr[-20000:],
                       "cleanup_returncode":cleanup.returncode})
        rc=0 if p.returncode==0 else 1
    raw=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(raw,encoding="utf-8")
    print(raw)
    return rc
if __name__=="__main__": raise SystemExit(main())
