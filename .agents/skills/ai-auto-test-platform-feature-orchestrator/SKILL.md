---
name: ai-auto-test-platform-feature-orchestrator
description: AI自动化测试执行平台跨前后端功能编排Skill；以 Single Full Impact Scan、Shared Task Context Pack、风险触发专家池和 Stage Checkpoint + Validated Resume 完成可中断恢复的产品、架构、实现与验证闭环。
---

# Full-stack Feature Orchestrator

## 核心模型

本 Orchestrator 不是“让所有 Agent 依次过一遍”的固定流水线。正式模型是：

`Single Full Impact Scan → Shared Task Context Pack → Risk Tier → Expert Selection Plan → Sparse Execution → Stage Checkpoint → Validated Resume → Incremental Closure`。

Custom Agents 是 `RISK_TRIGGERED_EXPERT_POOL`；Skill 是按需能力库。普通任务允许 `0` 个子 Agent，高风险任务也只启动真实受影响的专家。详见 `references/expert-pool-routing.md`。

## Stage Checkpoint + Validated Resume

本 Orchestrator 同时是 `TASK_LIFECYCLE_OWNER`。长时间正式 Task 只维护**一套 Task-level checkpoint**，不为各 Agent 建独立 checkpoint，不保存模型 Chain-of-Thought。阶段为：

`CP-0 TASK_INITIALIZED → CP-1 CONTEXT_READY → CP-2 DECISIONS_READY → CP-3 IMPLEMENTATION_READY → CP-4 IMPLEMENTATION_COMPLETE → CP-5 VERIFICATION_COMPLETE → CP-6 CLOSURE_COMPLETE`。

