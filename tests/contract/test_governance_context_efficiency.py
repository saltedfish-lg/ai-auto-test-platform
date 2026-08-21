from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from tools.context.authority_index import (
    authority_index_status,
    authority_preview,
    build_authority_index,
    expand_authority_refs,
    query_authority_result,
    refs_by_id,
)
from tools.context.context_loading import (
    CONTEXT_EXPANSION_REQUIRED,
    CONTEXT_SUFFICIENT,
    CONTEXT_UNAVAILABLE,
    context_decision,
    ensure_context_history,
    history_summary,
    project_context,
)
from tools.context.context_projection import enrich_task_context
from tools.context.repo_intelligence import CodeContextHint, repo_intelligence_projection
from tools.governance.impact_scan import infer_domains
from tools.governance.task_context import cleanup_task, load_context, save_context
from tools.governance.task_governance import start

GOVERNANCE_TEST_GROUP = 'routing'
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_profile(root: Path, *, authorities: dict | None = None, initial_records: int = 8, preview_chars: int = 4000) -> None:
    profile = root / '.governance'; profile.mkdir(parents=True, exist_ok=True)
    authority_config = authorities or {'product_model': {'domains': ['PRODUCT_MODEL', 'LIFECYCLE'], 'paths': ['docs/authority/model.yaml']}}
    (profile/'authorities.yaml').write_text(yaml.safe_dump({'schema_version':1,'authorities':authority_config},allow_unicode=True,sort_keys=False),encoding='utf-8')
    (profile/'context-efficiency.yaml').write_text(yaml.safe_dump({
        'schema_version':1,
        'context_efficiency': {'mode':'adaptive_context_loading','governance_gate':False},
        'context_loading': {
            'authority': {'strategy':'precise_slice','initial_records':initial_records,'preview_chars':preview_chars,'allow_on_demand_expand':True,'avoid_repeat_unchanged_read':True},
            'source_code': {'strategy':'symbol_first','allow_full_file_when_required':True,'avoid_repeat_unchanged_read':True},
            'tests': {'strategy':'relevant_first','allow_expand_when_required':True,'avoid_repeat_unchanged_read':True},
            'tool_output': {'strategy':'summarize_then_expand','summary_chars':80,'allow_raw_expand_when_required':True,'avoid_repeat_unchanged_read':True},
            'deduplication': {'enabled':True}, 'context_history': {'enabled':True},
            'repo_intelligence_max_results':2,'minimum_records_per_authority':1,'minimum_records_per_domain':1,
        },
        'authority_index': {
            'source_roots':['docs/authority'],'cache_path':'.runtime/context-index/authority-index.sqlite3','extensions':['.yaml','.yml','.json','.csv'],
            'exclude_patterns':['**/.governance-domain.yaml'],
            'canonical_identity_keys':[
                'record_id','canonical_id','structural_id','id',
                'rule_id','decision_id','scenario_id','lifecycle_id','state_definition_id','transition_id',
                'permission_code','permission_id','role_code','role_id','operationId','operation_id',
                'acceptance_id','requirement_id','capability_id','data_asset_id','architecture_decision_id',
                'contract_id','gate_id','policy_id','module_id','menu_id','domain_id','object_id',
            ],
            'identity_strategies': {
                'operation-permission-mapping.csv': {'primary':['operationId'],'secondary':['permission_code'],'composite':['operationId','permission_code']},
                'role-permission-matrix.csv': {'primary':['mapping_id'],'secondary':['role_id','permission_id','permission_code']},
                'openapi.operations': {'primary':['operationId'],'fallback':['method','path']},
            },
        },
        'repo_intelligence': {'provider':'none','authority_role':'forbidden','max_results':2,'include_paths':['apps/**','services/**','tools/**','tests/**'],'exclude_paths':['docs/authority/**','.runtime/**','.git/**','.env*','**/__pycache__/**']},
    },allow_unicode=True,sort_keys=False),encoding='utf-8')


def _write_authority(root: Path) -> None:
    path=root/'docs/authority/model.yaml'; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(yaml.safe_dump({'metadata':{'document_name':'fixture'},'objects':[{'object_id':'OBJ-001','canonical_name_zh':'用户','domain':'PRODUCT_MODEL'}],
        'business_rules':[{'rule_id':'BR-001','rule_name':'用户冻结规则','domain':'PRODUCT_MODEL','object_ids':['OBJ-001'],'rule_statement':'冻结后禁止登录'}],
        'lifecycles':[{'lifecycle_id':'LC-001','object_id':'OBJ-001','lifecycle_name':'用户生命周期','initial_stage':'ACTIVE'}]},allow_unicode=True,sort_keys=False),encoding='utf-8')


def test_authority_index_uses_canonical_ids_and_skips_projection_metadata(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); result=build_authority_index(tmp_path)
    assert result['status']=='READY'; refs=refs_by_id(tmp_path,'LC-001'); assert len(refs)==1; assert refs[0]['selector']=='/lifecycles/0'


