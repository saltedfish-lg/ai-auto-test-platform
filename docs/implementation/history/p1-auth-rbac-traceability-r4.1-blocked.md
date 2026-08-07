# 历史归档：P1 身份认证与 RBAC R4.1 阻断追踪

> **历史证据，禁止作为当前P1实现事实源。** 本文件记录 `PDBR-2026.08.06-R4.1` 阶段真实暴露的认证契约阻断；这些阻断已在 R4.2 定点治理中关闭。当前实现必须读取 `../p1-auth-rbac-traceability.md` 与 `docs/baseline/R4.2/**`。

- 发布基线：`PDBR-2026.08.06-R4.1`
- 权威模型：`AUTHORITY-MODEL-R4.1-001`
- 实现阶段：P1
- 文档状态：`BLOCKED_BY_FORMAL_AUTH_CONTRACT_GAP`
- 基线策略：仅引用 `docs/baseline/R4.1/**`，禁止修改冻结基线。

## 前置门禁证据

- `python tools/verify_baseline.py`：PASS；Manifest 718/718；缺失、额外、哈希漂移均为 0。
- `python tools/dev.py verify`：PASS；静态治理、格式、Lint、类型、单元、契约、集成、OpenAPI 客户端检查和构建均通过。
- 正式规范统计：权限 50、角色 12、角色权限映射 600、DDL 表 82、外键 171、OpenAPI 路径 133、操作 245、Schema 455、事件 628、验收项 1691。

## 契约追踪矩阵

> 本矩阵必须在产品代码修改前补齐。任何实现只能引用矩阵内的正式契约，不得自行扩展角色、权限、状态、接口或安全语义。

