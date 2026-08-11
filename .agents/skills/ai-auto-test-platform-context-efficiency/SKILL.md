---
name: ai-auto-test-platform-context-efficiency
description: AI自动化测试执行平台上下文效率与影响闭包Skill；在Single Living Authority和Git隔离前提下，通过一次全局影响扫描、共享Task Context Pack、文件系统快照和增量闭包降低重复探索。
---

# Context Efficiency

不再设置独立 Context Analyst Agent；正式 Full Impact Scan 的唯一执行者是 Orchestrator 当前主 Agent。 & Impact Closure

## 核心原则

> **全局检索不缩水，模型加载才收敛。**

本 Skill 只减少重复加载和重复推理，不得缩小事实检索、契约验证、测试或跨模块影响覆盖。

当前权威模型固定为：

```text
SINGLE_LIVING_AUTHORITY
root = docs/authority
versioned_baseline_copies = false
Git access for Codex = DISABLED
```

不存在 `CURRENT → R4.x` 解析；不得创建 R4.3/R4.4/R4.5 等整套 authority 副本，也不得依赖 Manifest/Release Snapshot 判断当前事实。

## 与 Stage Checkpoint 的边界

- `feature-orchestrator` 是唯一 `TASK_LIFECYCLE_OWNER`。
- 本 Skill 是 `CONTEXT_STATE_PROVIDER`，只提供 workspace identity、authority digest、Task Context Pack、filesystem snapshot、task delta 与 freshness。
- 本 Skill 不推进 stage、不维护第二套 checkpoint。
- `RESUME_EXACT` 直接复用仍有效证据。
- `RESUME_WITH_DELTA_REFRESH` 只允许 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`。
- workspace/root/authority-root 身份不兼容时由 Orchestrator `RESUME_REJECTED`。
- authority digest 变化不是新版本，也不是默认 Resume Reject；它触发 Authority/Product/下游的最小增量重验证。

## Shared Task Context Pack

父编排已有同 Task 且 `freshness=CURRENT` 的 Pack 时，所有子 Agent：

```text
MUST_CONSUME_TASK_CONTEXT_PACK
```

禁止：

- 自行建立第二个完整 Impact Map；
- 再次执行 `impact_scan.py`；
- 无条件重复通读完整 authority/OpenAPI/DDL/仓库；
- 以“独立审查”为理由重新 Full Scan。

正式 CROSS_MODULE/HIGH_RISK Pack 缺失或身份无效时返回 `TASK_CONTEXT_PACK_REQUIRED`。

## Task-start Filesystem Snapshot

正式修改开始前、任何 workspace 写入前执行：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  capture --root . --out <workspace外>/task-start-workspace.json
```

`snapshot_version=3`，采用 `FILESYSTEM_ONLY`：

- 对受控工作树文件做 SHA-256 指纹；
- 排除 `.git/node_modules/dist/build/.venv/__pycache__/.pytest_cache/.mypy_cache/.ruff_cache/.runtime/.tmp` 等噪声；
- 不执行任何 Git 命令；
- snapshot/delta 必须位于 workspace 外；
- 绑定 resolved root + filesystem workspace identity。

修改后执行：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  delta --root . --start <workspace外>/task-start-workspace.json --out <workspace外>/task-delta.json
```

得到：

```text
added
removed
modified
task_delta_paths
delta_digest
```

因此历史 Git dirty state 不再属于 Codex 上下文；Codex 只关心当前 Task 在文件系统上真正产生的变化。

## Pre-change Impact Closure

正式 CROSS_MODULE/HIGH_RISK Task 在首次写入前必须建立 Pre-change Impact Closure。`feature-orchestrator` 是唯一 Full Scan 调度 Owner，当前主 Agent 使用：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/impact_scan.py \
  <seed...> --risk HIGH_RISK --formal-task \
  --task-id <task-id> --scan-state <workspace外>/impact-scan.json --json
```

### Single Full Impact Scan

每个正式 Task：

```text
FULL_IMPACT_SCAN_MAX_SUCCESSFUL_RUNS = 1
```

- 第一次成功后 `full_rescan_allowed=false`；
- canonical guard 由 `workspace_root + task_id` 派生，更换 state 路径也不能绕过；
- 第二次必须 `IMPACT_SCAN_ALREADY_COMPLETED`；
- 首次扫描因 required scope/scan error 失败时 `successful_run_count=0`，修复后允许重试；
- 禁止通过更换 task_id 为同一个任务制造第二次额度。

