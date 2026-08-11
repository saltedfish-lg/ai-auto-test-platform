---
name: ai-auto-test-platform-code-quality
description: AI自动化测试执行平台代码质量实施规范与独立只读审查Skill；用于前后端编码时约束可维护性，也用于code_quality_reviewer按多Lane检查结构、hack、回归、测试、注释和长期维护风险。
---

# AI Auto Test Platform Code Quality

## 两种使用模式

### A. Implementation Standards Mode

当本 Skill 由 `backend_implementer`、`frontend_implementer` 或其他获准的实现 Agent 在编码过程中引用时：

- 本 Skill 作为实现质量规范，不改变父 Agent 的 `workspace-write` 权限；
- 实现 Agent 可以在父任务已授权范围内正常修改代码、测试和配置；
- 编码时主动满足结构、注释、测试、回归和可维护性要求；
- 不得因为加载本 Skill 自行切换成只读 Reviewer。

### B. Review Mode

当本 Skill 由 `code_quality_reviewer` 或最终独立审查流程调用时：

- 严格只读；
- 不修改代码、测试、配置、文档或 Git 状态；
- 只输出有证据、可验证、与当前 scope 直接相关的 finding；
- 相同 workspace 状态、相同 scope 已有最新专项报告时优先消费和去重，避免递归 Review Loop。

## 入口

先读根 `AGENTS.md`、core Skill，并优先消费 `$ai-auto-test-platform-context-efficiency` 生成的同一workspace/scope Task Context Pack、真实diff、改动代码和相关测试。按需读取 当前 authority 正式事实与 `references/**`，不要一次性把所有参考材料塞入上下文。Task Context Pack 只是索引：发现遗漏、过期或可疑跨层消费者时必须增量全局检索，不得为了省Token盲信Pack。

## 六个审查 Lane

1. **Structure / Thermo**：职责、依赖、ownership、过度间接层、God Service/Component；约350行只触发深查，不自动判错。
2. **Hack / Shortcut**：吞异常、fallback掩盖不变量、硬编码、平行重复模型、test-only生产逻辑、sleep/retry掩盖根因、临时兼容永久化。
3. **Regression**：比较改动前后输入→guard→状态/数据→外部效果→错误处理→用户可见结果，识别非预期行为回归。
4. **Testing**：重大逻辑/用户行为变化必须有与风险相称的测试；跨层行为优先contract/integration/E2E；避免只测实现细节。
5. **Comments / Readability**：关键原因型中文注释/Docstring、清晰命名、错误处理可读性；拒绝机械复述和过时注释。
6. **Maintainability**：复杂度、重复、错误处理、资源/性能坏味道、边界泄漏和长期技术债。

## 职责边界

本 Skill 不重新裁决：

- 当前 authority/OpenAPI/DDL/状态/权限事实：交给 `contract_guardian`；
- JWT/密码/RBAC/Secret 等安全事实：交给 `security_rbac_reviewer`；
- MySQL/Migration/FK/CHECK/事务完整性：交给 `database_integrity_reviewer`；
- 浏览器真实交互：交给 `ui_verifier`。

若质量问题同时触及这些领域，应给出路由目标，但避免重复完整专项审查。

## Finding原则

每个 finding 必须包含：

- 严重度；
- Lane；
- 文件与行号/符号；
- 证据；
- 具体影响；
- 最小且不扩大产品语义的修复方向；
- 复查/测试方法。

禁止：

- 仅凭个人风格偏好要求重构；
- 为减少行数机械拆文件；
- 将必要的防御性guard误判为hack；
- 把无正式事实支持的“最佳实践”当产品缺陷；
- 以增加抽象层作为默认答案。

## 参考

- `references/review-lanes.md`
- `references/python-quality-rules.md`
- `references/vue-typescript-quality-rules.md`
- `references/comments-and-docstrings.md`
- `references/testing-quality-rules.md`
- `references/report-format.md`
- `references/design-provenance.md`
