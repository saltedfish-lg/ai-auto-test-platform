---
name: ai-auto-test-platform-frontend
description: AI自动化测试执行平台 Vue 3 前端正式实现 Skill；适用于页面、组件、路由、Pinia、Element Plus、OpenAPI客户端、权限UI及前端测试。
---

# AI Auto Test Platform Frontend

## 入口

每次执行先读取：

1. 根 `AGENTS.md`；
2. `.agents/skills/ai-auto-test-platform-core/SKILL.md` 及与任务相关 references；
3. 本 Skill 的 `references/repository-map.md` 与 `references/engineering-autonomy.md`；
4. 当前任务相关的 R4.2 权威 YAML / OpenAPI / 状态 / 权限契约；
5. `apps/web` 现有代码和测试。

## 范围

默认修改 `apps/web/**`。跨到后端、DDL、OpenAPI 时先路由到相应 Skill，不要在前端自行发明契约。

## 技术栈固定事实

Vue 3.5、TypeScript 5.9、Vite 7、Vue Router、Pinia、Element Plus、Zod、Vitest、Testing Library、Playwright Test。

## 强制规则

- `src/generated/**` 只由 `tools/openapi_client.py` 生成，禁止手改。
- 前端只能消费正式 Operation/DTO/Schema/ProblemDetails；不能用 `any`、临时本地类型或硬编码字段绕过契约差异。
- Access Token 仅运行时内存；Refresh Token 仅 HttpOnly Cookie；禁止 localStorage/sessionStorage/IndexedDB 持久化。
- UI 权限是体验层，不是安全边界；服务端 403 必须正确处理。
- 不写死 admin 特权，不把角色名直接当 permission code。
- 页面必须处理必要的 loading/empty/error/forbidden/disabled/optimistic-conflict 状态。
- 不用 Mock API 掩盖正式 API 缺失。组件测试允许 mock，但必须标注测试层级，不能冒充真实集成验收。
- 基线未定义的纯 UI/工程实现按 Engineering Autonomy 自主决定。

## 实现流程

1. 识别当前页面对应菜单、权限、对象、Operation、状态；
2. 检查 generated client 是否已有正式 API；没有则先判断是生成物未同步还是契约确实未定义；
3. 设计页面信息架构和组件边界；
4. 实现路由、Store/Composable、页面和组件；
5. 完成错误态、权限态、并发/版本冲突交互；
6. 增加 Vitest/Testing Library 测试；
7. 对正式可运行页面执行 Playwright/浏览器验证；
8. 运行 `npm run typecheck:web`、`npm run lint:web`、`npm run test:web`、`npm run build:web`，以及需要时 `npm run check:api`。

## 完成条件

代码、类型、测试、构建通过；无手改 generated；无契约自创；关键 UI 状态与权限行为有验证证据。
