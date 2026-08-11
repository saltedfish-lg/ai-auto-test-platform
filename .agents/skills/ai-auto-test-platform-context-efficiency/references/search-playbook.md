# Search Playbook

## 原则

`SEARCH_BROAD_LOAD_NARROW_VERIFY_BROAD`：活动仓库搜索范围完整，模型正文加载按需收敛。

## 活动搜索范围

默认 required：root engineering facts、apps/services/workers/runner/packages/tests/tools、唯一 `docs/authority`。

Optional：`db`、`.github`。Agent/Skill/Codex治理任务再显式加入 `.agents/.codex`。

不存在版本化 CURRENT marker、历史 authority expansion 或 Git 元数据扫描。

## Full Impact Scan

正式 Task 最多一次成功 Full Scan。使用明确任务 seed 搜索活动仓库，结果只保留：

```text
path + responsibility group + line + short preview
```

超大文本按行流式扫描，不因体积静默跳过 authority YAML/JSON/CSV/SQL。

## Targeted Reverse Lookup

修改后只围绕真实 `task_delta_paths` 和 changed symbols 反查消费者。允许多次 targeted lookup，但不得调用 `impact_scan.py` 或退化成第二次无种子全仓探索。

## Filesystem Delta

Task 开始前使用 `workspace_snapshot.py capture`；修改后 `delta`。Git 完全由用户在 IDEA 管理，Codex 不调用 Git，也不依赖 branch/commit/index/tracked-deleted 判定任务影响。
