# E2E 测试入口

P0 只建立目录和门禁入口，不创建会伪装业务完成度的端到端用例。后续正式业务实现必须按
当前 Living Authority 验收闭包建立真实平台、Runner 与隔离被测系统证据；当前验收数量由
`tools/current_facts.py#acceptance.count` 机械派生，状态仍为 `SPECIFIED/NOT_STARTED`；历史 1691 仅表示 OBJ-085 退役前闭包。
