from __future__ import annotations
GOVERNANCE_TEST_GROUP='authority'
import importlib.util,os,sys
from pathlib import Path
import pytest
from tools.authority_validation import DEFAULT_VALIDATOR_TIMEOUT_SECONDS,MAX_VALIDATOR_TIMEOUT_SECONDS,MIN_VALIDATOR_TIMEOUT_SECONDS,validator_timeout_seconds
ROOT=Path(__file__).resolve().parents[2]; RUNNER_PATH=ROOT/'docs/authority/validation/run_all_validation.py'
def _module():
    spec=importlib.util.spec_from_file_location('authority_validation_aggregator_test',RUNNER_PATH); assert spec and spec.loader; module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def test_validator_timeout_defaults_and_bounds():
    assert validator_timeout_seconds({})==DEFAULT_VALIDATOR_TIMEOUT_SECONDS; assert validator_timeout_seconds({'ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS':str(MIN_VALIDATOR_TIMEOUT_SECONDS)})==MIN_VALIDATOR_TIMEOUT_SECONDS; assert validator_timeout_seconds({'ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS':str(MAX_VALIDATOR_TIMEOUT_SECONDS)})==MAX_VALIDATOR_TIMEOUT_SECONDS
    for raw in ('bad',str(MIN_VALIDATOR_TIMEOUT_SECONDS-1),str(MAX_VALIDATOR_TIMEOUT_SECONDS+1)):
        with pytest.raises(ValueError): validator_timeout_seconds({'ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS':raw})
def test_aggregator_consumes_configured_validator_timeout(tmp_path):
    script=tmp_path/'pass_validator.py'; script.write_text('raise SystemExit(0)\n',encoding='utf-8'); env=dict(os.environ); env['ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS']=str(MIN_VALIDATOR_TIMEOUT_SECONDS); report=_module().execute_validators(root=tmp_path,commands={'pass_validator':[str(script)]},env=env); assert report['status']=='PASS'; assert report['timeout_seconds']==MIN_VALIDATOR_TIMEOUT_SECONDS; assert report['steps'][0]['timeout_seconds']==MIN_VALIDATOR_TIMEOUT_SECONDS
def test_validator_timeout_propagates_as_overall_failure(tmp_path):
    script=tmp_path/'slow_validator.py'; script.write_text('import time\ntime.sleep(1)\n',encoding='utf-8'); report=_module().execute_validators(root=tmp_path,commands={'slow_validator':[str(script)]},env=dict(os.environ),timeout_seconds=0.05); assert report['status']=='FAIL'; assert report['summary']['timeouts']==1; assert report['steps'][0]['status']=='TIMEOUT'
def test_validator_failure_propagates_as_overall_failure(tmp_path):
    script=tmp_path/'failed_validator.py'; script.write_text('raise SystemExit(7)\n',encoding='utf-8'); report=_module().execute_validators(root=tmp_path,commands={'failed_validator':[str(script)]},env=dict(os.environ),timeout_seconds=1); assert report['status']=='FAIL'; assert report['summary']['failed']==1; assert report['steps'][0]['status']=='FAIL'
def test_dev_authority_delegates_to_canonical_aggregator(monkeypatch):
    from tools import dev
    calls=[]; monkeypatch.setattr(dev,'run',lambda command,**_kwargs:calls.append(tuple(str(x) for x in command))); dev.authority(); assert len(calls)==1; assert calls[0][0]==sys.executable; assert calls[0][1].endswith('docs/authority/validation/run_all_validation.py')


def test_validator_execution_error_propagates_as_overall_failure(tmp_path, monkeypatch):
    module = _module()
    def boom(*_args, **_kwargs):
        raise OSError('validator launch failed')
    monkeypatch.setattr(module.subprocess, 'run', boom)
    report = module.execute_validators(
        root=tmp_path,
        commands={'broken_validator': ['does-not-matter.py']},
        env=dict(os.environ),
        timeout_seconds=1,
    )
    assert report['status'] == 'FAIL'
    assert report['summary']['errors'] == 1
    assert report['steps'][0]['status'] == 'ERROR'


def test_aggregator_redacts_database_secret_from_validator_output(tmp_path):
    script = tmp_path / 'secret_validator.py'
    script.write_text("print('mysql+pymysql://demo:super-secret@127.0.0.1:3306/demo')\n", encoding='utf-8')
    report = _module().execute_validators(
        root=tmp_path,
        commands={'secret_validator': [str(script)]},
        env=dict(os.environ),
        timeout_seconds=5,
    )
    assert report['status'] == 'PASS'
    stdout_tail = report['steps'][0]['stdout_tail']
    assert 'super-secret' not in stdout_tail
    assert '***' in stdout_tail or 'REDACTED' in stdout_tail
