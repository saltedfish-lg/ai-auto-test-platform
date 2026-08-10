---
name: ai-auto-test-platform-feature-orchestrator
description: AI自动化测试执行平台跨前后端功能编排Skill；按影响闭包、产品主权门、技术架构、契约、业务UI设计、后端、生成客户端、前端、闭环反查、浏览器验证和独立审查完成闭环。
---

# Full-stack Feature Orchestrator

## 适用

一个任务同时涉及正式 API/数据库/前端页面，或用户要求“完整功能闭环”。

## 编排顺序

1. **上下文与影响闭包**：在任何工作区写入之前，Git 可读时先用 `$ai-auto-test-platform-context-efficiency` 的 `workspace_snapshot.py capture` 在 workspace 外建立 task-start snapshot（`snapshot_version=2`，绑定 resolved root 与 repository identity；真实 Git index 只通过临时副本读取），并把引用/摘要写入 Task Context Pack；随后使用该 Skill 对任务分级为 LOCAL/CROSS_MODULE/HIGH_RISK。普通业务任务扫描 required/optional 活动范围；Agent/Skill/Orchestrator/Codex治理任务显式 `--include-governance` 扩张 `.agents/.codex`。`scope_status=INCOMPLETE` 时必须停止闭环声明并进入 `BLOCKED_BY_INCOMPLETE_SCOPE`；若 `scope_status=COMPLETE` 但 `closure_safe=false` 且原因为 Git metadata `UNAVAILABLE`，进入 `BLOCKED_BY_ENVIRONMENT`；跨模块/高风险先建立 Impact Map 与 Task Context Pack；只有影响不清或范围较大时才调度 `context_impact_analyst`，避免简单任务增加Agent开销；
2. **事实与范围**：基于 Task Context Pack 精准读取 root AGENTS、core Skill、R4.2 权威事实，确定对象/权限/状态/验收边界；
3. **产品主权门**：先检查 Task Context Pack 的 `product_authority`。若其 `freshness=CURRENT`、`assessed_pack_revision == pack_revision` 且未发生新的 Product/Authority `IMPACT_EXPANSION`，直接复用，禁止重复产品分析；若仅发生不改变用户可观察行为/业务规则/API数据事件/权限安全/Runner业务语义/验收结果的工程 delta，可做 product revision rebind，仅更新 `assessed_pack_revision`。否则使用 `$ai-auto-test-platform-product-sovereignty` 执行轻量 `PRODUCT_AUTHORITY_GATE`：只有 `PRODUCT_DECISION_NOT_REQUIRED / PRODUCT_FACT_FOUND` 且 `workflow_state=READY_FOR_ARCHITECTURE` 才允许继续。`PRODUCT_DECISION_REQUIRED / PRODUCT_CONFLICT_DETECTED / PRODUCT_SCOPE_CHANGE` 若 `user_decision_status=PENDING`，生成/复用 Product Decision Pack 并进入 `BLOCKED_BY_PRODUCT_DECISION`；若当前请求或既有明确用户裁决已经使其 `CONFIRMED`，禁止重复询问，且新增/修改/删除产品事实、解决冲突或范围变化时必须进入 `AUTHORITY_UPDATE_ONLY`。该阶段只允许按用户授权同步受治理当前权威事实，禁止 Architecture/Implementation；同步完成后重新执行产品门，得到 `PRODUCT_FACT_FOUND` 才继续。推荐方案不等于用户批准，`CONFIRMED` 也不等于权威事实已更新；
4. **架构风险门禁**：先检查 Task Context Pack 的 `architecture_decision`。若 delta refresh 仅递增 `pack_revision` 且没有新增 state owner / transaction / consistency / concurrency / Runner-Worker / dependency domain，则先执行 **revision rebind**：保持 `freshness=CURRENT`、`recheck_required=false`，并把 `assessed_pack_revision` 更新到当前 `pack_revision`，禁止因此重跑架构裁决。完成 rebind 后，若 `freshness=CURRENT`、`assessed_pack_revision == pack_revision` 且未发生新的架构域 `IMPACT_EXPANSION`，直接复用现有 `ARCH_RISK / Architecture Check / Architecture Decision`，禁止重复判级。否则使用 `$ai-auto-test-platform-architecture` 判定 `ARCH_LOW / ARCH_MEDIUM / ARCH_HIGH`：ARCH_LOW 不调用架构 Agent；ARCH_MEDIUM 由当前实现 Agent 内嵌轻量 Architecture Check；只有 ARCH_HIGH 才调度只读 `solution_architect` 输出 Architecture Decision，并把状态/引用写回 Task Context Pack。架构裁决没有产品主权；发现产品/状态/契约/权限/恢复语义未决时进入 `BLOCKED_BY_PRODUCT_DECISION`；
5. **契约守卫**：使用 `$ai-auto-test-platform-api-contract` 确认 OpenAPI/DDL/权限/状态有正式来源；
6. **后端**：使用 `$ai-auto-test-platform-backend`；涉及 P1 认证/RBAC 时追加 `$ai-auto-test-platform-auth-rbac-security`；
7. **数据库**：需要持久化/事务时使用 `$ai-auto-test-platform-database`；
8. **业务UI设计门禁**：存在用户可见页面变更时使用 `$ai-auto-test-platform-business-ui-ux`。UI_LOW/UI_MEDIUM由`frontend_implementer`内嵌完成；UI_HIGH 的现有页面重设计先调用 `$ai-auto-test-platform-ui-quality` 的 `BASELINE_CAPTURE`；若成功则使用真实 Pre-change Browser Baseline，若因环境阻断则标记 `BLOCKED_BY_ENVIRONMENT + SOURCE_BASED_CURRENT_UI_BASELINE + VISUAL_BASELINE_CONFIDENCE = LIMITED` 并保留 `POST_CHANGE_BROWSER_VERIFY = REQUIRED`，不得伪造 Before；随后再调度`business_ui_ux_designer`输出Business UX Spec；新页面明确 baseline N/A；
9. **客户端生成**：从正式 OpenAPI 生成/校验 `apps/web/src/generated/**`，禁止手改；
10. **前端**：使用 `$ai-auto-test-platform-frontend`，按Business UX Spec/轻量设计决策实现，不套通用卡片墙模板；
11. **修改后影响闭环**：先用 task-start snapshot 计算 `task_delta_paths`，明确本任务相对原有 dirty workspace 真正新增/继续修改/清除的路径；后端/DB/契约/权限/状态等阶段若已使 Task Context Pack 失效，再基于 `task_delta_paths` + 真实 diff 做 delta refresh 并递增 `pack_revision`；若真实 delta 新增用户可观察行为、业务规则/API数据事件、权限安全、Runner业务/恢复语义或验收影响，则先把 `product_authority.freshness=STALE` 并回到产品主权门；未新增产品域时可对 CURRENT product_authority 做 revision rebind。若 delta 未引入新的架构域，则对 CURRENT Architecture Decision 做 **revision rebind**，只更新 `assessed_pack_revision`，不得重复调用 Architect；若引入新架构域则标记 `STALE / recheck_required=true`。随后再次使用 `$ai-auto-test-platform-context-efficiency` 从真实改动提取旧/新符号并全局反查。发现新消费者必须标记`IMPACT_EXPANSION`并返回实现阶段，直到`IMPACT_CLOSURE_PASS`；
12. **代码质量审查**：使用 `$ai-auto-test-platform-code-quality` 的 Review Mode，由 `code_quality_reviewer` 只读检查结构、hack、回归、测试、注释和可维护性；
13. **UI功能验证**：有可运行页面时使用 `$ai-auto-test-platform-ui-quality` / `ui_verifier`；
14. **业务UI/UX独立审查**：UI_HIGH或用户明确要求时调度`ui_ux_reviewer`，消费Business UX Spec和浏览器证据，不重复功能验证；
15. **独立审查**：使用 `$ai-auto-test-platform-code-review`，优先消费当前workspace状态下已有的Impact Closure与专项review结果，不无条件重复调度；
16. **Custom Agent兼容回退**：若运行时不能可靠选择 `.codex/agents/*.toml` 中的命名 Agent，禁止把 generic subagent 当作对应 Custom Agent 已生效；改由当前主 Agent 显式读取 `.agents/agent-roles/<role>.md` + 对应 Skill 串行执行，并在结果中标记 `CUSTOM_AGENT_ROUTING = FALLBACK_SERIAL`；
17. **DoD**：运行与改动范围相符的 `tools/dev.py` / npm / pytest 验证，区分工程测试与正式 acceptance evidence。