def test_authority_selector_round_trip_handles_slash_tilde_unicode_yaml_and_json(tmp_path: Path) -> None:
    authorities={'yaml_api':{'domains':['API_CONTRACT'],'paths':['docs/authority/api.yaml']},'json_api':{'domains':['API_CONTRACT'],'paths':['docs/authority/api.json']}}
    _write_profile(tmp_path,authorities=authorities,initial_records=10); base=tmp_path/'docs/authority'; base.mkdir(parents=True)
    payload={'paths':{'/users/{id}~view':{'get':{'operationId':'get_user_view','summary':'中文用户详情'}}}}
    (base/'api.yaml').write_text(yaml.safe_dump(payload,allow_unicode=True,sort_keys=False),encoding='utf-8'); (base/'api.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    build_authority_index(tmp_path)
    refs=refs_by_id(tmp_path,'get_user_view'); assert refs; assert all('~1users~1{id}~0view' in ref['selector'] for ref in refs)
    expanded=expand_authority_refs(tmp_path,[refs[0]]); assert expanded['status']=='PASS'; assert expanded['records'][0]['content']['summary']=='中文用户详情'


def test_authority_index_content_digest_detects_same_size_same_mtime_change(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path); p=tmp_path/'docs/authority/model.yaml'; st=p.stat(); raw=p.read_text(encoding='utf-8'); changed=raw.replace('冻结后禁止登录','冻结后禁止访问')
    assert len(changed)==len(raw); p.write_text(changed,encoding='utf-8'); os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns)); assert authority_index_status(tmp_path)['status']=='STALE'


def test_authority_index_parse_error_is_partial(tmp_path: Path) -> None:
    _write_profile(tmp_path,authorities={'a':{'domains':['LIFECYCLE'],'paths':['docs/authority/good.yaml','docs/authority/broken.yaml']}}); base=tmp_path/'docs/authority'; base.mkdir(parents=True)
    (base/'good.yaml').write_text('rules:\n- rule_id: BR-001\n  statement: good\n',encoding='utf-8'); (base/'broken.yaml').write_text('lifecycles: [\n  - lifecycle_id: LC-X\n    : bad\n',encoding='utf-8')
    built=build_authority_index(tmp_path); assert built['status']=='PARTIAL'; assert authority_index_status(tmp_path)['status']=='PARTIAL'


def test_plain_reference_id_is_not_promoted_to_canonical(tmp_path: Path) -> None:
    _write_profile(tmp_path); p=tmp_path/'docs/authority/model.yaml'; p.parent.mkdir(parents=True); p.write_text('records:\n- session_id: runtime-session\n  description: runtime value\n',encoding='utf-8'); build_authority_index(tmp_path)
    assert not refs_by_id(tmp_path,'runtime-session')


def test_duplicate_record_id_is_ambiguous_not_silently_selected(tmp_path: Path) -> None:
    authorities={'a':{'domains':['PRODUCT_MODEL'],'paths':['docs/authority/a.yaml','docs/authority/b.yaml']}}; _write_profile(tmp_path,authorities=authorities)
    for name in ('a','b'):
        p=tmp_path/f'docs/authority/{name}.yaml'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('rules:\n- rule_id: BR-DUP\n  name: duplicate\n',encoding='utf-8')
    build_authority_index(tmp_path); refs=refs_by_id(tmp_path,'BR-DUP'); assert len(refs)==2; assert all(x['ambiguous'] for x in refs)


def test_authority_schema_aware_identity_for_operation_and_role_mapping(tmp_path: Path) -> None:
    op='docs/authority/operation-permission-mapping.csv'; role='docs/authority/role-permission-matrix.csv'; _write_profile(tmp_path,authorities={'p':{'domains':['RBAC','API_CONTRACT'],'paths':[op,role]}})
    p=tmp_path/op; p.parent.mkdir(parents=True); p.write_text('operationId,method,path,permission_code\nreset_user_credential,POST,/users/{id}/credential,USER_CREATE\n',encoding='utf-8')
    (tmp_path/role).write_text('mapping_id,role_id,permission_id,permission_code\nRPM-R3-0021,ROLE-ADMIN,TERM-PER-021,USER_CREATE\n',encoding='utf-8'); build_authority_index(tmp_path)
    assert refs_by_id(tmp_path,'reset_user_credential')[0]['canonical_record_id']=='reset_user_credential'; assert refs_by_id(tmp_path,'RPM-R3-0021')[0]['canonical_record_id']=='RPM-R3-0021'; assert len(refs_by_id(tmp_path,'USER_CREATE'))==2


def test_routed_authority_file_minimum_recall_preserves_refs(tmp_path: Path) -> None:
    paths=[f'docs/authority/a{i}.yaml' for i in range(4)]; _write_profile(tmp_path,authorities={'bundle':{'domains':['AUTHENTICATION'],'paths':paths}},initial_records=2)
    for i,rel in enumerate(paths):
        p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(yaml.safe_dump({'rules':[{'rule_id':f'BR-{i:03d}','name':f'auth {i}'}]}),encoding='utf-8')
    build_authority_index(tmp_path); result=query_authority_result(tmp_path,request='authentication rules',domains=['AUTHENTICATION'],authority_paths=paths,max_records=2)
    assert set(paths)<={r['path'] for r in result['refs']}
    assert all(any(r['path']==path and not r.get('ref_only') for r in result['refs']) for path in paths)


def test_implementation_domain_not_authority_missing(tmp_path: Path) -> None:
    rel='docs/authority/auth.yaml'; _write_profile(tmp_path,authorities={'auth':{'domains':['AUTHENTICATION'],'paths':[rel]}}); p=tmp_path/rel; p.parent.mkdir(parents=True); p.write_text('rules:\n- rule_id: BR-AUTH\n  name: authentication\n',encoding='utf-8'); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='backend authentication',domains=['BACKEND','AUTHENTICATION'],authority_paths=[rel]); assert result['status']=='READY'; assert 'BACKEND' not in result['diagnostics']['missing_domains']


