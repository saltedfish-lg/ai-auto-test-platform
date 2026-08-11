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
