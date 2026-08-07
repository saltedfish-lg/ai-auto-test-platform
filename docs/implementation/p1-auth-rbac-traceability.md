# P1 身份认证与 RBAC 当前实现追踪

- 当前发布基线：`PDBR-2026.08.07-R4.2`
- 当前版本：`1.4.2-auth-contract-completion`
- 权威模型：`AUTHORITY-MODEL-R4.2-001`
- 实现阶段：P1
- 文档状态：`READY_FOR_P1_IMPLEMENTATION`
- 当前基线导航：`docs/baseline/CURRENT = R4.2`
- 当前编码事实源：仅使用 `docs/baseline/R4.2/**`；`R4.1` 仅作为历史父基线和升级来源，不得反向覆盖当前实现。
- 历史阻断证据：`docs/implementation/history/p1-auth-rbac-traceability-r4.1-blocked.md`

## 当前准入结论

R4.2 已关闭 R4.1 在真实 P1 实施中暴露的认证契约缺口。Release 状态为 `P1_AUTHENTICATION_CONTRACT_COMPLETED`，`code_readiness=READY_FOR_P1_IMPLEMENTATION`，`pending_user_decisions=0`。当前可以恢复“身份认证 + 默认 admin + RBAC”正式业务实现，但业务代码尚未因此自动视为完成。

基线冻结统计：

- DDL 表：84
- 外键：174
- Permission：50
- Role：12
- Role-Permission Mapping：600
- OpenAPI Paths：138
- OpenAPI Operations / TypeScript Client Methods：250
- OpenAPI Schemas / TypeScript Types：464
- Event：628
- Acceptance：1691，`PASSED=0`
- P1认证专项验收范围：`ACC-R3-1602..1688` / `CT-R3-1602..1688`，共87项，当前均为规范态而非业务执行通过。

## 当前权威契约入口

P1实现至少必须读取并追踪以下 R4.2 正式契约：

- `docs/baseline/R4.2/编码冻结基线/AUTHENTICATION_CONTRACT/authentication-contract.yaml`
- `docs/baseline/R4.2/编码冻结基线/OPENAPI/openapi.yaml`
- `docs/baseline/R4.2/编码冻结基线/DATABASE_DDL/database-schema.yaml`
- `docs/baseline/R4.2/编码冻结基线/DATABASE_DDL/V5__platform_authentication_contract.sql`
- `docs/baseline/R4.2/编码冻结基线/STATE_OWNER_REGISTRY/state-owner-registry.yaml`
- `docs/baseline/R4.2/编码冻结基线/PERMISSION_CLOSURE/**`（以实际目录成员为准）
- `docs/baseline/R4.2/编码冻结基线/ACCEPTANCE_CLOSURE/**`
- `docs/baseline/R4.2/编码冻结基线/ADR/ADR-032_P1平台认证凭据与会话契约.md`
- `docs/baseline/R4.2/编码冻结基线/SYSTEM_DESIGN.yaml`
- 六份核心业务 YAML 与根 `AGENTS.md`、活动核心 Skill。

## 契约追踪矩阵