def test_explicit_openapi_endpoint_extraction_has_priority(tmp_path: Path) -> None:
    rel='docs/authority/openapi.yaml'; _write_profile(tmp_path,authorities={'api':{'domains':['API_CONTRACT'],'paths':[rel]}}); p=tmp_path/rel; p.parent.mkdir(parents=True); p.write_text(yaml.safe_dump({'paths':{'/users/{id}':{'get':{'operationId':'get_user'}}}},sort_keys=False),encoding='utf-8'); build_authority_index(tmp_path)
    r=query_authority_result(tmp_path,request='check /users/{id} endpoint',domains=['API_CONTRACT'],authority_paths=[rel]); op=next(x for x in r['refs'] if x.get('canonical_record_id')=='get_user'); assert 'EXPLICIT_ENDPOINT' in op['relevance_reasons']


def test_empty_authority_slice_status_is_not_pass(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path); assert authority_preview([],max_chars=100)['status']=='NO_RECORDS'; assert expand_authority_refs(tmp_path,[])['status']=='NO_RECORDS'


def test_context_expansion_required_when_information_insufficient() -> None:
    assert context_decision(information_available=True,information_sufficient=False)==CONTEXT_EXPANSION_REQUIRED


def test_context_unavailable_blocks_guessing() -> None:
    assert context_decision(information_available=False,information_sufficient=False)==CONTEXT_UNAVAILABLE


def test_context_sufficient_state() -> None:
    assert context_decision(information_available=True,information_sufficient=True)==CONTEXT_SUFFICIENT


def test_authority_context_reuse_when_unchanged(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path); save_context(tmp_path,'TASK-HISTORY',{'request':'lifecycle','domains':['LIFECYCLE'],'authorities':['docs/authority/model.yaml']})
    cmd=[sys.executable,'-m','tools.context.authority_query','--root',str(tmp_path),'--id','LC-001','--expand','--task-id','TASK-HISTORY']
    first=subprocess.run(cmd,cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60); second=subprocess.run(cmd,cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60)
    assert first.returncode==0; payload=json.loads(second.stdout); assert payload['authority_slice']['status']=='REUSED_CONTEXT'; assert history_summary(load_context(tmp_path,'TASK-HISTORY'))['reused_context_count']>=1


def test_source_symbol_context_reuse_when_unchanged(tmp_path: Path) -> None:
    _write_profile(tmp_path); ctx={}; ctx,p1=project_context(ctx,tmp_path,'source_code','def f(): return 1',locator='services/a.py',scope='f'); ctx,p2=project_context(ctx,tmp_path,'source_code','def f(): return 1',locator='services/a.py',scope='f')
    assert p1['status']=='LOADED'; assert p2['status']=='REUSED_CONTEXT'


def test_authority_can_continue_expanding_without_task_quota(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path)
    for rid in ('OBJ-001','BR-001','LC-001'):
        expanded=expand_authority_refs(tmp_path,refs_by_id(tmp_path,rid)); assert expanded['status']=='PASS'; assert expanded['record_count']==1
    assert 'BUDGET_EXHAUSTED' not in json.dumps([expand_authority_refs(tmp_path,refs_by_id(tmp_path,r)) for r in ('OBJ-001','BR-001','LC-001')])



def test_context_expands_when_information_insufficient_without_task_quota(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path)
    path = tmp_path / 'docs/authority/model.yaml'
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    data['lifecycles'][0]['details'] = 'necessary-fact-' * 120
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
    build_authority_index(tmp_path)
    save_context(tmp_path, 'TASK-EXPAND', {'request':'user lifecycle','domains':['LIFECYCLE'],'authorities':['docs/authority/model.yaml']})
    base=[sys.executable,'-m','tools.context.authority_query','--root',str(tmp_path),'--id','LC-001','--expand','--task-id','TASK-EXPAND']
    partial=subprocess.run(base+['--max-chars','80'],cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60)
    assert partial.returncode==2
    assert json.loads(partial.stdout)['authority_slice']['status']=='TRUNCATED'
    full=subprocess.run(base,cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60)
    assert full.returncode==0
    payload=json.loads(full.stdout); assert payload['authority_slice']['status']=='PASS'; assert payload['authority_slice']['records'][0]['full_record'] is True
    reused=subprocess.run(base,cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60)
    assert reused.returncode==0; assert json.loads(reused.stdout)['authority_slice']['status']=='REUSED_CONTEXT'

def test_large_tool_output_summarize_then_expand(tmp_path: Path) -> None:
    _write_profile(tmp_path); raw='ordinary log\n'*100+'=== FAILURES ===\nAssertionError: CRITICAL_FAILURE_AT_END\nFAILED tests/example.py::test_x\n'; ctx={}; ctx,summary=project_context(ctx,tmp_path,'tool_output',raw,locator='pytest'); assert summary['status']=='DIAGNOSTIC_SUMMARY'; assert 'CRITICAL_FAILURE_AT_END' in summary['content']; assert 'FAILED tests/example.py::test_x' in summary['content']
    ctx,full=project_context(ctx,tmp_path,'tool_output',raw,locator='pytest',expand=True); assert full['status']=='LOADED'; assert full['content']==raw


