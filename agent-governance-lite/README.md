# GovernanceLite Standalone Template

这是 GovernanceLite 的可复制、可配置、可运行分发形态。Generic Runtime 不包含具体项目业务规则；项目事实必须由 `.governance/` Project Governance Profile 与项目 Authority 提供。目录语义固定为：`.governance/ = Rules`、`.agents/skills/ = How`、`.codex/agents/ = Who`。

## Prerequisites

- Python >= 3.12
- `pip install -r requirements.txt`

Standalone 当前直接依赖 `PyYAML` 与 `python-dotenv`；依赖声明见本目录 `requirements.txt`。

## 1. 复制到新项目

将以下内容复制到目标仓库：

- `agents/*.toml` → `.codex/agents/`
- `skills/*` → `.agents/skills/`
- `runtime/tools/` → `tools/`（包含 Generic Governance Runtime 与根 `.env` 只读加载辅助）
- `templates/project-profile/.governance/` → `.governance/`
- 将 `templates/AGENTS.governance-snippet.md` 合并到目标项目已有 `AGENTS.md`，不得覆盖原文件
- 保留 `requirements.txt` 或将其中依赖合并到目标项目依赖清单

Standalone Runtime 只包含目标项目运行所需机制；源仓库自身的业务事实和项目专属 Gate 不作为目标项目运行依赖。

## 2. 配置 Project Profile

编辑 `.governance/project.yaml`，设置项目名称、仓库类型和 Runtime 开关。`allow_no_gates` 默认保持 `false`；只有明确不需要 Gate 的项目才能设为 `true`。

## 3. 定义 Domain

在 `.governance/domains.yaml` 中定义 `paths`、`kind`、Gate、Authority、Reviewer Risk 等。Runtime 不依赖固定 Domain 名；`SERVER`、`CLIENT`、`APP` 或其他名称均可。跨实现域判断使用 `kind: implementation`。

## 4. 定义 Authority

在 `.governance/authorities.yaml` 中声明项目自己的产品、架构、数据或契约事实源及 `paths`。Authority 可以位于 `docs/authority/**`、`specs/product/**`、`policy/**` 或任何 Profile 声明的位置；Generic Runtime 不固定 Authority 目录。Authority Registry 允许为空；Runtime 不要求每个项目必须配置 Authority，但缺少产品事实时不会自行创造业务规则。

## 5. 定义 Gate

在 `.governance/gates.yaml` 中配置项目实际可执行命令。Standalone 默认 Registry 包含示例 `app_test`、Runtime 可能自动要求的 `code_quality_gate`，以及用于保护 Governance Core 自身的 `governance_lite_validator` 与 `governance_contract_test`。项目没有任何 Gate 配置且 `allow_no_gates: false` 时，Required Gate Runner 返回 `BLOCKED / NO_CONFIGURED_GATE`，不会伪 PASS。


## Governance Core self-protection

默认 Project Profile 内置 `GOVERNANCE` Domain，覆盖 `AGENTS.md`、`.governance/**`、`.agents/**`、`.codex/**`、`tools/governance/**` 以及保留分发目录时的 `agent-governance-lite/**`。修改 Governance Core 时至少要求 `governance_lite_validator + governance_contract_test`；高风险代码变更还可附加 `code_quality_gate`。因此 Governance Runtime 修改不得退化为 `NO_REQUIRED_GATE`。

`governance_contract_test` 在项目存在 `tests/contract/test_governance_*.py` 时自动执行完整稳定命名套件；新建 Standalone 项目尚无项目级 Governance Tests 时，则执行 Runtime 自带的机械 self-contract（Python 可编译性、核心 Runtime 文件、GOVERNANCE Domain 与 Gate Registry 完整性），不会 mock PASS。

## 6. 定义 Reviewer

在 `.governance/reviewers.yaml` 中按 Domain、Risk、Authority 或 Product Sovereignty 条件触发现有 Reviewer。不要把 Reviewer 配成全局常驻，也不要新增重复领域 Agent。

## 7. 配置技术栈

在 `.governance/technology.yaml` 中按文件路径定义语言/框架及 Adapter。项目可以覆盖默认质量检查能力。

## 8. 启动任务 / Single Full Impact Scan

```bash
python tools/governance/task_governance.py start --root . --task-id TASK-001 --request "implement feature" --seed-file src/example.py
```

