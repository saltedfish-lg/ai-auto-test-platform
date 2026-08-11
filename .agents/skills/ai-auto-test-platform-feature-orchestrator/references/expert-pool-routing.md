# Risk-triggered Expert Pool Routing

本项目把 Custom Agents 视为**按需专家池**，不是固定流水线。Skill 是能力库；Agent 只在对应风险信号真实存在时启动。

## Task Risk Tier

### LOCAL

局部、单职责、无产品/公开契约/状态Owner/事务/权限/Runner语义变化。

- 默认 child Agent budget：`0`；确有真实浏览器验证需要时最多 `1`。
- 当前主 Agent 内嵌使用相关 Skill 完成实现与轻量质量检查。
- 禁止为了“更保险”启动 Architect / Contract / DB / Security / Independent Reviewer。

### MEDIUM

同一既有边界内的常规 API、Service/Repository、页面、持久化或多文件功能；无新的高风险一致性/安全/状态Owner语义。

- 默认 child Agent budget：`1-3`。
- 只选择实际受影响的 implementer / reviewer。
- 若拟选超过 3 个，必须先重新评估是否应升级为 HIGH，并记录 `EXPERT_POOL_ESCALATION_JUSTIFICATION`。

### HIGH

存在以下任一信号：ARCH_HIGH、认证/RBAC/Secret、Migration/关键事务/幂等/并发、状态Owner/write authority、Runner/Worker/Scheduler/Execution协调、重大公开契约变化、跨模块恢复语义、UI_HIGH核心工作台、正式里程碑/final gate。

- 推荐 child Agent budget：`4-7`，不是必须填满。
- 仍按影响稀疏选择；无对应影响的专家必须跳过。
- 超过 7 个必须记录 `EXPERT_POOL_ESCALATION_JUSTIFICATION`，禁止默认全员出场。

## 专家触发矩阵

- `backend_implementer`：后端代码/领域/持久化真正需要写入时。
- `frontend_implementer`：Vue/路由/Pinia/前端交互真正需要写入时。
- `solution_architect`：**仅 ARCH_HIGH**。
- `contract_guardian`：OpenAPI/DTO/状态/事件/权限码/generated contract 有变化或存在漂移风险时。
- `database_integrity_reviewer`：DDL/Migration/FK/UNIQUE/事务/幂等/乐观锁/Outbox 等数据库完整性域受影响时。
- `security_rbac_reviewer`：认证、admin、JWT/Refresh、RBAC、DataScope、Secret/Cookie/Session 等安全域受影响时。
- `business_ui_ux_specialist`：仅 UI_HIGH、核心工作台/大规模重设计或用户明确要求；`DESIGN_MODE` 与 `REVIEW_MODE` 按阶段互斥执行。
- `ui_verifier`：存在可运行的用户可见页面/会话/权限/错误态，需要真实浏览器证据时。
- `code_quality_reviewer`：MEDIUM/HIGH 且存在非平凡结构、维护性、测试质量或脆弱捷径风险时；LOCAL 默认由实现 Agent 内嵌 code-quality Skill。
- `independent_code_reviewer`：仅 HIGH、正式里程碑/final gate，或用户明确要求最终独立审查时；不得成为每任务默认尾部 Lane。

## Expert Selection Plan

Task Context Pack 维护：

```yaml
expert_selection:
  risk_tier: LOCAL | MEDIUM | HIGH
  selected_agents: []
  selection_reasons: {}
  skipped_agents: {}
  child_agent_budget: "0" | "0-1" | "1-3" | "4-7"
  escalation_justification: null
  freshness: CURRENT | STALE
```

规则：

1. `selected_agents` 必须由 Impact Map / Product / Architecture /真实 diff 的风险信号驱动，禁止“全选”。
2. 子 Agent 只能消费 Shared Task Context Pack；不得自行创建新的专家链或递归调度。
3. `IMPACT_EXPANSION` 新增风险域时可以更新同一个 Expert Selection Plan；不得因此重新执行 Full Impact Scan。
4. 风险消失或专项已完成且 diff 未再触及该域时，不重复启动同一专家。
5. Product Sovereignty 是 Skill Gate，不是 Product Agent；Context Efficiency 是主编排能力，不再设置独立 Context Analyst Agent。
