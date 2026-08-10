---
name: ai-auto-test-platform-context-efficiency
description: AI自动化测试执行平台上下文效率与影响闭包Skill；通过全局影响检索、精准上下文加载和修改后闭环验证降低Codex Token消耗，同时保持跨模块修改完整性。
---

# Context Efficiency & Impact Closure

## 目标

降低模型上下文中的无关正文和重复探索，不降低检索覆盖率、契约完整性、跨模块影响分析、测试强度或最终审查强度。

核心原则：

> **全局检索不缩水，模型加载才收敛。**
>
> Context Efficiency ≠ Less Investigation。

本 Skill 只优化“进入模型的上下文载荷”，不得把 Token 节省作为漏检、跳过验证、跳过事实源或缩小测试范围的理由。

## 何时使用

所有正式编码、修复、重构、契约联动、数据库联动、UI功能变更和代码审查都可使用本 Skill。

- **LOCAL**：单文件/单组件/单函数且外部契约不变；由当前 Agent 内嵌执行，不额外启动子 Agent。
- **CROSS_MODULE**：涉及两个及以上模块、API/DB/generated/权限/状态/事件/Runner/Worker；必须完成 Pre-change Impact Closure。
- **HIGH_RISK**：认证、RBAC、状态机、事务、并发、锁/租约/fencing、Runner调度、正式OpenAPI/DDL/事件契约、高风险UI操作；必须扩大检索半径并完成 Post-change Closure Verification。

若父编排已提供同一 workspace 状态、同一 scope 的 `Task Context Pack`，优先复用；只有缺失、过期或发现新影响时才重新探索。

## 一、Pre-change Impact Closure

### 0. 任务起点 Workspace Snapshot

正式修改开始前、任何工作区写入之前，若当前目录是可读 Git workspace，先使用 `scripts/workspace_snapshot.py capture` 建立 task-start snapshot（`snapshot_version=2`，绑定 resolved root 与 repository identity）。快照只读采集任务开始时已有的 tracked dirty、untracked、tracked-but-deleted 路径，并对已有 dirty/untracked 文件做内容指纹；必须写到仓库外临时/任务制品路径；脚本会拒绝位于 workspace 内的 snapshot/delta 输出，禁止为了记录快照制造新的仓库 untracked 文件。Git workspace 查询通过临时 `GIT_INDEX_FILE` 副本执行，真实 repository/worktree index 必须保持字节不变。

- 无 `.git`：`git_workspace.status=NOT_APPLICABLE`；
- 有 `.git` 且 Git metadata 可读：`COMPLETE`；
- 有 `.git` 但 Git 命令/metadata 读取失败：`UNAVAILABLE`，不得伪造 fingerprint。

`CROSS_MODULE/HIGH_RISK` 必须建立 task-start snapshot；正式 LOCAL 修改在 Git 可用时也默认建立。后续 Review/Impact Closure 只把相对 task-start 新发生的 workspace 变化归因给当前任务。

### 1. 建立检索种子

从用户任务、当前代码和权威事实中提取：

- 对象名、类名、函数名、字段名；
- API path / operationId / DTO / ProblemDetails；
- 表、列、索引、FK、Migration；
- permission code、角色、状态枚举、事件名；
- 路由、页面、Store、Composable、generated type；
- Runner/Worker/Lease/Lock/Fencing/Idempotency/Outbox 等技术词；
- 旧符号与拟引入的新符号。

### 2. 宽检索，窄输出

优先运行 `scripts/impact_scan.py` 或等价的 `rg`/LSP/AST 引用检索。`impact_scan.py` 必须按 `schemas/context-policy.yaml` 的 `required_roots / optional_roots / governance_roots` 执行，动态解析 `docs/baseline/CURRENT`，对超大文本逐行流式扫描；不得用文件大小阈值静默跳过权威 YAML。required scope/CURRENT/活动文本扫描不完整时必须 fail-closed，`closure_safe=false` 并禁止 `IMPACT_CLOSURE_PASS`。若根目录存在 `.git` 但只读 Git metadata 无法读取，同样不得宣告 closure safe：扫描器必须输出 `git_workspace.status=UNAVAILABLE`、`closure_safe=false`。

检索覆盖必须包含当前活动实现、根级工程事实与当前权威基线：

- `AGENTS.md`；
- `package.json`、`package-lock.json`、`pyproject.toml`、`requirements-dev.lock`、`.env.example`、`.editorconfig`、`.gitattributes`、`.gitignore`；
- `apps/**`、`services/**`、`workers/**`、`runner/**`、`packages/**`、`tests/**`、`tools/**`；
- `db/**`、`.github/**`（存在时作为 optional scope）；
- `docs/baseline/CURRENT` 标记及其指向的当前正式基线；
- `.agents/**`、`.codex/**` 仅在 Agent/Skill/Orchestrator/Codex 治理任务时使用 `--include-governance` 条件扩张，普通业务任务不得无条件全量扫描治理目录。

