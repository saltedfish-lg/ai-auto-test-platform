from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from tools.context.authority_index import (
    authority_index_status,
    authority_preview,
    build_authority_index,
    clear_authority_index_runtime_caches,
    expand_authority_refs,
    query_authority_result,
    refs_by_id,
)
from tools.context.context_loading import (
    CONTEXT_EXPANSION_REQUIRED,
    CONTEXT_SUFFICIENT,
    CONTEXT_UNAVAILABLE,
    clear_context_efficiency_config_cache,
    context_decision,
    ensure_context_history,
    history_summary,
    load_context_efficiency_config,
    project_context,
)
from tools.context.context_projection import enrich_task_context
from tools.context.context_refresh import refresh_task_context
from tools.context.repo_intelligence import CodeContextHint, repo_intelligence_projection
from tools.governance.impact_scan import infer_domains
from tools.governance.task_context import cleanup_task, load_context, save_context
from tools.governance.task_governance import start

GOVERNANCE_TEST_GROUP = 'routing'
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_context_efficiency_runtime_state():
    clear_authority_index_runtime_caches()
    clear_context_efficiency_config_cache()
    yield
    clear_authority_index_runtime_caches()
    clear_context_efficiency_config_cache()



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
            'reference_fields': {
                'explicit':['reference_id','reference_ids','related_id','related_ids','depends_on','depends_on_ids','parent_id','parent_ids','child_id','child_ids','source_id','target_id','object_id','permission_code','permission_id','role_id'],
                'suffixes':['_ref','_refs','_reference','_references'],
            },
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
    assert refs_by_id(tmp_path,'reset_user_credential')[0]['canonical_record_id']=='reset_user_credential'; assert refs_by_id(tmp_path,'RPM-R3-0021')[0]['canonical_record_id']=='RPM-R3-0021'; user_create_refs=refs_by_id(tmp_path,'USER_CREATE'); assert len(user_create_refs)==2; assert {ref['path'] for ref in user_create_refs}=={op,role}


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
    routed=_prepare_e2e_root(tmp_path)
    _write_profile(tmp_path, authorities={
        'auth':{'domains':['AUTHENTICATION','CREDENTIAL','SESSION'],'paths':[routed[0]]},
        'api':{'domains':['API_CONTRACT','AUTHORIZATION'],'paths':[routed[1],routed[2]]},
        'permission':{'domains':['RBAC','AUTHORIZATION'],'paths':[routed[3],routed[4]]},
    }, initial_records=3, preview_chars=4000)
    build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'重置用户凭据后撤销 Refresh Session，并校验对应 RBAC 权限与 OpenAPI。','domains':['AUTHENTICATION','CREDENTIAL','SESSION','RBAC','AUTHORIZATION','API_CONTRACT'],'authorities':routed,'affected_files':[]})
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED
    assert 'REQUIRED_AUTHORITY_FACTS_NOT_LOADED' in ctx['context_efficiency']['expansion_reason']


