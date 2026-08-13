# AGENTS.md — AI自动化测试执行平台

## 当前权威模型

- authority_model: `SINGLE_LIVING_AUTHORITY`
- authority_root: `docs/authority/**`
- authority_status: `ACTIVE_CONTROLLED_MUTABLE`
- code_readiness: `READY_FOR_P1_IMPLEMENTATION`
- versioned_authority_copies: `FORBIDDEN`
- authority_copy_policy: `NO_VERSIONED_AUTHORITY_COPIES`
- manifest_or_release_snapshot: `NOT_REQUIRED`
- codex_git_access: `DISABLED`
- user_git_owner: `IDEA / 用户人工操作`
- git_ownership: `USER_OWNS_GIT`

当前源文档仍处于持续完善阶段。Codex可以在用户当前请求明确要求、既有用户裁决已明确，或仅做不改变产品语义的一致性修复时直接修改 `docs/authority/**`；修改后必须先通过 authority validators，再继续受影响实现。

## 权威职责域

1. `docs/authority/**` 是唯一活动产品、业务、状态、权限、Runner、安全、DDL、OpenAPI、事件与验收事实源。
2. 六份核心 YAML 负责产品范围、角色场景、对象规则、权限并发、AI/Runner 和安全验收业务语义。
3. `编码权威事实/**` 的 SYSTEM_DESIGN、DDL、OpenAPI、事件、状态 Owner、权限与验收契约负责技术和物理实现，必须服从核心 YAML。
4. ADR 负责当前技术/产品决策理由；若决定改变产品事实，必须同步受影响 authority 源文档后才成为实施依据。
5. 根 `AGENTS.md` 和 `.agents/skills/**` 负责 Codex 运行治理，不是产品事实源。
6. Markdown、DOCX、图形等投影不能反向覆盖权威 YAML/SQL/OpenAPI/CSV/JSON。

权威模型ID：`AUTHORITY-MODEL-LIVING-001`。

### 禁止版本目录复制

Codex不得创建任何按版本号复制整套 authority 的目录（例如把当前约 700 个事实文件整体复制为下一版本）。历史版本不得以重复源文件树形式保留在活动工作区。历史版本、commit、branch、tag、push 由用户在 IDE/Git 中自行管理，不属于 Codex 治理。

## P1认证编码强制规则

