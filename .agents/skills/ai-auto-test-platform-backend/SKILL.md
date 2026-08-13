---
name: ai-auto-test-platform-backend
description: AI自动化测试执行平台 FastAPI 后端正式实现 Skill；适用于API、应用服务、领域规则、SQLAlchemy持久化、事务、审计、幂等和后端测试。
---

# AI Auto Test Platform Backend

## 入口

先读根 `AGENTS.md`、core Skill、本 Skill references、任务相关 六份核心 authority YAML 与工程契约，然后读真实代码。

## 默认修改范围

- `services/api/**`
- 必要时：`packages/domain-kernel/**`、`packages/contracts/**`、`packages/observability/**`、`tests/**`
- 只有任务明确涉及调度、后台任务或 Runner 时进入 `workers/**` / `runner/**`

## 强制规则

- 编码时必须同时遵循 `$ai-auto-test-platform-code-quality` 的 **Implementation Standards Mode**；该模式只增加质量约束，不改变本实现 Skill/Agent 的写权限。
- Implementation 完成后、进入 Verification 前，必须基于 `workspace_snapshot.py delta` v4 机械产生的本 Task `changed_symbols / changed_line_ranges` 运行 code-quality `scripts/comment_quality_gate.py --task-delta ... --checkpoint ...`；不得仅传 changed path 触发整文件历史扫描。只对本 Task 真正改动的复杂符号要求中文原因型注释/Docstring，简单 CRUD/generated 不强制。

- 正式公开 API 必须来自当前 authority OpenAPI；禁止自创 Operation/DTO/状态/错误码。
- 正式字段和关系必须来自 DDL/对象映射；`docs/authority/**` 只读。
- 禁止 SQLite、Mock Repository、内存字典、JSON 文件冒充 MySQL 8.4 正式持久化。
- 外部写操作落实当前 contracts 要求的 idempotency / expected version / RBAC / data scope / state guard。
- 状态、审计、Outbox、幂等记录等要求同原子动作时必须同事务提交。
- 领域/应用/基础设施边界以“职责”而非为了形式主义强拆层；现有项目未预建完整业务目录，允许按 Engineering Autonomy 渐进建立清晰结构。
- 日志不得包含 password/hash/access token/refresh token/cookie/secret/database credential。
- 当前 Authority 未定义的纯工程实现自主决定；涉及用户可观察行为、业务/状态、公开契约、权限安全、Runner业务/恢复或验收语义时先使用 `$ai-auto-test-platform-product-sovereignty` 检查当前权威事实，真实缺口/冲突/范围变化才升级用户裁决。

## 实现流程

1. 先消费 Task Context Pack 的 `workspace_fingerprint.task_delta` 与 `architecture_decision`：不得把任务开始前已存在的整个 dirty workspace 当作当前后端改动；若 delta refresh 只是把 `pack_revision` 推进且未引入新的 state owner / transaction / consistency / concurrency / Runner-Worker / dependency domain，则先执行 **revision rebind**，保持 `freshness=CURRENT`、`recheck_required=false` 并更新 `assessed_pack_revision`，不得因此重复判级；rebind 后若其 `freshness=CURRENT` 且对应当前 `pack_revision`，直接遵循已有 `ARCH_RISK / Architecture Check / Architecture Decision`，不得重复判级或再次调度 `solution_architect`；只有决策缺失/STALE、`recheck_required=true` 或真实 `IMPACT_EXPANSION` 引入新架构域时，才使用 `$ai-auto-test-platform-architecture` 重新判断 ARCH_RISK；
2. 从 Operation/对象/权限/状态/DDL 形成最小追踪矩阵；
3. 检查现有 `platform_api`、packages、tests，可复用则复用；
4. 建立/扩展 Pydantic DTO 适配层、应用服务、领域规则、Repository/Unit of Work 等必要内部结构；
5. SQLAlchemy 映射与正式 DDL 对齐；
6. 实现事务、幂等、乐观锁、审计/Outbox；
7. 实现 FastAPI 路由、认证/授权依赖、ProblemDetails；
8. 增加 unit / contract / integration 测试；
9. 运行 Ruff、mypy、pytest、OpenAPI/contract 校验与相关 build。


- task-start snapshot 的 `snapshot_version`、resolved root 或 repository identity 与 current 不一致时，`task_delta=UNAVAILABLE`（`SNAPSHOT_VERSION_MISMATCH / SNAPSHOT_ROOT_MISMATCH / SNAPSHOT_REPOSITORY_MISMATCH`）并进入 `BLOCKED_BY_ENVIRONMENT`；禁止跨仓库复用 snapshot。

## 完成条件

无契约自创、无假持久化、事务和授权正确、测试覆盖关键失败路径和并发/版本语义、当前任务对应命令通过。
