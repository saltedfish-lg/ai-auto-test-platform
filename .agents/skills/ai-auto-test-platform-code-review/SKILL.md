---
name: ai-auto-test-platform-code-review
description: AI自动化测试执行平台实现后的严格只读代码审查；覆盖契约、权限、安全、事务、状态、生成物、测试真实性与R4.2一致性。
---

# Independent Code Review

严格只读，不修改文件。

如果支持 subagent，可分别委派 `contract-guardian`、`database-integrity-reviewer`、`security-rbac-reviewer`、`ui-verifier` 角色进行独立检查，再合并去重；不支持则按同样维度串行审查。

每个问题必须给：严重度、代码路径/行、权威契约路径、为什么错、影响、唯一修复方向、复查方法。

优先级：

- P0：安全绕过、数据破坏、冻结契约实质冲突、错误授权/越权；
- P1：业务状态/事务/幂等/并发错误、API/DDL 漂移、假持久化；
- P2：重要测试缺口、错误处理/可观测性/可维护性问题；
- P3：低风险质量问题。

禁止只给“代码更优雅”之类无证据意见。