def test_repo_intelligence_adapter_filters_deduplicates_and_has_no_budget_parameter(tmp_path: Path) -> None:
    _write_profile(tmp_path); (tmp_path/'services').mkdir(); (tmp_path/'services/a.py').write_text('x=1',encoding='utf-8')
    class Fake:
        name='fake'
        def search(self, *, root, request, affected_files, include_paths, exclude_paths, max_results, task_context):
            assert max_results==2; return [CodeContextHint('services/a.py',symbol='x'),CodeContextHint('services/a.py',symbol='x'),CodeContextHint('docs/authority/no.yaml')]
    out=repo_intelligence_projection(tmp_path,'find x',[],task_context={},provider=Fake()); assert out['status']=='READY'; assert len(out['hints'])==1; assert out['hints'][0]['path']=='services/a.py'; assert 'budget' not in out


def test_adaptive_config_contains_no_hard_context_quota_terms(tmp_path: Path) -> None:
    _write_profile(tmp_path); text=(tmp_path/'.governance/context-efficiency.yaml').read_text(encoding='utf-8').lower(); assert 'context_budget' not in text; assert 'total_budget' not in text; assert 'remaining_chars' not in text


def test_task_start_infers_rbac_authorization_credential_session_default_admin_domains() -> None:
    request='重置用户凭据后撤销 Refresh Session，并校验对应 RBAC 权限与 OpenAPI。'
    domains=infer_domains(request,[],PROJECT_ROOT); assert {'AUTHENTICATION','CREDENTIAL','SESSION','RBAC','AUTHORIZATION','API_CONTRACT'}<=domains
    admin=infer_domains('修改默认 admin 权限规则',[],PROJECT_ROOT); assert {'DEFAULT_ADMIN','RBAC','AUTHORIZATION'}<=admin
    role=infer_domains('修改角色权限矩阵',[],PROJECT_ROOT); assert {'RBAC','AUTHORIZATION'}<=role
    session=infer_domains('撤销 Refresh Session',[],PROJECT_ROOT); assert {'SESSION','AUTHENTICATION'}<=session


def _prepare_e2e_root(root: Path) -> list[str]:
    shutil.copytree(PROJECT_ROOT/'.governance',root/'.governance')
    paths=[
        'docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml',
        'docs/authority/编码权威事实/OPENAPI/openapi.yaml',
        'docs/authority/编码权威事实/OPENAPI/operation-permission-mapping.csv',
        'docs/authority/编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml',
        'docs/authority/编码权威事实/PERMISSION_CLOSURE/role-permission-matrix.csv',
    ]
    contents=[
        'records:\n- operation_id: reset_user_credential\n  credential: reset\n  session: revoke\n',
        yaml.safe_dump({'paths':{'/api/v1/users/{id}/credential':{'post':{'operationId':'reset_user_credential','summary':'重置用户凭据'}}}},allow_unicode=True,sort_keys=False),
        'operationId,permission_code,path\nreset_user_credential,USER_CREATE,/api/v1/users/{id}/credential\n',
        'permissions:\n- permission_code: USER_CREATE\n  name: user create\n',
        'mapping_id,role_id,permission_id,permission_code\nRPM-R3-0021,ROLE-ADMIN,TERM-PER-021,USER_CREATE\n',
    ]
    for rel,content in zip(paths,contents):
        p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8')
    return paths


def test_task_start_to_authority_projection_end_to_end(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); build_authority_index(tmp_path)
    ctx=start(tmp_path,'TASK-E2E-CONTEXT','重置用户凭据后撤销 Refresh Session，并校验对应 RBAC 权限与 OpenAPI。',[],mode='readonly')
    try:
        assert {'AUTHENTICATION','CREDENTIAL','SESSION','RBAC','AUTHORIZATION','API_CONTRACT'}<=set(ctx['domains'])
        assert set(routed)<={str(x) for x in ctx['authorities']}
        assert set(routed)<={str(x.get('path')) for x in ctx['authority_refs']}
        assert ctx['context_efficiency']['status'] in {CONTEXT_SUFFICIENT,CONTEXT_EXPANSION_REQUIRED}
    finally: cleanup_task(tmp_path,'TASK-E2E-CONTEXT')


def test_context_refresh_output_has_history_not_budget_fields(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path); save_context(tmp_path,'TASK-REFRESH',{'request':'user lifecycle','domains':['LIFECYCLE'],'authorities':['docs/authority/model.yaml'],'affected_files':[]})
    proc=subprocess.run([sys.executable,'-m','tools.context.context_refresh','--root',str(tmp_path),'--task-id','TASK-REFRESH'],cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60); assert proc.returncode==0
    payload=json.loads(proc.stdout); assert 'context_history' in payload; assert 'context_budget' not in payload; assert 'context_status' in payload


def test_pytest_import_structure_uses_package_module() -> None:
    assert (PROJECT_ROOT/'tools/context/context_loading.py').is_file(); assert not (PROJECT_ROOT/'tools/context/context_budget.py').exists(); assert not (PROJECT_ROOT/'tools/context/context_consume.py').exists()


