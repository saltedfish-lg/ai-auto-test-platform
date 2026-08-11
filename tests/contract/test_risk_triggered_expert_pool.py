from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[2]
ORCH=ROOT/'.agents/skills/ai-auto-test-platform-feature-orchestrator'

def test_expert_pool_is_reduced_to_ten_agents()->None:
    paths=sorted((ROOT/'.codex/agents').glob('*.toml')); assert len(paths)==10
    names={tomllib.loads(p.read_text(encoding='utf-8'))['name'] for p in paths}
    assert {'context_impact_analyst','business_ui_ux_designer','ui_ux_reviewer'}.isdisjoint(names); assert 'business_ui_ux_specialist' in names

def test_orchestrator_is_risk_triggered_not_fixed_pipeline()->None:
    text=(ORCH/'SKILL.md').read_text(encoding='utf-8')
    for token in ('RISK_TRIGGERED_EXPERT_POOL','LOCAL 默认 0 个子 Agent','MEDIUM 默认 1-3','HIGH 推荐 4-7','EXPERT_POOL_ESCALATION_JUSTIFICATION','EXPERT_NOT_SELECTED'): assert token in text

def test_context_analyst_removed_and_scan_owned_by_main_agent()->None:
    context=(ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency/SKILL.md').read_text(encoding='utf-8'); policy=(ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency/schemas/context-policy.yaml').read_text(encoding='utf-8')
    assert '不再设置独立 Context Analyst Agent' in context; assert 'orchestrator_current_main_agent_only' in policy; assert not (ROOT/'.codex/agents/context_impact_analyst.toml').exists()

def test_business_ui_ux_roles_are_merged_into_dual_mode_specialist()->None:
    ins=tomllib.loads((ROOT/'.codex/agents/business_ui_ux_specialist.toml').read_text(encoding='utf-8'))['developer_instructions']; assert 'DESIGN_MODE' in ins and 'REVIEW_MODE' in ins

def test_task_context_pack_carries_expert_selection_plan()->None:
    text=(ROOT/'.agents/skills/ai-auto-test-platform-context-efficiency/references/task-context-pack.md').read_text(encoding='utf-8')
    for token in ('expert_selection:','risk_tier: LOCAL | MEDIUM | HIGH','selected_agents','skipped_agents','child_agent_budget','EXPERT_POOL_ESCALATION_JUSTIFICATION','EXPERT_NOT_SELECTED'): assert token in text

def test_all_agents_are_on_demand_and_cannot_recursively_dispatch()->None:
    for p in sorted((ROOT/'.codex/agents').glob('*.toml')):
        ins=tomllib.loads(p.read_text(encoding='utf-8'))['developer_instructions']; assert 'RISK_TRIGGERED_EXPERT_POOL' in ins; assert 'EXPERT_NOT_SELECTED' in ins; assert '不得自行递归调度其它 Custom Agent' in ins

def test_independent_review_is_not_default_lane()->None:
    ins=tomllib.loads((ROOT/'.codex/agents/independent_code_reviewer.toml').read_text(encoding='utf-8'))['developer_instructions']; assert 'HIGH' in ins and 'final gate' in ins and '不得作为每任务默认尾部 Lane' in ins