| 主题 | R4.2正式事实 | 主要权威来源 | P1实现落点 / 约束 |
|---|---|---|---|
| 用户对象 | `OBJ-001`；业务唯一身份以正式 `username` 规则为准 | 核心对象/业务规则、DDL | 使用正式用户聚合和 `atp_user`，不得另建平行用户体系 |
| 内置 admin | `OBJ-002`；固定用户名 `admin`；不可删除、禁用、归档、改名或解除超级管理员绑定 | 核心规则、Authentication Contract | 通过显式 Bootstrap 创建，禁止用户名后门 |
| 角色对象 | `OBJ-003` | 核心对象、Permission Closure | 复用正式角色体系 |
| 超级管理员 | `OBJ-004`；正式角色码 `ROLE-SUPER-ADMIN` | 核心规则、Permission Closure | admin权限只能来自正式Role-Permission Mapping |
| 权限对象 | `OBJ-005`；稳定 `permission_code` | Permission Closure | 50个Permission，不得擅自新增或改码 |
| RBAC闭包 | 50 Permission / 12 Role / 600 Mapping；`ROLE-SUPER-ADMIN` 50项均为ALLOWED | Permission Closure、V4 Seed | 从正式关系表实时计算授权，不把权限永久固化进Access JWT |
| 平台凭据 | `AUTH-OBJ-001`；表 `atp_platform_user_credential` | Authentication Contract、V5、DDL | Argon2id PHC、credential_version、force_password_change、失败锁与生命周期均由正式字段承载 |
| Refresh Session | `AUTH-OBJ-002`；表 `atp_auth_refresh_session` | Authentication Contract、V5、DDL | 服务端持久化，仅存Refresh Token SHA-256 Hash，支持rotation/revoke/replay |
| Access JWT | Bearer JWT，RS256，15分钟，60秒时钟偏差；含 `sub/jti/session_id/credential_version`；权限不写入JWT | Authentication Contract、ADR-032 | Access Token只保存在浏览器运行时内存 |
| Refresh Cookie | 7天绝对有效期；HttpOnly、Secure、SameSite=Strict、Path=`/api/v1/auth` | Authentication Contract | 前端JS不得读取Refresh Token；refresh/logout按正式同源校验执行 |
| Session生命周期 | `ACTIVE/ROTATED/REVOKED/EXPIRED/COMPROMISED` | Authentication Contract、State Owner | SessionService为正式Owner；每用户最多5个ACTIVE Session |
| 用户登录状态 | 只有 `ACTIVE` 允许认证；`LOCKED/DISABLED/ARCHIVED/LOGICALLY_DELETED` 禁止登录并撤销会话 | Authentication Contract、用户生命周期 | 不新增 `security_status`；`NORMAL` 仅为派生语义 |
| 临时安全锁 | 15分钟失败锁由凭据 `locked_until` 等正式字段承载 | Authentication Contract | 与管理员业务 `LOCKED` 状态严格区分 |
| 密码哈希 | Argon2id v19，m=65536KiB、t=3、p=1、16字节盐、32字节Hash，PHC字符串 | Authentication Contract | 禁止明文、MD5、直接SHA-256、自研算法 |
| 密码策略 | 12–128字符；至少字母和数字；不强制特殊字符/定期过期；禁止首尾空白、全空白、与用户名相同及正式弱密码集合 | Authentication Contract | 前后端校验不得降低正式策略 |
| admin Bootstrap | 显式 `bootstrap-admin`；秘密只能通过无回显TTY或 `ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；幂等键 `SYSTEM_BOOTSTRAP_ADMIN_V1` | Authentication Contract | 第二次返回 `ALREADY_INITIALIZED`，不得覆盖密码或重置版本 |
| 首次改密 | Bootstrap admin及临时密码用户 `force_password_change=true`；改密前仅允许Me、Change Password、Logout，Refresh禁止 | Authentication Contract、OpenAPI | 改密后清标志、递增credential_version、撤销旧Session并按正式规则建立当前Session |
| Login API | `POST /api/v1/auth/login` / `login_platform_user` | OpenAPI | 匿名；真实数据库+Credential+User状态校验 |
| Refresh API | `POST /api/v1/auth/refresh` / `refresh_platform_session` | OpenAPI | Refresh Cookie + 同源校验；rotation和重放检测 |
| Logout API | `POST /api/v1/auth/logout` / `logout_platform_user` | OpenAPI | Refresh Cookie + 同源校验；按正式幂等语义撤销当前Session |
| Me API | `GET /api/v1/auth/me` / `get_current_user` | OpenAPI | Bearer Access Token；返回正式当前身份/角色/权限摘要 |
| Change Password API | `POST /api/v1/auth/change-password` / `change_current_user_password` | OpenAPI | Bearer Access Token；遵循强制改密、版本递增和Session撤销规则 |
| 401语义 | `AUTH_REQUIRED / AUTH_INVALID_CREDENTIALS / AUTH_TOKEN_INVALID / AUTH_TOKEN_EXPIRED / AUTH_SESSION_REVOKED / AUTH_IDENTITY_NOT_FOUND` | OpenAPI、Authentication Contract | 使用正式统一错误模型 |
| 403语义 | `AUTH_PERMISSION_DENIED / AUTH_ACCOUNT_LOCKED / AUTH_ACCOUNT_DISABLED / AUTH_ACCOUNT_ARCHIVED / AUTH_ACCOUNT_TEMPORARILY_LOCKED / AUTH_PASSWORD_CHANGE_REQUIRED / AUTH_OPERATION_FORBIDDEN_FOR_STATE` | OpenAPI、Authentication Contract | 身份有效但状态/权限禁止时使用正式语义 |
| Migration | `V3 → V4 → V5__platform_authentication_contract.sql` | SYSTEM_DESIGN、DDL | 历史Migration只读；实现不得自创平行认证表 |
| State Owner | 认证专项6个状态Owner、12个受管字段已唯一化 | State Owner Registry、认证专项验证 | User/Credential/Session各自只由正式Owner维护 |
| P1验收 | `ACC-R3-1602..1688` / `CT-R3-1602..1688` 共87项 | Acceptance Closure、Authentication Contract | 当前均为SPECIFIED/NOT_STARTED；实现完成后只能执行并更新真实P1证据，不能冒充全平台验收 |

## 当前已关闭的R4.1阻断

以下历史阻断均已由 R4.2 正式关闭，当前实现不得再次以这些理由自行停止：

1. 登录 / 登出 / 当前用户 API 缺失：**已关闭**，R4.2 冻结5个认证Operation。
2. 平台用户密码凭据物理模型缺失：**已关闭**，新增 `atp_platform_user_credential`。
3. Refresh Session / Token生命周期缺失：**已关闭**，新增 `atp_auth_refresh_session` 和完整rotation/revoke/replay契约。
4. admin初始凭据产生与交付规则缺失：**已关闭**，正式采用显式安全Bootstrap。
5. `ACTIVE / ENABLED / NORMAL` 状态语义冲突：**已关闭**，`ACTIVE`为唯一允许认证的用户业务状态，`NORMAL`仅为派生语义，不新增 `security_status`。

如果后续实现又发现新的、R4.2确实未定义且会改变产品主权/正式契约的问题，应产生新的待确认项；不得把上述已关闭历史缺口重新当作当前阻断。

## 当前实现边界

P1只实现：

- 平台用户身份认证；
- 平台密码Credential；
- 默认admin安全Bootstrap；
- Access JWT / Refresh Session；
- Login / Refresh / Logout / Me / Change Password；
- 后端RBAC授权；
- Vue登录、受保护路由和本阶段正式权限体验；
- 与上述能力直接相关的审计、状态、数据库和P1验收。

P1不得自动进入：

- 项目/环境/业务终端；
- Runner；
- 测试资产；
- AI探索/人工录制；
- 调度/锁/租约；
- 正式自动化执行；
- 报告/制品；
- 模型管理等后续业务域。

## 门禁与验收语义

R4.2基线治理验证与MySQL 8.4契约门禁已经证明“契约可实现”，但不能替代P1真实业务实现与验收。当前语义必须保持：

```text
BASELINE_R4_2 = PASS
AUTH_CONTRACT_GOVERNANCE = PASS
P1_IMPLEMENTATION = NOT_YET_COMPLETED
P1_AUTH_RBAC_ACCEPTANCE = NOT_YET_COMPLETED
REAL_PLATFORM_ACCEPTANCE = NOT_COMPLETED
```

P1完成后必须使用真实MySQL 8.4、正式Migration/Seed、真实API/Vue闭环和对应 Acceptance 项产生实施证据。
