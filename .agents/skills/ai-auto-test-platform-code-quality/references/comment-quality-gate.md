# Changed Complex Symbol Comment Gate

## 目标

本 Gate 只检查**当前 Task 真正发生变化的 symbol / line range**。它不扫描整个历史仓库，也不会因为某个大型文件被改过一行，就追溯要求该文件所有历史复杂函数补注释。

范围证据必须来自 Task Context Pack / Incremental Closure，例如：

```json
{
  "changes": [
    {
      "path": "services/api/src/platform_api/auth_service.py",
      "symbols": ["AuthenticationService.change_password"],
      "line_ranges": [[420, 486]]
    }
  ]
}
```

也支持 `changed_symbols / changed_line_ranges` 的 path-keyed 结构。没有 symbol/range scope evidence 时 Gate fail-closed 返回 `CHANGE_SCOPE_EVIDENCE_REQUIRED`；不存在的 symbol 返回 `CHANGED_SYMBOL_NOT_FOUND`。**禁止 path-only 整文件扫描作为正式 Verification Gate。**

Web/TS/JS/Vue 的 changed symbol 边界必须复用 `workspace_snapshot.py` 的机械 symbol parser，并且**逐 symbol 独立**做复杂度与原因型注释判定；禁止先把多个 symbol 合并为一个大文本窗口后用任意一条注释覆盖其它 symbol。函数调用点不能代替 declaration boundary。每个 symbol 只能消费自身函数体内注释或**紧邻 declaration、连续且无其它代码/`}` 隔断的 leading comment block**；固定 `start-N` 窗口禁止使用，前一个函数内部/尾部的原因型注释不得替后一个相邻函数通过 Gate。

## 复杂符号判定

风险关键词只是加权证据，不自动等于复杂。只有风险域同时存在一定结构复杂度（分支/调用/跨度），或符号本身达到明显复杂度阈值时才触发 Comment Gate。

因此：

- `get_state(state): return state` 即使含 `state` 也不强制注释；
- Auth/RBAC/事务/回滚/幂等/并发/锁/retry/补偿/状态转换/Runner/Worker/Scheduler 等存在非平凡控制流时触发；
- 简单 CRUD、DTO/Model 字段声明、getter/setter、显然赋值、generated/build output 自动跳过。

## 原因型注释

通过 Gate 的中文注释/Docstring必须表达原因、不变量或失败防护，例如包含“避免、防止、确保、保证、否则、因为、为了、以免、从而、因此、回滚、不变量”等原因语义。

`# 状态`、`# 校验`、`# 获取用户` 这类只复述代码的中文注释不能通过原因型 Gate。

## 执行

正式 Verification 只接受 `workspace_snapshot.py delta` v4 生成的 workspace 外 task-delta：

```text
python .agents/skills/ai-auto-test-platform-code-quality/scripts/comment_quality_gate.py \
  --root <workspace> \
  --task-delta <workspace外>/task-delta.json \
  --checkpoint <workspace外>/task-checkpoint.json
```

`task-delta.json` 必须包含完整 `task_start/current/task_delta`。FULL Task 使用完整 Stage Checkpoint；LOCAL 正式代码写入使用 `LIGHTWEIGHT_LOCAL` CP-0 evidence anchor，二者都提供同一机械 task-start 绑定。 Python 与 Web 都按 symbol declaration boundary 独立归属注释：只接受符号体内注释或与 declaration 同缩进、连续紧邻的 leading comment/docstring；前一个函数内部/尾部注释不得给后一个函数兜底。Gate 会校验两个 snapshot 的稳定 evidence digest，把 `task_start.snapshot_evidence_digest` 与 Checkpoint CP-0 绑定，再现场 capture 当前 workspace 并重新执行 `compare_snapshots(task_start, actual_current)`；只有重算结果与 supplied task_delta 完全一致时才接受。伪造 EMPTY delta、篡改 scope 或重放旧 current snapshot 均 fail-closed。调用方不得在 formal mode 叠加手工 symbol/range。

`--diagnostic-scope --changed-symbol/--changed-range/--changes-file` 仅允许定点诊断与 Contract Test，**不得作为正式 Verification 的可信证据**。

结果：

- `PASS`：本 Task 机械识别出的复杂 changed symbols 已有原因型注释，或没有需要注释的复杂 changed symbol；
- `FAIL`：存在 `COMMENT_REQUIRED` finding，必须修复后再进入 Verification；
- `ERROR`：机械 task-delta/Checkpoint 绑定缺失、snapshot evidence 不一致、delta 重算不一致或 stale replay，必须重新生成 Task Delta，禁止回退到调用方自报 scope。

本 Gate 是 Implementation Standards 的机械补充，不替代 `code_quality_reviewer` Review Mode。


正式 Gate 的 PASS 不是独立日志：Gate 必须通过 Feature Orchestrator Checkpoint 的私有进程内 API写入 `code_quality.comment_gate` attestation。该证据绑定 CP-0 task-start snapshot、当前 workspace digest 与 task-delta；LOCAL 完成、FULL Verification/Closure 必须机械消费它，Gate 后任何 workspace 改动都会使 attestation 失效并要求重新生成 delta/重新 Gate。
