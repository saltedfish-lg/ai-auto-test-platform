
GOVERNANCE_TEST_GROUP = 'authority'

from pathlib import Path
import json,re,subprocess,sys,yaml
ROOT=Path(__file__).resolve().parents[2]
CORE=(
 '产品总体需求与系统边界/产品总体需求与系统边界.yaml','用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml','核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml','权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml','AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml','数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml','系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml')
def test_single_living_authority_has_no_versioned_baseline_tree_or_manifest():
 assert (ROOT/'docs/authority').is_dir() and not (ROOT/'docs/baseline').exists(); assert not list((ROOT/'docs/authority').rglob('MANIFEST.sha256'))
def test_verify_authority_passes():
 c=subprocess.run([sys.executable,'tools/verify_authority.py'],cwd=ROOT,text=True,capture_output=True); assert c.returncode==0,c.stdout+c.stderr; assert json.loads(c.stdout)['status']=='PASS'
def test_core_documents_are_living_authority():
 for rel in CORE:
  head='\n'.join((ROOT/'docs/authority'/rel).read_text(encoding='utf-8').splitlines()[:40])
  assert re.search(r'(?m)^\s*authority_model:\s*SINGLE_LIVING_AUTHORITY\s*$', head), rel
def test_runtime_gate_catalog_has_no_current_results():
 d=yaml.safe_load((ROOT/'docs/authority/编码权威事实/SYSTEM_DESIGN.yaml').read_text(encoding='utf-8')); assert 'runtime_gate_contract' not in d; cat=d['runtime_gate_catalog']; assert cat['gates']; assert all(not any(k in g for k in ('status','last_execution_evidence','evidence_ref')) for g in cat['gates'])
