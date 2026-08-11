# Task Context Pack

Task Context Pack 是当前 workspace 的**可失效索引**，不是当前已确认事实副本。唯一产品/契约事实源是 `docs/authority/**`。

```yaml
task: <一句话>
risk: LOCAL | CROSS_MODULE | HIGH_RISK
pack_revision: 1

authority:
  model: SINGLE_LIVING_AUTHORITY
  root: docs/authority
  digest: <当前 authority 内容摘要>
  versioned_baseline_copies: false
  git_access: DISABLED
  freshness: CURRENT | STALE

task_lifecycle:
  checkpoint_schema_version: 2
  checkpoint_ref: <workspace外 checkpoint.json>
  current_stage: TASK_INITIALIZED | CONTEXT_READY | DECISIONS_READY | IMPLEMENTATION_READY | IMPLEMENTATION_COMPLETE | VERIFICATION_COMPLETE | CLOSURE_COMPLETE
  resume_status: NOT_EVALUATED | RESUME_EXACT | RESUME_WITH_DELTA_REFRESH | RESUME_REJECTED | CHECKPOINT_CORRUPTED
  next_stage: <下一阶段或NONE>
  invalidated_stages: []
  full_impact_scan_on_resume_allowed: false

impact_scan:
  mode: FULL_IMPACT_SCAN
  status: NOT_RUN | COMPLETE | FAILED
  task_id: <唯一Task ID>
  scan_state_ref: <workspace外状态文件>
  canonical_guard_ref: <workspace_root+task_id派生锁>
  successful_run_count: 0 | 1
  max_successful_runs: 1
  full_rescan_allowed: true | false
  scope_digest: <扫描范围摘要>

workspace_fingerprint:
  mode: FILESYSTEM_ONLY
  git_access: DISABLED
  freshness: CURRENT | STALE
  task_start:
    snapshot_version: 3
    workspace_identity_digest: <filesystem workspace identity>
    workspace_root_identity: <resolved root摘要>
    snapshot_ref: <workspace外快照>
    workspace_digest: <受控文件内容摘要>
  current:
    snapshot_version: 3
    workspace_identity_digest: <必须与task_start一致>
    workspace_digest: <当前受控文件摘要>
  task_delta:
    status: NOT_COMPUTED | EMPTY | CHANGED | UNAVAILABLE
    delta_ref: <workspace外delta文件>
    added: []
    removed: []
    modified: []
    task_delta_paths: []
    delta_digest: <任务级变化摘要>

product_authority:
  status: UNASSESSED | PRODUCT_DECISION_NOT_REQUIRED | PRODUCT_FACT_FOUND | PRODUCT_DECISION_REQUIRED | PRODUCT_CONFLICT_DETECTED | PRODUCT_SCOPE_CHANGE
  authority_refs: []
  assessed_pack_revision: 1
  freshness: CURRENT | STALE
  user_decision_status: NOT_REQUIRED | PENDING | CONFIRMED
  decision_source: NONE | CURRENT_USER_REQUEST | PRIOR_USER_DECISION | DECISION_PACK_SELECTION
  authority_update_required: false
  workflow_state: READY_FOR_ARCHITECTURE | BLOCKED_BY_PRODUCT_DECISION | AUTHORITY_UPDATE_ONLY

architecture_decision:
  arch_risk: UNASSESSED | ARCH_LOW | ARCH_MEDIUM | ARCH_HIGH
  decision_status: NOT_REQUIRED | ARCH_CHECK_PASS | ARCH_DECISION_READY | STALE
  assessed_pack_revision: 1
  freshness: CURRENT | STALE
  recheck_required: false

expert_selection:
  risk_tier: LOCAL | MEDIUM | HIGH
  selected_agents: []
  selection_reasons: {}
  skipped_agents: {}
  child_agent_budget: "0" | "0-1" | "1-3" | "4-7"
  escalation_justification: null  # 超预算时必须 EXPERT_POOL_ESCALATION_JUSTIFICATION
  unselected_agent_action: EXPERT_NOT_SELECTED
  freshness: CURRENT | STALE

impact:
  authority: []
  backend: []
  frontend: []
  database: []
  contract: []
  generated: []
  security: []
  state_event: []
  runner_worker: []
  observability_audit_artifact: []
  tooling: []
  architecture: []
  tests: []
affected_symbols: []
invariants: []
forbidden_changes: []
validation_targets: []
unresolved_risks: []
```

## Filesystem Task Snapshot

正式修改前、任何 workspace 写入前：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  capture --root . --out <workspace外>/task-start-workspace.json
```

该 helper：

- **不调用 Git**；
- 对受控工作树文件做 SHA-256 指纹；
- 排除 `.git/node_modules/dist/build/.venv/__pycache__/.pytest_cache/.mypy_cache/.ruff_cache/.runtime/.tmp` 等噪声；
- snapshot 必须位于 workspace 外；
- `snapshot_version=3`，绑定 resolved root + filesystem workspace identity。

修改后：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  delta --root . --start <workspace外>/task-start-workspace.json --out <workspace外>/task-delta.json
```

输出 `added / removed / modified / task_delta_paths`。因此 Git 完全退出 Codex 治理，但 Incremental Closure 仍可准确知道当前 Task 实际改变了哪些文件。

## Authority Freshness

- `docs/authority/**` 是唯一活动事实源；不存在 `CURRENT → R4.x` 解析。
- 用户明确请求或 Product Decision `CONFIRMED` 后，允许 `AUTHORITY_UPDATE_ONLY` 直接修改 `docs/authority/**`；修改后必须重新运行 authority validators 和 Product Gate。
- Authority digest 变化使相关 slice `STALE`，但**不创建 R4.3/R4.4 等目录，也不触发 Full Scan #2**。
- `STALE` / `IMPACT_EXPANSION` 仅允许 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`；**禁止重新执行 Full Impact Scan / Full Scan #2**。

## Architecture Decision 复用

- `architecture_decision.freshness=CURRENT` 且 `assessed_pack_revision == pack_revision` 时执行 `revision rebind`，不得重复判级。
- 只有新增架构影响域才设置 `recheck_required=true`；普通 pack revision 增长不等于重做 Architecture。

## Shared Pack 规则

- 父编排已有 CURRENT Pack 时，所有子 Agent `MUST_CONSUME_TASK_CONTEXT_PACK`。
- 子 Agent不得建立第二个 Impact Map，不得执行第二次 `impact_scan.py`。
- 正式 CROSS_MODULE/HIGH_RISK Pack 缺失时返回 `TASK_CONTEXT_PACK_REQUIRED`。
- Targeted lookup 必须有 changed symbol / operationId / table / permission / event / route 等明确 seed。

## Git 边界

本项目 Git 完全由用户在 IDEA 中管理。Codex、Agent、Skill 不运行 `git status/diff/log/add/commit/push/...`，也不把 Git branch/commit/tag/remote/index 作为 Task Context、Checkpoint 或 Closure 的必要证据。
