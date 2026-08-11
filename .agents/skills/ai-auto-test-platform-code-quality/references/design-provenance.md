# Design Provenance

本项目代码质量Skill是项目专用规则，不复制第三方Skill文本。设计上吸收以下公开模式：

- OpenAI Codex Code Review：总审查可以把专项review拆给独立subagent后汇总全部有效finding。
- OpenAI Codex Testing Review：重大agent/行为逻辑变化需要测试，跨层能力优先集成测试证据。
- 社区 thermo-review：使用维护源文件行数作为结构深查触发器，但判断重点是职责、依赖和ownership，而不是机械压缩行数。
- 社区 hack-review：识别掩盖根因、重复轮子、绕过稳定边界等脆弱捷径。
- 社区 regression-review：围绕用户可见行为链检查非预期回归，并记录未覆盖表面。

这些思想均已按当前 authority权威模型、项目Git限制和现有Reviewer职责重新解释；外部规则不是本项目事实源。
