# R4.2 Context Efficiency + Business UI/UX Customization

本定制层不修改 `docs/baseline/R4.2/**` 冻结产品/工程契约，只增强 Codex 运行时 Agent/Skill 治理。

新增：

- `ai-auto-test-platform-context-efficiency`
- `ai-auto-test-platform-business-ui-ux`
- `context_impact_analyst`
- `business_ui_ux_designer`
- `ui_ux_reviewer`

核心目标：

1. 全局影响检索 + 精准上下文加载 + 修改后闭环验证；
2. 降低重复上下文和多Agent重复探索 Token；
3. UI按真实测试业务设计，减少模板化/机械化AI界面；
4. UI Agent按风险调度，避免“小改动也启动全套设计审查”造成额外Token。

关键不变量：Token优化不得降低搜索覆盖、契约/权限/状态/DB/Runner影响分析、测试或独立Review强度。

## 定点修复（Context/UIUX Closure）

- `impact_scan.py` 改为 CURRENT 动态解析、active_roots 真正生效、>4MB 权威文本流式扫描，禁止静默漏检；
- 扫描输出增加 missing roots / large streamed / binary skipped / scan errors / group summary；
- CROSS_MODULE/HIGH_RISK Task Context Pack 强制 workspace fingerprint 与 delta freshness；
- UI_HIGH 现有页面重设计增加 Pre-change Browser Baseline 与同 viewport/关键状态 Before/After；
- 命名 Custom Agent 路由不可用时采用 Role Card + Skill 串行 fallback，禁止 generic agent 冒充；
- 新增行为级 Contract Tests 锁定以上机制。


## Risk Architecture merge closure

- Restored required/optional/conditional-governance fail-closed Context Scope.
- Preserved read-only Git tracked-deleted impact evidence.
- Added reusable Task Context Pack `architecture_decision` to avoid repeated ARCH_RISK classification and duplicate `solution_architect` calls.
