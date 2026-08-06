# AGENTS.md — AI自动化测试执行平台 R4.1

## 当前发布

- release_id: `PDBR-2026.08.06-R4.1`
- release_status: `GOVERNANCE_CLEANUP_COMPLETED`
- code_readiness: `READY_WITH_RUNTIME_DB_VALIDATION_PENDING`
- implementation_release_readiness: `NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT`
- pending_user_decisions: `0`

Codex可以初始化Monorepo、前端、API、Worker、Runner、测试和CI，并依据正式契约分阶段编码。MySQL 8.4运行门禁不阻断工程初始化或非数据库模块开发，但在通过前阻断数据库模块正式合并。1691项验收规范保持`SPECIFIED/NOT_STARTED`，仅阻断平台发布结论。

## 按职责域确定权威

1. Release/Manifest只负责当前发布身份、成员、版本、状态和哈希，不改写业务语义。
2. 六份核心YAML负责产品范围、角色场景、对象规则、权限并发、AI/Runner和安全验收业务语义。
3. SYSTEM_DESIGN及DDL、OpenAPI、事件、状态Owner、权限与验收契约负责技术和物理实现，必须服从核心YAML。
4. ADR负责决策和理由；只有同步核心YAML及工程契约后才成为当前实施依据。
5. AGENTS和Skill负责Codex流程、边界和门禁，不得自行改变产品或工程契约。
6. 导航Markdown、DOCX和图形为非权威投影。

权威模型ID：`AUTHORITY-MODEL-R4.1-001`。

## 门禁范围

- `MYSQL84_EMPTY_DATABASE_EXECUTION`: `DATABASE_MODULE_FORMAL_MERGE`。
- `REAL_ACCEPTANCE_EVIDENCE`: `IMPLEMENTATION_RELEASE_READINESS`。
- 两项均不阻断工程初始化。