def test_relationship_closure_same_canonical_id(tmp_path: Path) -> None:
    routed=_prepare_e2e_root(tmp_path)
    _write_profile(tmp_path, authorities={
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
    assert any(r.get('canonical_record_id')=='USER_CREATE' and r['path']==routed[4] for r in result['refs']) is False


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


def test_free_text_id_mention_does_not_create_relationship_edge(tmp_path: Path) -> None:
    rel='docs/authority/generic.yaml'
    _write_profile(tmp_path,authorities={'generic':{'domains':['GENERIC'],'paths':[rel]}})
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[
        {'record_id':'NODE-A','description':'Historical example mentions NODE-B but this is not a structured relation.'},
        {'record_id':'NODE-B','description':'Independent record'},
    ]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    node_a=refs_by_id(tmp_path,'NODE-A')[0]
    assert 'NODE-B' in node_a['references']
    assert 'NODE-B' not in node_a['reference_ids']
    result=query_authority_result(tmp_path,request='update NODE-A',domains=['GENERIC'],authority_paths=[rel])
    closure=result['diagnostics']['relationship_closure']
    assert not any(edge.get('to')=='NODE-B' for edge in closure['edges'])
    assert not any(ref.get('canonical_record_id')=='NODE-B' for ref in closure['candidate_refs'])


def test_production_config_contains_generic_canonical_identity_baseline() -> None:
    cfg=load_context_efficiency_config(PROJECT_ROOT)['authority_index']
    keys={str(value) for value in cfg.get('canonical_identity_keys') or []}
    assert {'record_id','canonical_id','structural_id','id'}<=keys


def test_generic_record_id_and_project_extension_are_canonical_identities(tmp_path: Path) -> None:
    rel='docs/authority/generic.yaml'
    _write_profile(tmp_path,authorities={'generic':{'domains':['GENERIC'],'paths':[rel]}})
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[{'record_id':'NODE_A'},{'rule_id':'RULE_A'}]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    assert refs_by_id(tmp_path,'NODE_A')[0]['canonical_record_id']=='NODE_A'
    assert refs_by_id(tmp_path,'RULE_A')[0]['canonical_record_id']=='RULE_A'


def test_identity_field_does_not_create_relationship_edge(tmp_path: Path) -> None:
    rel='docs/authority/generic.yaml'
    _write_profile(tmp_path,authorities={'generic':{'domains':['GENERIC'],'paths':[rel]}})
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[{'record_id':'NODE_A','domain_id':'NODE_B'},{'record_id':'NODE_B'}]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    node_a=refs_by_id(tmp_path,'NODE_A')[0]
    assert 'NODE_B' not in node_a['reference_ids']
    closure=query_authority_result(tmp_path,request='update NODE_A',domains=['GENERIC'],authority_paths=[rel])['diagnostics']['relationship_closure']
    assert not any(ref.get('canonical_record_id')=='NODE_B' for ref in closure['candidate_refs'])


def test_structured_reference_field_supports_generic_id_format(tmp_path: Path) -> None:
    rel='docs/authority/generic.yaml'
    _write_profile(tmp_path,authorities={'generic':{'domains':['GENERIC'],'paths':[rel]}})
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[
        {'record_id':'NODE_A','related_id':'NODE_B'},
        {'record_id':'NODE_B','status':'active'},
    ]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    node_a=refs_by_id(tmp_path,'NODE_A')[0]
    assert 'NODE_B' in node_a['reference_ids']
    result=query_authority_result(tmp_path,request='update NODE_A',domains=['GENERIC'],authority_paths=[rel])
    closure=result['diagnostics']['relationship_closure']
    assert closure['anchor_mode']=='STRONG_ANCHOR'
    assert 'NODE_A' in closure['anchor_ids']
    assert any(ref.get('canonical_record_id')=='NODE_B' for ref in closure['candidate_refs'])


def test_relationship_closure_uses_structured_reference_ids_only(tmp_path: Path) -> None:
    rel='docs/authority/generic.yaml'
    _write_profile(tmp_path,authorities={'generic':{'domains':['GENERIC'],'paths':[rel]}})
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[
        {'record_id':'NODE-A','description':'NODE-B is only prose'},
        {'record_id':'NODE-B'},
        {'record_id':'NODE-C','related_id':'NODE-B'},
    ]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    prose=refs_by_id(tmp_path,'NODE-A')[0]
    structured=refs_by_id(tmp_path,'NODE-C')[0]
    assert 'NODE-B' in prose['references'] and 'NODE-B' not in prose['reference_ids']
    assert 'NODE-B' in structured['reference_ids']
    closure_a=query_authority_result(tmp_path,request='update NODE-A',domains=['GENERIC'],authority_paths=[rel])['diagnostics']['relationship_closure']
    closure_c=query_authority_result(tmp_path,request='update NODE-C',domains=['GENERIC'],authority_paths=[rel])['diagnostics']['relationship_closure']
    assert not any(ref.get('canonical_record_id')=='NODE-B' for ref in closure_a['candidate_refs'])
    assert any(ref.get('canonical_record_id')=='NODE-B' for ref in closure_c['candidate_refs'])


def test_references_and_reference_ids_have_distinct_semantics(tmp_path: Path) -> None:
    rel='docs/authority/generic.yaml'
    _write_profile(tmp_path,authorities={'generic':{'domains':['GENERIC'],'paths':[rel]}})
    p=tmp_path/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[{'record_id':'ROOT_1','description':'mentions TEXT-ONLY','related_ids':['CHILD_1']},{'record_id':'CHILD_1'}]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    ref=refs_by_id(tmp_path,'ROOT_1')[0]
    assert 'TEXT-ONLY' in ref['references']
    assert 'TEXT-ONLY' not in ref['reference_ids']
    assert 'CHILD_1' in ref['reference_ids']


def test_context_efficiency_config_is_not_reloaded_per_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_profile(tmp_path)
    p=tmp_path/'docs/authority/model.yaml'; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(yaml.safe_dump({'records':[{'record_id':f'ITEM_{i}','related_id':f'DEP_{i}'} for i in range(1000)]},sort_keys=False),encoding='utf-8')
    import tools.context.context_loading as loading_module
    original=loading_module.yaml.safe_load
    calls={'config':0}
    def counting_safe_load(stream):
        if isinstance(stream,str) and 'context_efficiency:' in stream and 'authority_index:' in stream:
            calls['config']+=1
        return original(stream)
    monkeypatch.setattr(loading_module.yaml,'safe_load',counting_safe_load)
    clear_authority_index_runtime_caches()
    result=build_authority_index(tmp_path,force=True)
    assert result['record_count']==1000
    assert calls['config']<=2


def test_context_efficiency_config_cache_invalidates_safely(tmp_path: Path) -> None:
    _write_profile(tmp_path,preview_chars=4000)
    first=load_context_efficiency_config(tmp_path)['context_loading']['authority']['preview_chars']
    config=tmp_path/'.governance/context-efficiency.yaml'
    text=config.read_text(encoding='utf-8').replace('preview_chars: 4000','preview_chars: 4001')
    time.sleep(0.002)
    config.write_text(text,encoding='utf-8')
    second=load_context_efficiency_config(tmp_path)['context_loading']['authority']['preview_chars']
    assert first==4000
    assert second==4001


def test_context_test_state_does_not_leak_between_cases(tmp_path: Path) -> None:
    left=tmp_path/'left'; right=tmp_path/'right'
    _write_profile(left,preview_chars=1111); _write_profile(right,preview_chars=2222)
    assert load_context_efficiency_config(left)['context_loading']['authority']['preview_chars']==1111
    assert load_context_efficiency_config(right)['context_loading']['authority']['preview_chars']==2222
    clear_authority_index_runtime_caches()
    assert load_context_efficiency_config(left)['context_loading']['authority']['preview_chars']==1111


def test_full_context_efficiency_contract_suite_is_isolated(tmp_path: Path) -> None:
    _write_profile(tmp_path,preview_chars=3000)
    assert load_context_efficiency_config(tmp_path)['context_loading']['authority']['preview_chars']==3000
    clear_context_efficiency_config_cache()
    config=tmp_path/'.governance/context-efficiency.yaml'
    config.write_text(config.read_text(encoding='utf-8').replace('preview_chars: 3000','preview_chars: 3002'),encoding='utf-8')
    clear_authority_index_runtime_caches()
    assert load_context_efficiency_config(tmp_path)['context_loading']['authority']['preview_chars']==3002


def test_authority_index_marks_stale_when_context_config_changes(tmp_path: Path) -> None:
    _write_profile(tmp_path)
    _write_authority(tmp_path)
    build_authority_index(tmp_path)
    assert authority_index_status(tmp_path)['status']=='READY'
    config=tmp_path/'.governance/context-efficiency.yaml'
    payload=yaml.safe_load(config.read_text(encoding='utf-8'))
    payload.setdefault('authority_index',{})['reference_fields']={'explicit':['related_id'],'suffixes':['_ref']}
    time.sleep(0.002)
    config.write_text(yaml.safe_dump(payload,allow_unicode=True,sort_keys=False),encoding='utf-8')
    assert authority_index_status(tmp_path)['status']=='STALE'
    rebuilt=build_authority_index(tmp_path)
    assert rebuilt['status']=='READY'


def test_routed_authority_role_strategy_is_explicitly_conservative(tmp_path: Path) -> None:
    paths=_write_generic_relationship_fixture(tmp_path)
    build_authority_index(tmp_path)
    ctx=enrich_task_context(tmp_path,{'request':'adjust alpha beta gamma coordination policy','domains':['ALPHA','BETA','GAMMA'],'authorities':paths,'affected_files':[]})
    coverage=ctx['required_fact_coverage']
    assert coverage['authority_role_strategy']=='ALL_ROUTED_CONSERVATIVE'
    assert coverage['routed_supporting_authority_count']==0
    assert ctx['authority_slice']['authority_role_strategy']=='ALL_ROUTED_CONSERVATIVE'


def _write_context_coverage_fixture(root: Path, count: int = 8) -> tuple[list[str], list[dict]]:
    paths=[f'docs/authority/coverage-{index}.yaml' for index in range(count)]
    authorities={f'coverage_{index}':{'domains':['GOVERNANCE'],'paths':[path]} for index,path in enumerate(paths)}
    _write_profile(root,authorities=authorities,initial_records=3)
    refs=[]
    for index,path in enumerate(paths):
        target=root/path; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(yaml.safe_dump({'records':[{'record_id':f'COVERAGE-{index}','name':f'coverage requirement {index}','state':'current'}]},sort_keys=False),encoding='utf-8')
    build_authority_index(root)
    for index in range(count):
        refs.append(refs_by_id(root,f'COVERAGE-{index}')[0])
    return paths,refs


def _candidate_limit_projection(paths: list[str], refs: list[dict], precise_count: int = 3) -> dict:
    precise=[dict(ref) for ref in refs[:precise_count]]
    for ref in precise:
        ref['relevance_score']=100; ref['relevance_reasons']=['CORE_AUTHORITY_MINIMUM']
    fallback=[{
        'record_id':None,'canonical_record_id':None,'canonical_id_key':None,'structural_id':None,
        'identity_kind':'ROUTED_FILE_REF','fallback_locator':path,'section':None,'selector':None,
        'path':path,'display_path':path,'title':'','domains':[],'references':[],'reference_ids':[],
        'authority_group':f'coverage_{index}','authority_domains':['GOVERNANCE'],'ref_only':True,
        'relevance_score':0,'relevance_reasons':['ROUTED_AUTHORITY_FILE_MINIMUM_RECALL'],
    } for index,path in enumerate(paths[precise_count:],start=precise_count)]
    return {
        'status':'TRUNCATED','refs':precise+fallback,'diagnostics':{
            'unrepresented_authority_files':[],'unrepresented_authority_groups':[],'direct_read_required':[],
            'relationship_closure':{'anchor_ids':[],'anchor_mode':'NO_SPECIFIC_ANCHOR','weak_candidate_ids':[],
                'complete':True,'complete_semantics':'RELATIONSHIP_PATH_RESOLVED','candidate_refs':[],'missing_relationships':[],'edges':[]},
            'candidate_count':20000,'selected_count':len(paths),'max_records':3,
        },
    }


def _loaded_coverage_context(root: Path, task_id: str = 'TASK-CONTEXT-COVERAGE') -> tuple[dict,list[str],list[dict]]:
    paths,refs=_write_context_coverage_fixture(root)
    ctx={'task_id':task_id,'task_status':'ACTIVE','request':'validate governance context coverage','domains':['GOVERNANCE'],'authorities':paths,'affected_files':[]}
    save_context(root,task_id,ctx)
    _expand_required_authority_refs_via_cli(root,task_id,refs)
    return load_context(root,task_id),paths,refs


def test_task_loaded_precise_evidence_closes_candidate_limit_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs))
    refreshed=enrich_task_context(tmp_path,ctx)
    coverage=refreshed['required_fact_coverage']
    assert coverage['current_required_authority_count']==8
    assert coverage['current_covered_authority_count']==8
    assert refreshed['context_efficiency']['status']==CONTEXT_SUFFICIENT
    assert len([item for item in coverage['coverage_evidence'] if item['evidence_source']=='TASK_LOADED_PRECISE_EVIDENCE'])==5


