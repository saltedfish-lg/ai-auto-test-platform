---
name: ai-auto-test-platform-auth-rbac-security
description: R4.2 P1 身份认证、默认admin、JWT/Refresh Session、密码安全、RBAC与授权安全正式实现/审查Skill。
---

# P1 Authentication + Admin + RBAC + Security

## 唯一物理契约入口

必须读取：

- `docs/baseline/R4.2/编码冻结基线/AUTHENTICATION_CONTRACT/authentication-contract.yaml`
- `docs/baseline/R4.2/编码冻结基线/OPENAPI/openapi.yaml`
- `docs/baseline/R4.2/编码冻结基线/DATABASE_DDL/V5__platform_authentication_contract.sql`
- V3/V4、permission closure、state owner、ADR-032 及 core Skill 相关 references

## 不可发散的冻结事实

- Access JWT：RS256、kid、issuer/audience、900s、credential_version/session 实时校验；
- 权限不放入 JWT 作为授权事实；每个受保护请求从数据库实时解析；
- Refresh Session：服务端 MySQL，只存 SHA256 token hash，每次 refresh rotation，replay compromise family；
- 最多 5 个 ACTIVE Session；
- Access Token 仅前端内存，Refresh Token 仅 `atp_refresh` HttpOnly Cookie；
- Argon2id 参数按契约；
- admin bootstrap 只允许 CLI TTY 无回显或 `ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；
- admin 不可删除/禁用/归档/改名，且无 username 后门；
- `force_password_change`、登录失败窗口/临时锁、Session 撤销、401/403 错误码按契约。

## 可自主的工程实现

可自行选择成熟维护的 JWT/Argon2/crypto 库、内部 Service/Repository 结构、依赖注入方式、测试 builder/fixture，只要严格满足冻结算法、参数和外部语义；依赖必须固定版本并加入项目依赖治理。

## 安全红线

不得把密码、hash、JWT、refresh token、cookie、私钥、数据库凭据输出到日志、审计、测试快照、异常 detail、README 或仓库。
