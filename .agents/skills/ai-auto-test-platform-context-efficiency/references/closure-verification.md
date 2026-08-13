# Closure Verification

## Post-change Closure

1. 使用 `workspace_snapshot.py delta` 对比 由 `workspace_snapshot.py::SNAPSHOT_VERSION` 定义的 filesystem task-start/current 快照，得到 `added / removed / modified / task_delta_paths / changed_symbols / changed_line_ranges`，其中 symbol/range scope 由 snapshot v4 机械比较产生。
2. 从真实 task delta 提取旧/新 symbol、operationId、DTO、table、permission、state、event、route、config、Runner capability 等 seed。
3. 执行 `TARGETED_REVERSE_LOOKUP`，检查全部消费者。
4. 发现新消费者时标记 `IMPACT_EXPANSION`，扩充**同一个** Task Context Pack 并递增 `pack_revision`。
5. 运行与真实影响域对应的 contract/database/security/UI/code-quality/acceptance 验证。
6. 所有已知影响关闭后才允许 `IMPACT_CLOSURE_PASS`。

`STALE / Post-change Closure / IMPACT_EXPANSION` 均禁止重新执行 `impact_scan.py`；只允许 `DELTA_REFRESH + TARGETED_REVERSE_LOOKUP`。

Filesystem snapshot、delta、scan state、checkpoint 必须位于 workspace 外。Git 不参与当前 Task 归因，也不得作为 Closure 必需证据。
