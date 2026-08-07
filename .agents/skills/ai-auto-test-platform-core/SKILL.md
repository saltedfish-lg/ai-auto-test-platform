---
name: ai-auto-test-platform-core
description: R4.2认证契约补全后的AI自动化测试执行平台编码规则。
---

# 核心编码Skill

当前发布：`PDBR-2026.08.07-R4.2`。允许恢复P1身份认证、默认admin与RBAC编码。MySQL 8.4空库和R4.1升级门禁已通过；平台发布前仍必须执行1691项验收并绑定真实证据。

权威模型：`AUTHORITY-MODEL-R4.2-001`。Release管理成员和版本；六份核心YAML管理业务语义；工程契约管理物理实现；ADR同步后生效；AGENTS/Skill不得改变产品或契约。

编码基线：`READY_FOR_P1_IMPLEMENTATION`。
实现发布：`NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT`。
待用户决策：`0`。

P1认证必须读取`编码冻结基线/AUTHENTICATION_CONTRACT/authentication-contract.yaml`。必须使用正式Login/Refresh/Logout/Me/Change Password Operation、V5平台凭据与Refresh Session表、Argon2id和安全Bootstrap输入；不得写死admin密码、持久化Refresh原值、把权限固化在JWT或用用户名绕过RBAC。
