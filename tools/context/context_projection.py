from __future__ import annotations
from pathlib import Path
from typing import Any
from .authority_index import authority_index_status, authority_preview, query_authority_result
from .context_loading import CONTEXT_EXPANSION_REQUIRED, CONTEXT_SUFFICIENT, CONTEXT_UNAVAILABLE, context_consumer_id, context_consumer_status, ensure_context_history, file_sha256, history_summary, load_context_efficiency_config
from .repo_intelligence import repo_intelligence_projection


def _priority_refs(refs:list[dict[str,Any]],routed_paths:list[str])->list[dict[str,Any]]:
    ordered=[]; seen=set()
    for path in routed_paths:
        for ref in refs:
            if str(ref.get('path') or '')!=path: continue
            key=(path,str(ref.get('selector') or ''))
            if key not in seen: ordered.append(ref); seen.add(key)
            break
    for ref in refs:
        key=(str(ref.get('path') or ''),str(ref.get('selector') or ''))
        if key not in seen: ordered.append(ref); seen.add(key)
    return ordered


def _ref_key(ref:dict[str,Any])->tuple[str,str]:
    return (str(ref.get('path') or ''),str(ref.get('selector') or ''))


def _compact_required_ref(root:Path,ref:dict[str,Any])->dict[str,Any]:
    path=str(ref.get('path') or '')
    selector=str(ref.get('selector') or '')
    source=root/path
    return {
        'path':path,
        'selector':selector,
        'record_id':ref.get('record_id'),
        'canonical_record_id':ref.get('canonical_record_id'),
        'sha256':file_sha256(source) if path and source.is_file() else 'MISSING',
    }


def _required_authority_refs(root:Path,refs:list[dict[str,Any]],relationship:dict[str,Any],routed_paths:list[str])->tuple[list[dict[str,Any]],dict[str,Any]]:
    """Return the smallest deterministic set of Authority records whose facts must be loaded.

    Locator discovery and relationship closure only answer WHERE_TO_READ.  This set identifies
    the exact records whose full content must have been read before CONTEXT_SUFFICIENT is valid.
    """
    by_key={_ref_key(ref):ref for ref in refs if ref.get('identity_kind')!='ROUTED_FILE_REF' and ref.get('selector')}
    required_keys:set[tuple[str,str]]=set()
    for candidate in relationship.get('candidate_refs') or []:
        key=(str(candidate.get('path') or ''),str(candidate.get('selector') or ''))
        if key in by_key: required_keys.add(key)
    anchor_ids={str(x) for x in relationship.get('anchor_ids') or [] if str(x)}
    explicit_required_keys:set[tuple[str,str]]=set()
    relationship_required_keys:set[tuple[str,str]]=set(required_keys)
    for key,ref in by_key.items():
        reasons={str(x) for x in ref.get('relevance_reasons') or []}
        canonical=str(ref.get('canonical_record_id') or '')
        if canonical in anchor_ids or {'EXPLICIT_ID','EXPLICIT_ENDPOINT'} & reasons:
            explicit_required_keys.add(key)
            required_keys.add(key)
        if any(reason.startswith('RELATIONSHIP_') for reason in reasons):
            relationship_required_keys.add(key); required_keys.add(key)

    core_coverage_keys:set[tuple[str,str]]=set()
    missing_core_authorities:list[str]=[]
    for path in routed_paths:
        candidate=next((ref for ref in refs if str(ref.get('path') or '')==path and _ref_key(ref) in by_key),None)
        if candidate is None:
            missing_core_authorities.append(path)
            continue
        key=_ref_key(candidate); core_coverage_keys.add(key); required_keys.add(key)

    required=[_compact_required_ref(root,by_key[key]) for key in sorted(required_keys)]
    coverage={
        'routed_core_authority_count':len(routed_paths),
        'covered_core_authority_count':len(set(routed_paths)-set(missing_core_authorities)),
        'missing_core_authorities':sorted(set(missing_core_authorities)),
        'relationship_required_count':len(relationship_required_keys),
        'explicit_required_count':len(explicit_required_keys),
        'core_minimum_required_count':len(core_coverage_keys),
        'required_union_count':len(required),
        'complete':not bool(missing_core_authorities),
    }
    return required,coverage