## Search Scope

`schemas/context-policy.yaml` 的 required scope 默认包含：

- root engineering facts；
- apps/services/workers/runner/packages/tests/tools；
- **唯一 `docs/authority`**；
- `.agents/.codex` 仅治理任务显式扩张；
- `.github/db` 存在则纳入。

required root 或 `docs/authority` 缺失、活动文本扫描错误时：

```text
closure_safe = false
BLOCKED_BY_INCOMPLETE_SCOPE
```

不得把“不完整扫描”当作“无影响”。

## Broad Search, Narrow Load

第一次 Full Scan 使用 `impact_scan.py` 搜索活动仓库。大文件按行流式扫描，不因体积静默跳过 authority YAML。

全局搜索结果只保留：

```text
path + group + line + short preview
```

然后才按职责加载最小文件片段。不要把完整 OpenAPI、DDL、YAML、事件 schema 集合一次性塞入模型。

## Living Authority

`docs/authority/**` 是唯一活动事实源：

- 产品事实明确：直接引用；
- 用户明确要求改变事实，或 Product Decision 已 `CONFIRMED`：进入 `AUTHORITY_UPDATE_ONLY`，直接修改受影响源文档；
- 修改后运行 authority validators，再重新 Product Gate；
- `PRODUCT_FACT_FOUND` 后才进入 Architecture/Implementation；
- 不创建版本目录、不生成 Manifest、不把代码反向当成产品事实源。

Authority digest 只用于 freshness/Resume，不用于制造不可变版本。

## Incremental Closure

Pack `STALE`、实现完成或发现新消费者时，只允许：

```text
DELTA_REFRESH
+
TARGETED_REVERSE_LOOKUP
```

Targeted lookup 必须有明确 seed，例如：

- old/new symbol；
- operationId / DTO；
- table / column / migration；
- permission / state / event；
- route / store / component；
- config key / Runner capability。

可以多次执行 targeted lookup，但不得调用 `impact_scan.py`，不得退化成无种子第二次全仓探索。

`IMPACT_EXPANSION` 只扩充现有 Pack、递增 `pack_revision`、更新 `expert_selection`，不会获得新的 Full Scan。

## Architecture / Product Freshness

- Product/Authority 影响新增 → `product_authority.freshness=STALE`，重新 Product Gate；
- 新 state owner / transaction / consistency / concurrency / Runner-Worker domain → Architecture 标 STALE 并 recheck；
- 普通非架构 delta 仅做 revision rebind，不重复 Architecture Risk 判级；
- 已完成且 CURRENT 的专项 Reviewer 结果继续复用。

## Post-change Closure

实现后：

1. filesystem snapshot 计算 `task_delta_paths`；
2. 从真实变化提取 changed symbols/contracts；
3. 做 targeted reverse lookup；
4. 必要时 `IMPACT_EXPANSION`；
5. 运行与风险域相符的 contract/database/security/UI/code-quality 验证；
6. 得到 `IMPACT_CLOSURE_PASS` 或显式 blocker。

不得用任务开始前的历史状态、Git diff 或外部提交记录冒充当前 Task delta。

## Git 边界

Git 完全由用户在 IDEA 中负责。Codex、Custom Agent 和 Skill：

```text
MUST_NOT_INVOKE_GIT
```

包括只读和写入命令，例如 `git status/diff/log/show/add/commit/push/pull/fetch/checkout/reset/tag`。Git branch、commit、tag、remote、index、tracked-deleted 不进入 Context Pack、Checkpoint、Impact Closure 或 DoD。

## 完成状态

- `IMPACT_CLOSURE_PASS`
- `IMPACT_EXPANSION`
- `BLOCKED_BY_PRODUCT_DECISION`
- `BLOCKED_BY_ENVIRONMENT`
- `BLOCKED_BY_INCOMPLETE_SCOPE`

环境阻断只描述真实无法执行的验证，不再使用 Git metadata 缺失作为环境 blocker。


## Product Authority 同步边界

`CONFIRMED + authority_update_required=true` 时只允许 `AUTHORITY_UPDATE_ONLY`，禁止 Architecture/Implementation；authority digest 更新并重新 Product Gate 后才继续。
