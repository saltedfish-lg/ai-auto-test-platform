# AGENTS.md — AI自动化测试执行平台 R4.2

## 当前发布

- release_id: `PDBR-2026.08.07-R4.2`
- release_status: `P1_AUTHENTICATION_CONTRACT_COMPLETED`
- code_readiness: `READY_FOR_P1_IMPLEMENTATION`
- implementation_release_readiness: `NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT`
- pending_user_decisions: `0`

Codex可以基于R4.2恢复P1“身份认证 + 默认admin + RBAC”编码。MySQL 8.4空库安装和R4.1升级门禁已通过；1691项验收规范仍保持`SPECIFIED/NOT_STARTED`，不得把治理或Migration验证冒充平台业务验收。

## 按职责域确定权威

1. Release/Manifest只负责当前发布身份、成员、版本、状态和哈希，不改写业务语义。
2. 六份核心YAML负责产品范围、角色场景、对象规则、权限并发、AI/Runner和安全验收业务语义。
3. SYSTEM_DESIGN及DDL、OpenAPI、事件、状态Owner、权限与验收契约负责技术和物理实现，必须服从核心YAML。
4. ADR负责决策和理由；只有同步核心YAML及工程契约后才成为当前实施依据。
5. AGENTS和Skill负责Codex流程、边界和门禁，不得自行改变产品或工程契约。
6. 导航Markdown、DOCX和图形为非权威投影。

权威模型ID：`AUTHORITY-MODEL-R4.2-001`。

## P1认证编码强制规则

