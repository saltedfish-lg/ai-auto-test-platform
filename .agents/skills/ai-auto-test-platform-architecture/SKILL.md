---
name: ai-auto-test-platform-architecture
description: AI自动化测试执行平台按风险触发的技术架构裁决Skill；在当前产品/契约事实内判断模块边界、状态归属、事务、一致性、同步异步、事件、Runner/Worker、并发与恢复方案。ARCH_LOW不额外启动架构Agent，ARCH_MEDIUM由当前实现Agent内嵌轻量检查，ARCH_HIGH才调用只读solution_architect。
---

# Risk-triggered Architecture Decision

## 定位

本 Skill 是**技术架构裁决层**，不是产品经理、需求裁决者或常驻万能 Agent。

它回答：

- 这项能力应该落在哪个模块/层；
- 谁拥有状态与写权限；
- 谁可以依赖谁；
- 事务边界在哪里；
- 同步还是异步；
- 是否需要 Event / Outbox / Idempotency；
- Runner / Worker / Platform 各自承担什么职责；
- 并发、锁、租约、fencing、恢复和一致性如何实现；
- 当前方案是否产生循环依赖、双写、状态多主、旁路写入或不可恢复耦合。

它**不得**改变 当前 Living Authority 已确认的产品语义、OpenAPI、DDL、权限、状态机、Runner 规则、验收规则或安全边界。

## 一、先复用当前 Architecture Decision

若 Task Context Pack 已包含 `architecture_decision`，且 `freshness=CURRENT`、`assessed_pack_revision == pack_revision`、`recheck_required=false`，必须直接复用，不得再次判定 ARCH_RISK 或重复调度 `solution_architect`。若只是非架构型 delta refresh 导致 `pack_revision` 前进，则先执行 **revision rebind**：保持 `freshness=CURRENT`、`recheck_required=false`，把 `assessed_pack_revision` 更新为新的 `pack_revision`，不重新裁决。只有决策缺失/STALE、`recheck_required=true`，或真实 `IMPACT_EXPANSION` 新增 state owner、transaction、consistency、concurrency、Runner/Worker、dependency domain 时才进入重新判级。

## 二、再做 ARCH_RISK 分级

每个正式编码任务在完成 Context Efficiency 的 Impact Map 后判断一次架构风险，但**不是每个任务都调用架构 Agent**。

### ARCH_LOW

典型范围：

- 局部函数/类内部重构；
- 单个 Repository 查询优化；
- 普通 DTO/Mapper 内部实现；
- 单页面组件拆分、样式和纯视觉实现；
- 不改变对外契约、状态归属、事务边界和跨模块依赖的 Bug 修复；
- 测试补充。

处理：

`Context Efficiency → Implementer`

- 不调用 `solution_architect`；
- 不额外生成 Architecture Decision；
- 现有架构边界不变即可。

### ARCH_MEDIUM

典型范围：

- 在既有模块边界内新增 Service / Repository / Handler；
- 新增普通 API、表或内部业务流程，但状态 Owner、依赖方向和事务模型不变；
- 新增 Worker handler，但不引入新的跨域一致性/恢复模型；
- 有少量跨层联动，但可以在既有架构规则内明确落位。

处理：

- 默认**不启动独立 Agent**；
- 当前实现 Agent 内嵌使用本 Skill 做 `Architecture Check`；
- 只输出 5–10 行紧凑结论：ownership、dependency、transaction、consistency、forbidden shortcuts；
- 若检查中出现 ARCH_HIGH 信号，立即升级。

### ARCH_HIGH

以下任一条件成立，默认升级：

- 跨 3 个及以上职责模块，且存在真实写路径/状态传播；
- 新增或改变 State Owner / write authority；
- 改变事务边界、跨表/跨模块原子性或双写策略；
- Event / Outbox / 异步编排 / 最终一致性 / 补偿；
- 并发、锁、租约、fencing、幂等、expected_version；
- Runner / Worker / Scheduler / Execution 的协作或恢复；
- 故障恢复、重试归属、任务迁移、重复消费、旧 Runner 回写防护；
- 新的跨模块依赖方向、共享基础设施或循环依赖风险；
- 重大领域重构、服务拆分/合并、共享内核职责改变；
- 安全/权限架构发生跨模块职责变化（具体安全事实仍交给 Security Reviewer）；
- 缓存、队列、分布式协调被引入为正式一致性组成部分。

处理：

`Context Efficiency → solution_architect(read-only) → Architecture Decision → Implementers/Reviewers`

`solution_architect` 默认只执行一次修改前裁决。只有真实 diff 或 `IMPACT_EXPANSION` 新增了架构域，才触发 `ARCH_RECHECK_REQUIRED`，禁止为了形式重复调用。

