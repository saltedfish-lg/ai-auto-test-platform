# Task Context Pack

建议使用紧凑 YAML/Markdown，不复制大段源码。它是当前 workspace 的**可失效索引**，不是冻结事实副本。

```yaml
task: <一句话>
risk: LOCAL | CROSS_MODULE | HIGH_RISK
pack_revision: 1
workspace_fingerprint:
  release_id: <当前Release；无法解析时明确UNRESOLVED>
  current_baseline: <从docs/baseline/CURRENT动态解析>
  baseline_manifest_hash: <CROSS_MODULE/HIGH_RISK必填；无法取得时明确UNAVAILABLE>
  changed_paths_digest: <兼容字段；等于current.changed_paths_digest>
  contract_hash: <涉及OpenAPI/正式契约时填写>
  generated_contract_hash: <涉及generated client时填写>
  git_workspace_status: COMPLETE | NOT_APPLICABLE | UNAVAILABLE
  freshness: CURRENT | STALE
  task_start:
    snapshot_version: 2
    repository_identity_digest: <task-start仓库身份；用于防止错仓库/仓库替换后误算delta>
    workspace_root_identity: <resolved root身份摘要>
    snapshot_ref: <workspace_snapshot.py capture输出；必须位于仓库外临时/任务制品路径>
    captured_at: <UTC时间>
    changed_paths_digest: <任务开始前已有tracked dirty路径+内容指纹摘要>
    untracked_paths_digest: <任务开始前已有untracked路径+内容指纹摘要>
    tracked_deleted_digest: <任务开始前tracked-but-deleted摘要>
    workspace_digest: <以上三类稳定组合摘要>
  current:
    snapshot_version: 2
    repository_identity_digest: <当前仓库身份；必须与task_start一致>
    workspace_root_identity: <当前resolved root身份摘要>
    changed_paths_digest: <当前tracked dirty路径+内容指纹摘要>
    untracked_paths_digest: <当前untracked摘要>
    tracked_deleted_digest: <当前tracked-but-deleted摘要>
    workspace_digest: <当前工作区摘要>
  task_delta:
    status: NOT_COMPUTED | NOT_APPLICABLE | EMPTY | CHANGED | UNAVAILABLE
    delta_ref: <workspace_snapshot.py delta输出；无则NONE>
    task_delta_paths: []
    delta_digest: <current与task_start之间的任务级变化摘要>

product_authority:
  status: UNASSESSED | PRODUCT_DECISION_NOT_REQUIRED | PRODUCT_FACT_FOUND | PRODUCT_DECISION_REQUIRED | PRODUCT_CONFLICT_DETECTED | PRODUCT_SCOPE_CHANGE
  authority_refs: []
  decision_pack_ref: <Product Decision Pack索引；无则NONE>
  assessed_pack_revision: <产生该门禁结论时的pack_revision>
  freshness: CURRENT | STALE
  user_decision_status: NOT_REQUIRED | PENDING | CONFIRMED
  decision_source: NONE | CURRENT_USER_REQUEST | PRIOR_USER_DECISION | DECISION_PACK_SELECTION
  authority_update_required: false
  workflow_state: READY_FOR_ARCHITECTURE | BLOCKED_BY_PRODUCT_DECISION | AUTHORITY_UPDATE_ONLY

architecture_decision:
  arch_risk: UNASSESSED | ARCH_LOW | ARCH_MEDIUM | ARCH_HIGH
  decision_status: NOT_REQUIRED | ARCH_CHECK_PASS | ARCH_DECISION_READY | STALE
  decision_ref: <Architecture Check/Decision索引；无则NONE>
  assessed_pack_revision: <产生该决策时的pack_revision>
  freshness: CURRENT | STALE
  recheck_required: false
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
  tracked_deleted: []
  tests: []
affected_symbols: []
invariants: []
forbidden_changes: []
validation_targets: []
unresolved_risks: []
```

## Task-start Workspace Snapshot