- 必须使用`编码冻结基线/AUTHENTICATION_CONTRACT/authentication-contract.yaml`、正式OpenAPI和V5 Migration。
- 不得自创认证Operation、DTO、状态、Cookie、Token或密码政策。
- admin初始化只能使用无回显TTY输入或`ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；不得写死、输出或记录密码。
- Access Token不得持久化到Browser存储；Refresh Token不得进入JSON、数据库原值、日志或仓库。
- 权限不得写入JWT作为长期授权事实；每个受保护请求按数据库当前关系实时授权。
- 不得使用`if username == "admin"`绕过正式`ROLE-SUPER-ADMIN` Mapping。
- Migration顺序固定为V3 → V4 → V5；admin初始化在Migration和RBAC Seed之后独立执行。

## 门禁范围

- `MYSQL84_EMPTY_DATABASE_EXECUTION`: `PASS`。
- `REAL_ACCEPTANCE_EVIDENCE`: `IMPLEMENTATION_RELEASE_READINESS`。
- 两项均不阻断工程初始化。

## 当前基线与 Codex 执行层

- `docs/baseline/CURRENT` 必须指向 `R4.2`；活动工具从 CURRENT 解析冻结版本。
- `docs/baseline/R4.1/**` 是历史父基线，只用于溯源和 R4.1→R4.2 升级验证。
- `docs/baseline/R4.2/**` 是只读正式契约；其中打包的 `核心CodexSkill` 属于发布制品，不作为本地运行时 Skill 注册位置。
- 本地运行时 Skill 只使用 `.agents/skills/**`；不得用冻结包内历史 reference 覆盖活动 Skill 与当前 Release。

## Git操作限制

本项目的Git版本管理由用户负责。除非用户在**当前任务中明确授权具体Git操作**，Codex及其所有Custom Agent、Skill不得执行任何会改变Git仓库状态、分支、提交历史、标签、暂存区或远程仓库的Git写操作。

默认禁止包括但不限于：

- `git add`
- `git commit`
- `git push`
- `git pull`
- `git fetch`（除非当前任务明确授权）
- `git checkout`
- `git switch`
- `git branch` 的创建、删除或修改
- `git merge`
- `git rebase`
- `git reset`
- `git revert`
- `git cherry-pick`
- `git stash`
- `git tag` 的创建、删除或修改
- `git remote` 的新增、删除或修改
- 创建或提交Pull Request / Merge Request
- 修改、删除或重建 `.git/**`
- 任何等价的Git历史重写、分支切换、暂存或远程写入行为

仅在只读诊断确有必要时允许使用不会改变仓库状态的命令，例如：

- `git status`
- `git diff`
- `git log`
- `git show`

即使Git仓库存在，Codex也不得因为完成编码任务而自动建分支、暂存、提交、推送或创建PR。若任务需要Git写操作，必须先取得用户在当前任务中的明确授权，并仅执行被授权的具体操作。

## 代码质量与注释规范

本项目的正式实现必须同时满足正确性、契约一致性和长期可维护性。实现 Agent 在编码时应使用 `$ai-auto-test-platform-code-quality` 的 **Implementation Standards Mode**；`code_quality_reviewer` 使用同一 Skill 的 **Review Mode** 做独立只读审查。

- 注释用于解释“为什么”：业务不变量、状态转换原因、安全/权限边界、事务/幂等/并发、重试/补偿、外部系统限制、非显然算法或兼容策略。
- 复杂或非显然的正式业务逻辑原则上必须有必要的中文原因型注释或 Docstring；简单赋值、getter、直观CRUD和框架样板代码不要求逐行注释。
- 注释统一使用第三人称或客观陈述，不使用“我/我们/你”等第一、第二人称；不得机械复述代码。
- 公共 Domain/Application/Security 能力在仅凭函数名和类型无法说明契约时，应提供简洁 Docstring，说明职责、关键前置条件、异常或状态影响。
- 过时、与实现矛盾或只用于掩盖复杂度的注释属于代码质量缺陷；generated 代码不得人工补注释。
- 不得用 `TODO/FIXME` 隐藏当前任务必须完成的正式能力；确需保留时必须说明原因、边界和后续处理依据。
- 约 350 行的维护源文件只触发结构/职责/依赖/ownership 深度检查，不因行数本身自动判为缺陷，也不得为了压行数做无收益拆分。
- 禁止以 fallback、吞异常、硬编码、并行重复模型、测试专用生产逻辑、无界重试或临时兼容绕过正式不变量。
- 重大用户可见行为或跨层行为变化必须有与风险相称的测试；跨层契约优先使用 contract/integration/E2E 证明，不得只用 mock unit test 冒充真实闭环。

代码质量专项不重新裁决 R4.2 产品/契约事实：契约问题交给 `contract_guardian`，安全问题交给 `security_rbac_reviewer`，数据库完整性交给 `database_integrity_reviewer`。


## 上下文效率与跨模块影响闭包

所有正式修改允许使用 `$ai-auto-test-platform-context-efficiency` 降低 Token，但必须遵循：

- **业务/工程/契约检索不缩水，模型加载才收敛**；根级 package/pyproject/lock/env/editor 配置与 CURRENT 当前基线属于活动影响范围；不得通过少搜文件省 Token。
- 正式修改开始前、任何工作区写入之前，Git workspace 可读时必须建立只读 **task-start workspace snapshot（`snapshot_version=2`，绑定 resolved root 与 repository identity）**；Task Context Pack 记录 task_start/current/task_delta 指纹，修改后只把相对任务起点真正发生变化的路径归因给当前任务，禁止把预存 dirty workspace 全部冒充本任务改动。
- Context scope 分为 required / optional / conditional-governance：required 缺失、CURRENT无法解析或活动扫描报错时必须 `closure_safe=false` 并阻断 `IMPACT_CLOSURE_PASS`；`db/.github` 等 optional 缺失不制造阻断。
- Git workspace 状态必须显式区分 `COMPLETE / NOT_APPLICABLE / UNAVAILABLE`：若根目录存在 `.git` 但只读 Git metadata 无法读取，tracked-deleted 证据链不完整，必须 `closure_safe=false`；跨模块/高风险或 CI/依赖/构建/部署/环境/工程工具任务进入 `BLOCKED_BY_ENVIRONMENT`，不得把空 tracked-deleted 当作“无影响”。
- Task-start snapshot / task-delta 制品必须位于 workspace 外；Context helper 的 index-backed Git 查询必须通过临时 `GIT_INDEX_FILE` 副本执行，真实 repository/worktree index 不得被 stat refresh 改写。
- `.agents/.codex` 不在普通业务任务中无条件全量扫描；Agent/Skill/Orchestrator/Codex治理任务必须显式扩张 governance scope。
- LOCAL 简单任务由当前 Agent 内嵌执行，不额外启动分析 Agent。
- CROSS_MODULE/HIGH_RISK 任务必须建立 Pre-change Impact Closure；影响不清时可调用 `context_impact_analyst`。
- 子 Agent 优先消费同一 workspace/scope 的 Task Context Pack，仅按职责加载切片；不得无条件重复通读完整基线/OpenAPI/DDL/仓库。
- 修改后必须先计算 task-start → current 的 `task_delta_paths`，再结合真实 diff 提取旧/新符号并全局反查；发现新消费者进入 `IMPACT_EXPANSION`，补改后重新闭环。
- API、DB、RBAC、状态、事件、认证、事务、并发、锁/租约/fencing、Runner/Worker、generated client 属于自动扩大影响域。
- Token 预算是软约束，正确性、契约和验证优先。


## 产品主权门与需求裁决

所有正式功能/修复/重构在 Impact Map 建立后、Architecture Risk Gate 之前使用 `$ai-auto-test-platform-product-sovereignty` 做轻量 `PRODUCT_AUTHORITY_GATE`：

- 纯内部工程实现或不改变产品语义的视觉细节 → `PRODUCT_DECISION_NOT_REQUIRED`，不得为了形式生成产品分析；
- 当前 R4.2 权威事实已明确且一致 → `PRODUCT_FACT_FOUND`，记录最小 `authority_refs` 后继续；
- 权威事实缺失 → `PRODUCT_DECISION_REQUIRED`；当前候选权威冲突 → `PRODUCT_CONFLICT_DETECTED`；用户请求改变冻结产品范围/业务规则/状态/权限/公开契约/验收行为 → `PRODUCT_SCOPE_CHANGE`。若该问题尚无用户明确裁决，记录 `user_decision_status=PENDING` 并进入 `BLOCKED_BY_PRODUCT_DECISION`；若当前请求/既有明确用户裁决已经唯一决定该产品语义，必须记录 `CONFIRMED`，禁止重复询问，转入 `AUTHORITY_UPDATE_ONLY`。
- 产品门只拥有事实检索、差异分析、方案比较和**推荐权**，不拥有批准、冻结或覆盖产品事实的权限；`recommendation != approval`。
- 未决时应形成紧凑 Product Decision Pack，给出 2–4 个可实施候选、唯一推荐及业务/UI/API/数据/状态/权限/Runner/验收影响，让用户直接裁决；不得只问“这里怎么处理”。如果用户当前请求本身已经给出足够明确的产品裁决，则 Decision Pack 只记录该裁决、来源与影响，不得为了形式制造 A/B/C 或再次要求确认。
- 用户确认导致**新增、修改、删除产品事实，解决权威冲突或形成产品范围变化**时，`authority_update_required=true`；此时只允许 `AUTHORITY_UPDATE_ONLY` 同步受治理权威事实，禁止 Architecture/Implementation。权威事实更新后必须重新执行产品门并得到 `PRODUCT_FACT_FOUND`，代码不得先成为事实源。
- Task Context Pack 保存 `product_authority` slice；同一 workspace/scope 且 CURRENT 的结论优先复用。只有真实 Product/Authority 影响扩张或权威事实变化才重新执行门禁，避免常驻 PM Lane 增加 Token。

产品主权仍属于用户。本项目当前**不新增 Product Manager Agent**；只有未来真实使用证明产品分析需要独立长期上下文时，才评估只读 `product_decision_analyst`。


## 按风险触发的技术架构裁决

所有正式编码在 Impact Map 后使用 `$ai-auto-test-platform-architecture` 判定架构风险，但架构师**不是常驻万能 Agent**：

- `ARCH_LOW`：局部实现、契约/状态Owner/事务/依赖方向不变；不调用架构 Agent；
- `ARCH_MEDIUM`：既有边界内新增 Service/Repository/Handler 等；由当前实现 Agent 内嵌轻量 Architecture Check；
- `ARCH_HIGH`：状态Owner、事务/一致性、Event/Outbox、并发/锁/租约/fencing、Runner/Worker/Scheduler/Execution联动、恢复/迁移、重大依赖边界或领域重构；才调度只读 `solution_architect`。

`solution_architect` 只裁决技术架构，不拥有产品主权，不修改代码/契约/DDL/冻结基线。未定义事项若改变用户行为、业务/状态、API/数据/事件、权限安全或跨模块业务/恢复语义，必须输出 `BLOCKED_BY_PRODUCT_DECISION`。ARCH_HIGH 默认只在修改前调用一次；真实 diff/IMPACT_EXPANSION 新增架构域时才允许 `ARCH_RECHECK_REQUIRED`。

Task Context Pack 中若已有 `freshness=CURRENT` 的 Architecture Decision，各 Implementer 必须复用；若仅发生非架构型 delta refresh 使 `pack_revision` 前进，先执行 **revision rebind** 更新 `assessed_pack_revision` 并保持 `recheck_required=false`，禁止为了版本号变化重复 ARCH_RISK 判级或再次调用 `solution_architect`。

## 业务驱动 UI/UX 与反机械化规则

所有用户可见前端页面变更必须使用 `$ai-auto-test-platform-business-ui-ux`：

- 先按角色、核心任务、操作频率、风险、信息优先级、状态和操作路径设计，再进入 Vue/Element Plus 实现。
- 禁止把“欢迎语 + 英文Eyebrow + KPI卡片墙 + 表格”作为所有页面默认模板；Element Plus 只是组件库，不是信息架构。
- 项目/环境等管理页、用例编辑、AI探索/录制、执行/Runner、报告/诊断、系统治理必须按不同业务工作台原型设计。
- 允许在不改变冻结业务语义、API、状态、权限和安全边界的前提下自主决定布局、视觉层级、组件组合、密度、Design Token 和交互表现。
- UI_LOW/UI_MEDIUM 默认由 `frontend_implementer` 内嵌完成，避免额外 Agent Token；UI_HIGH、新核心工作台或大规模重设计才调用 `business_ui_ux_designer`，实现后调用 `ui_ux_reviewer`。现有页面 UI_HIGH 重设计必须在写代码前先做 Pre-change Browser Baseline；若环境阻断则使用 `SOURCE_BASED_CURRENT_UI_BASELINE`、标记 `VISUAL_BASELINE_CONFIDENCE = LIMITED` 并保留 `POST_CHANGE_BROWSER_VERIFY = REQUIRED`，禁止伪造 Before；新页面明确 N/A。
- `ui_verifier` 负责真实浏览器功能/状态验证，`ui_ux_reviewer` 负责业务信息架构与反机械化体验，两者不得重复完整审查。

## 项目级 Custom Agents

Codex 项目级原生 Agent 位于 `.codex/agents/*.toml`。跨前后端任务由 `$ai-auto-test-platform-feature-orchestrator` 编排，优先使用：

- `context_impact_analyst`
- `solution_architect`
- `contract_guardian`
- `backend_implementer`
- `database_integrity_reviewer`
- `security_rbac_reviewer`
- `business_ui_ux_designer`
- `frontend_implementer`
- `ui_verifier`
- `ui_ux_reviewer`
- `code_quality_reviewer`
- `independent_code_reviewer`

只读审查 Agent 不得修改工作区；实现 Agent 必须遵循根 AGENTS、对应 Skill 和 R4.2 正式契约。`.agents/agent-roles/**` 为角色文档与正式兼容回退：若当前 Codex 运行时不能可靠按名称选择 `.codex/agents/*.toml`，禁止用 generic subagent 冒充命名 Agent 已生效，必须由主 Agent 显式加载对应 Role Card + Skill 串行执行并标记 `CUSTOM_AGENT_ROUTING = FALLBACK_SERIAL`。