默认不把 `.git/**`、`node_modules/**`、构建产物、缓存、虚拟环境和历史父基线正文作为活动上下文；但必须搜索活动代码中对历史版本/路径的引用。迁移、溯源任务才按需加入历史基线。

全局检索结果先只保留：`路径 + 命中数 + 行号 + 符号/短片段`，不要立即读取每个命中文件全文。扫描结果必须显式报告 `scope_status`、`closure_safe`、`current_baseline`、missing required/optional roots、large files streamed、binary skipped、scan errors，以及只读 Git workspace 的 `status / tracked_deleted / read_error`。任何 required scope/CURRENT 解析失败都不能静默当作“无命中”；即使工作树中 `.github/**` 等文件已删除，只要仍是 Git tracked-but-deleted，就必须作为 CI/构建/配置影响证据进入闭包判断。若存在 `.git` 但 Git metadata 为 `UNAVAILABLE`，tracked-deleted 证据链不完整，`closure_safe` 必须为 false；`CROSS_MODULE/HIGH_RISK` 或 CI/依赖/构建/部署/环境配置/工程工具类任务进入 `BLOCKED_BY_ENVIRONMENT`。

### 3. 建立 Impact Map

至少按以下维度判断是否受影响：

- Product / Authority
- API / Contract / Generated Client
- Database / Migration / Transaction
- Backend / Domain / Application / Infrastructure
- Frontend / Route / Store / Component / View
- Auth / RBAC / Data Scope / Security
- State / Event / Concurrency / Runner / Worker
- Tests / Fixtures / E2E
- Observability / Audit / Artifact
- Architecture / Ownership / Transaction / Consistency

发现高风险信号时按 `references/risk-escalation.md` 自动扩张影响图，不得因为初始任务描述只提到一个文件就停止。

### 4. 形成 Task Context Pack

按 `references/task-context-pack.md` 输出最小任务上下文。Task Context Pack 是“索引”，不是权威事实本身；`CROSS_MODULE/HIGH_RISK` 必须带 workspace fingerprint，并引用 task-start snapshot。正式修改在 Git 可用时应记录 `workspace_fingerprint.task_start/current/task_delta`。后端/DB/契约/权限/状态等阶段产生实质变更后，先用 `workspace_snapshot.py delta` 计算相对任务起点的 `task_delta_paths`，再基于这些真实任务变化做 delta refresh 并递增 `pack_revision`；任何 Agent 怀疑其不完整或发现 `STALE` 时必须增量检索。

## 二、Precision Context Loading

按以下顺序加载：

1. 路径、符号、标题、局部命中；
2. 相关函数/类/组件/配置块；
3. 直接上下游调用点；
4. 对应权威事实片段；
5. 只有在局部信息无法证明正确性时才升级读取整文件；
6. 只有跨文档冲突/完整状态机/完整契约验证需要时才扩大到完整文档。

禁止设置会截断正确性的硬 Token 上限。Token Budget 只能是软预算；**Correctness Wins**。

子 Agent 只接收与职责直接相关的 Task Context Pack 切片，并携带：

- authority_refs
- affected_paths
- affected_symbols
- invariants
- forbidden_changes
- validation_targets
- unresolved_risks

禁止所有子 Agent 无条件重复通读 AGENTS、完整基线、完整 OpenAPI 和全仓库源码。

## 三、Post-change Closure Verification

完成修改后，先用 task-start snapshot 计算 `task_delta_paths`，再结合真实 diff / changed files 重新提取。`task_delta_paths` 用于区分“任务开始前已存在的 dirty workspace”与“当前任务真正新增/继续修改的变化”；如果某文件任务开始前已 dirty，但本任务再次改变其内容，内容指纹变化仍必须把它纳入本任务 delta。随后提取：

- 被删除/重命名的旧符号；
- 新增/修改的符号；
- API path / DTO / schema；
- DB 表列/约束；
- permission/status/event；
- route/store/component；
- 配置键、环境变量和工具入口。

随后执行全局反查；若只读 Git metadata 显示 tracked-but-deleted 路径（尤其 `.github/**`、构建/环境/部署配置），即使当前文件系统无正文也必须评估其消费者/删除状态是否属于本次影响。不得把任务开始前已有的全部 `git diff` 无差别归因给当前任务；优先围绕 `task_delta_paths` 展开，再对旧/新符号做全局消费者闭包：

1. 搜旧符号是否仍有活动引用；
2. 搜新符号是否所有消费者都已更新；
3. 检查 generated client 与正式 OpenAPI 是否一致；
4. 检查 DB mapping/Migration/测试是否闭合；
5. 检查权限、状态、事件、Runner/Worker消费者；
6. 检查前端路由、Store、组件、页面和E2E；
7. 检查测试、fixture、工具脚本和审计/可观测入口；
8. 运行与风险相称的 typecheck/lint/test/build/contract/integration/browser 验证。