正式修改开始前、**任何工作区写入之前**，若当前目录是可读 Git workspace，先执行只读快照：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  capture --root . --out <仓库外临时路径>/task-start-workspace.json
```

- 脚本只执行只读 Git 查询与文件哈希，不执行 `add/commit/stash/reset/checkout` 等 Git 写操作；需要 index 的查询全部使用临时 `GIT_INDEX_FILE` 副本，真实 repository/worktree index 必须保持字节不变；
- 快照记录任务开始时已经存在的 `changed / untracked / tracked-deleted`，并对已有 dirty/untracked 文件按内容做 SHA-256 指纹；
- `snapshot_ref` 必须指向仓库外临时目录或任务制品目录；workspace 内输出会被 fail-closed 拒绝，避免保存快照本身制造新的 untracked 文件；
- 若无 `.git`，状态为 `NOT_APPLICABLE`；若存在 `.git` 但 Git metadata 无法读取，状态为 `UNAVAILABLE`，不得伪造 task-start fingerprint；
- snapshot schema 当前为 `snapshot_version=2`，并绑定 resolved workspace root + Git toplevel/common-dir 仓库身份；`delta` 必须校验版本、root、repository identity，任一不一致都返回 `UNAVAILABLE` / exit 2，禁止把其他仓库或旧 schema 快照当成本任务起点；
- 对正式代码/治理修改，只要 Git workspace 可用就应建立 task-start snapshot；`CROSS_MODULE/HIGH_RISK` 不得省略。

修改后计算任务级差异：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  delta --root . --start <task-start-workspace.json> --out <仓库外临时路径>/task-delta.json
```

`task_delta_paths` 不等同于整个 `git diff`：它表示**同一 workspace / repository identity 下，相对于任务开始状态发生变化的路径**。即使某文件在任务开始前已经 dirty，只要本任务再次改变其内容，内容指纹变化也会把该路径纳入 `task_delta_paths`；反之，任务开始前已有但本任务未触碰的 dirty 路径不会被自动归因给当前任务。

如果任务意外清除了/恢复了任务开始前已有 dirty 或 untracked 状态，delta 也必须通过 `cleared` 类别显式暴露，禁止静默把他人的/历史工作区变化归入当前任务。

## Git Metadata 完整性

`impact_scan.py` 输出：

```text
git_workspace.status = COMPLETE | NOT_APPLICABLE | UNAVAILABLE
```

- `COMPLETE`：Git metadata 可读，tracked-deleted 证据可用于闭包；
- `NOT_APPLICABLE`：根目录不存在 `.git`，不得伪造 Git 证据，但不因不存在仓库而判定 scope 失败；
- `UNAVAILABLE`：存在 `.git`，但 Git 命令/metadata 读取失败。此时即使 required roots 全部可读，`closure_safe=false`，不得宣告 `IMPACT_CLOSURE_PASS`。

Git metadata 字段必须区分：`required_by_task_risk` 表示 CROSS_MODULE/HIGH_RISK 或显式敏感任务是否主动要求 Git 证据；`required_for_closure` 表示当前 Git 仓库若要宣告闭包安全是否必须读到 metadata；`blocking_for_closure` 表示该证据当前是否缺失并正在阻断闭包。LOCAL Git 仓库可以是 `required_by_task_risk=false`，但只要 metadata=UNAVAILABLE，仍必须是 `required_for_closure=true / blocking_for_closure=true`。

`CROSS_MODULE/HIGH_RISK` 以及 CI/依赖/构建/部署/环境配置/工程工具类任务必须把 Git metadata 视为正式影响证据；Git `UNAVAILABLE` 时进入 `BLOCKED_BY_ENVIRONMENT`，而不是把 tracked-deleted 缺失误判为“无影响”。

## Freshness 规则

- `LOCAL` 可使用轻量 fingerprint；`CROSS_MODULE/HIGH_RISK` 必须记录当前 baseline 与 workspace fingerprint，不能只写“可用时”。
- 后端/数据库阶段若改变 API、DTO、DDL、permission、state/event、Runner/Worker 并发语义或发现新消费者，旧 Pack 立即标记 `STALE`；若这些变化进入新的 ownership/transaction/consistency/concurrency 架构域，同时把 `architecture_decision.freshness` 标记为 `STALE` 并设置 `recheck_required=true`。
- `STALE` 不要求重新扫描全仓：先基于真实 `task_delta_paths` + changed paths 做 **delta refresh**，更新 `pack_revision`、受影响路径/符号、validation targets 与相关 hash；只有 delta 暴露新域时才升级到 `IMPACT_EXPANSION`。
- 若 delta refresh 仅使 `pack_revision` 递增，但**没有**引入新的 state owner / transaction / consistency / concurrency / Runner-Worker / dependency domain，且既有 Architecture Decision 的约束仍覆盖新影响面，则执行 **revision rebind**：保持 `architecture_decision.freshness=CURRENT`、`recheck_required=false`，仅把 `assessed_pack_revision` 更新为新的 `pack_revision`；不得因此重新判级或再次调用 `solution_architect`。
- 子 Agent 接收 Pack 时必须先核对 `freshness`；不得把旧 Pack 当成当前事实。

