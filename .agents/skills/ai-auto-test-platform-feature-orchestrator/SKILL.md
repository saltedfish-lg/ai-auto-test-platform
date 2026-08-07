---
name: ai-auto-test-platform-feature-orchestrator
description: AI自动化测试执行平台跨前后端功能编排Skill；按事实源、契约、后端、生成客户端、前端、浏览器验证和独立审查完成闭环。
---

# Full-stack Feature Orchestrator

## 适用

一个任务同时涉及正式 API/数据库/前端页面，或用户要求“完整功能闭环”。

## 编排顺序

1. **事实与范围**：读取 root AGENTS、core Skill、R4.2 权威事实，确定本任务对象/权限/状态/验收边界；
2. **契约守卫**：使用 `$ai-auto-test-platform-api-contract` 确认 OpenAPI/DDL/权限/状态有正式来源；
3. **后端**：使用 `$ai-auto-test-platform-backend`；涉及 P1 认证/RBAC 时追加 `$ai-auto-test-platform-auth-rbac-security`；
4. **数据库**：需要持久化/事务时使用 `$ai-auto-test-platform-database`；
5. **客户端生成**：从正式 OpenAPI 生成/校验 `apps/web/src/generated/**`，禁止手改；
6. **前端**：使用 `$ai-auto-test-platform-frontend`；
7. **UI验证**：有可运行页面时使用 `$ai-auto-test-platform-ui-quality`；
8. **独立审查**：使用 `$ai-auto-test-platform-code-review`；
9. **DoD**：运行与改动范围相符的 `tools/dev.py` / npm / pytest 验证，区分工程测试与正式 acceptance evidence。

## Multi-agent

项目已提供 Codex 原生 Custom Agents：

- `contract_guardian`：只读契约守卫；
- `backend_implementer`：后端正式实现；
- `database_integrity_reviewer`：只读数据库完整性审查；
- `security_rbac_reviewer`：只读认证/RBAC/安全审查；
- `frontend_implementer`：前端正式实现；
- `ui_verifier`：真实浏览器验证，只有父任务明确授权时才修测试/前端缺陷；
- `independent_code_reviewer`：最终只读独立审查。

若当前 Codex 支持 subagent，优先按上述原生 Agent 名称调度；只读 Contract/Security/Review 可并行，写代码阶段优先顺序化，避免前后端同时自行定义同一契约。

`.agents/agent-roles/*.md` 保留为人类可读角色规范和兼容回退说明，不是原生 Agent 注册位置。若运行环境不支持 subagent，主 Agent 按相同 Skill/Role 规则串行执行，不得降低门禁。

## 自主权

遵循 Engineering Autonomy：纯工程实现自行决定；产品级语义缺口才升级用户裁决。
