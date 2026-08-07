# coding-checklists.md

- release_id: PDBR-2026.08.07-R4.2
- status: FROZEN

编码前检查release_id、DTO、权限映射、状态Owner、迁移、事件Schema和验收映射；提交前运行validation/validate_contracts.py。


## R4.2状态

发布`PDBR-2026.08.07-R4.2`允许恢复P1身份认证、默认admin与RBAC编码；MySQL 8.4空库安装和R4.1→R4.2升级门禁已通过；1691项真实平台验收仍为`SPECIFIED/NOT_STARTED`。


权威模型：`AUTHORITY-MODEL-R4.2-001`；按职责域确定权威，本文不得覆盖核心事实或工程契约。
