# P1 身份认证与 RBAC 当前实现追踪

## 当前事实源与治理状态

- 当前唯一产品/技术事实源：`docs/authority/**`
- Authority Model：`SINGLE_LIVING_AUTHORITY`
- Git 主权：由用户在 IDEA 中人工查看、提交、推送；Codex 不执行 Git 读写操作。
- 实现阶段：P1 身份认证 + 默认 admin + RBAC。
- 当前 Authority 编码准入：`READY_FOR_P1_IMPLEMENTATION`。
- P1 Auth 当前实现状态：`IMPLEMENTED_PENDING_RUNTIME_VALIDATION`；静态/契约实现已落地，但真实 MySQL 8.4 与 Browser/E2E 运行证据尚未全部闭环。
- GOV-P1-001：**已确认并已纳入当前 Authority**——独立结构化、append-only 认证安全审计。
- GOV-P1-004：**已确认并已纳入当前 Authority**——JWT Key Ring 与安全轮换。
- GOV-P1-002：`TEMPORARY_CREDENTIAL_DELIVERY_AND_WRITE_SEMANTICS`——临时凭据交付及 User/Admin/Role 写侧语义，继续 `BLOCKED_BY_PRODUCT_DECISION`。
- GOV-P1-003：`LOGIN_REFRESH_SOURCE_RATE_LIMIT_POLICY`——Login/Refresh 来源级限流政策，继续 `BLOCKED_BY_PRODUCT_DECISION`。
- GOV-P1-005：`CHANGE_PASSWORD_LOST_RESPONSE_IDEMPOTENT_REPLAY`——Change Password 响应丢失后的幂等重放语义，继续 `BLOCKED_BY_PRODUCT_DECISION`。
- 上述3项均为 deferred product decisions，不阻断当前已批准的P1 Auth实现；其完整问题、缺失事实和阻断范围以 Authentication Contract 的 `product_decision_placeholders` 为唯一当前事实，未经用户裁决不得推导或实现。

当前不存在版本化历史基线目录、CURRENT 指针或 Release Manifest 作为活动编码事实源。历史 release/version 字段仅作为 provenance 保留，不参与当前权威选择。

## 当前准入结论

基础 P1 认证契约与已确认的 GOV-P1-001/004 已统一进入 Living Authority。当前正式实现可继续使用本地已完成的 JWT Key Ring、认证安全审计、默认 admin Bootstrap、Refresh Session、RBAC 和 Vue 登录能力，但必须继续通过当前 Authority Validators 与真实 MySQL/Browser Gate。

当前关键技术事实：

- 数据库表：85（对象表79 + 技术表6）
- 外键：174
- Permission：50
- Role：12
- Role-Permission Mapping：600
- OpenAPI Paths：138
- OpenAPI Operations / TypeScript Client Methods：250
- OpenAPI Schemas / TypeScript Types：464
- Event：628
- Acceptance：1691，当前 `PASSED=0`
- P1认证专项验收：`ACC-R3-1602..1688` / `CT-R3-1602..1688`，共87项，当前仍为规范态
- Migration：`V3 -> V4 -> V5 -> V6__p1_auth_governance_closure.sql`
- 认证 State Owner：7

## 当前权威契约入口

P1 实现至少必须读取并追踪：

- `docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml`
- `docs/authority/编码权威事实/OPENAPI/openapi.yaml`
- `docs/authority/编码权威事实/DATABASE_DDL/database-schema.yaml`
- `docs/authority/编码权威事实/DATABASE_DDL/V5__platform_authentication_contract.sql`
- `docs/authority/编码权威事实/DATABASE_DDL/V6__p1_auth_governance_closure.sql`
- `docs/authority/编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml`
- `docs/authority/编码权威事实/PERMISSION_CLOSURE/**`
- `docs/authority/编码权威事实/ACCEPTANCE_CLOSURE/**`
- `docs/authority/编码权威事实/ADR/ADR-032_P1平台认证凭据与会话契约.md`
- `docs/authority/编码权威事实/ADR/ADR-033_P1认证安全审计与JWTKeyRing治理闭环.md`
- `docs/authority/编码权威事实/SYSTEM_DESIGN.yaml`
- 六份核心业务 YAML、根 `AGENTS.md` 与活动核心 Skill。

## 契约追踪矩阵