def test_repeated_refresh_keeps_coverage_stable_without_duplicate_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs))
    first=enrich_task_context(tmp_path,ctx); first_reads=len(first['context_history']['authority'])
    second=enrich_task_context(tmp_path,first)
    assert second['context_efficiency']['status']==CONTEXT_SUFFICIENT
    assert len(second['context_history']['authority'])==first_reads==8
    assert second['coverage_evidence']==first['coverage_evidence']


def test_routed_file_refs_without_precise_task_evidence_remain_uncovered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths,refs=_write_context_coverage_fixture(tmp_path)
    projection=_candidate_limit_projection(paths,refs,precise_count=0)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:projection)
    ctx=enrich_task_context(tmp_path,{'task_id':'TASK-FILE-REF-ONLY','task_status':'ACTIVE','request':'coverage','domains':['GOVERNANCE'],'authorities':paths,'affected_files':[]})
    assert ctx['required_fact_coverage']['current_covered_authority_count']==0
    assert len(ctx['uncovered_authority_requirements'])==8
    assert ctx['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_selector_evidence_does_not_cover_different_projected_selector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path='docs/authority/selectors.yaml'; _write_profile(tmp_path,authorities={'selectors':{'domains':['GOVERNANCE'],'paths':[path]}})
    target=tmp_path/path; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(yaml.safe_dump({'records':[{'record_id':'SELECTOR-A'},{'record_id':'SELECTOR-B'}]},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path); ref_a=refs_by_id(tmp_path,'SELECTOR-A')[0]; ref_b=refs_by_id(tmp_path,'SELECTOR-B')[0]
    task_id='TASK-SELECTOR-PRECISION'; save_context(tmp_path,task_id,{'task_id':task_id,'task_status':'ACTIVE','request':'selector B','domains':['GOVERNANCE'],'authorities':[path],'affected_files':[]})
    _expand_required_authority_refs_via_cli(tmp_path,task_id,[ref_a])
    projected=dict(ref_b); projected['relevance_reasons']=['CORE_AUTHORITY_MINIMUM']; projected['relevance_score']=100
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:{'status':'READY','refs':[projected],'diagnostics':{'relationship_closure':{'anchor_ids':[],'complete':True,'candidate_refs':[],'missing_relationships':[]}}})
    refreshed=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert refreshed['required_authority_refs'][0]['selector']==ref_b['selector']
    assert refreshed['missing_required_authority_refs']
    assert refreshed['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED


def test_authority_record_change_invalidates_only_matching_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs))
    assert enrich_task_context(tmp_path,ctx)['context_efficiency']['status']==CONTEXT_SUFFICIENT
    target=tmp_path/paths[-1]; payload=yaml.safe_load(target.read_text(encoding='utf-8')); payload['records'][0]['state']='changed'
    target.write_text(yaml.safe_dump(payload,sort_keys=False),encoding='utf-8'); build_authority_index(tmp_path,force=True)
    refreshed=enrich_task_context(tmp_path,ctx)
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==7
    assert any(item['path']==paths[-1] and item['reason']=='AUTHORITY_RECORD_CHANGED' for item in refreshed['stale_authority_evidence'])
    assert refreshed['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED
    current=refs_by_id(tmp_path,'COVERAGE-7')[0]
    _expand_required_authority_refs_via_cli(tmp_path,'TASK-CONTEXT-COVERAGE',[current])
    restored=enrich_task_context(tmp_path,load_context(tmp_path,'TASK-CONTEXT-COVERAGE'))
    assert restored['required_fact_coverage']['current_covered_authority_count']==8
    assert restored['context_efficiency']['status']==CONTEXT_SUFFICIENT


def test_task_evidence_cannot_cross_task_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path,task_id='TASK-A')
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs,precise_count=0))
    copied={**ctx,'task_id':'TASK-B'}
    refreshed=enrich_task_context(tmp_path,copied)
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==0
    assert any(item['reason']=='TASK_OWNERSHIP_NOT_VERIFIED' for item in refreshed['stale_authority_evidence'])


