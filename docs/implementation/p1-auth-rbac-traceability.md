# P1 身份认证与 RBAC 当前实现追踪

## 当前事实源与治理状态

- 当前唯一产品/技术事实源：`docs/authority/**`
- Authority Model：`SINGLE_LIVING_AUTHORITY`
- Git 主权：由用户在 IDEA 中人工查看、提交、推送；Codex 不执行 Git 读写操作。
- 实现阶段：P1 身份认证 + 默认 admin + RBAC。
- 当前 Authority 编码准入：`READY_FOR_P1_IMPLEMENTATION`。
- P1 Auth 当前实现状态：`IMPLEMENTED_RUNTIME_VALIDATED`；静态/契约实现、MySQL 8.4 与真实 Chromium Browser/E2E 运行证据均已闭环。
- GOV-P1-001：**已确认并已纳入当前 Authority**——独立结构化、append-only 认证安全审计。
- GOV-P1-004：**已确认并已纳入当前 Authority**——JWT Key Ring 与安全轮换。
- GOV-P1-002：**已确认并已实现到本地验证边界**——`SYSTEM_GENERATED_ONE_TIME_TEMP_CREDENTIAL`，创建/重置凭据只在首次已提交响应交付临时密码，重放不得恢复秘密。
- GOV-P1-003：**已确认并已实现到本地验证边界**——`SOURCE_RATE_LIMIT_ENABLED_MYSQL84`，Login 60/5m、Refresh 300/5m，可信代理边界与MySQL共享窗口失败关闭。
- GOV-P1-005：**已确认并已实现到本地验证边界**——`PASSWORD_CHANGE_REVOKES_REFRESH_SESSIONS_AND_REAUTHENTICATES`，改密返回204、撤销Session、幂等重放且不签发Token。
- 三项决策均已由用户确认并进入当前 Living Authority；`product_decision_placeholders=[]`，不存在剩余产品主权阻断。

当前不存在版本化历史基线目录、CURRENT 指针或 Release Manifest 作为活动编码事实源。历史 release/version 字段仅作为 provenance 保留，不参与当前权威选择。

## 当前准入结论

GOV-P1-001..005 已统一进入 Living Authority，并已实现JWT Key Ring、认证安全审计、默认admin Bootstrap、Refresh Session、实时RBAC、用户治理、共享来源限流、改密幂等与Vue重新认证行为。当前仍须通过真实MySQL 8.4与Chromium Gate后才能更新依赖这些环境的Acceptance证据。

当前关键技术事实：

- 数据库、RBAC、OpenAPI、Event、Acceptance、Migration Head 与协议统计均由 `tools/current_facts.py` 机械派生，本文不复制 current 数字。
- Acceptance 当前数量读取 `tools/current_facts.py#acceptance.count`，`PASSED` 数量读取 `tools/current_facts.py#acceptance.passed_count`；历史 1691 是 OBJ-085 退役前闭包，不是当前口径。
- P1 认证专项验收及 State Owner 以当前 AUTHENTICATION_CONTRACT、ACCEPTANCE_CLOSURE 与 STATE_OWNER_REGISTRY 为准。

## 当前权威契约入口

P1 实现至少必须读取并追踪：