| 主题 | 当前 Living Authority 事实 | P1 实现约束 |
|---|---|---|
| 用户对象 | `OBJ-001`，username 为正式业务身份 | 复用 `atp_user`，不得建立平行用户体系 |
| 默认 admin | 固定用户名 `admin`；不可删除/禁用/归档/改名/解绑超级管理员 | 显式 Bootstrap，禁止用户名后门 |
| RBAC | 50 Permission / 12 Role / 600 Mapping | 权限实时从数据库关系计算，不进入 Access JWT |
| 平台凭据 | `AUTH-OBJ-001 / atp_platform_user_credential` | Argon2id、credential_version、force_password_change、失败锁均由正式字段承载 |
| Refresh Session | `AUTH-OBJ-002 / atp_auth_refresh_session` | 服务端持久化，仅存 Refresh Token SHA-256 Hash，支持 rotation/revoke/replay |
| 认证安全审计 | `AUTH-OBJ-003 / atp_auth_security_audit` | 只允许 INSERT；UPDATE/DELETE 由 MySQL trigger 拒绝；敏感状态变更与审计同事务 |
| Access JWT | RS256、15分钟、60秒 clock skew | 通过 `ATP_JWT_KEY_RING_FILE` 加载唯一 active signing key 和 previous verification keys；重叠至少960秒；unknown/expired kid 失败关闭 |
| Refresh Cookie | 7天；HttpOnly、Secure、SameSite=Strict、Path=`/api/v1/auth` | 前端 JS 不得读取 Refresh Token |
| Session 生命周期 | `ACTIVE/ROTATED/REVOKED/EXPIRED/COMPROMISED` | SessionService 为正式 Owner；每用户最多5个 ACTIVE Session |
| 用户登录状态 | 只有 `ACTIVE` 允许认证 | `LOCKED/DISABLED/ARCHIVED/LOGICALLY_DELETED` 均拒绝并撤销 Session |
| 临时安全锁 | 15分钟失败锁由 Credential 字段承载 | 与业务 `LOCKED` 严格区分 |
| admin Bootstrap | `SYSTEM_BOOTSTRAP_ADMIN_V1` | 密码只允许 TTY 或 `ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；失败整体回滚 |
| Migration | `V3 -> V4 -> V5 -> V6` | V6 只承接 GOV-P1-001 审计表和不可变 trigger |
| State Owner | 7个认证语义 | 新增 `AUTH-STATE-007 / AUTH_SECURITY_AUDIT_IMMUTABILITY` |
| P1验收 | 87项 SPECIFIED | 只有真实执行后才允许更新证据，不能把静态验证冒充平台验收 |

## 当前实现边界

P1 当前允许实现：

- 平台用户身份认证；
- 平台密码 Credential；
- 默认 admin 安全 Bootstrap；
- Access JWT / Refresh Session；
- JWT Key Ring 安全轮换；
- Login / Refresh / Logout / Me / Change Password；
- 后端 RBAC 授权；
- Vue 登录、受保护路由和本阶段正式权限体验；
- 认证结构化不可变审计；
- 与上述能力直接相关的状态、数据库和 P1 验收。

P1 不得自动进入：项目/环境/业务终端、Runner、测试资产、AI 探索/人工录制、调度/锁/租约、正式执行、报告/制品、模型管理等后续业务域。

## 当前门禁语义

```text
AUTHORITY_MODEL = SINGLE_LIVING_AUTHORITY
GOV_P1_001 = AUTHORITY_SYNCED_IMPLEMENTED_LOCAL_REVIEW_PASS
GOV_P1_004 = AUTHORITY_SYNCED_IMPLEMENTED_LOCAL_REVIEW_PASS
GOV_P1_002_003_005 = DEFERRED_BLOCKED_BY_PRODUCT_DECISION
P1_AUTH_IMPLEMENTATION_STATUS = IMPLEMENTED_PENDING_RUNTIME_VALIDATION
P1_AUTH_RBAC_ACCEPTANCE = NOT_YET_COMPLETED
REAL_PLATFORM_ACCEPTANCE = NOT_COMPLETED
```

静态 Contract / Authority / OpenAPI / Governance PASS 只证明当前契约与实现可继续推进；真实 MySQL 8.4、真实 API/Vue Chromium 闭环和对应 Acceptance 证据仍需在具备环境条件时执行。
