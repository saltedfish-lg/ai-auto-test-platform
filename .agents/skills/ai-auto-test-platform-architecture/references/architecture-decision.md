# Compact Architecture Decision

ARCH_HIGH 输出保持紧凑：

```yaml
architecture_decision:
  arch_risk: ARCH_HIGH
  decision_status: ARCH_DECISION_READY
  affected_domains: []
  authority_refs: []
  state_owners:
    <state/resource>: <owner + write authority>
  dependency_direction: []
  transaction_boundaries: []
  communication:
    sync: []
    async_or_events: []
  consistency_model: []
  idempotency_concurrency: []
  failure_recovery: []
  forbidden_shortcuts: []
  implementation_targets: []
  validation_targets: []
  adr_candidate: false
  product_decision_required: []
```

## 输出纪律

- 只写对本任务有约束力的裁决；
- 不复制完整业务文档；
- 不设计与当前任务无关的“未来完美架构”；
- 不把冻结契约改写成新的平行事实源；
- `product_decision_required` 非空时，不得把对应语义假装已裁决。