def test_terminal_task_history_does_not_supply_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs,precise_count=0))
    refreshed=enrich_task_context(tmp_path,{**ctx,'task_status':'ABORTED'})
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==0
    assert all(item['reason']=='TASK_NOT_ACTIVE' for item in refreshed['stale_authority_evidence'])


def test_incremental_authority_requirement_needs_its_own_precise_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths,refs=_write_context_coverage_fixture(tmp_path,count=2); task_id='TASK-INCREMENTAL-COVERAGE'
    ctx={'task_id':task_id,'task_status':'ACTIVE','request':'coverage','domains':['GOVERNANCE'],'authorities':[paths[0]],'affected_files':[]}
    save_context(tmp_path,task_id,ctx); _expand_required_authority_refs_via_cli(tmp_path,task_id,[refs[0]])
    projection=_candidate_limit_projection(paths,refs,precise_count=0)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:projection)
    expanded={**load_context(tmp_path,task_id),'authorities':paths}
    refreshed=enrich_task_context(tmp_path,expanded)
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==1
    assert refreshed['uncovered_authority_requirements']==[{'path':paths[1],'reason':'PRECISE_AUTHORITY_EVIDENCE_REQUIRED'}]


def test_index_rebuild_preserves_unchanged_canonical_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs))
    before=enrich_task_context(tmp_path,ctx); build_authority_index(tmp_path,force=True)
    after=enrich_task_context(tmp_path,before)
    assert before['context_efficiency']['status']==after['context_efficiency']['status']==CONTEXT_SUFFICIENT
    assert after['required_fact_coverage']['current_covered_authority_count']==8


