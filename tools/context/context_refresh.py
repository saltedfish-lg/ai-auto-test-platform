from __future__ import annotations
if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0,str(_BootstrapPath(__file__).resolve().parents[2])); __package__='tools.context'
import argparse,json
from pathlib import Path
from tools.governance.task_context import load_context,save_context
from .context_projection import enrich_task_context

def refresh_task_context(root:Path,task_id:str)->dict:
    root=root.resolve(); ctx=load_context(root,task_id); enriched=enrich_task_context(root,ctx); save_context(root,task_id,enriched); return enriched

def main()->int:
    p=argparse.ArgumentParser(description='Refresh adaptive context projections for an active task.'); p.add_argument('--root',default='.'); p.add_argument('--task-id',required=True); a=p.parse_args(); r=refresh_task_context(Path(a.root),a.task_id); s=r.get('authority_slice') or {}; h=r.get('context_history_summary') or {}
    print(json.dumps({'task_id':r.get('task_id'),'context_status':(r.get('context_efficiency') or {}).get('status'),'context_efficiency':r.get('context_efficiency'),'authority_index':r.get('authority_index'),'authority_ref_count':len(r.get('authority_refs') or []),'required_authority_refs':r.get('required_authority_refs') or [],'loaded_authority_refs':r.get('loaded_authority_refs') or [],'missing_required_authority_refs':r.get('missing_required_authority_refs') or [],'authority_slice':{'status':s.get('status'),'record_count':s.get('record_count'),'ref_only_count':s.get('ref_only_count'),'unrepresented_routed_authorities':s.get('unrepresented_routed_authorities') or []},'context_history':h,'reused_context_count':h.get('reused_context_count',0),'expanded_context_count':h.get('expanded_context_count',0),'repo_intelligence':{'status':(r.get('repo_intelligence') or {}).get('status'),'provider':(r.get('repo_intelligence') or {}).get('provider')}},ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