def test_context_not_sufficient_when_relationship_chain_unresolved(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path, authorities={
        'auth':{'domains':['AUTHENTICATION','CREDENTIAL','SESSION'],'paths':[routed[0]]},
        'api':{'domains':['API_CONTRACT','AUTHORIZATION'],'paths':[routed[1],routed[2]]},
        'permission':{'domains':['RBAC','AUTHORIZATION'],'paths':[routed[3],routed[4]]},
    }, initial_records=3, preview_chars=4000)
    build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'重置用户凭据后撤销 Refresh Session，并校验对应 RBAC 权限与 OpenAPI。','domains':['AUTHENTICATION','CREDENTIAL','SESSION','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]})
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED
    assert 'REQUIRED_AUTHORITY_FACTS_NOT_LOADED' in ctx['context_efficiency']['expansion_reason']


def test_relationship_closure_same_canonical_id(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path, authorities={
        'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}
    }, initial_records=12); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='重置用户凭据 reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed)
    reset_paths={r['path'] for r in result['refs'] if r.get('canonical_record_id')=='reset_user_credential'}
    assert {routed[0],routed[1],routed[2]}<=reset_paths


def test_relationship_closure_reference_ids(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path, authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}}, initial_records=12); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='重置用户凭据 reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed)
    assert result['diagnostics']['relationship_closure']['complete'] is True
    assert any(r.get('canonical_record_id')=='USER_CREATE' and r['path']==routed[3] for r in result['refs'])
    assert any('USER_CREATE' in (r.get('reference_ids') or []) and r['path']==routed[4] for r in result['refs'])


def test_operation_permission_role_relationship_closure(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path, authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}}, initial_records=12); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='重置用户凭据 reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed)
    refs=result['refs']; assert any(r['path']==routed[2] and r.get('canonical_record_id')=='reset_user_credential' for r in refs)
    assert any(r['path']==routed[3] and r.get('canonical_record_id')=='USER_CREATE' for r in refs)
    assert any(r['path']==routed[4] and 'USER_CREATE' in (r.get('reference_ids') or []) for r in refs)


def test_relationship_closure_precedes_generic_top_n(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); auth=tmp_path/routed[0]; data=yaml.safe_load(auth.read_text(encoding='utf-8')); data['background']=[{'rule_id':f'BR-GENERIC-{i:02d}','name':'credential permission openapi background'} for i in range(20)]; auth.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
    _write_profile(tmp_path, authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}}, initial_records=5); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='重置用户凭据 reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed,max_records=5)
    assert result['refs'][0].get('canonical_record_id')=='reset_user_credential'
    assert any(r['path']==routed[2] and r.get('canonical_record_id')=='reset_user_credential' for r in result['refs'])


def test_relationship_closure_is_not_truncated_by_soft_initial_record_target(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path, authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}}, initial_records=2); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed,max_records=2)
    closure=result['diagnostics']['relationship_closure']; assert closure['complete'] is True; assert not closure['missing_relationships']


def _expand_required_authority_refs_via_cli(root: Path, task_id: str, refs: list[dict]) -> None:
    for ref in refs:
        cmd=[sys.executable,'-m','tools.context.authority_query','--root',str(root),'--authority-path',str(ref['path']),'--selector',str(ref['selector']),'--expand','--task-id',task_id]
        proc=subprocess.run(cmd,cwd=PROJECT_ROOT,text=True,capture_output=True,timeout=60)
        assert proc.returncode==0, proc.stdout + proc.stderr