def _loaded_required_authority_refs(root:Path,ctx:dict[str,Any],required:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    history=ensure_context_history(ctx)
    loaded_entries=list(history.get('authority') or [])
    consumer=context_consumer_id(ctx)
    loaded=[]; missing=[]
    for ref in required:
        path=str(ref.get('path') or ''); selector=str(ref.get('selector') or ''); expected_sha=str(ref.get('sha256') or '')
        source=root/path
        current_sha=file_sha256(source) if path and source.is_file() else 'MISSING'
        matched=next((item for item in loaded_entries if str(item.get('consumer_id') or 'SINGLE_CONTINUOUS_CONTEXT_CONSUMER')==consumer and str(item.get('locator') or '')==path and str(item.get('scope') or '')==selector and str(item.get('sha256') or '')==current_sha and bool(item.get('expanded'))),None)
        normalized={**ref,'sha256':current_sha}
        if matched is not None and expected_sha==current_sha: loaded.append(normalized)
        else: missing.append(normalized)
    return loaded,missing


def enrich_task_context(root:Path,ctx:dict[str,Any])->dict[str,Any]:
    root=root.resolve(); out=dict(ctx); ensure_context_history(out)
    request=str(out.get('request') or ''); domains=[str(x) for x in out.get('domains') or []]; authorities=[str(x) for x in out.get('authorities') or []]; affected=[str(x) for x in out.get('affected_files') or []]
    cfg=load_context_efficiency_config(root); loading=cfg['context_loading']; index_state=authority_index_status(root)
    query={'status':index_state['status'],'refs':[],'diagnostics':{}}
    if index_state['status'] in {'READY','PARTIAL'}: query=query_authority_result(root,request=request,domains=domains,authority_paths=authorities,build_if_missing=False)
    refs=_priority_refs(list(query.get('refs') or []),authorities)
    preview=authority_preview(refs,max_chars=int(loading['authority'].get('preview_chars',12000)))
    repo=repo_intelligence_projection(root,request,affected,task_context=out)
    diagnostics=dict(query.get('diagnostics') or {}); unrepresented=list(diagnostics.get('unrepresented_authority_files') or [])
    unavailable_sources=list(diagnostics.get('direct_read_required') or [])
    relationship=dict(diagnostics.get('relationship_closure') or {})
    missing_relationships=list(relationship.get('missing_relationships') or [])
    relationship_incomplete=bool(relationship.get('anchor_ids')) and not bool(relationship.get('complete',False))
    required_refs,required_fact_coverage=_required_authority_refs(root,refs,relationship,authorities)
    loaded_refs,missing_required_refs=_loaded_required_authority_refs(root,out,required_refs)
    core_authority_coverage_incomplete=not bool(required_fact_coverage.get('complete',False))
    index_ready=index_state['status']=='READY'
    required_facts_not_loaded=bool(missing_required_refs) or (bool(authorities) and not index_ready)
    # The locator preview is only the initial discovery batch.  Once every required fact has
    # been loaded, a truncated preview of lower-priority locators must not keep the task blocked.
    preview_incomplete=preview.get('status') in {'TRUNCATED','REF_ONLY','NO_RECORDS'} and (required_facts_not_loaded or not required_refs)
    if unavailable_sources and all(not (root/path).exists() for path in unavailable_sources):
        context_status=CONTEXT_UNAVAILABLE
    elif index_state['status'] in {'MISSING','STALE','INVALID','PARTIAL'} or query.get('status') in {'PARTIAL','TRUNCATED'} or unrepresented or relationship_incomplete or core_authority_coverage_incomplete or required_facts_not_loaded or preview_incomplete:
        context_status=CONTEXT_EXPANSION_REQUIRED
    else:
        context_status=CONTEXT_SUFFICIENT
    out['authority_index']=index_state; out['authority_refs']=refs
    out['required_authority_refs']=required_refs; out['loaded_authority_refs']=loaded_refs; out['missing_required_authority_refs']=missing_required_refs
    out['required_fact_coverage']=required_fact_coverage
    out['authority_slice']={**preview,'query_status':query.get('status'),'query_diagnostics':diagnostics,'routed_core_authorities':sorted(set(authorities)),'unrepresented_routed_authorities':unrepresented,'direct_read_required':unavailable_sources}
    out['repo_intelligence']=repo
    expansion_reason=[]
    if relationship_incomplete: expansion_reason.append('UNRESOLVED_AUTHORITY_RELATIONSHIP')
    if core_authority_coverage_incomplete: expansion_reason.append('ROUTED_CORE_AUTHORITY_FACT_MISSING')
    if required_facts_not_loaded: expansion_reason.append('REQUIRED_AUTHORITY_FACTS_NOT_LOADED')
    if unrepresented: expansion_reason.append('UNREPRESENTED_ROUTED_AUTHORITY')
    if preview_incomplete: expansion_reason.append('INITIAL_PREVIEW_INCOMPLETE')
    if index_state['status'] in {'MISSING','STALE','INVALID','PARTIAL'}: expansion_reason.append('AUTHORITY_INDEX_NOT_FULLY_READY')
    if context_status==CONTEXT_EXPANSION_REQUIRED and required_facts_not_loaded:
        next_action='EXPAND_REQUIRED_AUTHORITY'
    elif context_status==CONTEXT_EXPANSION_REQUIRED:
        next_action='PRECISE_EXPAND_REQUIRED'
    elif context_status==CONTEXT_UNAVAILABLE:
        next_action='STOP_AND_REPORT_MISSING_FACTS'
    else:
        next_action='IMPLEMENT_OR_CONTINUE'
    out['context_efficiency']={
        'status':context_status,'strategy':'ADAPTIVE_CONTEXT_LOADING','authority_selection_granularity':'RECORD_OR_ROUTED_FILE_REF','code_selection_granularity':'AGENT_TOOL_DRIVEN','tests_selection_granularity':'AGENT_TOOL_DRIVEN','governance_facts_unchanged':True,'authority_source_unchanged':True,'degraded_sources':unavailable_sources,
        'structural_context_ready':not bool(unrepresented),'locator_ready':bool(required_refs) or not bool(authorities),'facts_loaded':index_ready and not required_facts_not_loaded and not core_authority_coverage_incomplete,
        'semantic_relationship_closure_complete':not relationship_incomplete,'relationship_complete_semantics':str(relationship.get('complete_semantics') or 'RELATIONSHIP_PATH_RESOLVED'),
        'required_authority_ref_count':len(required_refs),'loaded_authority_ref_count':len(loaded_refs),'missing_required_authority_ref_count':len(missing_required_refs),
        'required_fact_coverage':required_fact_coverage,
        'core_authority_coverage_complete':not core_authority_coverage_incomplete,
        'context_consumer_id':context_consumer_id(out),'context_consumer_status':context_consumer_status(out),
        'anchor_mode':str(relationship.get('anchor_mode') or 'NO_SPECIFIC_ANCHOR'),'weak_candidate_ids':list(relationship.get('weak_candidate_ids') or []),
        'expansion_reason':expansion_reason,'missing_relationships':missing_relationships,'candidate_refs':list(relationship.get('candidate_refs') or []),'next_action':next_action,
    }
    out['context_history_summary']=history_summary(out); return out
