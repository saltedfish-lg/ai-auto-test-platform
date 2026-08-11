# 当前 authority Runtime Governance Customization

本定制层不修改 `docs/authority/**`，只增强 Codex 运行时治理。

当前核心：

- `Single Full Impact Scan + Shared Task Context Pack + Incremental Closure`；
- `Risk-triggered Expert Pool`：10 个 Custom Agent 按 LOCAL/MEDIUM/HIGH 和真实影响信号稀疏调度；
- `context_impact_analyst` 已移除，Full Scan 收回 feature-orchestrator + context-efficiency；
- `business_ui_ux_designer + ui_ux_reviewer` 合并为 `business_ui_ux_specialist` 的 DESIGN_MODE / REVIEW_MODE；
- Product Sovereignty 继续作为 Skill Gate，不增加 Product Manager Agent；
- 命名 Agent 不可用时只对 Expert Selection Plan 中 selected_agents 走 Role Card + Skill 串行 fallback。

关键不变量：Token/Agent 优化不得降低搜索覆盖、产品/契约/权限/状态/DB/Runner影响分析、测试或高风险独立 Review 强度。
