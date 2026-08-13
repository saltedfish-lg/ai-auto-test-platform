# Authority Write Coordination

## 目标

`docs/authority/**` 是 Single Living Authority。物理 Authority root 固定为 `<workspace>/docs/authority`；Guard/Checkpoint 的正式 CLI 即使保留 `--authority-root` 兼容参数，也只接受解析后等于该固定目录的值，其它值统一返回 `AUTHORITY_ROOT_OVERRIDE_FORBIDDEN`。为避免同一 Task 的多个阶段、多个 Custom Agent 或两个并行 Task 对大型 Authority 文件产生 stale overwrite，本项目使用 **Single Authority Writer + Workspace-level Mutex + Optimistic SHA-256 Guard + Ephemeral Change Set**。

## 唯一 Writer

- `feature-orchestrator` / 当前主 Agent 是唯一 `AUTHORITY_PHYSICAL_WRITE_OWNER`。
- 所有 Custom Agent、Reviewer、fallback role 对 `docs/authority/**` 一律 `READ_ONLY`。
- 子 Agent 发现事实缺口、冲突或需要同步时，只返回 `AUTHORITY_CHANGE_REQUEST`，不得自行编辑 Authority。
- 实现阶段发现 Authority 缺口时返回 Orchestrator，进入 Product Sovereignty / `AUTHORITY_UPDATE_ONLY`；禁止顺手改文档后继续实现。

## 写事务

只有 `AUTHORITY_UPDATE_ONLY` 可以进入物理 Authority 写事务：

```text
AUTHORITY_CHANGE_REQUEST(S)
→ Coalesced Authority Change Set
→ acquire workspace-level mutex
→ bind existing Task Checkpoint + unique authority_transaction_id + canonical state-dir
→ verify expected SHA-256
→ capture before-images
→ atomic replace
→ authority_write_guard.py validate（Guard 自己执行正式 Validators）
→ execution-proven validator evidence + digest binding
→ update authority_digest / pack_revision
→ Product Gate re-check
→ cleanup authority runtime state
→ CP-6 CLOSURE_COMPLETE
```

同一个文件来自 Product / Architecture / Security 等多个阶段的修改意图必须在写入前合并为一个 target；Guard 拒绝同一 change-set 中的重复 target。

## 临时数据

Authority 写事务所有运行数据必须位于 workspace 外，例如：

```text
%TEMP%/ai-auto-test-platform/tasks/<task-id>/authority-write/
  change-set.json
  write-state.json
  before/**
  prepared/**
```

这些文件：

- `AUTHORITY_CHANGE_SET_IS_EPHEMERAL = true`
- `MUST_NOT_BECOME_AUTHORITY = true`
- `MUST_NOT_BE_COMMITTED = true`
- `MUST_NOT_SURVIVE_COMPLETED_TASK = true`

`CLOSURE_COMPLETE` 前必须先完成 Authority cleanup。存在 change-set 时只有 `VALIDATED` 状态允许 `CLOSURE_COMPLETE` cleanup；`PLANNED / APPLYING / APPLIED_PENDING_VALIDATION / ROLLBACK_CONFLICT` 均禁止静默结束。

`TASK_ABORTED / TASK_ABANDONED`：如有已应用改动，仅在目标当前 SHA 仍等于 Guard 写入结果时恢复 before-image。若用户/IDEA/其它外部过程已修改目标，返回 `AUTHORITY_ROLLBACK_STALE_CONFLICT`，**保留 canonical lock、state-dir、before-image 和 change-set** 供人工处理或 Validated Resume，禁止覆盖外部新修改。

`INTERRUPTED` 不是终态：为了 `Validated Resume` 暂时保留 change-set、before-image、write-state 和锁；同一 task_id 可以恢复，其他 Task 不得自动抢锁。

## Workspace-level Mutex 与 canonical state-dir

锁按 resolved workspace identity 存在系统临时目录，禁止 TTL 自动抢锁 / auto-steal。canonical lock 必须先在同目录完整写入 candidate（flush + fsync），再用 no-clobber 原子发布，禁止先创建空 canonical lock 再逐步填 JSON。若进程在 candidate 已完整写入或已 hard-link 发布、但 `finally` 尚未删除 candidate 时崩溃，`recover` 只允许清理由 `workspace_root + task_id + canonical state-dir` 三者可证明属于当前恢复目标的 `*.candidate`；其它 candidate 保留并 fail-safe，不做泛化目录清扫。历史版本遗留的空/半写 `CORRUPTED` lock 只有在同 task_id 的 `PREPARING_LOCK + ever_planned=false` state 可证明安全时才允许 `recover` 删除，否则 fail-closed。

锁不仅绑定：

```text
task_id
workspace_root
```

还必须绑定唯一：

```text
Task Checkpoint
authority_transaction_id
canonical state-dir
```

