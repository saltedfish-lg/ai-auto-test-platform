# Agent Role Cards

这些文件是项目级 Custom Agent 的人类可读角色规范与命名路由不可用时的兼容回退。正式 Agent Pool 共 **10** 个：

- `backend-implementer.md` → `backend_implementer`
- `frontend-implementer.md` → `frontend_implementer`
- `solution-architect.md` → `solution_architect`
- `contract-guardian.md` → `contract_guardian`
- `database-integrity-reviewer.md` → `database_integrity_reviewer`
- `security-rbac-reviewer.md` → `security_rbac_reviewer`
- `business-ui-ux-specialist.md` → `business_ui_ux_specialist`
- `ui-verifier.md` → `ui_verifier`
- `code-quality-reviewer.md` → `code_quality_reviewer`
- `independent-code-reviewer.md` → `independent_code_reviewer`

## Risk-triggered Expert Pool

- Custom Agents 不是固定流水线；只读取 `Expert Selection Plan` 选中的 Role Card。
- LOCAL 默认 0 个子 Agent；MEDIUM 默认 1-3；HIGH 推荐 4-7，但无对应风险域的专家必须跳过。
- `context_impact_analyst` 已取消：Full Impact Scan 由 feature-orchestrator 授权当前主 Agent直接使用 Context Efficiency 执行。
- `business_ui_ux_designer + ui_ux_reviewer` 已合并为 `business_ui_ux_specialist`，通过 `DESIGN_MODE / REVIEW_MODE` 区分阶段。
- `independent_code_reviewer` 只用于 HIGH / final gate / 用户明确要求，不是每任务默认尾部步骤。

## Shared Task Context Pack

- 被选中的角色必须 `MUST_CONSUME_TASK_CONTEXT_PACK`；不得再次 `impact_scan.py`。
- 正式 CROSS_MODULE/HIGH_RISK Pack 缺失时返回 `TASK_CONTEXT_PACK_REQUIRED`。
- 未被 `expert_selection.selected_agents` 选中却误启动时返回 `EXPERT_NOT_SELECTED`。
- 只允许带 seed 的 targeted lookup / delta refresh；不得自行建立第二个 Impact Map 或递归启动其它 Custom Agent。

命名 Custom Agent 路由不可用时，由主 Agent **只针对 selected_agents** 显式加载对应 Role Card + Skill 串行执行，并标记 `CUSTOM_AGENT_ROUTING = FALLBACK_SERIAL`；禁止 generic subagent 冒充，也禁止 fallback 时加载全体 Role Cards。