def test_context_sufficient_after_relationship_closure(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path, authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}}, initial_records=12); build_authority_index(tmp_path)
    task_id='TASK-FACTS-LOADED'; initial={'task_id':task_id,'request':'重置用户凭据 reset_user_credential','domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]}
    first=enrich_task_context(tmp_path,initial); save_context(tmp_path,task_id,first)
    assert first['context_efficiency']['semantic_relationship_closure_complete'] is True
    assert first['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED
    _expand_required_authority_refs_via_cli(tmp_path,task_id,first['required_authority_refs'])
    second=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert second['context_efficiency']['facts_loaded'] is True
    assert second['context_efficiency']['status']==CONTEXT_SUFFICIENT


def test_tool_output_preserves_failure_tail(tmp_path: Path) -> None:
    _write_profile(tmp_path); raw='setup log\n'*80+'=== FAILURES ===\nAssertionError: CRITICAL_FAILURE_AT_END\nFAILED tests/example.py::test_x\nshort test summary info\n'; _,projection=project_context({},tmp_path,'tool_output',raw,locator='pytest')
    assert projection['status']=='DIAGNOSTIC_SUMMARY'; assert 'CRITICAL_FAILURE_AT_END' in projection['content']; assert 'FAILED tests/example.py::test_x' in projection['content']; assert 'short test summary' in projection['content']


def test_tool_output_preserves_assertion_error(tmp_path: Path) -> None:
    _write_profile(tmp_path); raw='normal\n'*100+'Traceback (most recent call last):\n  File "tests/a.py", line 9\nAssertionError: expected 2 got 3\n'; _,projection=project_context({},tmp_path,'tool_output',raw,locator='pytest'); assert 'AssertionError: expected 2 got 3' in projection['content']; assert 'Traceback' in projection['content']


def test_tool_output_preserves_failed_test_name(tmp_path: Path) -> None:
    _write_profile(tmp_path); raw='x\n'*100+'FAILED tests/unit/test_auth.py::test_reset_credential - AssertionError\n'; _,projection=project_context({},tmp_path,'tool_output',raw,locator='pytest'); assert 'tests/unit/test_auth.py::test_reset_credential' in projection['content']


def test_tool_output_summary_can_expand_to_raw_without_force(tmp_path: Path) -> None:
    _write_profile(tmp_path); raw='ordinary\n'*100+'ERROR: important\n'; ctx,summary=project_context({},tmp_path,'tool_output',raw,locator='pytest'); assert summary['status']=='DIAGNOSTIC_SUMMARY'
    ctx,expanded=project_context(ctx,tmp_path,'tool_output',raw,locator='pytest',expand=True); assert expanded['status']=='LOADED'; assert expanded['content']==raw


def test_force_only_reloads_already_full_context(tmp_path: Path) -> None:
    _write_profile(tmp_path); raw='ordinary\n'*100+'ERROR: important\n'; ctx,_=project_context({},tmp_path,'tool_output',raw,locator='pytest'); ctx,expanded=project_context(ctx,tmp_path,'tool_output',raw,locator='pytest',expand=True); assert expanded['content']==raw
    ctx,reused=project_context(ctx,tmp_path,'tool_output',raw,locator='pytest',expand=True); assert reused['status']=='REUSED_CONTEXT'
    _,forced=project_context(ctx,tmp_path,'tool_output',raw,locator='pytest',expand=True,force=True); assert forced['status']=='LOADED'; assert forced['content']==raw


def test_context_not_sufficient_before_required_authority_records_are_loaded(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=12); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'重置用户凭据 reset_user_credential','domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]})
    assert ctx['context_efficiency']['semantic_relationship_closure_complete'] is True
    assert ctx['required_authority_refs']
    assert ctx['loaded_authority_refs']==[]
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_context_expansion_required_when_required_authority_refs_only(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=12); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'reset_user_credential','domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]})
    assert 'REQUIRED_AUTHORITY_FACTS_NOT_LOADED' in ctx['context_efficiency']['expansion_reason']
    assert ctx['context_efficiency']['next_action']=='EXPAND_REQUIRED_AUTHORITY'
    assert ctx['missing_required_authority_refs']==ctx['required_authority_refs']


def test_context_sufficient_after_required_authority_records_are_loaded(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=12); build_authority_index(tmp_path)
    task_id='TASK-LOAD-REQUIRED'; first=enrich_task_context(tmp_path,{'task_id':task_id,'request':'reset_user_credential','domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]}); save_context(tmp_path,task_id,first)
    _expand_required_authority_refs_via_cli(tmp_path,task_id,first['required_authority_refs'])
    second=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert not second['missing_required_authority_refs']; assert len(second['loaded_authority_refs'])==len(second['required_authority_refs'])
    assert second['context_efficiency']['status']==CONTEXT_SUFFICIENT; assert second['context_efficiency']['next_action']=='IMPLEMENT_OR_CONTINUE'


def test_locator_ready_does_not_equal_facts_loaded(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'LC-001 生命周期','domains':['LIFECYCLE'],'authorities':['docs/authority/model.yaml'],'affected_files':[]})
    assert ctx['context_efficiency']['locator_ready'] is True
    assert ctx['context_efficiency']['facts_loaded'] is False
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_relationship_closure_complete_does_not_equal_context_sufficient(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=12); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'reset_user_credential','domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]})
    closure=ctx['authority_slice']['query_diagnostics']['relationship_closure']
    assert closure['complete'] is True; assert closure['complete_semantics']=='RELATIONSHIP_PATH_RESOLVED'
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_required_authority_refs_are_tracked(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=12); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'reset_user_credential','domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]})
    keys={(r['path'],r['selector']) for r in ctx['required_authority_refs']}
    assert any(path==routed[2] for path,_ in keys); assert any(path==routed[3] for path,_ in keys); assert any(path==routed[4] for path,_ in keys)
    assert all(r.get('sha256') not in {None,''} for r in ctx['required_authority_refs'])


def test_loaded_authority_refs_are_tracked(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path)
    task_id='TASK-LOADED-TRACK'; first=enrich_task_context(tmp_path,{'task_id':task_id,'request':'LC-001 生命周期','domains':['LIFECYCLE'],'authorities':['docs/authority/model.yaml'],'affected_files':[]}); save_context(tmp_path,task_id,first)
    assert first['required_authority_refs']
    _expand_required_authority_refs_via_cli(tmp_path,task_id,first['required_authority_refs'])
    second=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert second['loaded_authority_refs']; assert not second['missing_required_authority_refs']


def test_required_authority_missing_returns_expansion_required(tmp_path: Path) -> None:
    _write_profile(tmp_path); _write_authority(tmp_path); build_authority_index(tmp_path)
    task_id='TASK-PARTIAL-LOAD'; ctx=enrich_task_context(tmp_path,{'task_id':task_id,'request':'用户生命周期规则','domains':['LIFECYCLE','PRODUCT_MODEL'],'authorities':['docs/authority/model.yaml'],'affected_files':[]}); save_context(tmp_path,task_id,ctx)
    assert ctx['required_authority_refs']
    # A locator preview alone is not a read; missing required facts remain explicit.
    refreshed=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert refreshed['missing_required_authority_refs']; assert refreshed['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_one_to_many_relationship_uses_representative_when_task_does_not_require_full_cardinality(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); role=tmp_path/routed[4]; role.write_text('mapping_id,role_id,permission_id,permission_code\nRPM-1,ROLE-A,P-1,USER_CREATE\nRPM-2,ROLE-B,P-1,USER_CREATE\nRPM-3,ROLE-C,P-1,USER_CREATE\n',encoding='utf-8')
    _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=20); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='重置用户凭据并校验权限 reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed,max_records=20)
    closure=result['diagnostics']['relationship_closure']; role_refs=[r for r in closure['candidate_refs'] if r['path']==routed[4] and 'USER_CREATE' in (r.get('reference_ids') or [])]
    assert closure['cardinality_mode']=='REPRESENTATIVE_ALLOWED'; assert closure['complete_semantics']=='RELATIONSHIP_PATH_RESOLVED'; assert len(role_refs)==1


def test_one_to_many_relationship_expands_when_task_requires_all_role_mappings(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path); role=tmp_path/routed[4]; role.write_text('mapping_id,role_id,permission_id,permission_code\nRPM-1,ROLE-A,P-1,USER_CREATE\nRPM-2,ROLE-B,P-1,USER_CREATE\nRPM-3,ROLE-C,P-1,USER_CREATE\n',encoding='utf-8')
    _write_profile(tmp_path,authorities={'all':{'domains':['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],'paths':routed}},initial_records=20); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='检查所有角色对 USER_CREATE 的权限，确认哪些角色 ALLOWED，哪些角色 DENIED。 reset_user_credential',domains=['AUTHENTICATION','CREDENTIAL','RBAC','AUTHORIZATION','API_CONTRACT'],authority_paths=routed,max_records=20)
    closure=result['diagnostics']['relationship_closure']; role_refs=[r for r in closure['candidate_refs'] if r['path']==routed[4] and 'USER_CREATE' in (r.get('reference_ids') or [])]
    assert closure['cardinality_mode']=='FULL_REQUIRED'; assert len(role_refs)==3; assert closure['complete'] is True



def _write_generic_relationship_fixture(root: Path, *, empty_core: bool = False) -> list[str]:
    paths=['docs/authority/alpha.yaml','docs/authority/beta.yaml','docs/authority/gamma.yaml']
    _write_profile(root,authorities={
        'alpha':{'domains':['ALPHA'],'paths':[paths[0]]},
        'beta':{'domains':['BETA'],'paths':[paths[1]]},
        'gamma':{'domains':['GAMMA'],'paths':[paths[2]]},
    },initial_records=2)
    payloads=[
        {'records':[{'record_id':'NODE-A','name':'alpha coordination','related_ids':['NODE-B']}]},
        {'records':[{'record_id':'NODE-B','name':'beta dependency','status':'active'}]},
        {'metadata':{'note':'no concrete records'}} if empty_core else {'records':[{'record_id':'NODE-C','name':'gamma policy','status':'active'}]},
    ]
    for rel,payload in zip(paths,payloads):
        p=root/rel; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(yaml.safe_dump(payload,allow_unicode=True,sort_keys=False),encoding='utf-8')
    return paths


def test_broad_multi_authority_task_requires_fact_from_each_routed_core_authority(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{
        'request':'adjust alpha beta gamma coordination policy',
        'domains':['ALPHA','BETA','GAMMA'],'authorities':paths,'affected_files':[],
    })
    assert ctx['context_efficiency']['anchor_mode']=='NO_SPECIFIC_ANCHOR'
    assert ctx['required_fact_coverage']['routed_core_authority_count']==3
    assert ctx['required_fact_coverage']['covered_core_authority_count']==3
    assert {ref['path'] for ref in ctx['required_authority_refs']}==set(paths)
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_generic_relevance_candidate_is_not_promoted_to_strong_anchor(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='adjust alpha coordination and beta dependency',domains=['ALPHA','BETA'],authority_paths=paths[:2])
    closure=result['diagnostics']['relationship_closure']
    assert closure['anchor_mode']=='NO_SPECIFIC_ANCHOR'
    assert closure['anchor_ids']==[]
    assert closure['weak_candidate_ids']


def test_explicit_canonical_id_is_strong_anchor(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='update NODE-A dependency',domains=['ALPHA','BETA'],authority_paths=paths[:2])
    closure=result['diagnostics']['relationship_closure']
    assert closure['anchor_mode']=='STRONG_ANCHOR'
    assert 'NODE-A' in closure['anchor_ids']


def test_relationship_closure_is_domain_agnostic(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='update NODE-A dependency',domains=['ALPHA','BETA'],authority_paths=paths[:2])
    closure=result['diagnostics']['relationship_closure']
    assert 'NODE-A' in closure['anchor_ids']
    assert any(ref.get('canonical_record_id')=='NODE-B' for ref in closure['candidate_refs'])
    runtime=(PROJECT_ROOT/'tools/context/authority_index.py').read_text(encoding='utf-8')
    for forbidden in ('USER_CREATE','ROLE-SUPER-ADMIN','reset_user_credential','RBAC','AUTHENTICATION'):
        assert forbidden not in runtime


def test_required_facts_union_explicit_relationship_and_core_coverage(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{
        'request':'update NODE-A dependency while reviewing gamma policy',
        'domains':['ALPHA','BETA','GAMMA'],'authorities':paths,'affected_files':[],
    })
    by_path={ref['path'] for ref in ctx['required_authority_refs']}
    assert set(paths)<=by_path
    coverage=ctx['required_fact_coverage']
    assert coverage['explicit_required_count']>=1
    assert coverage['relationship_required_count']>=1
    assert coverage['core_minimum_required_count']==3
    assert coverage['complete'] is True


def test_context_not_sufficient_when_core_authority_has_no_required_fact(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path,empty_core=True); build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{
        'request':'adjust alpha beta gamma coordination policy',
        'domains':['ALPHA','BETA','GAMMA'],'authorities':paths,'affected_files':[],
    })
    assert paths[2] in ctx['required_fact_coverage']['missing_core_authorities']
    assert ctx['context_efficiency']['core_authority_coverage_complete'] is False
    assert 'ROUTED_CORE_AUTHORITY_FACT_MISSING' in ctx['context_efficiency']['expansion_reason']
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_context_sufficient_after_all_core_required_facts_loaded(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    task_id='TASK-GENERIC-BROAD'
    first=enrich_task_context(tmp_path,{
        'task_id':task_id,'request':'adjust alpha beta gamma coordination policy',
        'domains':['ALPHA','BETA','GAMMA'],'authorities':paths,'affected_files':[],
    })
    save_context(tmp_path,task_id,first)
    assert first['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED
    _expand_required_authority_refs_via_cli(tmp_path,task_id,first['required_authority_refs'])
    second=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert second['required_fact_coverage']['complete'] is True
    assert not second['missing_required_authority_refs']
    assert second['context_efficiency']['facts_loaded'] is True
    assert second['context_efficiency']['status']==CONTEXT_SUFFICIENT


def test_missing_index_does_not_report_facts_loaded(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path)
    ctx=enrich_task_context(tmp_path,{
        'request':'adjust alpha beta gamma coordination policy',
        'domains':['ALPHA','BETA','GAMMA'],'authorities':paths,'affected_files':[],
    })
    assert ctx['authority_index']['status']=='MISSING'
    assert ctx['context_efficiency']['facts_loaded'] is False
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_context_history_is_domain_agnostic(tmp_path: Path) -> None:
    _write_profile(tmp_path)
    ctx={'context_consumer_id':'consumer-a'}
    ctx,first=project_context(ctx,tmp_path,'source_code','def generic(): return 1',locator='src/generic.py',scope='generic')
    ctx,second=project_context(ctx,tmp_path,'source_code','def generic(): return 1',locator='src/generic.py',scope='generic')
    assert first['status']=='LOADED'
    assert second['status']=='REUSED_CONTEXT'
    assert history_summary(ctx)['context_consumer_status']=='CONSUMER_SCOPED'


def test_context_consumer_boundary_is_explicit(tmp_path: Path) -> None:
    _write_profile(tmp_path)
    assert history_summary({})['context_consumer_status']=='SINGLE_CONTINUOUS_CONTEXT_CONSUMER_ASSUMPTION'
    assert history_summary({'context_epoch':'2'})['context_consumer_status']=='CONSUMER_SCOPED'


def test_loaded_authority_is_scoped_to_context_consumer_or_epoch(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path); build_authority_index(tmp_path)
    task_id='TASK-CONSUMER-SCOPE'
    first=enrich_task_context(tmp_path,{
        'task_id':task_id,'context_consumer_id':'consumer-a','request':'update NODE-A dependency',
        'domains':['ALPHA','BETA'],'authorities':paths[:2],'affected_files':[],
    })
    save_context(tmp_path,task_id,first)
    _expand_required_authority_refs_via_cli(tmp_path,task_id,first['required_authority_refs'])
    same=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert same['context_efficiency']['status']==CONTEXT_SUFFICIENT
    changed=load_context(tmp_path,task_id); changed['context_consumer_id']='consumer-b'
    changed=enrich_task_context(tmp_path,changed)
    assert changed['loaded_authority_refs']==[]
    assert changed['missing_required_authority_refs']
    assert changed['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_real_non_permission_relationship_closure_uses_lifecycle_authority(tmp_path: Path) -> None:
    rel='docs/authority/核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml'
    _write_profile(tmp_path,authorities={'product_model':{'domains':['PRODUCT_MODEL','LIFECYCLE'],'paths':[rel]}},initial_records=8)
    # Use exact records from the real Authority, but keep the fixture small enough for the
    # contract suite. No synthetic business rule is introduced.
    source=yaml.safe_load((PROJECT_ROOT/rel).read_text(encoding='utf-8'))
    obj=next(item for item in source['objects'] if item.get('object_id')=='OBJ-001')
    lifecycle=next(item for item in source['lifecycles'] if item.get('lifecycle_id')=='LC-001')
    dst=tmp_path/rel; dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(yaml.safe_dump({'objects':[obj],'lifecycles':[lifecycle]},allow_unicode=True,sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    result=query_authority_result(tmp_path,request='检查 LC-001 生命周期及其关联对象',domains=['PRODUCT_MODEL','LIFECYCLE'],authority_paths=[rel],max_records=8)
    closure=result['diagnostics']['relationship_closure']
    assert closure['anchor_mode']=='STRONG_ANCHOR'
    assert 'LC-001' in closure['anchor_ids']
    assert any(ref.get('canonical_record_id')=='OBJ-001' for ref in closure['candidate_refs'])


def test_context_runtime_contains_no_project_business_value_special_cases() -> None:
    runtime='\n'.join(path.read_text(encoding='utf-8') for path in sorted((PROJECT_ROOT/'tools/context').glob('*.py')))
    forbidden=('USER_CREATE','ROLE-SUPER-ADMIN','reset_user_credential','RBAC','AUTHENTICATION','RUNNER_OFFLINE','TASK_INTERRUPTED')
    for value in forbidden:
        assert value not in runtime
