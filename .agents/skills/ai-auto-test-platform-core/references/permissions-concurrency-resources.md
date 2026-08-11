# permissions-concurrency-resources.md

- authority_model: SINGLE_LIVING_AUTHORITY
- authority_root: docs/authority
- status: CURRENT

关系型RBAC包含50个权限点、12个角色和600条决策。版本提交人与批准人不得相同。

当前事实以 `docs/authority/**` 为准；本文只是运行时紧凑索引，不复制完整源文档。若用户已明确改变相关产品事实，先 `AUTHORITY_UPDATE_ONLY` 修改当前 authority 并通过 validators，再继续实现。Git 历史与提交由用户在 IDEA 管理，Codex 不运行 Git。

权威模型：`AUTHORITY-MODEL-LIVING-001`。