def test_unstructured_legacy_history_is_not_promoted_to_precise_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths,refs=_write_context_coverage_fixture(tmp_path,count=1)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs,precise_count=0))
    ctx={'task_id':'TASK-LEGACY-EVIDENCE','task_status':'ACTIVE','request':'coverage','domains':['GOVERNANCE'],'authorities':paths,'affected_files':[],
         'context_history':{'authority':[{'consumer_id':'SINGLE_CONTINUOUS_CONTEXT_CONSUMER','locator':paths[0],'scope':refs[0]['selector'],'sha256':'legacy-file-hash','expanded':True}]}}
    refreshed=enrich_task_context(tmp_path,ctx)
    assert refreshed['context_efficiency']['status']==CONTEXT_EXPANSION_REQUIRED
    assert refreshed['stale_authority_evidence'][0]['reason']=='TASK_OWNERSHIP_NOT_VERIFIED'


def test_normal_expand_upgrades_legacy_history_after_successful_full_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths,refs=_write_context_coverage_fixture(tmp_path,count=1); task_id='TASK-LEGACY-RECOVERY'
    file_hash=__import__('hashlib').sha256((tmp_path/paths[0]).read_bytes()).hexdigest()
    ctx={'task_id':task_id,'task_status':'ACTIVE','request':'coverage','domains':['GOVERNANCE'],'authorities':paths,'affected_files':[],
         'context_history':{'authority':[{'consumer_id':'SINGLE_CONTINUOUS_CONTEXT_CONSUMER','locator':paths[0],'scope':refs[0]['selector'],'sha256':file_hash,'expanded':True}]}}
    save_context(tmp_path,task_id,ctx)
    _expand_required_authority_refs_via_cli(tmp_path,task_id,refs)
    upgraded=load_context(tmp_path,task_id)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs,precise_count=0))
    refreshed=enrich_task_context(tmp_path,upgraded)
    evidence=upgraded['context_history']['authority'][0]['authority_evidence']
    assert evidence['status']=='FULL_RECORD_LOADED'
    assert evidence['task_id']==task_id
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==1
    assert refreshed['context_efficiency']['status']==CONTEXT_SUFFICIENT


