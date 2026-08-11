---
name: ai-auto-test-platform-code-review
description: AI自动化测试执行平台实现后的严格只读代码审查；覆盖契约、权限、安全、事务、状态、生成物、测试真实性与当前 authority 一致性。
---

# Independent Code Review

严格只读，不修改文件。

优先消费父 Orchestrator 已提供的、与**同一 workspace 状态和同一 scope**对应的最新 `contract_guardian`、`database_integrity_reviewer`、`security_rbac_reviewer`、`code_quality_reviewer`、`ui_verifier` 结果，并进行去重、反证和遗漏检查。

只有专项报告不存在、scope发生变化，或代码在专项审查后再次修改时，才重新调度对应Reviewer；不得无条件递归重复Review。若当前环境不支持subagent，则按相同维度串行审查。

每个问题必须给：严重度、代码路径/行、权威契约路径、为什么错、影响、唯一修复方向、复查方法。

优先级：

- P0：安全绕过、数据破坏、当前 authority 契约实质冲突、错误授权/越权；
- P1：业务状态/事务/幂等/并发错误、API/DDL 漂移、假持久化；
- P2：重要测试缺口、错误处理/可观测性/可维护性问题；
- P3：低风险质量问题。

禁止只给“代码更优雅”之类无证据意见。

## Context / Impact Closure

最终审查优先消费同一workspace/scope的 Task Context Pack 与 Post-change Impact Closure。若闭环不是 `IMPACT_CLOSURE_PASS`、证据过期或审查发现新的跨层消费者，必须触发增量影响检索/`IMPACT_EXPANSION`，不得仅因现有diff看起来正确就通过。Task Context Pack不是权威事实，Reviewer可按风险扩张。
