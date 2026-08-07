# AI自动化测试执行平台系统设计（R4.2阅读投影）

> GENERATED_PROJECTION · NON_AUTHORITATIVE · DO_NOT_EDIT_MANUALLY  
> 权威源：`SYSTEM_DESIGN.yaml`；发布：`PDBR-2026.08.07-R4.2`。

## 当前架构

模块化单体控制面、独立异步Worker、独立Runner Agent、MySQL 8.4、Redis、S3兼容对象存储、Outbox事件。

## R4.2冻结契约

- 凭证版本主键：`credential_revision_id`；业务唯一键：`(test_account_id, revision_no)`。
- 技术告警接入端点主键：`technical_alert_endpoint_id`；`signature_config_ref`为可轮换引用。
- 新建执行任务：`final_result=UNKNOWN`。
- RBAC：50个权限点、12个角色模板、600条角色权限映射；权限点表不持有`role_id`。
- 数据库：新增平台用户凭据和Refresh Session对象表，共84张；V5为R4.1上的加法Migration。
- 认证：RS256短期Bearer Access JWT（15分钟）+服务端可撤销轮换Refresh Session（7天）。
- Browser：Access Token仅内存，Refresh Token仅HttpOnly/Secure/SameSite=Strict Cookie。
- 密码：Argon2id；admin由显式无回显秘密输入初始化，首次登录强制改密，重复初始化不得覆盖密码。
- 授权：权限不进入JWT，每个新请求实时读取正式RBAC及数据范围。

## 两级门禁

- 编码基线：认证静态契约、MySQL 8.4空库安装和R4.1升级验证通过。状态为`READY_FOR_P1_IMPLEMENTATION`。
- 平台发布：平台尚未实现，1691项验收保持`SPECIFIED/NOT_STARTED`，状态为`NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT`。
