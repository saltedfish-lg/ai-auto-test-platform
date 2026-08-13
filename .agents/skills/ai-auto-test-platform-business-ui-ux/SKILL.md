---
name: ai-auto-test-platform-business-ui-ux
description: AI自动化测试执行平台业务驱动UI/UX设计与审查Skill；先理解测试角色、任务、状态、风险和操作频率，再设计信息架构、交互和视觉，避免机械化AI后台，同时控制额外上下文与Agent开销。
---

# Business-driven UI/UX

## 目标

解决两类问题：

1. UI 不能只是“Element Plus + 卡片 + 表格 + Dialog”的机械拼装；
2. UI 美化必须服务测试业务，而不是为了视觉效果改变当前产品语义。

本 Skill 的设计权属于 **Engineering Autonomy**：可以自主决定布局、视觉层级、组件组合、密度、间距和交互表现，但不得自创业务对象、状态、权限、API、规则、审核流程或高风险行为。

## Token 策略

默认不单独启动 Designer Agent。

- **UI_LOW**：文案、小样式、单控件、无业务流变化；`frontend_implementer` 内嵌使用本 Skill 的轻量清单。
- **UI_MEDIUM**：新增常规页面、较大信息架构调整、复杂表格/表单/详情；生成紧凑 Business UX Spec，通常仍由当前 Agent 内嵌完成。
- **UI_HIGH**：新建核心工作台、AI探索/录制/执行/Runner/报告等复杂页面，或大规模重设计；才按需调用 `business_ui_ux_specialist`：修改前使用 `DESIGN_MODE` 产出 Business UX Spec，实现后确需独立体验审查时复用同一角色的 `REVIEW_MODE`。

所有 UI Agent 优先消费 `$ai-auto-test-platform-context-efficiency` 生成的 Task Context Pack，不重复通读完整当前 Authority。

### UI_HIGH 现有页面改造：Pre-change Browser Evidence

UI_HIGH 若是**现有页面重设计/美化**，在 Designer 产出方案前必须先用 `$ai-auto-test-platform-ui-quality` 的 `PRE_CHANGE_CAPTURE` 模式记录当前真实页面：

- 固定常用桌面 viewport；
- 记录主工作台首屏、一个核心业务状态、当前主要操作路径；
- 记录信息层级、密度、溢出/遮挡、Console/Network 明显问题；
- 只保存紧凑证据/截图索引，不把整页 DOM 或大量截图文本塞入上下文。

新建页面没有可比较的旧页面时标记 `PRE_CHANGE_EVIDENCE = NOT_APPLICABLE_NEW_PAGE`，禁止伪造 before 证据。

如果因为后端/MySQL/认证/测试账号/浏览器依赖/旧页面自身故障导致真实 Before 页面无法取得，标记：

- `PRE_CHANGE_EVIDENCE = BLOCKED_BY_ENVIRONMENT`
- `CURRENT_UI_EVIDENCE = SOURCE_BASED_CURRENT_UI_EVIDENCE`
- `VISUAL_EVIDENCE_CONFIDENCE = LIMITED`

此时允许基于当前 Vue 源码、路由、组件、已有测试/截图和业务事实继续设计与实现，但**禁止把源码推断冒充真实 Before 截图**；同时登记 `POST_CHANGE_BROWSER_VERIFY = REQUIRED`，环境恢复后必须补真实浏览器验证。`business_ui_ux_specialist` 的 `REVIEW_MODE` 在这种状态下审查“变更前源码证据 + Post-change 真实证据 + LIMITED 置信度”，不得强制要求一个不存在的 Before screenshot。


## 一、设计前必须回答的业务问题

只读取与当前页面直接相关的角色、菜单、场景、对象、状态、权限和API片段，回答：

- **WHO**：谁最常使用？角色/Persona 是什么？
- **WHY**：进入页面的核心目标是什么？
- **WHAT**：最重要的 1–3 个任务是什么？
- **FREQUENCY**：高频动作与低频动作分别是什么？
- **RISK**：哪些动作不可逆、敏感、破坏性或会影响执行？
- **PRIORITY**：第一屏必须看见哪些状态/异常/证据？
- **STATE**：Loading、Empty、Error、Forbidden、Conflict、Running、Partial Failure 等如何表达？
- **FLOW**：完成主任务最短操作路径是什么？

禁止先决定“放几个卡片”，再倒推业务。

## 二、页面原型选择

按 `references/page-archetypes.md` 选择最接近的工作台原型，不允许全平台套同一种 Dashboard/Card 模板。

核心分类：

- Management Workspace
- Authoring Workspace
- AI Assisted Workspace
- Operational Monitoring
- Diagnosis / Analysis
- Governance / Configuration
- Monitoring / Logs
- Authentication / Security Flow

## 三、Business UX Spec

