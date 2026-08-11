---
name: ai-auto-test-platform-product-sovereignty
description: AI自动化测试执行平台产品主权门；在Single Living Authority下判断产品事实是否明确，识别缺口/冲突/范围变化，并在用户已明确裁决后允许AUTHORITY_UPDATE_ONLY直接修改docs/authority，不创建版本化基线。
---

# Product Sovereignty Gate

`authority_model = SINGLE_LIVING_AUTHORITY`。

## 定位

本 Skill 是 `PRODUCT_AUTHORITY_GATE`，不是 Product Manager Agent，也不是自动需求批准器。

核心原则：

> AI拥有检索、分析、比较和推荐权；用户拥有产品批准权。`recommendation != approval`。

唯一活动产品/契约事实源：

```text
docs/authority/**
```

该目录是**受治理的可修改 living authority**，不是不可变 R4.x baseline。Git 历史由用户在 IDEA 中管理；`MUST_NOT_INVOKE_GIT`，Codex 不运行任何 Git 命令。

## 调用位置

正式功能/修复/重构在 Impact Map 已建立后、Architecture Risk Gate 前执行轻量产品主权检查。

- 纯内部工程实现、代码结构、日志组织、测试 helper、非产品语义视觉细节 → `PRODUCT_DECISION_NOT_REQUIRED`。
- 用户可观察行为、业务规则/状态、公开 API/数据/事件、权限安全、Runner/Worker 业务/恢复语义、验收结果 → 检查当前 authority。
- 已有 CURRENT Task Context Pack 时 `MUST_CONSUME_TASK_CONTEXT_PACK`；正式跨模块/高风险任务缺 Pack 时返回 `TASK_CONTEXT_PACK_REQUIRED`；不得执行 `impact_scan.py` 或建立第二套 Impact Map。
- 补证据只允许带明确 seed 的 `TARGETED_AUTHORITY_LOOKUP`。

## 权威检索顺序

1. `docs/authority` 六份核心业务 YAML；
2. `docs/authority/编码权威事实/**` 中的 SYSTEM_DESIGN、OpenAPI、DDL、State Owner、Permission Closure、Authentication Contract、Event Contracts、Acceptance；
3. ADR 只提供决策理由，必须同步当前 authority 后才成为实施依据；
4. 活动代码、测试、UI 文案只能作为现状证据，不能反向覆盖产品事实。

## 门禁状态

### `PRODUCT_DECISION_NOT_REQUIRED`

不改变产品可观察语义。直接进入 Architecture/Implementation。

### `PRODUCT_FACT_FOUND`

当前 authority 已明确且一致。记录最小 `authority_refs`，后续只能实现该事实。

### `PRODUCT_DECISION_REQUIRED`

当前 authority 对必须由产品决定的事项缺少足以唯一实现的事实。

- 用户尚未明确 → `PENDING / BLOCKED_BY_PRODUCT_DECISION`；
- 当前请求或既有用户决定已经唯一明确 → `CONFIRMED / AUTHORITY_UPDATE_ONLY`，**禁止为了门禁形式再次要求确认**。`PRODUCT_DECISION_REQUIRED + CONFIRMED` 默认意味着新增原缺失产品事实，因此 `authority_update_required=true`。

### `PRODUCT_CONFLICT_DETECTED`

当前 authority 中存在无法按 Authority Model 自动消解的冲突。

- 未决 → Product Decision Pack；
- 用户已选择 → `CONFIRMED / AUTHORITY_UPDATE_ONLY`。

### `PRODUCT_SCOPE_CHANGE`

用户请求新增、删除或改变当前产品能力、业务规则、状态、权限、公开契约或验收行为。

若当前请求已经明确目标行为，它本身就是 `CURRENT_USER_REQUEST` 裁决，直接记录 `CONFIRMED`；不得为了门禁形式再次要求确认。

## Product Decision Pack

只有真实缺口/冲突且用户尚未明确时才生成。内容包括：

- 当前事实与 authority refs；
- 缺口/冲突；
- 2–4 个互斥可实施方案；
- business/UI/API/data/state/security/Runner/acceptance 影响；
- 一个推荐方案，但 `recommendation_is_approval=false`；
- `user_decision.status/source`。

当前用户请求已经明确唯一答案时，不制造伪 A/B/C。

## 用户裁决后的 Authority Update

凡确认会新增、修改、删除产品事实，解决冲突或形成范围变化：

```text
authority_update_required = true
workflow_state = AUTHORITY_UPDATE_ONLY
```

此阶段：`CONFIRMED` 只证明用户已经决定，不代表当前权威事实已经同步。进入 `AUTHORITY_UPDATE_ONLY` 后**禁止 Architecture/Implementation**，只允许同步源文档与验证；代码不修改。

1. 直接修改受影响的 `docs/authority/**` 源文档；
2. **不得创建 R4.3/R4.4/R5.x 目录**；
3. 不生成 Manifest/Release Snapshot；
4. 运行 `tools/verify_authority.py` 和相关 validators；
5. 更新同一个 Task Context Pack authority digest / pack revision；
6. 重新执行 Product Gate；
7. 只有重新得到 `PRODUCT_FACT_FOUND` 才进入 Architecture/Implementation。

代码不得先成为事实源。只有 authority 同步完成、重新 Product Gate 得到 `PRODUCT_FACT_FOUND`，才能解除 `AUTHORITY_UPDATE_ONLY`。

## 与其它 Skill / Agent 的边界

- `context-efficiency`：唯一 Full Scan、authority slice、freshness；本 Skill 只消费 Pack + targeted lookup。
- `feature-orchestrator`：管理 `AUTHORITY_UPDATE_ONLY`、Checkpoint、Resume 和 Expert Selection。
- `architecture` / `solution_architect`：只在产品事实明确后做技术裁决。
- Contract/DB/Security/UI/Backend/Frontend：消费已确认 authority，不拥有产品批准权。

当前不新增 Product Manager Agent。

## 禁止事项

- 把 AI 推荐、行业惯例或当前代码写成已批准产品事实；
- 为了不中断编码自动替用户选择方案；
- 用户已经明确时重复询问；
- 创建新的版本化 baseline 目录；
- 生成 release manifest 来替代用户 Git 历史；
- 运行 Git；
- 在 CURRENT Pack 存在时重新 Full Scan；
- 为“配合代码”擅自修改 authority。

## 输出

```text
PRODUCT_AUTHORITY_GATE = <状态>
authority_refs = <最小引用或NONE>
decision_pack_ref = <NONE或引用>
user_decision_status = <NOT_REQUIRED|PENDING|CONFIRMED>
decision_source = <NONE|CURRENT_USER_REQUEST|PRIOR_USER_DECISION|DECISION_PACK_SELECTION>
authority_update_required = <true|false>
workflow_state = <READY_FOR_ARCHITECTURE|BLOCKED_BY_PRODUCT_DECISION|AUTHORITY_UPDATE_ONLY>
```

只有 `PRODUCT_DECISION_NOT_REQUIRED` 或 `PRODUCT_FACT_FOUND` 且 `READY_FOR_ARCHITECTURE` 才继续。