## Multi-agent

项目级 Custom Agents：

- `context_impact_analyst`：只读影响检索/Task Context Pack；仅跨模块、高风险或影响不清时调用；
- `solution_architect`：仅 ARCH_HIGH 触发的只读技术架构裁决；ARCH_LOW禁止调用、ARCH_MEDIUM默认内嵌Skill；
- `contract_guardian`：只读契约守卫；
- `backend_implementer`：后端正式实现；
- `database_integrity_reviewer`：只读数据库完整性审查；
- `security_rbac_reviewer`：只读认证/RBAC/安全审查；
- `business_ui_ux_designer`：只读业务UI设计；仅UI_HIGH/核心工作台；
- `frontend_implementer`：前端正式实现；
- `ui_verifier`：真实浏览器功能验证；
- `ui_ux_reviewer`：只读业务UI/UX审查；仅UI_HIGH/明确要求；
- `code_quality_reviewer`：只读代码质量多Lane审查；
- `independent_code_reviewer`：最终只读独立审查。


- task-start snapshot 的 `snapshot_version`、resolved root 或 repository identity 与 current 不一致时，`task_delta=UNAVAILABLE`（`SNAPSHOT_VERSION_MISMATCH / SNAPSHOT_ROOT_MISMATCH / SNAPSHOT_REPOSITORY_MISMATCH`）并进入 `BLOCKED_BY_ENVIRONMENT`；禁止跨仓库复用 snapshot。

## Token治理

- 主编排只生成一次 Task Context Pack，并保留 task-start/current/task_delta workspace fingerprint；各子Agent按职责消费切片；`solution_architect` 只消费 architecture slice，默认不重新全仓探索；
- 子Agent不得无条件重复读取完整AGENTS/基线/OpenAPI/DDL/仓库；
- Reviewer优先消费同一workspace状态的专项结果与浏览器证据；
- 若 Task Context Pack 不完整、过期或发现新消费者，必须增量检索，不能为了Token强行复用；
- 命名 Custom Agent 路由不可用/不确定时必须走 Role Card 串行 fallback；不得用 generic Agent 冒充自定义角色已加载；
- Token优化只能减少上下文重复，不能减少业务/工程/契约搜索覆盖、风险扩张、测试或审查；普通业务任务不无条件扫描整个治理目录，治理任务必须显式扩张治理 scope；CURRENT 的 Architecture Decision 必须复用，禁止重复判级/重复调度。

## 自主权

遵循 Engineering Autonomy：纯工程/视觉实现自行决定；产品级语义由 `$ai-auto-test-platform-product-sovereignty` 先查当前权威事实，真实缺口/冲突/范围变化才生成 Decision Pack 并升级用户裁决。
