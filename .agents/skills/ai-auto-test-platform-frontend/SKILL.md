---
name: ai-auto-test-platform-frontend
description: AI自动化测试执行平台 Vue 3 前端正式实现 Skill；适用于页面、组件、路由、Pinia、Element Plus、OpenAPI客户端、业务UI/UX、权限UI及前端测试。
---

# AI Auto Test Platform Frontend

## 入口

每次执行先：

1. 读取根 `AGENTS.md`；
2. 使用 `$ai-auto-test-platform-context-efficiency` 复用/建立当前任务 Task Context Pack；
3. 精准读取 `.agents/skills/ai-auto-test-platform-core/SKILL.md` 及任务相关 references；
4. 读取本 Skill 的 `references/repository-map.md` 与 `references/engineering-autonomy.md`；
5. 只加载当前任务相关的 当前 authority 权威角色/场景/菜单/对象/状态/权限/OpenAPI 片段；
6. 检查 `apps/web` 当前代码和相关测试。

不要无条件通读完整当前 Authority、完整OpenAPI或所有前端文件。

## 范围

默认修改 `apps/web/**`。跨到后端、DDL、OpenAPI 时先路由到相应 Skill，不要在前端自行发明契约。

## 技术栈固定事实

Vue 3.5、TypeScript 5.9、Vite 7、Vue Router、Pinia、Element Plus、Zod、Vitest、Testing Library、Playwright Test。

## 强制规则

- 编码时同时遵循 `$ai-auto-test-platform-code-quality` 的 **Implementation Standards Mode**；
- Implementation 完成后、进入 Verification 前，必须基于 `workspace_snapshot.py delta` v4 机械产生的本 Task `changed_symbols / changed_line_ranges` 运行 code-quality `scripts/comment_quality_gate.py --task-delta ... --checkpoint ...`；不得仅传 changed path 触发整文件历史扫描。只对本 Task 真正改动的复杂符号要求中文原因型注释/Docstring，简单 CRUD/generated 不强制；
- 用户可见页面变更同时遵循 `$ai-auto-test-platform-business-ui-ux`；先理解业务，再设计UI；
- `src/generated/**` 只由 `tools/openapi_client.py` 生成，禁止手改；
- 前端只能消费正式 Operation/DTO/Schema/ProblemDetails；不能用 `any`、临时本地类型或硬编码字段绕过契约差异；
- Access Token 仅运行时内存；Refresh Token 仅 HttpOnly Cookie；禁止 localStorage/sessionStorage/IndexedDB 持久化；
- UI 权限是体验层，不是安全边界；服务端 403 必须正确处理；
- 不写死 admin 特权，不把角色名直接当 permission code；
- 页面必须处理必要的 loading/empty/error/forbidden/disabled/conflict/running/partial-failure 状态；
- 不用 Mock API 掩盖正式 API 缺失；组件测试允许 mock，但不得冒充真实集成验收；
- 当前 Authority 未定义的纯 UI/视觉/工程实现按 Engineering Autonomy 自主决定；若页面变更暗含新的产品能力、业务/状态、权限、公开契约或验收语义，先使用 `$ai-auto-test-platform-product-sovereignty`，不得由前端交互设计反向创造产品规则；
- 不得默认使用“欢迎语 + 英文Eyebrow + KPI卡片墙 + 表格”作为所有业务页面模板；
- Element Plus 是组件库，不是信息架构。应按测试业务选择 table、split-pane、master-detail、editor、timeline、monitoring 等结构。

## UI风险分级

- UI_LOW：局部样式/文案/单控件；内嵌轻量Business UX清单；
- UI_MEDIUM：新增常规页面/复杂表格表单/详情；内嵌生成紧凑Business UX Spec；
- UI_HIGH：AI探索、录制、执行、Runner、报告等核心工作台或大规模重设计；可由父编排按需选择 `business_ui_ux_specialist` 的 `DESIGN_MODE`，实现后仅在 UI_HIGH/明确要求时使用同一角色 `REVIEW_MODE`。

## 实现流程

1. 用 Context Efficiency 确认当前页面的菜单、角色、权限、对象、Operation、状态和跨层消费者；
2. 检查 generated client 是否已有正式 API；没有则判断生成物未同步还是契约确实未定义；
3. UI_HIGH 且为现有页面重设计时，编码前先取得 `PRE_CHANGE_EVIDENCE`；若真实 Before 因环境阻断则使用 `SOURCE_BASED_CURRENT_UI_EVIDENCE` 并标记 `VISUAL_EVIDENCE_CONFIDENCE = LIMITED`、`POST_CHANGE_BROWSER_VERIFY = REQUIRED`，禁止伪造截图；随后使用 Business UI/UX Skill 回答 WHO/WHY/WHAT/FREQUENCY/RISK/PRIORITY/STATE/FLOW；
4. 选择页面原型并形成轻量设计决策/Business UX Spec；
5. 设计页面信息架构和组件边界；
6. 实现路由、Store/Composable、页面和组件；
7. 完成错误态、权限态、并发/版本冲突和危险动作交互；
8. 增加 Vitest/Testing Library 测试；
9. 对正式可运行页面执行 Playwright/浏览器验证；
10. 修改完成后执行 Context Efficiency 的全局反查，发现新消费者时继续补改；
11. 运行 `npm run typecheck:web`、`npm run lint:web`、`npm run test:web`、`npm run build:web`，以及需要时 `npm run check:api`。

## 完成条件

代码、类型、测试、构建通过；无手改 generated；无契约自创；关键 UI 状态与权限行为有验证证据；UI_MEDIUM/UI_HIGH有明确业务信息层级；UI_HIGH通过业务UI/UX独立审查；现有页面重设计具备同 viewport/关键状态的 Before/After 证据；Post-change Impact Closure 为 PASS 或明确环境阻断。
