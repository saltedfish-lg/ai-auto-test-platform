# Technical Sovereignty Boundary

架构师拥有的是**技术实现自主权**，不是产品主权。

## Freeze Wins

以下已有正式来源时只允许服从：

- 产品对象、角色、场景；
- 状态及生命周期；
- 权限/数据范围；
- OpenAPI operation/DTO/error；
- DDL关键字段/约束；
- Runner、并发、租约、资源冲突规则；
- 安全/认证契约；
- 正式验收语义。

## Engineering Autonomy

在不改变上述事实的前提下，可以自主选择：

- 内部分层与类/方法组织；
- Repository/UoW/Adapter 形态；
- 事务代码组织；
- 成熟库与内部技术实现；
- 日志、Tracing、错误封装；
- 可维护性重构。

## Product Decision Gate

遇到未定义事项，依次问：

1. 是否改变用户可观察行为？
2. 是否改变业务规则/状态语义？
3. 是否改变 API/数据/事件契约？
4. 是否改变权限/安全边界？
5. 是否改变跨模块业务职责、并发或恢复语义？

任一“是” → `BLOCKED_BY_PRODUCT_DECISION`。
全部“否” → 技术自主裁决。
