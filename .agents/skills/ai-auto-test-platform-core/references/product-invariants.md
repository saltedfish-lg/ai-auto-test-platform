# product-invariants.md

- authority_model: SINGLE_LIVING_AUTHORITY
- authority_root: docs/authority
- status: CURRENT

admin不可删除；项目和数据范围隔离；人工录制不强制绑定平台测试账号；管理端、客户端、PDA均为Web并优先Playwright。

当前事实以 `docs/authority/**` 为准；本文只是运行时紧凑索引，不复制完整源文档。若用户已明确改变相关产品事实，先 `AUTHORITY_UPDATE_ONLY` 修改当前 authority 并通过 validators，再继续实现。Git 历史与提交由用户在 IDEA 管理，Codex 不运行 Git。

权威模型：`AUTHORITY-MODEL-LIVING-001`。