Task Start 是唯一 Full Impact Scan 入口，并先建立本地 Workspace Baseline。Baseline 记录治理范围内文件的 `size + mtime_ns + file_state`，不读取 Git HEAD/Diff；后续实际 Task 变更由 Baseline 与当前 Workspace 比较得到，发现新影响使用 Incremental Closure，不重复 Full Repository Scan。Workspace Tracking 假设 cooperative local editing，不尝试防御主动伪造时间戳。默认 `start` 为 writer mode；同一物理 Workspace 同时只能有一个 writer，第二个 writer 返回 `WORKSPACE_WRITER_BUSY`，只读 reviewer 可使用 `--mode readonly` 并行启动。

## 9. Product Decision Check

如果 Task Context 为 `product_decision_status=REQUIRED`，Gate 和成功 Finish 都会被机械阻断。只有用户提供正式产品裁决后才执行：

```bash
python tools/governance/task_governance.py resolve-product-decision --root . --task-id TASK-001 --decision "用户确认的正式产品裁决"
```

Reviewer、Coder、测试 PASS 均不得自动把 REQUIRED 改为 RESOLVED。

## 10. Implementation / Incremental Closure

按 Shared Task Context 实现。若实际修改扩展到 Context 外文件，Final Reconciliation 会触发 Incremental Closure 补齐影响范围、Gate、Reviewer 与 Authority。

## 11. Final Reconciliation + Required Gates

推荐只使用统一 Gate 入口：

```bash
python tools/governance/task_governance.py gate --root . --task-id TASK-001
```

该命令执行：

`Final Reconciliation → Required Gates → Gate workspace freshness recording`

也可单独执行 `reconcile`，但 Required Gate Runner 本身仍会机械检查 Reconciliation 是否 current。

Gate Result 绑定当前 Task 的 affected files 内容摘要。Gate PASS 后只要 affected file 内容、新增/删除状态发生变化，旧 PASS 就会失效。

## 12. SUCCESS Finish

```bash
python tools/governance/task_governance.py finish --root . --task-id TASK-001 --outcome SUCCESS
```

`SUCCESS/COMPLETED` 至少要求：

- Final Reconciliation current；
- Product Decision 不处于 REQUIRED；
- Required Gates 已执行；
- 每个 Required Gate 都存在当前 Task 的 PASS Result；
- Gate Result 的 workspace digest 与当前 affected files 状态一致。

`FAILED/CANCELLED/ABORTED` 仅用于异常清理，不声称成功闭环。

## 13. 推荐安装验证流程

1. Copy runtime
2. Copy agents
3. Copy skills
4. Copy `.governance` profile template
5. `pip install -r requirements.txt`
6. Merge `AGENTS.governance-snippet.md` into existing `AGENTS.md`
7. Customize Project Profile / Authority paths
8. Run `python tools/governance/governance_lite_validator.py --root .`
9. Run `start → implement → gate → finish SUCCESS`
10. 再执行一个 high-risk code-quality task，确认 `code_quality_gate` 不会 `NOT_CONFIGURED`

## Canonical lifecycle

`Task Governance Start → Workspace Baseline → Single Full Impact Scan → Shared Task Context → Product Decision Check → Implementation → Workspace Change Detection → Incremental Closure → Final Reconciliation → Required Gates → Workspace Digest / Gate Freshness → SUCCESS Finish → Optional Git Read-only Review Summary → User Review / Git Commit`

Workspace 是 Task 变更事实源，Task Context 是治理状态源，Authority 是规则事实源，Gate Result 是验证事实源。Git 只是可选只读辅助信息源，不参与 affected-files、Impact、Required Gates、Product Decision、Freshness、Reconciliation 或 SUCCESS 判断。项目没有 Git、Git 命令失败或不可执行时 Governance 仍必须正常完成。用户需要最终 Review 信息时可单独运行 `python tools/governance/git_readonly_adapter.py --root .`。Agent/Runtime 不得自动 add、commit、push、reset、checkout、switch、merge、rebase、stash、tag、cherry-pick 或 clean；提交由用户人工 Review 后自行执行。


## Local process ownership safety

Process liveness checks are platform-aware. Windows never uses `os.kill(pid, 0)` as a liveness probe. Lock ownership uses PID plus process creation identity where available; inaccessible or unverifiable process identity is handled conservatively rather than deleting a lock.
