# Stage Checkpoint + Validated Resume

## 目标

为长时间正式 Task 提供任务级阶段断点续跑。核心原则：

> `COMPLETED + VALID → REUSE`；中断不是重跑已完成阶段的理由。

本机制不依赖 Git，不维护版本化 baseline，不保存模型 Chain-of-Thought，也不为每个 Agent 建独立 checkpoint。

## 唯一 Owner

- `feature-orchestrator`：唯一 `TASK_LIFECYCLE_OWNER`，负责阶段状态、checkpoint、resume validation、阶段失效和下一阶段调度。
- `context-efficiency`：`CONTEXT_STATE_PROVIDER`，只提供 workspace identity、`docs/authority` digest、Task Context Pack、filesystem snapshot、delta 与 freshness；不得维护第二套阶段状态。
- 子 Agent：只消费当前有效 Task Context Pack，不得自行创建、推进或回滚 Task checkpoint。

## 阶段

`TASK_INITIALIZED → CONTEXT_READY → DECISIONS_READY → IMPLEMENTATION_READY → IMPLEMENTATION_COMPLETE → VERIFICATION_COMPLETE → CLOSURE_COMPLETE`

- `CONTEXT_READY`：唯一成功 `FULL_IMPACT_SCAN` 已完成，Shared Task Context Pack 已建立。
- `DECISIONS_READY`：Product Authority、Architecture Risk/Decision、Expert Selection 已完成或明确 NOT_REQUIRED。
- `IMPLEMENTATION_READY`：实现计划、允许/禁止路径和验证目标明确。
- `IMPLEMENTATION_COMPLETE`：当前任务修改已完成并记录真实 `task_delta_paths / changed_symbols`。
- `VERIFICATION_COMPLETE`：验证结果绑定当前 workspace fingerprint。
- `CLOSURE_COMPLETE`：`DELTA_REFRESH + TARGETED_REVERSE_LOOKUP + Impact Closure` 完成。

阶段只能逐级推进。

## Checkpoint 身份

Checkpoint 必须位于 workspace 外，并记录：

- `schema_version=2`；
- `task_id`；
- resolved workspace root；
- filesystem-only `workspace_identity`；
- 固定 `authority_root=docs/authority`；
- 每阶段 `workspace_fingerprint + authority_digest + pack_revision + compact evidence`；
- SHA-256 checksum；
- 原子写入：temp → flush/fsync → atomic replace。

Git 不属于 Codex checkpoint identity。用户在 IDEA 中管理的 Git commit/branch/tag/remote 状态不得进入 Codex Resume 判定。

## Resume Validation

### `RESUME_EXACT`

满足 task/workspace/authority root identity 一致，且 latest stage 的 workspace fingerprint 与 authority digest 都未变化。

动作：直接从下一阶段继续；禁止重新 Full Scan，也禁止重放仍有效的 Product/Architecture/Implementation 阶段。

### `RESUME_WITH_DELTA_REFRESH`

workspace fingerprint 或 `docs/authority` digest 发生变化，但仍属于同一 workspace/task。

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
| `docs/authority` digest 改变 | `RESUME_WITH_DELTA_REFRESH`，不得创建新 baseline 目录 |
| workspace identity/root 改变 | `RESUME_REJECTED` |

验证 PASS 必须绑定产生它时的 workspace fingerprint；变化后只重跑受影响验证。

## Helper

`feature-orchestrator/scripts/task_checkpoint.py` 提供：

- `init`
- `advance`
- `resume-validate`

Helper 不运行 Git、不执行 repository-wide scan、不生成 release manifest，也不保存模型思考过程。