UI_MEDIUM/UI_HIGH 先产出紧凑规格，禁止大段作文：

```yaml
page: <页面/工作台>
ui_risk: UI_MEDIUM | UI_HIGH
primary_users: []
primary_goal: <一句话>
top_tasks: []
first_screen_information: []
primary_actions: []
secondary_actions: []
high_risk_actions: []
page_archetype: <类型>
layout: <master-detail/split-pane/table/editor/monitoring/...>
states: []
permission_experience: []
visual_hierarchy: []
anti_patterns_to_avoid: []
```

规格只引用权威事实，不复制完整业务文档。

## 四、反机械化设计规则

必须避免：

- 无业务理由的“三张/四张 KPI 卡片”首屏；
- 所有内容都套 `el-card`；
- 每个页面都用相同“标题 + 描述 + 卡片墙 + 表格”；
- 大量圆角、渐变、阴影、胶囊标签只是为了“像AI生成”；
- 内部工具页使用营销型 Hero、空洞英文 Eyebrow、装饰性大标题；
- 用 emoji / 随意字符代替一致的图标体系；
- 把低频设置项和高频主动作放在同一视觉层级；
- 仅靠颜色表达状态；
- 为“高级感”牺牲信息密度和扫描效率。

优先使用：

- 信息密度与可扫描性；
- Master-Detail、Split Pane、Sticky Action/Filter、Inline Status；
- 任务/执行时间线、失败优先、异常聚焦；
- 高风险动作降权、分组、确认和审计反馈；
- 语义化状态颜色 + 文本/图标；
- 统一 Design Token 与 Element Plus 组件语义；
- 测试工程工具应呈现“专业工作台”而不是“营销 SaaS”。

详见 `references/anti-mechanical-ui.md`。

## 五、测试业务特化

设计时必须主动识别：

- 测试资产：自然语言用例、结构化用例、模板、套件；
- AI任务：结构转换、页面探索、候选、checkpoint；
- 执行：计划、任务、用例进度、失败、重试；
- Runner：在线/离线/忙闲、能力、当前任务、心跳、租约/资源风险；
- 数据：资源池、分配、占用、回收、敏感性；
- 报告：失败定位、执行事实、制品、日志、重试聚合；
- 治理：用户、角色、权限、模型、配置、审计。

页面信息层级必须围绕当前业务目标，不得因为某字段存在就全部等权展示。

## 六、实现衔接

`frontend_implementer` 在编码前：

1. 使用 Context Efficiency 的 Task Context Pack；
2. 完成 UI 风险分级；
3. 使用本 Skill 生成轻量设计决策或 Business UX Spec；
4. 再进入 Vue/Element Plus 实现；
5. 复用现有 Design Token/组件，必要时新增可复用组件；
6. 不手改 generated client，不改变权限/状态/API语义；
7. 通过 `$ai-auto-test-platform-ui-quality` 做真实浏览器验证。

## 七、Review Mode

`business_ui_ux_specialist` 使用本 Skill 的 `REVIEW_MODE` 只读检查：

- 页面信息层级是否与业务优先级一致；
- 高频任务是否容易完成；
- 异常/失败/冲突是否比次要信息更醒目；
- 危险动作是否误与普通动作同权；
- 是否出现模板化卡片墙/营销式内部页面；
- 不同页面是否根据业务采用不同工作台结构；
- Loading/Empty/Error/Forbidden/Conflict 是否有可行动反馈；
- 权限隐藏是否被误当安全边界；
- 视觉是否一致但不过度装饰；
- 可访问性、键盘、焦点、文本对比和非颜色状态表达。

UI_LOW 默认不额外调度 Reviewer；UI_MEDIUM 由 `ui_verifier` + 内嵌清单即可；UI_HIGH 或用户明确要求“美化/重设计/审查体验”时才选择 `business_ui_ux_specialist` 的 `REVIEW_MODE`；不得为了固定流水线重复启动。

## 八、完成条件

UI_HIGH 必须具备：

- 现有页面重设计时的 Pre-change Browser Evidence；若因环境阻断则必须有 `SOURCE_BASED_CURRENT_UI_EVIDENCE + VISUAL_EVIDENCE_CONFIDENCE = LIMITED + POST_CHANGE_BROWSER_VERIFY = REQUIRED`（新页面明确 N/A）；
- Business UX Spec；
- 可运行页面；
- 关键状态浏览器证据；
- UI/UX Review 结论；
- 现有页面重设计时 Before/After 使用同 viewport、同关键状态做业务级比较；
- 不改变当前产品/契约事实；
- 无明显机械化模板反模式。

## 参考

- `references/page-archetypes.md`
- `references/anti-mechanical-ui.md`
- `references/business-context-loading.md`
- `references/design-system-rules.md`
- `references/ui-review-checklist.md`
- `references/token-budget.md`

