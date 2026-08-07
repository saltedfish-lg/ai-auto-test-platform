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
