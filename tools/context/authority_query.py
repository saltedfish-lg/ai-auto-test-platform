from __future__ import annotations

if __package__ in (None, ''):
    import sys as _sys
    from pathlib import Path as _BootstrapPath
    _sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[2]))
    __package__ = 'tools.context'

import argparse
import json
from pathlib import Path

from .context_loading import context_read_seen, file_sha256, record_context_read, ensure_context_history, history_summary
from tools.governance.task_context import load_context, save_context
from .authority_index import (
    build_authority_index,
    expand_authority_refs,
    query_authority_result,
    refs_by_id,
)


def main() -> int:
    parser = argparse.ArgumentParser(description='Deterministic project Authority locator/slicer.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--request', default='')
    parser.add_argument('--domain', action='append', default=[])
    parser.add_argument('--authority-path', action='append', default=[])
    parser.add_argument('--selector')
    parser.add_argument('--id', dest='record_id')
    parser.add_argument('--max-records', type=int)
    parser.add_argument('--max-chars', type=int)
    parser.add_argument('--expand', action='store_true')
    parser.add_argument('--task-id', help='Bind query/expand read history to an active Task Context.')
    parser.add_argument('--force-expand', action='store_true', help='Reload unchanged content only when a larger/explicit reread is required.')
    parser.add_argument('--rebuild-index', action='store_true')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.rebuild_index:
        result = build_authority_index(root, force=True)
        print(json.dumps({
            key: result[key]
            for key in ('kind', 'status', 'source_signature', 'record_count', 'parse_errors', 'cache_path')
        }, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'READY' else 2

    if args.selector:
        if len(args.authority_path) != 1:
            output = {
                'status': 'INVALID_SELECTOR',
                'reason': 'SELECTOR_REQUIRES_EXACTLY_ONE_AUTHORITY_PATH',
                'record_count': 0,
                'authority_refs': [],
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 2
        locator = f'{args.authority_path[0]}#{args.selector}'
        refs = refs_by_id(root, locator, authority_paths=args.authority_path, selector=args.selector)
        query_status = 'READY' if refs else 'NOT_FOUND'
        diagnostics = {'lookup': 'FALLBACK_LOCATOR'}
    elif args.record_id:
        refs = refs_by_id(root, args.record_id, authority_paths=args.authority_path)
        if not refs:
            query_status = 'NOT_FOUND'
        elif len(refs) > 1:
            query_status = 'AMBIGUOUS'
        else:
            query_status = 'READY'
        diagnostics = {'lookup': 'IDENTITY', 'candidate_count': len(refs)}
    else:
        result = query_authority_result(
            root,
            request=args.request,
            domains=args.domain,
            authority_paths=args.authority_path,
            max_records=args.max_records,
        )
        refs = result['refs']
        query_status = result['status'] if refs else ('NOT_FOUND' if result['status'] in {'READY', 'PARTIAL'} else result['status'])
        diagnostics = result.get('diagnostics') or {}

    output: dict = {
        'status': query_status,
        'record_count': len(refs),
        'authority_refs': refs,
        'diagnostics': diagnostics,
    }
    if args.expand:
        task_ctx = load_context(root, args.task_id) if args.task_id else None
        refs_to_expand = refs
        reused_refs = []
        fresh_identity: dict[tuple[str, str], str] = {}
        if task_ctx is not None:
            ensure_context_history(task_ctx); fresh=[]
            for ref in refs:
                path=str(ref.get('path') or ''); selector=str(ref.get('selector') or ''); source=root/path
                sha=file_sha256(source) if source.is_file() else 'MISSING'
                if not args.force_expand and context_read_seen(task_ctx,'authority',locator=path,scope=selector,sha256=sha):
                    task_ctx,_=record_context_read(task_ctx,'authority',locator=path,scope=selector,sha256=sha,expanded=True,force=False)
                    reused_refs.append({'path':path,'selector':selector,'sha256':sha})
                else:
                    fresh.append(ref); fresh_identity[(path,selector)] = sha
            refs_to_expand=fresh
        expansion = expand_authority_refs(root, refs_to_expand, max_chars=args.max_chars)
        if task_ctx is not None:
            for item in expansion.get('records') or []:
                path=str(item.get('path') or ''); selector=str(item.get('selector') or '')
                sha=fresh_identity.get((path,selector))
                # Only a complete record satisfies the exact selector read. A partial batch
                # remains expandable on the next call without requiring a quota override.
                if sha and bool(item.get('full_record')):
                    task_ctx,_=record_context_read(task_ctx,'authority',locator=path,scope=selector,sha256=sha,expanded=True,force=args.force_expand)
        if reused_refs and not refs_to_expand:
            expansion={'status':'REUSED_CONTEXT','strategy':'ADAPTIVE_AUTHORITY_EXPANSION','record_count':0,'ref_only_count':0,'records':[],'errors':[],'reused_refs':reused_refs,'can_continue_expanding':True}
        elif reused_refs: expansion['reused_refs']=reused_refs
        output['authority_slice'] = expansion
        output['context_scope'] = 'TASK_HISTORY' if args.task_id else 'STANDALONE_DIAGNOSTIC'
        if task_ctx is not None:
            save_context(root,args.task_id,task_ctx); output['context_history_summary']=history_summary(task_ctx)
        if expansion['status'] not in {'PASS','REUSED_CONTEXT'}:
            if query_status == 'AMBIGUOUS' and expansion.get('record_count'):
                output['status'] = 'AMBIGUOUS'
            else:
                output['status'] = expansion['status']
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0 if output['status'] in {'READY','PASS','REUSED_CONTEXT'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