def test_precise_locator_evidence_closes_candidate_limit_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path='docs/authority/locator-only.yaml'; task_id='TASK-LOCATOR-COVERAGE'
    _write_profile(tmp_path,authorities={'locator':{'domains':['GOVERNANCE'],'paths':[path]}},initial_records=1)
    target=tmp_path/path; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(yaml.safe_dump({'runtime_policy':{'max_steps':50,'timeout':'30m'}},sort_keys=False),encoding='utf-8')
    build_authority_index(tmp_path)
    ref=refs_by_id(tmp_path,f'{path}#/runtime_policy',authority_paths=[path],selector='/runtime_policy')[0]
    assert ref['identity_kind']=='LOCATOR'
    save_context(tmp_path,task_id,{'task_id':task_id,'task_status':'ACTIVE','request':'runtime policy','domains':['GOVERNANCE'],'authorities':[path],'affected_files':[]})
    _expand_required_authority_refs_via_cli(tmp_path,task_id,[ref])
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection([path],[ref],precise_count=0))
    refreshed=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==1
    assert refreshed['context_efficiency']['status']==CONTEXT_SUFFICIENT


def test_record_fingerprint_supports_mixed_yaml_mapping_keys(tmp_path: Path) -> None:
    path='docs/authority/mixed-keys.yaml'
    _write_profile(tmp_path,authorities={'mixed':{'domains':['GOVERNANCE'],'paths':[path]}})
    target=tmp_path/path; target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('records:\n  - record_id: MIXED-KEYS\n    values:\n      text: alpha\n      1: numeric\n',encoding='utf-8')
    result=build_authority_index(tmp_path)
    refs=refs_by_id(tmp_path,'MIXED-KEYS')
    assert result['status']=='READY'
    assert len(refs)==1
    assert len(refs[0]['record_sha256'])==64


