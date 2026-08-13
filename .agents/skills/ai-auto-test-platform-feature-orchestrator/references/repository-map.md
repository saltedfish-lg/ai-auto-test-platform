# Repository Map & Authority

## 当前权威模型

- 根 `AGENTS.md`: `CURRENT_LIVING_AUTHORITY`
- 权威模型：`SINGLE_LIVING_AUTHORITY`
- 唯一活动事实源：`docs/authority/**`
- 当前 P1：身份认证 + 默认 admin + RBAC 可正式编码
- authority 是受控可变事实源：不得因实现方便擅自改产品语义；用户请求或已确认的 Product/Authority 决策可在 `AUTHORITY_UPDATE_ONLY` 阶段直接同步源文档。
- 不创建 按历史发布号复制的整套 Authority 目录，不维护 CURRENT marker、Authority Copy Manifest 或 Release Snapshot。

## 权威顺序（按职责域）

1. 六份核心 YAML：产品范围、角色场景、对象规则、权限并发、AI/Runner、安全验收；
2. SYSTEM_DESIGN + OpenAPI + DDL + Event + State Owner + Permission / Acceptance contracts：工程和物理实现；
3. ADR：只有同步核心事实/工程契约后才生效；
4. AGENTS / Skills：只管理 Codex 执行流程，不改变产品事实；
5. README、导航 Markdown、DOCX、图：非权威投影。

## 代码目录

- `apps/web`: 前端应用；
- `services/api`: 平台 API 进程与正式后端业务；
- `workers/scheduler`: 调度进程；
- `workers/background`: 后台任务进程；
- `runner/agent`: 独立 Runner Agent；
- `packages/domain-kernel`: 通用领域内核，不应变成业务对象垃圾桶；
- `packages/contracts`: 当前 authority OpenAPI/事件 Schema 加载和验证；
- `packages/observability`: 日志、correlation ID、敏感字段过滤；
- `tests/contract`: 契约验证；
- `tests/integration`: 集成验证；
- `tests/e2e`: 后续真实端到端验证；
- `tools`: 生成、校验、门禁工具。

## 当前 authority 解析规则

活动工具、OpenAPI 生成器与契约加载边界必须直接解析 `docs/authority`；不得要求版本目录、CURRENT marker、Manifest、Release Snapshot 或 Git 元数据。
