# Post-change Closure Verification

## 反查对象

- renamed/deleted symbols
- new symbols
- API / schema / DTO
- table / column / constraint
- permission / role / scope
- state / event
- route / store / component
- config / env / command

## 必做

0. 用 `workspace_snapshot.py delta` 比较 current 与 task-start snapshot（`snapshot_version=2`，绑定 resolved root 与 repository identity；snapshot/delta artifact 必须位于 workspace 外；Git index 查询使用临时 `GIT_INDEX_FILE` 副本且真实 index 字节不变），得到 `task_delta_paths`；优先把这些路径归因给当前任务，并显式报告本任务对任务开始前既有 dirty/untracked 状态的继续修改或清除；
1. 旧引用残留扫描；
2. 新引用消费者扫描；
3. 当前基线契约一致性；
4. generated 生成链一致性；
5. 测试和fixture同步；
6. 跨层构建/类型/契约/集成验证；
7. UI变更时浏览器真实验证；
8. 高风险变更时专项 Reviewer；
9. 检查只读 Git workspace 的 `status` 与 tracked-but-deleted 路径，特别是 `.github/**`、构建、依赖、环境、部署配置；文件已删除不等于影响已消失；若 `.git` 存在但 metadata 为 `UNAVAILABLE`，不得宣告 Impact Closure。

## 失败处理

发现新消费者不是“审查发现”，而是新的实施范围：先回到修改流程，补完后再审查。若 task-start snapshot 或 Git metadata 因环境不可用导致任务归因证据不完整，必须明确 `BLOCKED_BY_ENVIRONMENT`，不能把整个预存 dirty workspace 当作当前任务结果。
