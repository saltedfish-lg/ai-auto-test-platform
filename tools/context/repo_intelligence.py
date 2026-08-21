from __future__ import annotations
import fnmatch
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from .context_loading import load_context_efficiency_config, content_sha256, ensure_context_history, record_context_read
from tools.governance.workspace_path_policy import classify_relative_path, load_policy

@dataclass(frozen=True)
class CodeContextHint:
    path:str; symbol:str|None=None; relationship:str|None=None; reason:str|None=None; excerpt:str|None=None

class RepoIntelligenceProvider(Protocol):
    name:str
    def search(self, *, root:Path, request:str, affected_files:list[str], include_paths:list[str], exclude_paths:list[str], max_results:int, task_context:dict[str,Any]) -> list[CodeContextHint]: ...

class NullRepoIntelligenceProvider:
    name='none'
    def search(self, *, root:Path, request:str, affected_files:list[str], include_paths:list[str], exclude_paths:list[str], max_results:int, task_context:dict[str,Any]) -> list[CodeContextHint]:
        del root,request,affected_files,include_paths,exclude_paths,max_results,task_context; return []

def _match(path:str,pattern:str)->bool:
    normalized=path.replace('\\','/').lstrip('./'); pat=str(pattern).replace('\\','/').lstrip('./')
    return fnmatch.fnmatch(normalized,pat) or (pat.endswith('/**') and normalized.startswith(pat[:-3].rstrip('/')+'/'))

def _path_allowed(root:Path,path:str,include_paths:list[str],exclude_paths:list[str])->bool:
    normalized=path.replace('\\','/').lstrip('./')
    if any(_match(normalized,p) for p in exclude_paths): return False
    try: category=classify_relative_path(normalized,load_policy(root))
    except ValueError: return False
    if category in {'AUTHORITY','SECRET','TRANSIENT','CACHE','BUILD_OUTPUT','RUNTIME_OUTPUT'}: return False
    return True if not include_paths else any(_match(normalized,p) for p in include_paths)

def _normalize_hints(root:Path,hints:list[CodeContextHint],*,include_paths:list[str],exclude_paths:list[str],max_results:int)->tuple[list[dict[str,Any]],dict[str,Any]]:
    accepted=[]; rejected=[]; seen=set(); limited=False
    for hint in hints:
        if len(accepted)>=max_results: limited=True; break
        if not _path_allowed(root,hint.path,include_paths,exclude_paths): rejected.append(hint.path); continue
        payload=asdict(hint); key=(payload['path'],payload.get('symbol'),payload.get('relationship'),payload.get('excerpt'))
        if key in seen: continue
        seen.add(key); accepted.append(payload)
    return accepted,{'result_limit_reached':limited,'rejected_path_count':len(rejected),'rejected_paths':rejected[:20],'deduplicated':len(hints)-len(accepted)-len(rejected)}

def repo_intelligence_projection(root:Path,request:str,affected_files:list[str],*,task_context:dict[str,Any]|None=None,provider:RepoIntelligenceProvider|None=None)->dict[str,Any]:
    root=root.resolve(); cfg=load_context_efficiency_config(root); settings=cfg['repo_intelligence']; provider_name=str(settings.get('provider') or 'none').lower(); selected=provider or NullRepoIntelligenceProvider()
    if provider is None and provider_name!='none': selected=NullRepoIntelligenceProvider()
    include_paths=[str(x) for x in settings.get('include_paths') or []]; exclude_paths=[str(x) for x in settings.get('exclude_paths') or []]
    if str(settings.get('authority_role') or 'forbidden').lower()!='forbidden': raise ValueError('REPO_INTELLIGENCE_AUTHORITY_ROLE_MUST_BE_FORBIDDEN')
    if 'docs/authority/**' not in [x.replace('\\','/') for x in exclude_paths]: exclude_paths.append('docs/authority/**')
    if not any(x.startswith('.env') for x in exclude_paths): exclude_paths.append('.env*')
    max_results=max(1,int(settings.get('max_results') or cfg['context_loading'].get('repo_intelligence_max_results',20)))
    raw=selected.search(root=root,request=request,affected_files=list(affected_files),include_paths=include_paths,exclude_paths=exclude_paths,max_results=max_results,task_context=dict(task_context or {}))
    hints,norm=_normalize_hints(root,list(raw),include_paths=include_paths,exclude_paths=exclude_paths,max_results=max_results)
    if task_context is not None:
        ensure_context_history(task_context); signature=content_sha256({'request':request,'affected_files':affected_files,'include_paths':include_paths,'exclude_paths':exclude_paths})
        record_context_read(task_context,'repo_intelligence',locator=request,sha256=signature,scope='query')
    status='READY' if provider is not None else ('RESERVED_NOT_CONFIGURED' if provider_name=='none' else 'PROVIDER_NOT_INSTALLED')
    return {'status':status,'provider':provider_name if provider is None else getattr(provider,'name',provider_name),'authority_role':'FORBIDDEN','may_locate_code_only':True,'may_override_authority':False,'include_paths':include_paths,'exclude_paths':exclude_paths,'max_results':max_results,'normalization':norm,'hints':hints}
