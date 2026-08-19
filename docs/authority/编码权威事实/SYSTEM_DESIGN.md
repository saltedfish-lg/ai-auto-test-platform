# AI自动化测试执行平台系统设计（当前 Living Authority 阅读投影）

> GENERATED_PROJECTION · NON_AUTHORITATIVE · DO_NOT_EDIT_MANUALLY  
> 权威源：`SYSTEM_DESIGN.yaml`；权威模型：`SINGLE_LIVING_AUTHORITY`；生成器：`tools/authority_projection.py`。

## 当前架构

模块化单体控制面 + 独立Runner Agent + 异步Worker + Outbox事件

## 当前工程事实

- 前端：`Vue 3 + TypeScript`；API：`Python 3.12 + FastAPI`；Runner：`Python 3.12 + Playwright Web`。
- 状态维度：124。
- 数据库：86 张表；Migration：`V3__platform_contract_rebuild.sql → V4__rbac_seed_data.sql → V5__platform_authentication_contract.sql → V6__p1_auth_governance_closure.sql → V7__p1_remaining_authentication_closure.sql → V8__retire_platform_design_baseline_release.sql → V9__project_management_foundation.sql`。
- RBAC：50 个权限点、12 个角色模板、600 条映射。
- 权限解析：每个受保护请求实时读取关系型RBAC、项目职责和数据范围。

## Runtime Gates

|Gate|Scope|Command|
|---|---|---|
|AUTH_MYSQL_RUNTIME_GATE|AUTH_RBAC|python tools/gates/auth_mysql_gate.py|
|AUTH_BROWSER_RUNTIME_GATE|AUTH_RBAC|python tools/gates/auth_browser_gate.py|
|FULL_SCHEMA_MYSQL84_RUNTIME_GATE|DATABASE_SCHEMA|python tools/mysql84_gate.py --execute|
|REAL_ACCEPTANCE_GATE|ACCEPTANCE|task-specific acceptance tests|

## Authority 规则

- 当前事实源仅为 `docs/authority/**` 的 Single Living Authority。
- 本文件是生成投影，不得人工编辑；`python tools/authority_projection.py check` 必须通过。
