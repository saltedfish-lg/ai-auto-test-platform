# ADR Policy

ADR 只用于长期架构事实，不作为每次编码任务的日志。

## 不需要 ADR

- ARCH_LOW；
- 单模块常规实现；
- 可轻易回退、不会成为长期依赖的技术细节；
- 仅代码质量重构。

## 可标记 ADR_CANDIDATE

ARCH_HIGH 且满足至少一项：

- 长期改变模块依赖方向；
- 确立新的状态 Owner / write authority；
- 确立跨模块事务/一致性模型；
- 引入 Event/Outbox/Queue/Cache 作为正式架构组成；
- 确立 Runner/Worker/Scheduler 的长期协作边界；
- 确立统一故障恢复/并发协调模式。

`solution_architect` 只输出候选决策内容，不写文件。主 Agent 只有在当前任务明确包含架构治理文档、且目标路径不是当前 Living Authority时才允许落盘。