## 内容规则

- 只写“足以让执行 Agent 正确工作的事实和索引”；
- 不粘贴完整 OpenAPI/DDL/YAML；
- `authority_refs` 与 `impact.authority` 明确区分权威来源和普通候选；
- 不把搜索推断写成冻结事实；
- Agent 发现 Pack 与权威事实或真实代码冲突时，以权威事实和真实代码为准并触发 `IMPACT_EXPANSION`；
- `generated`、`state_event`、`observability_audit_artifact`、`tooling`、`architecture`、`tracked_deleted` 不得被含糊塞进 backend 而丢失跨层消费者；
- Post-change Review/Architecture Recheck/Independent Review 优先以 `task_delta_paths` 作为“本任务新变化”入口，再结合全局反查；不得把任务开始前已有 dirty workspace 全部冒充本任务改动。

## Product Authority 复用与失效规则

- `product_authority` 是产品事实索引，不是新的事实源。`PRODUCT_FACT_FOUND` 必须带最小 `authority_refs`；`PRODUCT_DECISION_NOT_REQUIRED` 不得制造虚假产品事实。
- `freshness=CURRENT` 且 `assessed_pack_revision == pack_revision` 时直接复用；普通工程 delta 未新增 Product/Authority 影响时可做 revision rebind，只更新 `assessed_pack_revision`。
- 新增用户可观察行为、业务/状态规则、API/数据/事件产品语义、权限安全、Runner/Worker 业务/恢复语义或验收行为时，立即把 `product_authority.freshness=STALE`，重新执行产品主权门。
- `PRODUCT_DECISION_REQUIRED / PRODUCT_CONFLICT_DETECTED / PRODUCT_SCOPE_CHANGE` 描述的是**权威事实状态**，不等于用户一定尚未裁决：若当前请求/已记录用户决定尚未唯一解决问题，使用 `user_decision_status=PENDING / decision_source=NONE / workflow_state=BLOCKED_BY_PRODUCT_DECISION`；AI 推荐不得写成 `CONFIRMED`。
- 若用户当前请求、既有明确用户决定或 Decision Pack 选择已经唯一解决该产品问题，必须使用 `user_decision_status=CONFIRMED` 并记录 `decision_source=CURRENT_USER_REQUEST | PRIOR_USER_DECISION | DECISION_PACK_SELECTION`，禁止再次要求同一产品确认。
- `PRODUCT_DECISION_REQUIRED + CONFIRMED` 表示为原缺失域**新增正式产品事实**；`PRODUCT_CONFLICT_DETECTED + CONFIRMED` 表示已选择冲突解决方案；`PRODUCT_SCOPE_CHANGE + CONFIRMED` 表示已确认范围/规则变化。上述三类均默认 `authority_update_required=true / workflow_state=AUTHORITY_UPDATE_ONLY`，在当前权威事实完成同步前只允许权威更新，禁止 Architecture/Implementation。
- 权威事实同步完成后必须重新执行产品主权门；只有重新得到 `PRODUCT_FACT_FOUND`（或重新判定为 `PRODUCT_DECISION_NOT_REQUIRED`）且 `workflow_state=READY_FOR_ARCHITECTURE` 才允许继续，禁止让 `CONFIRMED` 本身替代权威事实。

## Architecture Decision 复用规则

- 若 `architecture_decision.freshness = CURRENT` 且 `assessed_pack_revision == pack_revision`，Implementer 必须直接消费现有 `ARCH_RISK / Architecture Check / Architecture Decision`，禁止为了形式重新判级或重复调用 `solution_architect`。
- 非架构型 delta refresh 后先做 **revision rebind**，再按上述 CURRENT 条件复用；只有新架构域、`STALE` 或 `recheck_required=true` 才需要重新执行 Architecture Skill。
- 只有 `architecture_decision` 缺失、`STALE`、`recheck_required=true`，或真实 `IMPACT_EXPANSION` 引入新的 state owner / transaction / consistency / concurrency / Runner-Worker / dependency domain 时，才重新执行 Architecture Skill。
- `ARCH_HIGH` 的 `decision_ref` 只保存紧凑索引/路径，不复制大段架构报告。