| 主题 | 正式契约 ID / 定义 | 权威来源 | P1 实现落点 | 验证证据 |
|---|---|---|---|---|
| 用户对象 | `OBJ-001` / `user` / `user_id` / 业务唯一键 `username` | 核心对象 YAML | `atp_user`；正式 API `list_user/create_user/get_user/update_user` | V3 空库安装、唯一键和 CHECK 实库验证 PASS |
| 内置 admin | `OBJ-002` / `admin` / 固定 `username=admin`；`DR-002`、`PC-002` 禁止删除且仅初始化/保护逻辑可维护 | 核心对象 YAML | `atp_admin` 关联 `atp_user` | 受认证物理契约缺口阻断，未写入半成品 admin |
| 角色对象 | `OBJ-003` / `role` / `role_id` / 业务唯一键 `role_code` | 核心对象 YAML | `atp_role`；正式 API `list_role/create_role/get_role/update_role` | 12 个唯一预置角色实库验证 PASS |
| SUPER_ADMIN | `OBJ-004`；ADR-023 规定仅内置 admin 可绑定；V4 正式角色码为 `ROLE-SUPER-ADMIN` | 核心对象 YAML / ADR-023 / V4 | `atp_entity_super_admin_role` + `atp_role` | `ROLE-SUPER-ADMIN` 的 50 项权限均为 ALLOWED |
| 权限对象 | `OBJ-005` / `permission_code` / 最小授权标识 | 核心对象 YAML / permission-closure | `atp_permission_code` | 50 个 ID、50 个 code，均唯一 |
| 用户角色关系 | `BR-PERM-0002` 用户与角色分离；`BR-USER-0035` 创建有有效期绑定；`BR-USER-0085` 绑定 `ACTIVE→ENDED` | 核心对象 YAML | `atp_user_role_binding`，唯一键 `(user_id, role_id, project_id, valid_from)` | 2 个 FK、1 个唯一约束实库存在 |
| 角色权限关系 | `SYSTEM_DESIGN.permission_contract`：关系型 RBAC；权限表不得持有 `role_id` | SYSTEM_DESIGN / permission-closure / V4 | `atp_role_permission(role_id, permission_id, decision, conditions)` | 600 个唯一映射；181 ALLOWED、419 DENIED；悬空角色/权限引用均为 0 |
| 用户与角色状态 | `SD-001-LIFECYCLE`：用户 `CREATED/DRAFT/ACTIVE/LOCKED/DISABLED/RECOVERING/ARCHIVED/LOGICALLY_DELETED`；`SD-003-LIFECYCLE`：角色 `CREATED/DRAFT/ACTIVE/DISABLED/RECOVERED/ARCHIVED/LOGICALLY_DELETED` | 核心对象 YAML / STATE_OWNER_REGISTRY / V3 / OpenAPI | `lifecycle_status` | CHECK 实库验证 PASS；初始化语义冲突见下文 |
| 登录标识与凭据规则 | `OBJ-001.username` 唯一；`CRD-001` 密码不得明文保存、回显、记录或导出；失败不得泄露敏感身份信息；`CRD-012` 要求认证失败、凭据失效、停用、无权限使用不同错误语义 | 核心对象 YAML / 安全 YAML | 登录标识可落 `atp_user.username`；平台凭据无正式物理落点 | `atp_user`/`atp_admin` 中密码、凭据、安全状态、会话、Token 列数量为 0 |
| 密码哈希与失败语义 | `SEL-038` / `security_architecture.password_hash=Argon2id`；`AUD-001` 审计登录成功与失败 | 技术选型 YAML / 安全 YAML | 哈希算法已冻结；参数、平台凭据表/字段、失败计数与锁定参数未冻结 | 受正式契约缺口阻断 |
| 会话、Token、Cookie、过期 | `BR-USER-0056` 建立会话；`TCK-001` 完整 Token 禁止进入日志/报告/AI/导出；`TCK-002` Cookie 仅受控浏览器会话且终止后清理；`TCK-003` 用户停用或安全锁定后新请求不得继续使用失效会话；OpenAPI `BearerAuth` 为 bearer/JWT | 核心对象 YAML / 安全 YAML / OpenAPI | 鉴权载体方向为 JWT；签发、刷新、撤销、过期和存储契约未定义 | 受正式契约缺口阻断 |
| 认证端点 | 核心业务规则 `BR-USER-0047..0066` 定义登录业务；冻结 OpenAPI 的 133 path / 245 operation 中不存在登录、登出或当前用户 operation | 核心对象 YAML / OpenAPI 3.1.2 | 禁止自行新增端点、DTO 或 Operation ID | 受正式 API 决策阻断 |
| 401 / 403 | 所有正式受保护 operation 定义 `401 Unauthenticated` 与 `403 Forbidden`，响应为 `application/problem+json` / `ProblemDetails` | OpenAPI 3.1.2 | 待认证入口冻结后按统一错误中间件实现 | OpenAPI 静态验证 PASS |
| 权限计算 | `BR-PERM-0004`：有效授权为角色权限、项目成员关系、数据范围和资源归属的交集；`BR-USER-0050/0057/0065`：登录成功后按实时绑定加载 system role、project duty、active/history scope；新请求实时使用新权限 | 核心对象 YAML / permission-closure / SYSTEM_DESIGN | 必须从关系表查询，不得按用户名或前端状态旁路 | RBAC Seed 与引用完整性实库验证 PASS |
| RBAC Seed | 正式闭包 50 权限、12 角色、600 映射 | permission-closure / V4 / SYSTEM_DESIGN | 原样 V4 Seed | 首次与第二次执行均 PASS，计数不变 |
| admin 初始化 | `BR-PERM-0001`、`BR-USER-0001..0025`、`ACC-R3-1602..1626`：单事务创建 admin、绑定 SUPER_ADMIN、写不可变事件/审计、提交初始化标记、幂等；不得停用、归档、删除或解除绑定 | 核心对象 YAML / acceptance-closure | 需同时写 `atp_user`、`atp_admin`、角色绑定、审计、Outbox、初始化记录和平台凭据 | 凭据、安全状态与初始化标记无正式表/字段，故未执行不完整初始化 |
| 数据库表与约束 | `atp_user`、`atp_admin`、`atp_role`、`atp_entity_super_admin_role`、`atp_permission_code`、`atp_user_role_binding`、`atp_role_permission`、`atp_data_scope_grant`、`atp_audit_log`、`atp_outbox_event`、`atp_idempotency_record` | database-schema / V3 | 冻结 V3 原样安装 | MySQL 8.4.11：82 表、171 FK、109 CHECK，正式断言 `R4_MYSQL84_GATE_PASS` |
| 领域与审计事件 | `admin.active`/`admin.locked`；`entity_super_admin_role.active`/`.locked`；`user.active`/`.locked`/`.disabled`/`.archived`/`.recovering`/`.logically_deleted`；role、permission_code、role_binding 对应状态事件；均为 `AT_LEAST_ONCE_OUTBOX` 且禁止密码、Secret、Token、原始凭据 | event-registry / schemas | 状态、Outbox 与审计必须同事务 | 事件契约静态验证 PASS；认证初始化尚未写事件 |
| P1 正式验收项 | `ACC-R3-1602..1688` / `CT-R3-1602..1688`，覆盖 `USR-SCN-001..004` 的初始化、用户创建、登录与权限变更 | acceptance-closure | P1 只执行该范围并保留全平台验收为未完成 | 数据库闭包子集 PASS；认证与 admin 子集因契约缺口 NOT_EXECUTED |

