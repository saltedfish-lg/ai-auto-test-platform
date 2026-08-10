---
name: ai-auto-test-platform-product-sovereignty
description: AI自动化测试执行平台产品主权门与需求决策辅助Skill；在技术架构和实现前判断产品事实是否已由R4.2权威源定义，识别需求缺口/冲突/范围变化，形成可供用户裁决的Product Decision Pack，但绝不替用户批准或冻结产品规则。
---

# Product Sovereignty Gate

## 定位

本 Skill 是**产品主权门（PRODUCT_AUTHORITY_GATE）**，不是 Product Manager Agent，也不是自动需求批准器。

它只回答三类问题：

1. 当前任务是否涉及产品主权，而非纯工程实现；
2. 涉及的产品事实是否已经由当前 R4.2 权威事实源明确且一致地定义；
3. 若没有明确事实、存在冲突或用户要求改变冻结事实，应如何把问题整理成可由用户快速裁决的 Product Decision Pack。

核心原则：

> **AI拥有检索、分析、比较和推荐权；用户拥有产品批准权。推荐方案永远不等于已批准事实（`recommendation != approval`）。**

本 Skill 不修改代码、OpenAPI、DDL、状态、权限、事件或 `docs/baseline/R4.2/**`，也不因为“业内通常如此”而创建新的产品规则。

## 一、调用位置与成本控制

正式功能/修复/重构任务在 Context Impact Map 已建立后、Architecture Risk Gate 之前执行轻量产品主权检查。

- 纯内部实现、代码结构、日志组织、测试 helper、非产品语义视觉细节：`PRODUCT_DECISION_NOT_REQUIRED`，立即继续，不做重型产品分析；
- 涉及用户可观察行为、业务规则/状态、公开 API/数据/事件、权限安全、Runner/Worker 业务/恢复语义、验收结果：检查当前权威事实；
- 已有同一 workspace/scope 且 `freshness=CURRENT` 的 `product_authority` slice 时优先复用；只有真实 Product/Authority 影响扩张、权威事实变化或 slice 失效时才重跑。

不得把本 Skill 变成每个任务都生成长篇 PRD 的常驻 Lane。

## 二、产品主权判定

以下任一问题回答“是”，即进入产品事实检查：

- 是否改变最终用户/管理员/测试人员可观察行为或默认行为？
- 是否新增、删除或改变业务规则、业务状态、状态转换或失败/恢复语义？
- 是否新增、删除或改变公开 API、DTO 字段、错误码、持久化业务数据或正式事件语义？
- 是否改变角色、权限、DataScope、认证/安全边界？
- 是否改变 Runner/Worker/Scheduler/Execution 的业务职责、任务迁移、重试/恢复、资源冲突语义？
- 是否改变正式验收结果或系统范围/模块能力？

全部为“否”时输出 `PRODUCT_DECISION_NOT_REQUIRED`。

## 三、权威事实检索顺序

只从 `docs/baseline/CURRENT` 动态解析当前基线，不硬编码未来版本。R4.2 下按根 `AGENTS.md` 的 Authority Model 检索：

1. 六份核心业务 YAML：产品范围、角色场景、核心对象规则、权限并发、AI/Runner、安全与验收业务语义；
2. 服从核心 YAML 的当前工程契约：SYSTEM_DESIGN、OpenAPI、DDL、State Owner、Permission Closure、Authentication Contract、Event Contracts、正式验收规范；
3. ADR 只提供决策理由；未同步核心 YAML/工程契约时不得单独升级为当前产品事实；
4. 活动代码、测试、UI 文案只能作为现状证据，不能反向覆盖冻结产品事实。

使用 `$ai-auto-test-platform-context-efficiency` 的 `impact.authority / authority_refs` 做精准检索；全局检索不缩水，但不得为了产品门无条件把整个基线正文加载进模型。

## 四、唯一允许的门禁状态

### `PRODUCT_DECISION_NOT_REQUIRED`

任务只涉及不改变产品可观察语义的工程/视觉实现。记录状态后直接进入 Architecture Risk Gate 或实现流程。

### `PRODUCT_FACT_FOUND`

当前权威事实已明确且无冲突。必须记录最小 `authority_refs`，后续 Architecture/Contract/Implementation 只能实现该事实，不得重新裁决。

### `PRODUCT_DECISION_REQUIRED`

任务涉及产品主权，但当前权威源没有定义足以唯一实现的规则。若当前/既有用户输入尚未给出唯一裁决，生成 Product Decision Pack 并保持 `PENDING / BLOCKED_BY_PRODUCT_DECISION`；若用户已经明确决定该缺失规则，则保持 gate status 为 `PRODUCT_DECISION_REQUIRED` 直到权威事实同步，但记录 `CONFIRMED / AUTHORITY_UPDATE_ONLY`，不得重复询问。

### `PRODUCT_CONFLICT_DETECTED`

两个或以上当前候选权威来源对同一产品语义冲突，且不能按 Authority Model 确定唯一有效事实。不得自行挑选“看起来更合理”的版本；未决时生成 Product Decision Pack 并阻断。若用户已经明确选择冲突解决方向，则记录 `CONFIRMED / AUTHORITY_UPDATE_ONLY`，先同步受治理权威事实，不得再次要求用户选择同一问题。

### `PRODUCT_SCOPE_CHANGE`

用户请求本身要求新增/删除/改变 R4.2 已冻结产品能力、业务规则、状态、权限、公开契约或验收行为。必须明确这是产品范围变化，而不是 Engineering Autonomy。若当前用户请求已经把目标行为描述到足以唯一落地，它本身就是 `CURRENT_USER_REQUEST` 来源的明确裁决，应记录 `CONFIRMED`，**禁止为了门禁形式再次要求确认**；但在形成可追溯的当前权威事实前仍不得编码该新语义，只能进入 `AUTHORITY_UPDATE_ONLY`。

