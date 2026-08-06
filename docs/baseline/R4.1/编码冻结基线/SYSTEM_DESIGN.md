# AI自动化测试执行平台系统设计（R4.1阅读投影）

> GENERATED_PROJECTION · NON_AUTHORITATIVE · DO_NOT_EDIT_MANUALLY  
> 权威源：`SYSTEM_DESIGN.yaml`；发布：`PDBR-2026.08.06-R4.1`。

## 当前架构

模块化单体控制面、独立异步Worker、独立Runner Agent、MySQL 8.4、Redis、S3兼容对象存储、Outbox事件。

## R4冻结契约（R4.1治理发布沿用）

- 凭证版本主键：`credential_revision_id`；业务唯一键：`(test_account_id, revision_no)`。
- 技术告警接入端点主键：`technical_alert_endpoint_id`；`signature_config_ref`为可轮换引用。
- 新建执行任务：`final_result=UNKNOWN`。
- RBAC：50个权限点、12个角色模板、600条角色权限映射；权限点表不持有`role_id`。
- 数据库：77张对象表+5张技术表，共82张。

## 两级门禁

- 编码基线：静态契约通过；MySQL 8.4空库和种子实跑待执行。状态为`READY_WITH_RUNTIME_DB_VALIDATION_PENDING`。
- 平台发布：平台尚未实现，1691项验收保持`SPECIFIED/NOT_STARTED`，状态为`NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT`。