## 已确认的正式契约缺口

### GAP-P1-AUTH-001：认证 API 缺失

- 冻结 OpenAPI 明确全局使用 `BearerAuth`，`bearerFormat=JWT`。
- 133 个 path、245 个 operation 中只有“登录策略”对象 CRUD，不存在平台用户登录、登出、当前用户 operation，也不存在相应请求/响应 DTO。
- P1 指令明确“OpenAPI 没有正式定义的接口不得自行添加”，因此不能在实现层自创 `/login`、`/logout` 或 `/me`。

### GAP-P1-AUTH-002：平台凭据与会话物理模型缺失

- V3 的 `atp_user` 只有 `user_id, username, role_binding_id, lifecycle_status, display_name, row_version` 和审计通用字段；`atp_admin` 同样没有平台凭据字段。
- 两表中与 password、credential、security、session、token 相关的正式列数量为 0。
- `atp_credential_revision` 明确通过 FK 归属于 `atp_test_account`，受 `CRD-002` 的测试账号/凭据分离语义约束，不得挪作平台用户密码表。
- `extension_json` 不是已冻结的平台凭据、失败计数、安全状态或会话模型，不能自行塞入这些新正式语义。

### GAP-P1-AUTH-003：初始化状态语义不一致

- `BR-USER-0013`、`BR-USER-0022` 要求首次初始化设置用户业务状态 `ENABLED`、安全状态 `NORMAL`。
- V3、STATE_OWNER_REGISTRY 与 OpenAPI 的用户生命周期只允许 `ACTIVE`，不允许 `ENABLED`；V3 也没有 `security_status` 字段。
- 将 `ENABLED` 映射为 `ACTIVE` 或把 `NORMAL` 写入扩展字段都会改变正式生命周期/持久化语义，需要用户确认并同步权威契约。

### GAP-P1-AUTH-004：初始 admin 密码交付规则缺失

- 正式契约只冻结 Argon2id 与“不得明文保存/回显/记录/导出”，未冻结初始密码来源、最低策略、一次性交付、首次强制修改或安全参数。
- P1 指令禁止发明弱密码或在输出中泄露密码，因此不能安全地产生一个未经契约批准的 admin 初始凭据流程。

## 已执行但不跨越缺口的真实数据库工作

- 自动发现 Windows 服务 `MySQL84`，状态 Running，端口 3306，服务器 `8.4.11 MySQL Community Server`。
- 创建此前不存在的 `ai_auto_test_platform_dev`，未删除或覆盖既有数据库。
- 原样执行 V3，原样执行 V4 两次；两份临时 ASCII 路径副本与冻结源 SHA-256 一致。
- 正式 `mysql84_assertions.sql` 返回 `R4_MYSQL84_GATE_PASS`。
- 真实计数：82 表、171 FK、109 CHECK、50 权限、12 角色、600 映射；角色/权限悬空引用均为 0。
- admin 与 admin 用户数量保持 0：避免在缺少正式凭据、安全状态和初始化标记契约时写入无法登录或无法幂等治理的半成品管理员。

## P1 边界

- 本阶段仅实现身份认证、默认 admin 与 RBAC 正式业务闭环。
- 不进入项目、环境、测试资产、任务执行、报告、Runner、AI 或其他后续业务域。
- `REAL_PLATFORM_ACCEPTANCE` 在 P1 完成后仍保持 `NOT_COMPLETED`。
