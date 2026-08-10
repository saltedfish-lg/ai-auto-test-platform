# Architecture Risk Routing

## ARCH_LOW

满足全部条件：

- 修改局部；
- 不改变状态 Owner / write authority；
- 不改变模块依赖方向；
- 不改变事务/一致性/恢复模型；
- 不引入新的跨模块写路径；
- 不涉及 Runner/Worker 并发、锁、租约、fencing；
- 不改变正式契约或产品行为。

结论：`ARCH_NOT_REQUIRED`，不启动架构 Agent。

## ARCH_MEDIUM

存在结构性实现选择，但仍完全位于既有架构边界：

- 新 Service / Repository / Handler；
- 新增普通表/API后需要内部落位；
- 单模块内复杂业务流程；
- 少量跨层调用但 ownership/transaction 已有先例。

结论：当前实现 Agent 内嵌 Architecture Skill，输出 `ARCH_CHECK_PASS` 或升级 HIGH。

## ARCH_HIGH 自动触发词/信号

- state owner / ownership / write authority
- transaction boundary / dual write
- event / outbox / async / eventual consistency / compensation
- retry ownership / recovery / failover / task migration
- idempotency / optimistic lock / expected_version
- lock / lease / fencing / distributed coordination
- runner / worker / scheduler / execution 联动
- shared kernel ownership / circular dependency / service split
- cache/queue 参与正式一致性

## 升级规则

初始为 LOW/MEDIUM，但 Impact Map 或真实 diff 出现 HIGH 信号时必须升级，不能因为任务标题看起来简单而保持低风险。

ARCH_HIGH 的 `solution_architect` 默认只在修改前运行一次。若修改后影响闭包新增了新的 state owner、事务、一致性、并发、Runner/Worker 或依赖域，标记 `ARCH_RECHECK_REQUIRED` 再增量复核。
