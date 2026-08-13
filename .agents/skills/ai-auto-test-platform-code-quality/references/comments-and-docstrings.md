# Comments and Docstrings

## 必须优先说明的内容

- 业务不变量；
- 非显然状态转换；
- 安全/权限边界；
- 事务、幂等、并发、锁、重试、补偿原因；
- 外部系统/框架限制；
- 兼容行为和删除条件。

## 风格

- 使用中文、第三人称或客观陈述。
- 解释“为什么”，不重复“代码做了什么”。
- 保持短而准确，随实现同步更新。
- 简单 CRUD、getter、赋值和显而易见分支不强制注释。
- generated 代码禁止人工补注释。
- `# 状态`、`# 校验`、`# 获取用户` 等仅有中文但没有原因/不变量语义的注释，不视为原因型注释。

## Docstring

公共 Domain/Application/Security 能力在签名无法充分表达职责、前置条件、异常或状态影响时应提供简洁 Docstring；需要通过原因型 Gate 时，Docstring 同样应说明为什么存在该约束或需要保护什么不变量。

## Changed Complex Symbol Gate

本规范不使用“注释率”或“每个函数必须 Docstring”。Implementation 完成后必须消费 `workspace_snapshot.py delta` v4 机械生成的当前 Task `changed_symbols / changed_line_ranges`，只对真正改动且具备非平凡复杂度的业务符号运行 `scripts/comment_quality_gate.py`。风险关键词只是复杂度加权，不能单独把简单 getter/CRUD 判成复杂。禁止仅凭 `task_delta_paths` 对整个大型历史文件做追溯整改。

治理脚本/Contract 测试不属于本业务注释 Gate；它们仍遵循可读性规范，但不以业务原因型注释作为机械准入条件。