详见 `references/risk-routing.md`。

## 三、Architecture Decision 输出

ARCH_HIGH 使用 `references/architecture-decision.md` 的紧凑格式，至少包含：

- `arch_risk`；
- `affected_domains`；
- `state_owners` / write authority；
- `dependency_direction`；
- `transaction_boundaries`；
- `communication`（sync/async/event）；
- `consistency_model`；
- `idempotency_concurrency`；
- `failure_recovery`；
- `forbidden_shortcuts`；
- `implementation_targets`；
- `validation_targets`；
- `product_decision_required`。

只引用必要事实路径和 Task Context Pack，不复制完整 OpenAPI/DDL/YAML。

## 四、技术自主权与产品主权

架构裁决遵循 Engineering Autonomy：

### 可以自主裁决

- 模块内部类/方法拆分；
- Application/Domain/Infrastructure 的实现组织；
- 在当前 authority 契约内选择事务实现、Repository/UoW 组织；
- 在已明确需要幂等/Outbox/锁等前提下选择成熟技术实现；
- 日志、Tracing、内部 Adapter、Mapper 的结构；
- 不改变外部可观察语义的工程优化。

### 必须升级用户/产品裁决

如果“未定义事项”会改变任一项：

1. 用户可观察行为；
2. 业务规则或状态语义；
3. API / 数据 / 事件契约；
4. 权限或安全边界；
5. 跨模块业务职责、并发/恢复语义。

则输出 `BLOCKED_BY_PRODUCT_DECISION`，并路由 `$ai-auto-test-platform-product-sovereignty` 形成/复用 Product Decision Pack；禁止架构师自行创造规则。

例如“Runner 离线后任务是否自动迁移”属于产品/执行语义，不得由架构 Agent 私自决定。

详见 `references/technical-sovereignty.md`。

## 五、与现有专项 Agent 的边界

- `solution_architect`：技术架构边界、ownership、依赖、事务、一致性、恢复；
- `contract_guardian`：正式 API/DTO/状态/事件契约是否一致；
- `database_integrity_reviewer`：DDL/ORM/Migration/约束/事务物理实现；
- `security_rbac_reviewer`：认证/RBAC/数据范围/Secrets；
- `backend_implementer` / `frontend_implementer`：实际写代码；
- `code_quality_reviewer`：结构、hack、回归、测试、注释、可维护性；
- `independent_code_reviewer`：最终独立收口。

架构师不得重复这些专项 Reviewer 的完整审查，更不得以“最佳实践”为由覆盖当前已确认事实。

## 六、Context / Token 规则

- 优先消费 `$ai-auto-test-platform-context-efficiency` 的 Task Context Pack；
- ARCH_HIGH 只加载 architecture slice：authority、affected domains、state/event、DB/API边界、Runner/Worker、并发/事务、相关代码与历史有效 ADR；
- 不重新无条件通读完整当前 Authority/完整仓库；
- ARCH_LOW 禁止为了“更稳”额外调用架构 Agent；
- `ARCH_MEDIUM` 默认由当前 Agent 内嵌 Skill；
- `ARCH_HIGH` 才调度 `solution_architect`；
- 若命名 Custom Agent 不可可靠选择，走 Role Card + Skill 串行 fallback，禁止 generic Agent 冒充。

## 七、ADR 规则

本 Skill 不要求每个任务写 ADR。

- `ARCH_LOW`：不记录；
- `ARCH_MEDIUM`：Architecture Check 只进入任务结果；
- `ARCH_HIGH`：若是长期、跨模块、以后会反复被依赖的技术裁决，输出 `ADR_CANDIDATE = true`；
- `solution_architect` 自身只读，不直接创建 ADR；由主任务在明确需要治理文档且不触碰living authority时决定是否落盘。

详见 `references/adr-policy.md`。

## 八、完成状态

- `ARCH_NOT_REQUIRED`：ARCH_LOW；
- `ARCH_CHECK_PASS`：ARCH_MEDIUM 内嵌检查通过；
- `ARCH_DECISION_READY`：ARCH_HIGH 已形成只读架构裁决；
- `ARCH_RECHECK_REQUIRED`：真实改动暴露新的架构域；
- `BLOCKED_BY_PRODUCT_DECISION`：产品主权缺口；
- `BLOCKED_BY_INCOMPLETE_CONTEXT`：架构事实/Impact Pack 不足，必须增量检索。

## 九、参考

- `references/risk-routing.md`
- `references/architecture-decision.md`
- `references/technical-sovereignty.md`
- `references/adr-policy.md`