- `docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml`
- `docs/authority/编码权威事实/OPENAPI/openapi.yaml`
- `docs/authority/编码权威事实/DATABASE_DDL/database-schema.yaml`
- `docs/authority/编码权威事实/DATABASE_DDL/V5__platform_authentication_contract.sql`
- `docs/authority/编码权威事实/DATABASE_DDL/V6__p1_auth_governance_closure.sql`
- `docs/authority/编码权威事实/DATABASE_DDL/V7__p1_remaining_authentication_closure.sql`
- `docs/authority/编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml`
- `docs/authority/编码权威事实/PERMISSION_CLOSURE/**`
- `docs/authority/编码权威事实/ACCEPTANCE_CLOSURE/**`
- `docs/authority/编码权威事实/ADR/ADR-032_P1平台认证凭据与会话契约.md`
- `docs/authority/编码权威事实/ADR/ADR-033_P1认证安全审计与JWTKeyRing治理闭环.md`
- `docs/authority/编码权威事实/ADR/ADR-034_P1用户治理来源限流与改密幂等闭环.md`
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
| 来源限流 | `AUTH-OBJ-004 / atp_auth_source_rate_limit` | 直接peer优先、可信代理受控；规范化IP只存HMAC；MySQL固定窗口跨实例一致 |
| 认证HMAC Key Ring | `ATP_AUTH_HMAC_MASTER_KEY_FILE` | 严格JSON、至少32字节master key、HKDF-SHA256三域分离、previous兼容读取至少24小时 |
| Access JWT | RS256、15分钟、60秒 clock skew | 通过 `ATP_JWT_KEY_RING_FILE` 加载唯一 active signing key 和 previous verification keys；重叠至少960秒；unknown/expired kid 失败关闭 |
| Refresh Cookie | 7天；HttpOnly、Secure、SameSite=Strict、Path=`/api/v1/auth` | 前端 JS 不得读取 Refresh Token |
| Session 生命周期 | `ACTIVE/ROTATED/REVOKED/EXPIRED/COMPROMISED` | SessionService 为正式 Owner；每用户最多5个 ACTIVE Session |
| 用户登录状态 | 只有 `ACTIVE` 允许认证 | `LOCKED/DISABLED/ARCHIVED/LOGICALLY_DELETED` 均拒绝并撤销 Session |
| 临时安全锁 | 15分钟失败锁由 Credential 字段承载 | 与业务 `LOCKED` 严格区分 |
| admin Bootstrap | `SYSTEM_BOOTSTRAP_ADMIN_V1` | 密码只允许 TTY 或 `ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；失败整体回滚 |
| 用户治理 | Create/Reset/Enable/Disable/Role Binding | 服务端权限与admin保护；临时密码一次性交付；幂等、row_version、审计同事务 |
| Change Password | 204且无Token；相同幂等请求重放204 | 先claim幂等V2，再锁User/Credential/Session；只变更一次并撤销全部Session |
| Migration | `V3 -> V4 -> V5 -> V6 -> V7` | V6保持不变；V7新增来源限流、幂等V2兼容字段、索引和审计action约束 |
| State Owner | 8个认证语义 | `AUTH-STATE-007`不可变审计；`AUTH-STATE-008`来源限流窗口 |
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
- 普通平台用户创建、凭据重置、启停和角色绑定治理API；
- MySQL 8.4共享来源限流；
- Change Password 204与请求丢失幂等重放；
- 与上述能力直接相关的状态、数据库和 P1 验收。

P1 不得自动进入：项目/环境/业务终端、Runner、测试资产、AI 探索/人工录制、调度/锁/租约、正式执行、报告/制品、模型管理等后续业务域。

## 当前门禁语义

```text
AUTHORITY_MODEL = SINGLE_LIVING_AUTHORITY
GOV_P1_001 = AUTHORITY_SYNCED_IMPLEMENTED_LOCAL_REVIEW_PASS
GOV_P1_004 = AUTHORITY_SYNCED_IMPLEMENTED_LOCAL_REVIEW_PASS
GOV_P1_002_003_005 = IMPLEMENTED_RUNTIME_VALIDATED
P1_AUTH_IMPLEMENTATION_STATUS = IMPLEMENTED_RUNTIME_VALIDATED
P1_AUTH_RBAC_ACCEPTANCE = NOT_YET_COMPLETED
REAL_PLATFORM_ACCEPTANCE = NOT_COMPLETED
```

静态 Contract / Authority / OpenAPI / Governance PASS 只证明当前契约与实现可继续推进；真实 MySQL 8.4、真实 API/Vue Chromium 闭环和对应 Acceptance 证据仍需在具备环境条件时执行。

当前认证运行门禁使用长期能力域入口：`tools/gates/auth_mysql_gate.py` 与 `tools/gates/auth_browser_gate.py`；状态名分别为 `AUTH_MYSQL_RUNTIME_GATE` 与 `AUTH_BROWSER_RUNTIME_GATE`。管理员连接由 `ATP_MYSQL_ADMIN_URL` 注入，应用/隔离测试数据库连接统一由 `ATP_DATABASE_URL` 注入；破坏性验证仅允许命中 `ai_auto_test_platform_gate_auth_<unique>` 临时库。
