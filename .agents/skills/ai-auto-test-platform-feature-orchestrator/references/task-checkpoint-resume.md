# Stage Checkpoint + Validated Resume

## 目标

为 MEDIUM/HIGH 或需要断点续跑的正式 Task 提供完整任务级阶段断点续跑；LOCAL 正式代码写入只建立 LIGHTWEIGHT_LOCAL CP-0 机械证据锚。核心原则：

> `COMPLETED + VALID → REUSE`；中断不是重跑已完成阶段的理由。

本机制不依赖 Git，不维护版本化 Authority 副本，不保存模型 Chain-of-Thought，也不为每个 Agent 建独立 checkpoint。

## 唯一 Owner

- `feature-orchestrator`：唯一 `TASK_LIFECYCLE_OWNER`，负责阶段状态、checkpoint、resume validation、阶段失效和下一阶段调度。
- `context-efficiency`：`CONTEXT_STATE_PROVIDER`，只提供 workspace identity、`docs/authority` digest、Task Context Pack、filesystem snapshot、delta 与 freshness；不得维护第二套阶段状态。
- 子 Agent：只消费当前有效 Task Context Pack，不得自行创建、推进或回滚 Task checkpoint。

## 阶段

`TASK_INITIALIZED → CONTEXT_READY → DECISIONS_READY → IMPLEMENTATION_READY → IMPLEMENTATION_COMPLETE → VERIFICATION_COMPLETE → CLOSURE_COMPLETE`

- `CONTEXT_READY`：唯一成功 `FULL_IMPACT_SCAN` 已完成，Shared Task Context Pack 已建立。
- `DECISIONS_READY`：Product Authority、Architecture Risk/Decision、Expert Selection 已完成或明确 NOT_REQUIRED。
- `IMPLEMENTATION_READY`：实现计划、允许/禁止路径和验证目标明确。
- `IMPLEMENTATION_COMPLETE`：当前任务修改已完成，并由 filesystem snapshot v4 记录真实 `task_delta_paths / changed_symbols / changed_line_ranges`。
- `VERIFICATION_COMPLETE`：验证结果绑定当前 workspace fingerprint。
- `CLOSURE_COMPLETE`：`DELTA_REFRESH + TARGETED_REVERSE_LOOKUP + Impact Closure` 完成。

阶段只能逐级推进。

## Checkpoint 身份

Checkpoint 必须位于 workspace 外，并记录：

- `schema_version=5`；
- `task_id`；
- resolved workspace root；
- filesystem-only `workspace_identity`；
- 固定 `authority_root=docs/authority`；
- 每阶段由 helper 现场 `capture_workspace(root)` 机械生成 `workspace_fingerprint`，并现场重算 `authority_digest`；调用方参数不得覆盖事实；
- CP-0 同时记录稳定 `snapshot_evidence_digest`，供后续 Comment Gate 绑定 task-start snapshot；
- 每阶段 `pack_revision + compact evidence`，且 `pack_revision` 只能保持或递增、禁止倒退；
- SHA-256 checksum；
- 原子写入：temp → flush/fsync → atomic replace。

Git 不属于 Codex checkpoint identity。用户在 IDEA 中管理的 Git commit/branch/tag/remote 状态不得进入 Codex Resume 判定。

## Resume Validation

### `RESUME_EXACT`

满足 task/workspace/authority root identity 一致，且 helper 机械重算出的当前 workspace fingerprint 与 Authority digest 都等于 latest stage 记录。

动作：直接从下一阶段继续；禁止重新 Full Scan，也禁止重放仍有效的 Product/Architecture/Implementation 阶段。

### `RESUME_WITH_DELTA_REFRESH`

helper 机械重算发现 workspace fingerprint 或 `docs/authority` digest 发生变化，但仍属于同一 workspace/task。

动作：

