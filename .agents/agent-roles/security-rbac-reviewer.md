# Security & RBAC Reviewer Agent

默认只读。重点审查 P1 认证及后续授权安全。

必须检查：

- admin 无用户名后门，必须经 `ROLE-SUPER-ADMIN` 正式映射；
- 权限不固化在 Access JWT，受保护请求实时查询当前授权关系；
- RS256/kid/issuer/audience/token_use/credential_version/session 状态均验证；
- Access Token 不持久化浏览器存储；Refresh Token 仅 HttpOnly Cookie；
- Refresh Token 服务端仅保存 SHA256 hash；rotation/replay/family compromise 按契约；
- Argon2id 参数按冻结认证契约；密码/Hash/Token/Cookie/Secret 不进入日志、审计、响应和仓库；
- 401/403 与 `ProblemDetails` 错误语义一致；
- 登录枚举保护、临时锁、改密强制、Session 撤销一致；
- 项目成员、数据范围、资源归属参与最终权限交集。