每次 `acquire` 由 Guard 生成新的 `authority_transaction_id`，并通过**进程内私有 checkpoint mutation API**登记到 `authority_write.transactions[]`；`task_checkpoint.py` 不暴露 `authority-begin / authority-terminal` 公共 CLI。Checkpoint 同时维护 `active_transaction_id`，因此同一 Task 在任一时刻最多一笔 ACTIVE 事务；该事务终态化并释放 workspace mutex 后，同一 Task 可以开启下一笔 sequence 递增的 Authority transaction。每笔事务都记录独立 `authority_digest_at_acquire` 与 closure attestation，禁止复用 transaction_id。

`plan / apply / reconcile / validate / rollback / cleanup / recover` 每一个命令都必须重新验证传入 `--state-dir` 与 workspace lock 中的 canonical state-dir 完全一致。换 state-dir 不得绕过锁、不得删除错误目录、不得释放真实 Task 的锁。

不一致返回：

```text
AUTHORITY_WRITE_STATE_DIR_MISMATCH
```

选择 workspace 级锁而不是文件级锁，是因为不同 Authority 文件可能描述同一跨文件事实；允许两个 Task 分别锁两个文件仍会造成跨文档不一致。

## Optimistic SHA-256 Guard

每个目标必须记录：

```yaml
path: docs/authority/...
expected_sha256: <读取/计划时的hash>
sources: [PRODUCT, ARCHITECTURE, SECURITY]
```

真正 apply 前再次计算 current SHA-256。若不相等：

```text
AUTHORITY_STALE_WRITE_CONFLICT
→ stop write
→ DELTA_REFRESH
→ TARGETED_REVERSE_LOOKUP
→ rebuild/coalesce change-set
```

禁止用旧上下文覆盖新文件。

## Atomic Replace + stale-safe rollback

Guard 在 apply 前保存 before-image；prepared replacement 也必须位于 workspace 外。每个文件使用 temp + fsync + `os.replace()` 原子替换。

Guard 写入后记录 `resulting_sha256`。任何 rollback / abort cleanup 前必须比较：

```text
current_sha256 == guard_resulting_sha256
```

只有相等时才允许恢复 before-image；如果当前文件已经被外部修改，必须返回：

```text
AUTHORITY_ROLLBACK_STALE_CONFLICT
```

并保留全部恢复材料和锁，不得覆盖外部编辑。

## Execution-proven Validator evidence

正式写事务**不信任调用方自报 PASS**。`mark-validated --validator-evidence` 已退出正式信任边界；调用它必须返回 `CALLER_SUPPLIED_VALIDATION_EVIDENCE_FORBIDDEN`。

必须由 Guard 自己执行：

```text
authority_write_guard.py validate
→ tools/verify_authority.py
→ docs/authority/validation/validate_all.py
→ docs/authority/validation/validate_governance.py
→ docs/authority/validation/validate_auth_contract.py
→ tools/openapi_client.py check
```

Guard 必须记录每个命令的 exit code、stdout/stderr hash，并检查：

1. canonical Validator 集合均真实执行且 exit=0；
2. Validator 执行前后 `docs/authority` digest 完全相同；
3. 每个 target 仍等于 Guard 的 `resulting_sha256`；
4. evidence 只能由 Guard 写入 canonical state-dir 的 `validator-evidence.json`。

任一失败都不得进入 `VALIDATED`。

## Crash-safe mutex / recover / reconcile

`acquire` 先在 workspace 外准备 Task 私有 state-dir 和 `PREPARING_LOCK` 状态，记录当前固定 `docs/authority` 的 `authority_digest_at_acquire`，再把**完整写入并 fsync 的 candidate lock**通过 no-clobber 原子发布为 workspace mutex；随后由 Guard 进程内调用 checkpoint 私有 mutation API，将同一个 `authority_transaction_id + authority_digest_at_acquire` 写入既有 Task Checkpoint。checkpoint 绑定失败时，在任何 plan/apply 发生前释放新锁与 state；中断恢复只能继续同一 checkpoint/transaction_id。因此正常路径既不暴露半写 canonical lock，也不能通过遗漏 checkpoint 记录伪装为“未使用 Authority”。历史损坏 lock 只允许在可证明的 `PREPARING_LOCK` 无事务历史场景安全恢复；若 checkpoint 已记录该未计划事务，recover 会先将其机械终态化为 `TASK_ABORTED` 再删除临时材料。

若事务从未建立 change-set，`cleanup(CLOSURE_COMPLETE)` 仍不得无条件成功：Guard 必须重算当前 Authority digest 并要求它严格等于 `authority_digest_at_acquire`。若用户/IDEA/其它进程在锁持有期间修改了 Authority，返回 `AUTHORITY_EXTERNAL_CHANGE_DURING_TRANSACTION`；该变化必须通过 DELTA_REFRESH 纳入正式 change-set/Validator，禁止由“no-change transaction”替外部未验证修改背书。