如果发现初始 Impact Map 之外的新真实消费者，状态必须变为：

`IMPACT_EXPANSION`

然后扩张 Task Context Pack、补改、重新验证，直到闭环。

## 四、完成状态

只允许以下结论：

- `IMPACT_CLOSURE_PASS`：影响面、修改、反查和验证闭合；
- `IMPACT_EXPANSION`：发现新消费者，必须继续处理；
- `BLOCKED_BY_PRODUCT_DECISION`：产品主权门发现 `PRODUCT_DECISION_REQUIRED / PRODUCT_CONFLICT_DETECTED / PRODUCT_SCOPE_CHANGE` 且 `user_decision_status=PENDING`，需要用户裁决；
- `AUTHORITY_UPDATE_ONLY`：用户已经明确裁决产品缺口/冲突/范围变化，但受治理当前权威事实尚未同步；只允许权威事实更新并重新执行产品门，禁止 Architecture/Implementation，也禁止重复询问同一决定；
- `BLOCKED_BY_ENVIRONMENT`：验证因环境缺失无法执行，或存在 `.git` 但 Git metadata 无法读取导致 tracked-deleted/task-start 证据链不完整；必须列出未验证项，禁止冒充通过；
- `BLOCKED_BY_INCOMPLETE_SCOPE`：required scope/CURRENT/活动文本扫描不完整，禁止以不完整检索结果宣告闭环。

## 五、与其它 Skill / Agent 的关系

- `feature-orchestrator`：负责调用本 Skill 的前置和后置门禁；
- `$ai-auto-test-platform-product-sovereignty`：消费 Impact Map 的 Product/Authority slice，在 Architecture 前判断现有权威事实、真实缺口/冲突/范围变化；本 Skill 只负责检索和 freshness，不替产品门批准需求；
- `backend_implementer` / `frontend_implementer`：默认内嵌使用，不为简单任务额外启动 Agent；
- `context_impact_analyst`：仅 CROSS_MODULE/HIGH_RISK 或当前代码陌生、影响面不清时独立运行；若当前 Codex 运行时不能可靠选择命名 Custom Agent，则不得用 generic subagent 冒充成功，必须由当前 Agent 显式读取 `.agents/agent-roles/context-impact-analyst.md` + 本 Skill 串行执行同职责；
- `solution_architect` / `$ai-auto-test-platform-architecture`：复用同一个 Task Context Pack 的 architecture slice 与当前 `architecture_decision`；若决策仍为 CURRENT 则禁止无条件重新全仓探索或重复裁决；
- Contract/DB/Security/CodeQuality/UI Reviewer：优先消费 Task Context Pack，再在自身职责域增量检索；
- Reviewer 不得把 Task Context Pack 当成不可质疑结论。

## 六、禁止事项

- 通过缩小业务/工程/契约搜索覆盖省 Token；
- 普通业务任务无条件扫描整个 `.agents/**` / `.codex/**` 制造治理噪声；治理变更却未显式 `--include-governance`；
- 忽略 `scope_status=INCOMPLETE` / `closure_safe=false` 继续宣告 Impact Closure；
- 仓库存在 `.git` 且 `git_workspace.status=UNAVAILABLE` 时把 tracked-deleted 缺失当作“无影响”；
- 在 dirty workspace 中只看全量 `git diff` 就把任务开始前已有变化全部冒充当前任务改动；
- 通过最大文件大小阈值静默跳过当前权威事实源；
- 使用截断的命中列表直接宣告 Impact Closure（若限制输出，必须保留/可展开完整索引）；
- 因命中多而只处理前几个文件；
- 只看 diff 不查外部消费者；
- 只看源码不查契约/DB/权限/状态/测试；
- 只读摘要就声称完整理解复杂契约；
- 用 mock/build 成功替代真实集成闭环；
- 多 Agent 重复读取相同大文档却没有新增证据。

## 参考

- `references/impact-discovery.md`
- `references/precision-loading.md`
- `references/risk-escalation.md`
- `references/task-context-pack.md`
- `references/closure-verification.md`
- `references/search-playbook.md`
- `schemas/context-policy.yaml`

- task-start snapshot 的 `snapshot_version`、resolved root 或 repository identity 与 current 不一致时，`task_delta=UNAVAILABLE`（`SNAPSHOT_VERSION_MISMATCH / SNAPSHOT_ROOT_MISMATCH / SNAPSHOT_REPOSITORY_MISMATCH`）并进入 `BLOCKED_BY_ENVIRONMENT`；禁止跨仓库复用 snapshot。
