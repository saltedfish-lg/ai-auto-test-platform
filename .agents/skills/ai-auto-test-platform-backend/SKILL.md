---
name: ai-auto-test-platform-backend
description: AI自动化测试执行平台 FastAPI 后端正式实现 Skill；适用于API、应用服务、领域规则、SQLAlchemy持久化、事务、审计、幂等和后端测试。
---

# AI Auto Test Platform Backend

## 入口

先读根 `AGENTS.md`、core Skill、本 Skill references、任务相关 R4.2 六份核心 YAML 与工程契约，然后读真实代码。

## 默认修改范围

- `services/api/**`
- 必要时：`packages/domain-kernel/**`、`packages/contracts/**`、`packages/observability/**`、`tests/**`
- 只有任务明确涉及调度、后台任务或 Runner 时进入 `workers/**` / `runner/**`

## 强制规则

- 正式公开 API 必须来自冻结 OpenAPI；禁止自创 Operation/DTO/状态/错误码。
- 正式字段和关系必须来自 DDL/对象映射；`docs/baseline/**` 只读。
- 禁止 SQLite、Mock Repository、内存字典、JSON 文件冒充 MySQL 8.4 正式持久化。
- 外部写操作落实当前 contracts 要求的 idempotency / expected version / RBAC / data scope / state guard。
- 状态、审计、Outbox、幂等记录等要求同原子动作时必须同事务提交。
- 领域/应用/基础设施边界以“职责”而非为了形式主义强拆层；现有项目未预建完整业务目录，允许按 Engineering Autonomy 渐进建立清晰结构。
- 日志不得包含 password/hash/access token/refresh token/cookie/secret/database credential。
- 基线未定义的纯工程实现自主决定；产品级未决事项才升级。

## 实现流程

1. 从 Operation/对象/权限/状态/DDL 形成最小追踪矩阵；
2. 检查现有 `platform_api`、packages、tests，可复用则复用；
3. 建立/扩展 Pydantic DTO 适配层、应用服务、领域规则、Repository/Unit of Work 等必要内部结构；
4. SQLAlchemy 映射与正式 DDL 对齐；
5. 实现事务、幂等、乐观锁、审计/Outbox；
6. 实现 FastAPI 路由、认证/授权依赖、ProblemDetails；
7. 增加 unit / contract / integration 测试；
8. 运行 Ruff、mypy、pytest、OpenAPI/contract 校验与相关 build。

## 完成条件

无契约自创、无假持久化、事务和授权正确、测试覆盖关键失败路径和并发/版本语义、当前任务对应命令通过。
