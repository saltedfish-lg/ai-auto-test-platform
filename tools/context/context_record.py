from __future__ import annotations
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2])); __package__='tools.context'
import argparse, json
from pathlib import Path
from .context_loading import project_task_context

def main() -> int:
    p=argparse.ArgumentParser(description='Project model-facing context into one Task with adaptive deduplication.')
    p.add_argument('--root',default='.'); p.add_argument('--task-id',required=True); p.add_argument('--category',choices=['source_code','tests','tool_output'],required=True)
    p.add_argument('--locator',required=True); p.add_argument('--scope',default=''); p.add_argument('--text'); p.add_argument('--file'); p.add_argument('--expand',action='store_true'); p.add_argument('--force',action='store_true')
    a=p.parse_args(); content=a.text
    if a.file: content=Path(a.file).read_text(encoding='utf-8',errors='replace')
    if content is None: content=''
    ctx,projection=project_task_context(Path(a.root),a.task_id,a.category,content,locator=a.locator,scope=a.scope,expand=a.expand,force=a.force)
    print(json.dumps({'task_id':a.task_id,'projection':projection,'context_history':ctx.get('context_history')},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
