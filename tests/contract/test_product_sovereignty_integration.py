from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SKILL=ROOT/'.agents/skills/ai-auto-test-platform-product-sovereignty'
CONTEXT=ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency'

def test_product_sovereignty_is_skill_not_manager_agent()->None:
    text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
    assert 'PRODUCT_AUTHORITY_GATE' in text
    assert 'recommendation != approval' in text
    assert not list((ROOT/'.codex/agents').glob('*product*manager*.toml'))

def test_product_sovereignty_uses_single_living_authority()->None:
    text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
    for token in ('SINGLE_LIVING_AUTHORITY','docs/authority/**','AUTHORITY_UPDATE_ONLY','不得创建 R4.3/R4.4/R5.x','不生成 Manifest/Release Snapshot'):
        assert token in text

def test_current_user_decision_does_not_repeat_pending()->None:
    text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
    assert 'CURRENT_USER_REQUEST' in text
    assert '禁止为了门禁形式再次要求确认' in text
    assert 'CONFIRMED / AUTHORITY_UPDATE_ONLY' in text

def test_confirmed_missing_fact_requires_authority_sync_before_implementation()->None:
    text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
    for token in ('PRODUCT_DECISION_REQUIRED + CONFIRMED','authority_update_required=true','禁止 Architecture/Implementation','代码不修改','PRODUCT_FACT_FOUND'):
        assert token in text

def test_product_skill_consumes_shared_pack_and_never_full_scans()->None:
    text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
    for token in ('MUST_CONSUME_TASK_CONTEXT_PACK','TASK_CONTEXT_PACK_REQUIRED','TARGETED_AUTHORITY_LOOKUP','不得执行 `impact_scan.py`'):
        assert token in text

def test_task_context_pack_has_product_authority_slice()->None:
    pack=(CONTEXT/'references/task-context-pack.md').read_text(encoding='utf-8')
    for token in ('product_authority:','authority_refs:','user_decision_status:','decision_source:','authority_update_required:','workflow_state:'):
        assert token in pack

def test_authority_digest_change_is_incremental_not_new_baseline()->None:
    pack=(CONTEXT/'references/task-context-pack.md').read_text(encoding='utf-8')
    assert 'Authority digest 变化' in pack
    assert 'DELTA_REFRESH + TARGETED_REVERSE_LOOKUP' in pack
    assert '不创建 R4.3/R4.4' in pack