- 使用 `docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml`、当前 OpenAPI 和由 `tools/current_facts.py` 机械发现的 Migration Head。
- 不得自创认证 Operation、DTO、状态、Cookie、Token 或密码政策。
- admin 初始化只能使用无回显 TTY 输入或 `ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；不得写死、输出或记录密码。
- Access Token 不得持久化到 Browser 存储；Refresh Token 不得进入 JSON、数据库原值、日志或仓库。
- 权限不得写入 JWT 作为长期授权事实；每个受保护请求按数据库当前关系实时授权。
- 不得使用 `if username == "admin"` 绕过正式 `ROLE-SUPER-ADMIN` Mapping。
- Migration 以 `docs/authority/编码权威事实/DATABASE_DDL/V<整数>__*.sql` 为 append-only 定义，当前 Head/完整执行链由 `tools/current_facts.py` 按数字版本机械发现；新增 V9/V10 等只追加 Migration，不得在治理文档复制当前上限。admin 初始化在完整 Migration 链和 RBAC Seed 后独立执行。

## Authority 更新规则

`docs/authority/**` 是**受治理的可修改当前事实源**，不是只读历史副本目录。

允许修改的来源：

1. 用户当前请求已经明确给出目标产品事实；
2. 既有明确用户决定可以唯一落地；
3. Product Decision Pack 已被用户确认；
4. 不改变产品语义的事实一致性/格式/引用修复。

若 Codex 只是认为“这样更合理”，但用户行为、业务规则、状态、权限、API/数据/事件、Runner 恢复或验收行为会改变，则必须进入 `$ai-auto-test-platform-product-sovereignty`，不得擅自改 authority。

产品事实更新流程：

```text
CONFIRMED
→ AUTHORITY_UPDATE_ONLY
→ 修改 docs/authority/**
→ authority validators
→ Product Gate 再验证
→ PRODUCT_FACT_FOUND
→ Architecture / Implementation
```

不得先改代码再用代码反向修正文档。


## Authority 单写者与临时写事务

`docs/authority/**` 虽然是受控可修改事实源，但物理写入实行 **Single Authority Writer**：

- `feature-orchestrator` / 当前主 Agent 是唯一 `AUTHORITY_PHYSICAL_WRITE_OWNER`；所有 Custom Agent、Reviewer、fallback role 对 `docs/authority/**` 均为 `READ_ONLY`。
- 子 Agent 只能返回 `AUTHORITY_CHANGE_REQUEST`；实现阶段发现 Authority 缺口必须退回 Orchestrator → Product Sovereignty → `AUTHORITY_UPDATE_ONLY`，禁止顺手修改后继续实现。
- `AUTHORITY_UPDATE_ONLY` 写入前必须把 Product / Architecture / Security 等修改意图合并为一个 `authority_change_set`，按目标文件去重并记录 `expected_sha256`；同一大型 Authority 文件不得被多个阶段分别反复写入。
- Authority 写事务使用 workspace 级互斥锁，不使用文件级锁；每次 acquire 必须绑定当前 Task Checkpoint 并由 Guard 生成新的唯一 `authority_transaction_id`；同一 Workspace 任一时刻只允许一个 ACTIVE Authority 写事务，但同一 Task 在前一事务合法终态化并释放 mutex 后可以开启下一笔顺序事务；锁和所有 change-set/before-image/write-state/prepared 内容必须位于 workspace 外。锁禁止 TTL 自动抢占。
- apply 前必须再次校验 expected SHA-256；不一致返回 `AUTHORITY_STALE_WRITE_CONFLICT`，只允许 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP` 后重建 change-set，禁止旧上下文覆盖新内容。
- 文件写入使用 temp + fsync + atomic replace；多文件写失败使用 before-image 回滚。写入后先运行 authority validators，验证通过才可关闭 Authority 写事务。
- `authority_change_set` 是 Task 级临时事务数据：`CLOSURE_COMPLETE` 必须先把 Guard terminal attestation 写入既有 Task Checkpoint，再释放锁并删除整个临时目录；CP-6 必须自行重算当前 Authority digest，并要求**最新一笔 Authority transaction 本身为成功 `CLOSURE_COMPLETE`** 且其 closure digest 与当前 Authority 一致后才能完成。`TASK_ABORTED / TASK_ABANDONED` 必要时先回滚并把失败终态写入 checkpoint 后再清理；失败事务可由后续新的顺序事务解决，但不能以更早成功事务替最新失败事务兜底。`INTERRUPTED` 暂时保留以支持 Validated Resume。临时数据不得进入工作区、Authority 或 Git。
- 机械实现见 `.agents/skills/ai-auto-test-platform-feature-orchestrator/scripts/authority_write_guard.py` 与 `references/authority-write-coordination.md`。

## Git 完全由用户负责

本项目的 Git 历史、提交、分支、标签和远程操作由用户在 IDEA 中人工管理。Codex及所有 Custom Agent / Skill：

```text
MUST_NOT_INVOKE_GIT
```

禁止包括只读和写入 Git 命令：

- `git status`
- `git diff`
- `git log`
- `git show`
- `git add`
- `git commit`
- `git push/pull/fetch`
- `git checkout/switch`
- `git branch/merge/rebase/reset/revert/cherry-pick/stash/tag/remote`
- 修改或读取 `.git/**` 作为任务治理证据

Codex只修改工作区文件、运行工程/authority validators 并报告结果。是否提交、提交哪些文件、是否推送完全由用户决定。

## Authority 验证

Git 只能告诉用户“哪些文件变化”，不能证明当前事实彼此一致。因此保留 validators，但取消 Manifest/Release Snapshot 验证。

当前正式验证入口：

```text
python tools/verify_authority.py
python docs/authority/validation/validate_all.py --root docs/authority
python docs/authority/validation/validate_governance.py --root docs/authority
python docs/authority/validation/validate_auth_contract.py --root docs/authority
python tools/authority_projection.py check
python tools/current_facts.py check
python tools/authority_referential_integrity.py check
python tools/openapi_client.py check
```

验证目标是**当前 living authority 的结构、语义、跨文档一致性和可编码性**，不是验证它与某个 R4.x 哈希完全相同。

## 代码质量与注释规范

正式实现必须同时满足正确性、契约一致性和长期可维护性。**所有正式代码写入都必须应用** `$ai-auto-test-platform-code-quality` 的 Implementation Standards Mode；LOCAL 任务也不能跳过，只是不默认启动 `code_quality_reviewer`。`code_quality_reviewer` 仅在风险触发时使用 Review Mode。

- 注释解释业务不变量、状态转换原因、安全边界、事务/幂等/并发、重试/补偿、外部限制和非显然算法；不机械复述代码。
- 复杂正式业务逻辑原则上提供必要中文原因型注释或 Docstring；简单 CRUD/赋值/框架样板不逐行注释。
- 注释使用第三人称或客观陈述，不使用“我/我们/你”。
- 公共 Domain/Application/Security 能力在函数名和类型不足以表达契约时提供简洁 Docstring。
- 过时注释、与实现矛盾注释、掩盖复杂度注释属于质量缺陷；generated 代码不得人工修改。
- 不得用 TODO/FIXME、fallback、吞异常、硬编码、并行重复模型、无界重试或测试专用生产逻辑绕过正式能力。
- 重大用户可见或跨层行为变化必须有与风险相称的 contract/integration/E2E 证据。
- Implementation 完成后、进入 Verification 前，必须以 `workspace_snapshot.py delta` v4 机械产生的本 Task `changed_symbols / changed_line_ranges` 作为 `comment_quality_gate.py --task-delta ... --checkpoint ...` 的可信 scope evidence；禁止仅凭 `task_delta_paths` 对整个历史文件回溯扫描。仅对本 Task 真正改动的复杂符号强制原因型中文注释/Docstring，不以注释率为门禁。

## 上下文效率与跨模块影响闭包

所有正式修改使用 `$ai-auto-test-platform-context-efficiency` 时遵循：

- **业务/工程/契约检索不缩水，模型加载才收敛**。
- 唯一活动 authority 是 `docs/authority/**`；不存在 CURRENT marker、R4.x 目录解析、历史版本化 Authority 副本默认搜索。
- 正式修改前、任何写入前建立 filesystem-only task-start snapshot（版本以 `workspace_snapshot.py::SNAPSHOT_VERSION` 为唯一事实）；不调用 Git。
- snapshot/delta 制品必须位于 workspace 外；对受控工作树按 SHA-256 指纹比较，得到 `added/removed/modified/task_delta_paths`。
- required scope 缺失、`docs/authority` 缺失或扫描错误时 `closure_safe=false`。
- `.agents/.codex` 只在 Agent/Skill/Orchestrator 治理任务显式扩张。
- LOCAL 简单任务由当前 Agent 内嵌执行，不额外启动分析 Agent。若 LOCAL 写正式代码，只创建 `LIGHTWEIGHT_LOCAL` CP-0 机械证据锚以绑定 task-start snapshot/Comment Gate，不运行完整 CP-1→CP-6；完成时使用 `local-complete` 写入轻量终态证据。不写正式代码的 LOCAL 不要求 checkpoint。若发现需要 Resume、Authority transaction、CROSS_MODULE/HIGH_RISK，必须先执行 `promote-local-to-full` 保留原 CP-0 后升级为 FULL；LIGHTWEIGHT_LOCAL 本身禁止 acquire Authority。
- CROSS_MODULE/HIGH_RISK 必须建立 Pre-change Impact Closure。

### Single Full Impact Scan

- `feature-orchestrator` 是正式 Task 的 `FULL_IMPACT_SCAN` 唯一调度 Owner；执行者是当前主 Agent。
- 每 Task 最多 1 次成功 Full Scan：`FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS=1`。
- formal scan state 与 canonical guard 必须在 workspace 外；`workspace_root + task_id` 阻止更换 state 路径后再次扫描。
- 第二次 Full Scan 必须 `IMPACT_SCAN_ALREADY_COMPLETED`。
- 首次失败不占成功额度；修复 required scope/scan error 后允许重试。

### Shared Task Context Pack

- 父编排已有 CURRENT Pack 时所有子 Agent `MUST_CONSUME_TASK_CONTEXT_PACK`。
- 禁止子 Agent建立第二个 Impact Map、再次 `impact_scan.py`、重复全仓探索。
- CROSS_MODULE/HIGH_RISK Pack 缺失时返回 `TASK_CONTEXT_PACK_REQUIRED`。

### Incremental Closure

- Pack `STALE`、实现后闭环和 `IMPACT_EXPANSION` 只允许 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`。
- Targeted lookup 必须以 changed symbol、operationId、table、permission、event、route、config 等明确 seed 为入口。
- `IMPACT_EXPANSION` 只扩充同一 Pack、递增 `pack_revision`；禁止 Full Scan #2。
- API、DB、RBAC、状态、事件、认证、事务、并发、Runner/Worker、generated client 属于自动扩大影响域。

## Stage Checkpoint + Validated Resume

MEDIUM/HIGH、需要 Resume 或进入 Authority 写事务的正式 Task 使用 FULL Task-level Stage Checkpoint；LOCAL 正式代码写入使用 LIGHTWEIGHT_LOCAL CP-0 evidence anchor：

```text
TASK_INITIALIZED
→ CONTEXT_READY
→ DECISIONS_READY
→ IMPLEMENTATION_READY
→ IMPLEMENTATION_COMPLETE
→ VERIFICATION_COMPLETE
→ CLOSURE_COMPLETE
```

- LOCAL 正式代码写入：`task_checkpoint.py init --lifecycle-profile LIGHTWEIGHT_LOCAL` 只产生 CP-0 task-start evidence；Comment Gate 仍强制执行，但 `advance`/CP-1→CP-6 不适用；定向验证后使用 `task_checkpoint.py local-complete` 封存轻量终态。若范围升级，先 `promote-local-to-full`，然后才允许 FULL stage chain 或 Authority transaction。
- `feature-orchestrator` 是唯一 `TASK_LIFECYCLE_OWNER`；`context-efficiency` 只提供 workspace identity、authority digest、Pack、filesystem delta 与 freshness。
- Checkpoint 在 workspace 外，原子写入并带 SHA-256 checksum；不保存 Chain-of-Thought。
- Resume 状态：`RESUME_EXACT / RESUME_WITH_DELTA_REFRESH / RESUME_REJECTED / CHECKPOINT_CORRUPTED`。
- `RESUME_EXACT`：从下一阶段继续，不重放已完成且仍有效阶段。
- `RESUME_WITH_DELTA_REFRESH`：workspace fingerprint 或 authority digest 变化时只做增量刷新和最小阶段失效，禁止 Full Scan #2。
- authority digest 变化**不创建新 R4.x，也不自动拒绝 Resume**；它表示当前唯一事实源需要重新验证受影响 Product/Architecture/Verification。
- workspace root/identity、task_id 或 authority root 不兼容才 `RESUME_REJECTED`。
- `IMPLEMENTATION_COMPLETE` 后恢复直接进入 Verification，不重新实现。

## 产品主权门与需求裁决

正式功能/修复/重构在 Impact Map 后、Architecture Risk Gate 前使用 `$ai-auto-test-platform-product-sovereignty`：

- 纯内部工程实现、不改变产品语义的视觉细节 → `PRODUCT_DECISION_NOT_REQUIRED`。
- 当前 authority 已明确且一致 → `PRODUCT_FACT_FOUND`。
- 事实缺失 → `PRODUCT_DECISION_REQUIRED`。
- 候选事实冲突 → `PRODUCT_CONFLICT_DETECTED`。
- 用户请求改变当前产品范围/业务规则/状态/权限/公开契约/验收行为 → `PRODUCT_SCOPE_CHANGE`。
- 当前请求本身已经明确唯一方案时记录 `CONFIRMED / CURRENT_USER_REQUEST`，不得为形式重复询问。
- `CONFIRMED + authority_update_required=true` 时只允许 `AUTHORITY_UPDATE_ONLY`；直接修改 `docs/authority/**` 并验证，不创建新的版本化 Authority 副本目录。
- Product Skill只有检索、差异、方案比较和推荐权；产品批准权属于用户。

## 风险触发专家池

- Skill 是按需能力库，Agent 是稀疏专家；禁止固定流水线。
- Orchestrator 在 Pack 中维护 `expert_selection`。
- LOCAL：默认 0 个子 Agent；必要浏览器验证最多 1 个。
- MEDIUM：默认 1–3 个真实受影响专家。
- HIGH：推荐 4–7 个，但不填满预算；超过 7 个需 `EXPERT_POOL_ESCALATION_JUSTIFICATION`。
- `code_quality_reviewer` 不是 LOCAL 默认步骤。
- `independent_code_reviewer` 仅 HIGH / final gate / 用户明确要求。
- 子 Agent不得递归启动其它 Agent；风险新增回 Orchestrator 更新同一 Expert Selection Plan。

## 按风险触发的技术架构裁决

所有正式编码在 Product Gate 后使用 `$ai-auto-test-platform-architecture`：

- `ARCH_LOW`：当前边界不变，不调用架构 Agent；
- `ARCH_MEDIUM`：既有边界内新增 Service/Repository/Handler，由当前实现 Agent内嵌检查；
- `ARCH_HIGH`：状态 Owner、事务/一致性、Event/Outbox、并发/锁/租约/fencing、Runner/Worker/Scheduler/Execution、恢复/迁移、重大依赖边界或领域重构，才调度 `solution_architect`。

`solution_architect` 只裁决技术架构，不拥有产品主权。当前 authority 中的技术决策是实施约束，但文件本身可在用户已确认的 Authority Update 中同步修改；不得以“最佳实践”为由擅自覆盖产品事实。

Task Context Pack 已有 CURRENT Architecture Decision 且无新架构域时必须复用；普通 delta 只 revision rebind，不重复 ARCH_RISK 判级。

## 业务驱动 UI/UX 与反机械化规则

所有用户可见前端页面变更使用 `$ai-auto-test-platform-business-ui-ux`：

- 按角色、核心任务、频率、风险、信息优先级、状态和路径设计，再进入 Vue/Element Plus 实现。
- 禁止把“欢迎语 + 英文 Eyebrow + KPI 卡片墙 + 表格”作为默认页面模板。
- 项目/环境、用例编辑、AI探索/录制、执行/Runner、报告/诊断、系统治理采用不同业务工作台原型。
- 在不改变当前 authority 业务/API/状态/权限/安全边界时，可自主决定布局、视觉层级、组件组合、密度、Design Token 和交互表现。
- UI_LOW/UI_MEDIUM 由当前实现 Agent 内嵌；UI_HIGH/核心工作台/大规模重设计/用户明确要求才选择 `business_ui_ux_specialist`。
- `ui_verifier` 负责真实浏览器功能/状态；`business_ui_ux_specialist` 负责业务信息架构与体验复核，不重复完整审查。

## 项目级 Custom Agents：风险触发专家池

当前专家池固定 **10 个**：

- `backend_implementer`
- `frontend_implementer`
- `solution_architect`
- `contract_guardian`
- `database_integrity_reviewer`
- `security_rbac_reviewer`
- `business_ui_ux_specialist`
- `ui_verifier`
- `code_quality_reviewer`
- `independent_code_reviewer`

`context_impact_analyst` 已移除；Full Impact Scan 由 Orchestrator 授权当前主 Agent使用 Context Efficiency。`business_ui_ux_designer + ui_ux_reviewer` 已合并为 `business_ui_ux_specialist`。

Task Context Pack 必须记录 `expert_selection`；未选 Agent 误启动时返回 `EXPERT_NOT_SELECTED`。Fallback Serial 只加载 `selected_agents` 对应 Role Card + Skill，禁止全量加载所有角色。

- `COMMENT_GATE_ATTESTATION_REQUIRED`：所有正式代码写入的 Comment Quality Gate PASS 必须绑定 Task Checkpoint；LOCAL/FULL 终态不得仅凭调用约定跳过 Gate。
