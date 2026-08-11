# Impact Discovery

## 目标

修改前先建立“可能受影响的闭包”，而不是直接打开用户点名的文件开始改。

## 检索层级

### L0 任务词
用户给出的模块、页面、API、类、字段、错误、权限、状态和路径。

### L1 定义与直接引用
定义位置、import/export、函数调用、组件引用、路由、Store、测试。

### L2 契约消费者
OpenAPI/generated、DTO、DB mapping、permission/status/event、序列化/反序列化。

### L3 跨模块行为
Worker/Runner、调度、事务、Outbox、审计、制品、监控、E2E、工具脚本。

### L4 用户可见后果
页面状态、危险动作、错误反馈、报告/日志、权限可见性和操作路径。

## 闭包停止条件

只有当新增一层检索不再发现新的活动消费者，且高风险扩张项已检查，才能认为 Pre-change Impact Closure 完成。

不要因为某个文件“看起来就是唯一实现”而提前停止。

## Single Full Impact Scan 约束

上述 L0→L4 的首次广域闭包属于同一个 `FULL_IMPACT_SCAN`，每个正式 Task 最多成功执行一次。它完成后形成唯一 Task Context Pack。后续发现新消费者时不重新从 L0 扫描仓库，而以新消费者/符号作为 seed 执行 `TARGETED_REVERSE_LOOKUP` 并扩充现有 Pack。

- Pack CURRENT：子 Agent 必须消费，不得重建；
- Pack STALE：`DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`；
- `IMPACT_EXPANSION`：扩充现有 Pack，不得触发 Full Scan #2；
- 正式 CROSS_MODULE/HIGH_RISK 子 Agent 没拿到 Pack：返回 `TASK_CONTEXT_PACK_REQUIRED`。
