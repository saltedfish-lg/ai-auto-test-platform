import re
import tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_root_agents_disables_all_codex_git_access()->None:
    text=(ROOT/'AGENTS.md').read_text(encoding='utf-8')
    for token in ('MUST_NOT_INVOKE_GIT','codex_git_access: `DISABLED`','Git 完全由用户负责','IDEA'):
        assert token in text
    for command in ('git status','git diff','git log','git add','git commit','git push'):
        assert command in text

def test_all_custom_agents_inherit_git_disabled_policy()->None:
    paths=sorted((ROOT/'.codex/agents').glob('*.toml')); assert len(paths)==10
    for p in paths:
        ins=tomllib.loads(p.read_text(encoding='utf-8'))['developer_instructions']
        assert 'CODEX_GIT_ACCESS=DISABLED' in ins, p.name
        assert '不得执行任何 Git 命令' in ins, p.name

def test_ci_uses_locked_bootstrap_and_verify_entrypoints()->None:
    workflow=ROOT/'.github/workflows/ci.yml'
    assert workflow.is_file()
    text=workflow.read_text(encoding='utf-8')
    assert re.search(r"python-version:\s*['\"]?3\.12['\"]?", text)
    assert re.search(r"node-version:\s*['\"]?22['\"]?", text)
    assert 'python tools/dev.py bootstrap' in text
    assert 'python tools/dev.py verify' in text


def test_all_authority_entrypoints_share_one_canonical_validator_definition()->None:
    canonical=(ROOT/'tools/authority_validation.py').read_text(encoding='utf-8')
    for token in ('verify_authority','validate_all','validate_governance','validate_auth_contract','authority_projection_check','current_facts_check','authority_referential_integrity','openapi_client_check'):
        assert token in canonical
    dev=(ROOT/'tools/dev.py').read_text(encoding='utf-8')
    guard=(ROOT/'.agents/skills/ai-auto-test-platform-feature-orchestrator/scripts/authority_write_guard.py').read_text(encoding='utf-8')
    aggregate=(ROOT/'docs/authority/validation/run_all_validation.py').read_text(encoding='utf-8')
    assert 'validator_commands' in dev
    assert 'authority_validation.py' in guard and '_validator_commands(root)' in guard
    assert 'authority_validation.py' in aggregate and '_validator_commands()' in aggregate
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    assert 'python tools/openapi_client.py check' in readme
