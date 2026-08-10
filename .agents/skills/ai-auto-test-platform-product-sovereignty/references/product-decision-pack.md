# Product Decision Pack

仅在产品主权门发现真实需求缺口、当前权威冲突或产品范围变化时创建。它是**决策辅助制品，不是权威事实源**。

```yaml
product_decision:
  decision_id: <PD-YYYY-NNN或任务内稳定ID>
  gate_status: PRODUCT_DECISION_REQUIRED | PRODUCT_CONFLICT_DETECTED | PRODUCT_SCOPE_CHANGE
  question: <一个可裁决的问题>

  authority_check:
    current_baseline: <动态CURRENT>
    searched_refs: []
    authoritative_fact_found: false
    conflict_refs: []

  current_facts: []
  constraints: []

  options:
    - id: A
      decision: <互斥方案>
      benefits: []
      risks: []
      impacts:
        business: []
        ui_ux: []
        api_contract: []
        data_state_event: []
        security_rbac: []
        runner_worker: []
        acceptance: []

  recommendation:
    option: <A|B|C|NONE>
    rationale: <为什么推荐>
    confidence: LOW | MEDIUM | HIGH
    recommendation_is_approval: false

  user_decision:
    status: PENDING | CONFIRMED
    selected_option: null | A | B | C | USER_DEFINED
    confirmed_by_user: false
    decision_source: NONE | CURRENT_USER_REQUEST | PRIOR_USER_DECISION | DECISION_PACK_SELECTION

  authority_update_required: false
  authority_update_targets: []
  workflow_state: BLOCKED_BY_PRODUCT_DECISION | AUTHORITY_UPDATE_ONLY
```

## 规则

- 候选方案一般 2–4 个；若只有一个不违背已知约束的方案，应说明为什么其它方向不可行，而不是制造伪选项。
- 推荐必须建立在当前事实与约束上；不得用“行业最佳实践”替代当前产品主权。
- `recommendation_is_approval` 永远为 `false`。
- `user_decision.status=CONFIRMED` 只能来自用户当前请求、已记录的明确用户裁决或用户对 Decision Pack 的明确选择，不得由 Agent 推断；必须记录真实 `decision_source`。
- 如果当前用户请求本身已经提供足以唯一落地的产品决定，直接记录 `CONFIRMED / selected_option=USER_DEFINED / decision_source=CURRENT_USER_REQUEST`；不得为了形式制造伪选项或再次要求确认。
- 用户确认导致**新增、修改、删除产品事实，解决权威冲突或产品范围变化**时，`authority_update_required=true / workflow_state=AUTHORITY_UPDATE_ONLY`。尤其 `PRODUCT_DECISION_REQUIRED + CONFIRMED` 默认意味着新增原缺失产品事实。
- `PENDING` 时 `workflow_state=BLOCKED_BY_PRODUCT_DECISION`；`CONFIRMED + authority_update_required=true` 时只能同步受治理权威事实，禁止 Architecture/Implementation。权威更新完成后必须重新执行产品门并得到 `PRODUCT_FACT_FOUND`，Decision Pack 本身不能升级为事实源。
- Decision Pack 只保存紧凑事实、差异和影响，不复制完整 YAML/OpenAPI/DDL。