- checkpoint 必须位于 workspace 外，使用 `scripts/task_checkpoint.py` 原子写入并带 SHA-256 checksum；
- Resume 前必须经过 `RESUME_VALIDATION_GATE`，只允许 `RESUME_EXACT / RESUME_WITH_DELTA_REFRESH / RESUME_REJECTED / CHECKPOINT_CORRUPTED`；
- `RESUME_EXACT`：复用 latest `COMPLETED + VALID` stage，从下一阶段继续；
- `RESUME_WITH_DELTA_REFRESH`：只允许 `$ai-auto-test-platform-context-efficiency` 执行 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`，按失效矩阵最小化回退阶段；**禁止 Full Scan #2**；
- workspace identity / workspace root / authority root 不一致时 `RESUME_REJECTED`；`docs/authority` digest 变化只进入 `RESUME_WITH_DELTA_REFRESH`，不创建新 baseline；
- `CP-4 IMPLEMENTATION_COMPLETE` 后恢复必须直接进入 Verification，不得重新实现；`CP-5` 的验证证据必须绑定 workspace fingerprint，代码再次变化则相应验证失效；
- 详见 `references/task-checkpoint-resume.md`。

## 编排顺序

1. **CP-0 / CP-1 上下文与影响闭包**：任何写入前，用 `$ai-auto-test-platform-context-efficiency` 的 filesystem-only `workspace_snapshot.py capture` 在 workspace 外建立 task-start snapshot；Codex 不调用 Git。本 Orchestrator 是正式 Task 的 **FULL_IMPACT_SCAN 唯一调度 Owner**，**唯一执行者固定为当前主 Agent**，不再委托独立 Context Analyst Agent。正式扫描使用 `--formal-task --task-id <task-id> --scan-state <仓库外路径>`；每个 Task `FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS=1`，`workspace_root + task_id` canonical guard 阻断更换 state 路径后的第二次成功 Full Scan；第二次必须返回 `IMPACT_SCAN_ALREADY_COMPLETED`。第一次失败不占成功额度。成功后只形成一个 Shared Task Context Pack。
2. **产品主权门**（CP-2 决策阶段）：精准消费 Pack 的 authority/product slice。`PRODUCT_DECISION_NOT_REQUIRED / PRODUCT_FACT_FOUND + READY_FOR_ARCHITECTURE` 才继续；PENDING 进入 `BLOCKED_BY_PRODUCT_DECISION`；已由用户明确 `CONFIRMED` 但权威未同步时进入 `AUTHORITY_UPDATE_ONLY`，同步后重新 Product Gate。`PRODUCT_DECISION_REQUIRED / PRODUCT_CONFLICT_DETECTED / PRODUCT_SCOPE_CHANGE` 只能按既有状态机处理；推荐方案/recommendation 不等于用户批准。若 `CONFIRMED + authority_update_required=true`，只允许 `AUTHORITY_UPDATE_ONLY`，**禁止 Architecture/Implementation**；完成权威同步后必须**重新执行产品门**，取得 `PRODUCT_FACT_FOUND` 才能继续。
3. **CP-2 决策阶段 / Task Risk Tier + Expert Selection Plan**：在 Pack 中写入 `expert_selection`。按 `LOCAL / MEDIUM / HIGH` 选择最少必要专家：LOCAL 默认 0 个子 Agent；MEDIUM 默认 1-3；HIGH 推荐 4-7 但禁止为了填预算全选。超过预算必须 `EXPERT_POOL_ESCALATION_JUSTIFICATION`。
4. **架构风险门禁**（CP-2 决策阶段）：使用 `$ai-auto-test-platform-architecture`。若 `freshness=CURRENT`、`assessed_pack_revision == pack_revision` 且没有新架构域，则做/复用 `revision rebind`，保持 `recheck_required=false` 并**禁止重复判级**；仅新增架构域才 recheck。ARCH_LOW 不调用 Architect；ARCH_MEDIUM 当前实现 Agent 内嵌 Architecture Check；**只有 ARCH_HIGH** 才选中 `solution_architect`。未定义产品语义必须 `BLOCKED_BY_PRODUCT_DECISION`。
5. **CP-3 / CP-4 实现阶段**：只有真实写入域被影响才选择 `backend_implementer` / `frontend_implementer`；纯 LOCAL 修改可由当前主 Agent 内嵌对应 Skill 完成，不强制创建实现子 Agent。
6. **专项 Reviewer 稀疏触发**：
   - `contract_guardian`：仅 contract/API/DTO/status/event/permission/generated-client 影响；
   - `database_integrity_reviewer`：仅 DB/Migration/transaction/idempotency/concurrency persistence 影响；
   - `security_rbac_reviewer`：仅 auth/RBAC/session/secret/security 影响；
   无风险信号则必须 skip，并在 `skipped_agents` 记录理由。
7. **业务 UI/UX**：UI_LOW/UI_MEDIUM 由当前 `frontend_implementer` 或主 Agent 内嵌 `$ai-auto-test-platform-business-ui-ux`。仅 UI_HIGH/核心工作台/大规模重设计/用户明确要求时选择 `business_ui_ux_specialist`：改造前以 `DESIGN_MODE` 产出 Business UX Spec，实现后需要独立体验审查时以 `REVIEW_MODE` 复用同一专家角色；功能验证仍由 `ui_verifier`。现有页面 UI_HIGH 需 `BASELINE_CAPTURE`；环境阻断时使用 `SOURCE_BASED_CURRENT_UI_BASELINE + VISUAL_BASELINE_CONFIDENCE = LIMITED + POST_CHANGE_BROWSER_VERIFY = REQUIRED`，禁止伪造 Before。
8. **代码质量**：`$ai-auto-test-platform-code-quality` 的 Implementation Standards Mode 始终可由实现者内嵌使用；只有 MEDIUM/HIGH 且存在非平凡结构/维护性/测试质量风险时才选中 `code_quality_reviewer`。LOCAL 不默认启动。
9. **真实 UI 验证**：只有存在可运行用户可见页面/会话/权限/错误态且需要浏览器证据时选择 `ui_verifier`。
10. **CP-5 验证阶段 / 最终独立审查**：`independent_code_reviewer` **仅 HIGH、正式里程碑/final gate 或用户明确要求**时选中；不得作为每个任务的默认最后一步。优先消费已有专项 review 与 Impact Closure。
11. **CP-5 / CP-6 Incremental Closure**：实现后基于 filesystem task-start snapshot 得到 `task_delta_paths`；只允许 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`，严禁再次运行 `impact_scan.py`，即禁止 Full Scan #2。`IMPACT_EXPANSION` 只扩充同一个 Pack、递增 `pack_revision`，并按新增风险域更新 `expert_selection`；不得重新全仓扫描或默认重启所有专家。
12. **Validated Resume**：如果当前 Task 已有仓库外 checkpoint，任何继续执行前先用 `scripts/task_checkpoint.py resume-validate` 验证 task_id、workspace root、filesystem workspace identity、固定 `docs/authority` root、authority digest、checksum 与当前 workspace fingerprint。`RESUME_EXACT` 从下一阶段继续；`RESUME_WITH_DELTA_REFRESH` 先增量刷新并只失效受影响阶段；`RESUME_REJECTED / CHECKPOINT_CORRUPTED` 禁止继续旧 Task。不得因 Codex/Agent 重启重复已经完成且仍有效的 Product/Architecture/Implementation/Verification 阶段。
13. **Custom Agent fallback**：命名路由不可靠时，主 Agent 只对 `selected_agents` 中的角色读取 `.agents/agent-roles/<role>.md` + 对应 Skill 串行执行，并标记 `CUSTOM_AGENT_ROUTING = FALLBACK_SERIAL`；禁止 generic subagent 冒充，也禁止 fallback 时把全部 Role Card 都加载。
14. **DoD**：只运行与真实改动/风险域相符的工程验证、专项 Reviewer 与 acceptance evidence；正确性优先于 Token，但禁止以“更保险”为理由重复专家、重复 Full Scan 或全量加载所有 Skill。

