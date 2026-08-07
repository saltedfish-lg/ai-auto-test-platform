# ai-runner-rules.md

- release_id: PDBR-2026.08.07-R4.2
- status: FROZEN

Runner必须健康、已绑定、能力匹配且空闲；无环境锁、账号租约和资源冲突时，SCHEDULABLE到CLAIMED满足P95≤3秒、P99≤10秒。


## R4.2状态

发布`PDBR-2026.08.07-R4.2`允许恢复P1身份认证、默认admin与RBAC编码；MySQL 8.4空库安装和R4.1→R4.2升级门禁已通过；1691项真实平台验收仍为`SPECIFIED/NOT_STARTED`。


权威模型：`AUTHORITY-MODEL-R4.2-001`；按职责域确定权威，本文不得覆盖核心事实或工程契约。