def test_record_fingerprint_distinguishes_typed_mapping_from_lookalike_payload(tmp_path: Path) -> None:
    path='docs/authority/fingerprint-collision.yaml'
    mixed_root=tmp_path/'mixed'; lookalike_root=tmp_path/'lookalike'
    for root in (mixed_root,lookalike_root):
        _write_profile(root,authorities={'fingerprints':{'domains':['GOVERNANCE'],'paths':[path]}})
    mixed_target=mixed_root/path; mixed_target.parent.mkdir(parents=True,exist_ok=True)
    mixed_target.write_text("records:\n  - record_id: SAME\n    value: {1: x, a: y}\n",encoding='utf-8')
    lookalike_target=lookalike_root/path; lookalike_target.parent.mkdir(parents=True,exist_ok=True)
    lookalike_target.write_text("records:\n  - record_id: SAME\n    value:\n      __typed_mapping__:\n        - [[int, 1], x]\n        - [[str, a], y]\n",encoding='utf-8')
    build_authority_index(mixed_root); build_authority_index(lookalike_root)
    mixed=refs_by_id(mixed_root,'SAME')[0]
    lookalike=refs_by_id(lookalike_root,'SAME')[0]
    assert mixed['record_sha256']!=lookalike['record_sha256']


def test_record_fingerprint_distinguishes_yaml_date_from_string(tmp_path: Path) -> None:
    path='docs/authority/fingerprint-types.yaml'
    date_root=tmp_path/'date'; string_root=tmp_path/'string'
    for root in (date_root,string_root):
        _write_profile(root,authorities={'fingerprints':{'domains':['GOVERNANCE'],'paths':[path]}})
    date_target=date_root/path; date_target.parent.mkdir(parents=True,exist_ok=True)
    date_target.write_text("records:\n  - record_id: SAME\n    value: 2026-01-01\n",encoding='utf-8')
    string_target=string_root/path; string_target.parent.mkdir(parents=True,exist_ok=True)
    string_target.write_text("records:\n  - record_id: SAME\n    value: '2026-01-01'\n",encoding='utf-8')
    build_authority_index(date_root); build_authority_index(string_root)
    date_ref=refs_by_id(date_root,'SAME')[0]
    string_ref=refs_by_id(string_root,'SAME')[0]
    assert date_ref['record_sha256']!=string_ref['record_sha256']


def test_unrelated_record_change_preserves_precise_record_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths,refs=_write_context_coverage_fixture(tmp_path,count=1); task_id='TASK-RECORD-FRESHNESS'
    ctx={'task_id':task_id,'task_status':'ACTIVE','request':'coverage','domains':['GOVERNANCE'],'authorities':paths,'affected_files':[]}
    save_context(tmp_path,task_id,ctx); _expand_required_authority_refs_via_cli(tmp_path,task_id,refs)
    target=tmp_path/paths[0]; payload=yaml.safe_load(target.read_text(encoding='utf-8')); payload['records'].append({'record_id':'UNRELATED','state':'new'})
    target.write_text(yaml.safe_dump(payload,sort_keys=False),encoding='utf-8'); build_authority_index(tmp_path,force=True)
    current_ref=refs_by_id(tmp_path,'COVERAGE-0')[0]
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,[current_ref],precise_count=0))
    refreshed=enrich_task_context(tmp_path,load_context(tmp_path,task_id))
    assert refreshed['context_efficiency']['status']==CONTEXT_SUFFICIENT
    assert refreshed['stale_authority_evidence']==[]


def test_context_refresh_persists_coverage_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx,paths,refs=_loaded_coverage_context(tmp_path)
    monkeypatch.setattr('tools.context.context_projection.query_authority_result',lambda *args,**kwargs:_candidate_limit_projection(paths,refs))
    save_context(tmp_path,'TASK-CONTEXT-COVERAGE',ctx)
    refreshed=refresh_task_context(tmp_path,'TASK-CONTEXT-COVERAGE')
    persisted=load_context(tmp_path,'TASK-CONTEXT-COVERAGE')
    assert refreshed['required_fact_coverage']['current_covered_authority_count']==8
    assert persisted['coverage_evidence']==refreshed['coverage_evidence']
    assert len(persisted['fallback_authority_file_refs'])==5
