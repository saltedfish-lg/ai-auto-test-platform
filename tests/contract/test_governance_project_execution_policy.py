
GOVERNANCE_TEST_GROUP = 'validator'

import re,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_root_agents_user_owned_git_and_write_forbidden():
 text=(ROOT/'AGENTS.md').read_text(encoding='utf-8'); assert 'USER_OWNS_GIT' in text
 for cmd in ('git status','git diff','git rev-parse','git branch --show-current','git log','git show'): assert cmd in text
 for cmd in ('git add','git commit','git push','git reset','git checkout','git switch','git merge','git rebase','git stash','git tag','git cherry-pick','git clean'): assert cmd in text
 assert '可选只读工程辅助' in text and '无 Git 环境必须完整可运行' in text

def test_custom_agents_do_not_enable_git_writes():
 for p in (ROOT/'.codex/agents').glob('*.toml'):
  ins=tomllib.loads(p.read_text(encoding='utf-8'))['developer_instructions'].lower(); assert 'git 写' in ins or 'git write' in ins or 'git' in ins

def test_ci_uses_locked_bootstrap_and_verify_entrypoints():
 text=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8'); assert re.search(r"python-version:\s*['\"]?3\.12",text); assert 'python tools/dev.py bootstrap' in text; assert 'python tools/dev.py verify' in text

def test_canonical_validator_set_is_shared():
 canonical=(ROOT/'tools/authority_validation.py').read_text(encoding='utf-8')
 for token in ('verify_authority','validate_all','validate_governance','validate_auth_contract','validate_acceptance_evidence','authority_projection_check','current_facts_check','authority_referential_integrity','openapi_client_check'): assert token in canonical
 assert 'validate_current_governance_evidence' not in canonical
