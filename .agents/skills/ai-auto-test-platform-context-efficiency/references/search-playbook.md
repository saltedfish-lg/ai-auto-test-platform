# Search Playbook

优先级：

1. `scripts/impact_scan.py`：跨平台、低输出、可生成JSON；
2. `rg -n`：精准文本检索；
3. LSP/IDE references：符号级调用关系；
4. AST/类型检查：动态或重构影响确认；
5. `scripts/workspace_snapshot.py` + `git diff` / `git status` / `git ls-files --deleted`：先建立任务起点只读快照，再提取当前真实改动与 tracked-but-deleted 路径，禁止Git写操作。

## 建议检索组合

- 精确符号 + snake_case + camelCase + path片段；
- operationId + URL path；
- permission code + menu/route；
- table + ORM model；
- status值 + UI tag/filter；
- event name + producer/consumer；
- old name + new name。

检索命中很多时先聚合文件和命中数，不要把所有匹配正文直接打印进模型上下文。


## 高命中量 Progressive Disclosure

当命中文件很多时，扫描覆盖仍必须完整，但可减少**打印给模型**的行数：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/impact_scan.py <terms> \
  --max-output-files 80 \
  --index-out <临时完整索引.json>
```

- `--max-output-files` 只限制可见输出，不限制实际扫描；
- 使用截断输出时必须通过 `--index-out` 保留完整命中索引，或随后无截断重跑；
- 不得根据 Top N 结果直接宣告 `IMPACT_CLOSURE_PASS`；
- 先看 `group_summary` 决定展开 authority/backend/frontend/tests 等域，再读取局部正文。


## Task-start Snapshot

正式修改开始前、任何工作区写入之前：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  capture --root . --out <仓库外临时路径>/task-start-workspace.json
```

修改完成后：

```bash
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py \
  delta --root . --start <task-start-workspace.json> --out <仓库外临时路径>/task-delta.json
```

- `task_delta_paths` 是“相对任务开始状态发生变化的路径”，不是整个 dirty workspace；
- 任务开始前已经 dirty 的文件若本任务再次修改，内容指纹变化仍会进入 delta；
- 任务开始前已有且本任务未触碰的 dirty/untracked 文件不会被自动归因给当前任务；
- 快照/Delta 文件**必须**放仓库外；helper 会以 `SNAPSHOT_OUTPUT_INSIDE_WORKSPACE` 拒绝 workspace 内输出，避免工具自己制造 untracked 噪声。所有依赖 index 的 Git 查询使用临时 `GIT_INDEX_FILE` 副本，真实 repository/worktree index 不得发生字节变化。

## Scope 分层与失败语义

- `required_roots`：根工程配置、核心源码/测试/工具、CURRENT 标记与当前基线；缺失 => `INCOMPLETE` / 非零退出。
- `optional_roots`：例如当前仓库可能不存在的 `db/`、`.github/`；存在则搜索，缺失只记录。
- `governance_roots`：`.agents/`、`.codex/`；仅 Agent/Skill/Orchestrator/Codex治理任务使用 `--include-governance` 扩张，普通业务修改不全量拉入。
- 输出 `closure_safe=false` 时禁止根据该次结果宣告 `IMPACT_CLOSURE_PASS`。
- `git_workspace.status=UNAVAILABLE` 表示仓库存在 `.git` 但 Git metadata 无法读取；此时 tracked-deleted 证据不完整，scanner 必须 `closure_safe=false`。`CROSS_MODULE/HIGH_RISK` 或 CI/依赖/构建/部署/环境配置/工程工具类任务应视为 `BLOCKED_BY_ENVIRONMENT`。

典型调用：

```bash
# 普通业务影响检索：覆盖源码、根工程事实、测试、CURRENT；不全量扫治理目录
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/impact_scan.py <term> --root . --risk LOCAL --json

# Agent/Skill/Codex治理修改：显式扩大治理目录
python .agents/skills/ai-auto-test-platform-context-efficiency/scripts/impact_scan.py <term> --root . --risk CROSS_MODULE --include-governance --json
```


## Tracked-but-deleted 边界

`impact_scan.py` 会从只读 Git metadata 报告 `git_workspace.status` 与 `git_workspace.tracked_deleted`。这些路径的工作树正文已经不存在，但仍属于当前 workspace 影响证据。尤其 `.github/**`、依赖/构建/环境/部署文件被删除时，必须确认删除是否为当前预期、是否仍存在脚本/文档/构建入口消费者；不得因为文件系统搜索不到正文就宣告“无影响”。若 `.git` 存在但 status=`UNAVAILABLE`，不得把空的 `tracked_deleted` 列表解释为“没有已删除消费者”。
