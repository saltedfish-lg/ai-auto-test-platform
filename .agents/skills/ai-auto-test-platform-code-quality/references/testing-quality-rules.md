# Testing Quality Rules

- 先列出本次重大逻辑变化和用户可见行为，再映射到测试。
- 跨层行为优先contract/integration/E2E；unit test用于纯逻辑和边界。
- 测试失败路径、状态冲突、幂等/重复提交、认证失效、刷新恢复等高风险路径。
- 不用Mock成功替代真实MySQL/API/浏览器门禁。
- 避免只断言内部方法调用次数而没有业务结果断言。
- 不为了测试方便在生产代码加入test-only后门。