`cleanup` 固定顺序为：

```text
state = CLEANING
lock.status = CLEANING
→ 删除 state-dir
→ 最后删除 canonical lock
```

若中断在 CLEANING，`recover` 可由同 task_id 完成清理。无 change-set 历史的安全 orphan lock 也可由 `recover` 释放；有事务历史但 state 丢失时 fail-closed，不自动抢锁。

若进程在 `APPLYING` 中断，使用：

```text
authority_write_guard.py reconcile --strategy continue|rollback
```

逐 target 比较 `before_sha256 / prepared_sha256 / current_sha256`：全部或部分处于 before/prepared 且没有第三方 SHA 时，可以继续 apply 或安全 rollback；出现第三方 SHA 则 `AUTHORITY_RECONCILE_STALE_CONFLICT`。

## Task Checkpoint / CP-6 联动

`task_checkpoint.py` 仍然是唯一 `TASK_LIFECYCLE_OWNER` 状态机；Authority Guard 的 `change-set/before/prepared/write-state/lock` 仍是短生命周期事务材料，但**“本 Task 是否使用过 Authority、active_transaction_id、顺序 transaction history、每笔事务终态和 closure attestation”直接记录在既有 Task Checkpoint 中**，不再创建第二份外部 receipt/活动事实源。

但 CP-6 不是独立于 Authority cleanup 的第二条成功路径：

- 每次 `acquire --checkpoint <Task Checkpoint>` 时 Guard 生成新的 `authority_transaction_id`，登记 `authority_write.ever_used=true`、`active_transaction_id` 与递增 `sequence`；调用方不能自报“未使用 Authority”；
- Authority transaction 只接受 `lifecycle_profile=FULL` 的 Checkpoint；`LIGHTWEIGHT_LOCAL` 必须先通过 `promote-local-to-full` 升级，Guard 机械拒绝轻量 profile 直接获取 mutex；
- workspace mutex + `active_transaction_id` 保证**同一时刻只存在一个物理 Authority writer**。前一 transaction 终态化并清理后允许同 task_id 再次 acquire；新 transaction 必须有新的 id/sequence，旧成功 attestation 只能属于原 transaction；
- `cleanup` 在删除 lock/state 前，必须把该 transaction 的 `CLOSURE_COMPLETE / TASK_ABORTED / TASK_ABANDONED` 终态写入 Task Checkpoint。成功终态包含带 checksum 的 Guard closure attestation，绑定 `task_id/workspace/authority_root/authority_transaction_id/state-dir/final_status/validated_authority_digest/closure_authority_digest`；
- 对有 change-set 的成功事务，`validated_authority_digest == closure_authority_digest` 是硬条件；Guard 使用同一已确认 digest 写 attestation，不在 attestation writer 内重新计算另一个 digest；
- `task_checkpoint.py advance --stage CLOSURE_COMPLETE` 必须机械检查 canonical Authority lock 已不存在、`active_transaction_id=null`、所有 transaction 均已终态化且 state-dir 已删除，并**自行重新计算当前 `docs/authority` digest**；最新 transaction 必须是成功 `CLOSURE_COMPLETE` 且与 `last_successful_transaction_id` 相同，随后才校验 `current_actual_digest == 最新成功 transaction.closure_attestation.digest`。`SUCCESS → FAILED/ABANDONED → CP-6` 必须拒绝；只有后续新的成功 transaction 明确解决失败后才可 Closure。兼容保留的 `--authority-digest` 不参与事实判定；
- `TASK_ABORTED / TASK_ABANDONED` 已作为 checkpoint 机械终态；
- checkpoint 中 `authority_write.ever_used=false` 才能机械判定 `AUTHORITY_WRITE_NOT_USED`，正式 CLI 不提供调用方 `--authority-write-not-used` 成功声明入口；
- 不再生成 workspace 外 closure receipt，因此不存在 receipt 跨事务复用、消费删除失败或完成任务后 receipt 残留问题；
- 因此顺序固定为 `Authority VALIDATED → cleanup 写入 Guard terminal attestation → 删除短生命周期 Authority state/lock → CP-6 校验当前真实 Authority digest`。

恢复时：

- 同 task_id + 同 workspace + 同 canonical state-dir：可检查/继续已有 Authority 写事务；
- 其他 task_id：不得抢锁；
- Authority digest 或 workspace fingerprint 变化：按既有 `RESUME_WITH_DELTA_REFRESH` 处理；
- `APPLYING / APPLIED_PENDING_VALIDATION / ROLLBACK_CONFLICT` 中断：先检查实际 hash、before-image 和 prepared/resulting hash，再决定继续验证或显式 rollback；不得重新 Full Scan。
