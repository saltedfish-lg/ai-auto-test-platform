from __future__ import annotations
GOVERNANCE_TEST_GROUP = 'authority'

import importlib.util
import os
import shutil
from pathlib import Path

import yaml

from tools.authority_validation import validator_commands

ROOT = Path(__file__).resolve().parents[2]
CORE_REL = Path('核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml')
RUNNER_PATH = ROOT / 'docs/authority/validation/run_all_validation.py'


def _runner_module():
    spec = importlib.util.spec_from_file_location('authority_gate_semantics_runner', RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authority_fixture(tmp_path: Path) -> Path:
    target = tmp_path / 'docs' / 'authority'
    shutil.copytree(ROOT / 'docs' / 'authority', target)
    return target


def test_formal_authority_gate_invokes_canonical_aggregator() -> None:
    config = yaml.safe_load((ROOT / '.governance/gates.yaml').read_text(encoding='utf-8'))
    assert config['gates']['authority_validators']['command'] == [
        'python', 'docs/authority/validation/run_all_validation.py'
    ]


def test_canonical_registry_contains_complete_validator_set() -> None:
    assert list(validator_commands()) == [
        'verify_authority',
        'validate_all',
        'validate_governance',
        'validate_auth_contract',
        'validate_acceptance_evidence',
        'authority_projection_check',
        'current_facts_check',
        'authority_referential_integrity',
        'openapi_client_check',
    ]


def test_invalid_lifecycle_stage_fails_canonical_aggregator(tmp_path: Path) -> None:
    authority_root = _authority_fixture(tmp_path)
    core = authority_root / CORE_REL
    text = core.read_text(encoding='utf-8')
    old = '- lifecycle_id: LC-001\n  object_id: OBJ-001\n  lifecycle_name: 用户生命周期\n  profile: USER\n  initial_stage: CREATED\n'
    assert old in text
    core.write_text(text.replace(old, old.replace('initial_stage: CREATED', 'initial_stage: IMPOSSIBLE_STAGE'), 1), encoding='utf-8')
    report = _runner_module().execute_validators(
        root=tmp_path,
        commands={
            'validate_all': [str(ROOT / 'docs/authority/validation/validate_all.py'), '--root', str(authority_root)]
        },
        env=dict(os.environ),
        timeout_seconds=60,
    )
    assert report['status'] == 'FAIL', report
    step = report['steps'][0]
    assert step['status'] == 'FAIL', step
    assert 'IMPOSSIBLE_STAGE' in step['stdout_tail'] or 'CORE_IDENTITY_STATE_LIFECYCLE' in step['stdout_tail']


def test_dangling_authority_reference_fails_canonical_aggregator(tmp_path: Path) -> None:
    authority_root = _authority_fixture(tmp_path)
    core = authority_root / CORE_REL
    text = core.read_text(encoding='utf-8')
    old = '  lifecycle_id: LC-001\n  state_dimensions:\n'
    assert old in text
    core.write_text(text.replace(old, '  lifecycle_id: LC-NOT-FOUND\n  state_dimensions:\n', 1), encoding='utf-8')
    report = _runner_module().execute_validators(
        root=tmp_path,
        commands={
            'authority_referential_integrity': [str(ROOT / 'tools/authority_referential_integrity.py'), 'check', '--root', str(tmp_path)]
        },
        env=dict(os.environ),
        timeout_seconds=60,
    )
    assert report['status'] == 'FAIL', report
    step = report['steps'][0]
    assert step['status'] == 'FAIL', step
    assert 'LC-NOT-FOUND' in step['stdout_tail'] or 'dangling' in step['stdout_tail'].lower()