## 五、Product Decision Pack

遇到 `PRODUCT_DECISION_REQUIRED / PRODUCT_CONFLICT_DETECTED / PRODUCT_SCOPE_CHANGE` 时，按 `references/product-decision-pack.md` 输出紧凑决策包，至少包括：

- 决策问题与业务上下文；
- 已检索的当前权威事实及引用；
- 明确缺口/冲突；
- 2–4 个真正可实现且互斥的候选方案；
- 每个方案的用户/业务、UI、API、数据、状态、权限、安全、Runner/Worker、验收影响；
- **一个推荐方案与理由**，但显式标记 `recommendation_is_approval: false`；
- 未有明确用户裁决时记录 `user_decision.status=PENDING / decision_source=NONE`；
- 当前请求、既有用户决定或 Decision Pack 选择已明确时记录 `user_decision.status=CONFIRMED` 与真实 `decision_source`，不得重复询问；
- 用户确认导致新增/修改/删除产品事实、解决权威冲突或范围变化时，标记 `authority_update_required=true / workflow_state=AUTHORITY_UPDATE_ONLY`。

不要向用户抛出“这个怎么处理？”这类无结构问题；应尽量让用户可以直接在 A/B/C 中裁决。若当前用户请求已经给出完整决定，不得为了形式制造伪选项；Decision Pack 可直接记录 `selected_option=USER_DEFINED` 及其影响。

## 六、用户裁决后的处理

用户明确选择方案后，或当前用户请求本身已经包含足够明确的产品决定时：

- 记录 `user_decision.status=CONFIRMED`，并把 `decision_source` 设置为 `CURRENT_USER_REQUEST / PRIOR_USER_DECISION / DECISION_PACK_SELECTION` 中的真实来源；不得把 AI 推荐当作用户确认，也不得重复询问用户已经明确决定的同一问题；
- 只要该确认会**新增、修改、删除产品事实，解决权威冲突或形成产品范围变化**，必须设置 `authority_update_required=true / workflow_state=AUTHORITY_UPDATE_ONLY`；其中 `PRODUCT_DECISION_REQUIRED + CONFIRMED` 默认意味着新增原缺失产品事实，不能因为“不是修改已有事实”而保持 false；
- `AUTHORITY_UPDATE_ONLY` 阶段仅允许受治理权威事实更新/新基线流程，或按用户当前任务明确授权同步相应权威文档；Architecture、Contract 设计扩张和 Implementation 均不得提前消费该新语义，代码不得先成为事实源；
- 权威事实更新后必须重新执行产品主权门，Task Context Pack 的 `product_authority` 只有重新得到 `PRODUCT_FACT_FOUND`（或重新判定 `PRODUCT_DECISION_NOT_REQUIRED`）才能设置 `workflow_state=READY_FOR_ARCHITECTURE` 并进入 Architecture Risk Gate；
- 用户只决定纯工程选项且不改变产品语义时，应重新判定为 `PRODUCT_DECISION_NOT_REQUIRED`，不应伪造产品范围变化。

## 七、与其它 Skill / Agent 的边界

- `$ai-auto-test-platform-context-efficiency`：负责宽检索、Impact Map、authority slice 和 freshness；本 Skill 不重复全仓探索；
- `$ai-auto-test-platform-feature-orchestrator`：负责在 Architecture 之前执行本门，并在真实 Product/Authority `IMPACT_EXPANSION` 后重新检查；
- `$ai-auto-test-platform-architecture` / `solution_architect`：只在产品事实明确后决定技术实现；架构师发现产品缺口时必须路由回本 Skill；
- Contract/DB/Security/UI/Backend/Frontend：消费 `PRODUCT_FACT_FOUND` 的事实，不拥有批准权；发现新产品语义必须使 `product_authority` 失效并回到本门；
- 本 Skill **不新增 Product Manager Agent**；若未来真实任务证明需要长期独立产品分析上下文，再单独评估只读 `product_decision_analyst` Agent。

## 八、禁止事项

- 把推荐方案、常见行业做法或现有代码行为写成“已批准产品事实”；
- 为了不中断编码而自动选择候选方案；
- 用架构合理性、数据库便利性或 UI 美观性反向决定产品业务规则；
- 产品事实已明确时重复发散多个方案制造无意义决策；
- 产品门每次都加载完整基线或生成长篇 PRD；
- 在 `PRODUCT_DECISION_REQUIRED / PRODUCT_CONFLICT_DETECTED / PRODUCT_SCOPE_CHANGE` 未关闭时让未决语义进入 Architecture/Implementation；
- 修改冻结基线来“配合”当前代码，而不是先取得用户产品裁决。

## 九、完成输出

至少给出：

```text
PRODUCT_AUTHORITY_GATE = <状态>
authority_refs = <最小引用或NONE>
decision_pack_ref = <NONE或引用>
user_decision_status = <NOT_REQUIRED|PENDING|CONFIRMED>
decision_source = <NONE|CURRENT_USER_REQUEST|PRIOR_USER_DECISION|DECISION_PACK_SELECTION>
authority_update_required = <true|false>
workflow_state = <READY_FOR_ARCHITECTURE|BLOCKED_BY_PRODUCT_DECISION|AUTHORITY_UPDATE_ONLY>
```

只有 `PRODUCT_DECISION_NOT_REQUIRED` 或 `PRODUCT_FACT_FOUND` 且 `workflow_state=READY_FOR_ARCHITECTURE` 才允许该产品域继续进入 Architecture Risk Gate。`CONFIRMED` 只证明用户已经决定，不代表当前权威事实已经同步。

## 参考

- `references/product-decision-pack.md`
