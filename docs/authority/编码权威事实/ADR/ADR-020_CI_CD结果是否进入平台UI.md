# ADR-020：CI/CD结果是否进入平台UI

- 状态：`INCORPORATED`
- 对应决策：`PEND-R3-003`
- 权威来源：`USER_SELECTED_IN_REPAIR_INSTRUCTION`
- 目标发布：`PDBR-2026.08.06-R3`
- 阻断 FULL_CODE_READY：`false`

## 决策

V1不建设CI/CD管理UI；仅提供受权API触发并记录trigger_source、external_pipeline_id、commit_sha、branch。完整聚合、回写和Webhook管理延期。

## 兼容性与实施约束

- 不改变已确认的产品范围、Runner权威边界、四条AI/录制/执行路径和既有状态历史。
- 实现必须经由冻结端口、状态Owner、权限守卫、幂等键和不可变审计。
- 若状态为待确认，本ADR仅作为候选设计，不得生成最终初始化种子或发布门禁通过证据。

## 追溯

- 唯一输入基线SHA-256：`c146e9a1913b5e8a22dc8f19275a0fa902736b3ad178b473dad502e2ad95ff57`
- 发布ID：`PDBR-2026.08.06-R3`