1. filesystem snapshot 计算真实 task delta；
2. 只执行 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`；
3. 按最小失效原则刷新 Product/Architecture/Expert Selection/Verification；
4. 更新同一个 Pack revision；
5. **禁止 Full Impact Scan #2**。

Authority digest 变化不再意味着创建 R4.x 新版本，也不自动拒绝 Resume；它表示当前唯一源文档发生变化，需要重新验证受影响事实。

### `RESUME_REJECTED`

仅在以下身份不兼容时拒绝旧 Task：

- task_id 不一致；
- workspace root 不一致；
- filesystem workspace identity 不一致；
- authority root 不再是 `docs/authority`；
- checkpoint schema/checksum 不兼容。

### `CHECKPOINT_CORRUPTED`

JSON、schema 或 checksum 无效时 fail-closed。

## 最小失效

| 变化 | 处理 |
|---|---|
| 普通实现文件变化 | 从 Implementation/Verification 相关阶段刷新 |
| OpenAPI/DTO/permission/event/DDL 变化 | 刷新对应 authority slice、Expert Selection 和验证目标 |
| 新 state owner / transaction / concurrency / Runner-Worker domain | Architecture 标 STALE 并 recheck |
| 用户确认后修改产品事实 | Product Authority 标 STALE，修改 `docs/authority` 后重新 Product Gate |
| `docs/authority` digest 改变 | `RESUME_WITH_DELTA_REFRESH`，不得创建新的版本化 Authority 副本目录 |
| workspace identity/root 改变 | `RESUME_REJECTED` |

验证 PASS 必须绑定产生它时的机械 workspace fingerprint；CP-6 会再次 capture 当前 workspace，若与 CP-5 `VERIFICATION_COMPLETE` 不一致则返回 `WORKSPACE_CHANGED_AFTER_VERIFICATION`，必须重新 Verification。Resume 同样自行机械重算当前 workspace/Authority，调用方无法通过重放旧 fingerprint 获得 `RESUME_EXACT`。

## Helper

`feature-orchestrator/scripts/task_checkpoint.py` 提供：

- `init`
- `advance`
- `resume-validate`

Authority transaction 的 begin/terminal 变更**不提供公开 CLI 子命令**。它们仅作为 `authority_write_guard.py` 进程内加载的私有 checkpoint mutation API 使用；任何人工/Codex 直接调用 `task_checkpoint.py` 都不能伪造 `generated_by=authority_write_guard` 的终态 attestation。

Helper 不运行 Git、不执行 Git/release 操作，也不保存模型思考过程。它通过既有 `workspace_snapshot.py` 对受控工作树做机械捕获；兼容保留的 `--workspace-fingerprint/--authority-digest/--current-*` 参数不参与事实判定。`init --force` 被正式禁止：checkpoint 一经创建就不能覆盖重置，需新任务时必须使用新的 `task_id + checkpoint`，避免抹除 `TASK_ABORTED / TASK_ABANDONED / ACTIVE` 的审计历史。`authority_root` 物理固定为 `docs/authority`，传入任何其它路径都返回 `AUTHORITY_ROOT_OVERRIDE_FORBIDDEN`。


## LOCAL 轻量证据锚

LOCAL 任务若**不写正式代码**，不要求创建 Checkpoint。LOCAL 任务若写正式代码，为了给 Comment Quality Gate 提供不可伪造的 task-start snapshot，只创建：

```text
task_checkpoint.py init --lifecycle-profile LIGHTWEIGHT_LOCAL
→ CP-0 TASK_INITIALIZED / mechanical snapshot evidence
→ implementation
→ workspace_snapshot delta
→ comment_quality_gate --checkpoint <该 CP-0>
   → Gate PASS 后由 Gate 进程内私有 API 将 code_quality.comment_gate attestation 写入 Checkpoint
