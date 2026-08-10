# Agent Role Cards

这些文件保留为人类可读角色规范与兼容回退说明。Codex 原生项目级 Custom Agents 已注册在：

```text
.codex/agents/*.toml
```

对应关系：

- `context-impact-analyst.md` → `context_impact_analyst`
- `business-ui-ux-designer.md` → `business_ui_ux_designer`
- `ui-ux-reviewer.md` → `ui_ux_reviewer`
- `frontend-implementer.md` → `frontend_implementer`
- `backend-implementer.md` → `backend_implementer`
- `contract-guardian.md` → `contract_guardian`
- `database-integrity-reviewer.md` → `database_integrity_reviewer`
- `security-rbac-reviewer.md` → `security_rbac_reviewer`
- `ui-verifier.md` → `ui_verifier`
- `code-quality-reviewer.md` → `code_quality_reviewer`
- `independent-code-reviewer.md` → `independent_code_reviewer`

## Token / Agent 调度原则

- LOCAL简单任务：当前实现Agent内嵌使用Context Efficiency，不额外启动`context_impact_analyst`。
- CROSS_MODULE/HIGH_RISK且影响不清：才启动`context_impact_analyst`生成Task Context Pack。
- UI_LOW/UI_MEDIUM：`frontend_implementer`内嵌使用Business UI/UX Skill。
- UI_HIGH、新核心工作台、大规模重设计：才启动`business_ui_ux_designer`。
- `ui_ux_reviewer`只用于UI_HIGH或用户明确要求独立体验审查。

只有运行时能够**可靠按名称选择** Custom Agent 时，才把 `.codex/agents` 调度视为成功；若 agent_type/命名路由不可用、不可确认或只产生 generic subagent，则不得冒充 Custom Agent 已加载。此时由主 Agent 显式读取对应 Role Card + Skill 串行执行，并标记 `CUSTOM_AGENT_ROUTING = FALLBACK_SERIAL`。任何 Token 优化都不得降低搜索覆盖率或验证强度。