## Expert Pool（10）

- `backend_implementer`：后端写入；
- `frontend_implementer`：前端写入；
- `solution_architect`：仅 ARCH_HIGH；
- `contract_guardian`：仅契约影响；
- `database_integrity_reviewer`：仅数据库完整性影响；
- `security_rbac_reviewer`：仅安全/RBAC影响；
- `business_ui_ux_specialist`：仅 UI_HIGH/明确要求；支持 `DESIGN_MODE / REVIEW_MODE`；
- `ui_verifier`：真实浏览器功能/状态证据；
- `code_quality_reviewer`：MEDIUM/HIGH 非平凡代码质量风险；
- `independent_code_reviewer`：仅 HIGH / final gate / 明确要求。

## Shared Context / Token 治理

- `1 × FULL_IMPACT_SCAN + 1 × SHARED_TASK_CONTEXT_PACK + N × DELTA_REFRESH + N × TARGETED_REVERSE_LOOKUP`。
- 所有被选中的子 Agent `MUST_CONSUME_TASK_CONTEXT_PACK`；正式跨模块/高风险 Pack 缺失时返回 `TASK_CONTEXT_PACK_REQUIRED`。
- 未被 `expert_selection.selected_agents` 选中的 Agent 不应启动；若误启动且 Pack 明确未选中，返回 `EXPERT_NOT_SELECTED`。
- 子 Agent 不得递归启动其它 Custom Agent，不得建立第二条专家链。
- Skill 按风险/职责渐进加载；禁止每个 Agent 默认加载全部 14 个 Skill。
- Reviewer 不重复其它 Reviewer 已完成的事实裁决；专项结果 CURRENT 时复用。
- 已完成阶段同样遵循复用原则：`COMPLETED + VALID → REUSE`；Agent 重启不是阶段失效理由。
- Checkpoint 只存事实/状态/路径/hash/验证结果索引，不保存完整 grep 输出、完整文件正文或模型思考过程。

## 自主权

纯工程/视觉实现继续使用 Engineering Autonomy；产品级语义由 `$ai-auto-test-platform-product-sovereignty` Gate 处理。Product Sovereignty 是 Skill，不增加 Product Manager Agent。