→ targeted verification
```

`LIGHTWEIGHT_LOCAL` **不运行 CP-1→CP-6**，`task_checkpoint.py advance` 对该 profile 返回 `LIGHTWEIGHT_LOCAL_STAGE_CHAIN_NOT_APPLICABLE`。它是 Comment Gate 的证据锚，不是长任务断点续跑链；`local-complete` 必须机械验证当前 workspace 与 `code_quality.comment_gate` PASS attestation 完全一致，未运行 Gate 或 Gate 后又修改 workspace 均拒绝。定向验证后才记录 `LOCAL_EVIDENCE_COMPLETE`，从而区分“仍在执行”和“轻量任务已封存”。`resume-validate` 对 LOCAL 只返回 LOCAL continuation/delta 动作，绝不指向 `CONTEXT_READY`。若过程中发现需要跨阶段 Resume、Authority transaction、CROSS_MODULE/HIGH_RISK，必须先运行 `task_checkpoint.py promote-local-to-full`，保留原 CP-0 事实并升级为 `FULL`；Authority Guard 对未升级的 LOCAL 返回 `AUTHORITY_TRANSACTION_REQUIRES_FULL_CHECKPOINT`。

## 与 Authority Write Transaction 的关系

Authority 写事务的 `change-set/before/prepared/write-state/lock` 仍由 `authority_write_guard.py` 维护为 workspace 外**短生命周期事务状态**；Task Checkpoint 只保存 `authority_write.transactions[]` 历史、`active_transaction_id` 与每个事务的 Guard attestation，不建立第二套 receipt/活动事实源。一个 Workspace 同时只能有一个 ACTIVE Authority transaction，但同一 Task 在前一事务合法终态化并释放 mutex 后，可以按 sequence 开启下一笔顺序事务；Single Writer 约束的是**并发物理写者**，不是 Task 生命周期只能写一次。

- 若事务存在 change-set，必须完成 `APPLY → validate → VALIDATED → cleanup(CLOSURE_COMPLETE)`；
- 若事务没有 change-set，成功 cleanup 仍必须证明 `current_authority_digest == authority_digest_at_acquire`。出现外部 Authority 改动时返回 `AUTHORITY_EXTERNAL_CHANGE_DURING_TRANSACTION`，必须转入 DELTA_REFRESH 并正式验证，禁止把外部未验证改动当成本事务成功结果；
- cleanup 先通过 Guard 私有 API把 terminal attestation 写入 checkpoint，再删除短生命周期 state/lock；
- CP-6 检查 lock 不存在、所有 `transactions[]` 都已合法终态化且不存在 `active_transaction_id`、所有 state-dir 已删除，并自行重算当前 `docs/authority` digest；**最新一笔 transaction 必须自身为成功 `CLOSURE_COMPLETE`，且它也必须是 `last_successful_transaction_id`**，当前真实 digest 必须等于该最新成功 transaction 的 closure digest；更早成功事务不得替后续 `TASK_ABORTED / TASK_ABANDONED` 兜底；兼容保留的 `--authority-digest` 不参与事实判定；
- `TASK_ABORTED / TASK_ABANDONED` 在 Authority 记录中表示该笔事务的失败清理终态，不自动抹除更早的合法事务历史；是否继续 Task 由 Task lifecycle 决定。“未使用 Authority”只由 checkpoint 的 `ever_used=false` 推导，不存在调用方 `--authority-write-not-used` 成功声明入口。


## Comment Gate 与终态绑定

- `comment_quality_gate.py` 正式 PASS 后会把 `code_quality.comment_gate` attestation 写入同一个 Task Checkpoint；attestation 绑定 `task_id`、CP-0 `snapshot_evidence_digest`、当前 `workspace_fingerprint`、`task_delta_digest` 与 `change_scope_digest`。
- `LIGHTWEIGHT_LOCAL local-complete`、FULL `VERIFICATION_COMPLETE` 与 FULL `CLOSURE_COMPLETE` 都必须验证该 attestation；缺失返回 `COMMENT_GATE_ATTESTATION_MISSING`，Gate 后再改 workspace 返回 `COMMENT_GATE_WORKSPACE_CHANGED_AFTER_PASS`。
- CP-6 仍额外要求当前 workspace 与 CP-5 完全一致，因此 Comment Gate PASS 后的修改不能绕过 Verification/Closure。

## 已完成 Task 的 Resume

`CLOSURE_COMPLETE` 是不可逆终态。旧 Task 完成后若当前 Living Workspace 已被后续 Task 推进，`resume-validate` 返回 `TASK_ALREADY_COMPLETE_CURRENT_WORKSPACE_ADVANCED / COMPLETED_TASK_WORKSPACE_DRIFT`，`next_stage=null`，要求 `CREATE_NEW_TASK_FOR_POST_COMPLETION_CHANGES`；绝不再计算 CP-6 之后的“下一阶段”。
