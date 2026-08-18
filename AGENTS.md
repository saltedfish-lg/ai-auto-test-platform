# AGENTS.md — AI自动化测试执行平台

## 1. Authority 与产品主权
- 当前唯一活动业务事实源：`docs/authority/**`，采用 `SINGLE_LIVING_AUTHORITY`。
- `.governance/**` 是 Project Governance Profile / Rules，只描述 Domain/Authority/Gate/Reviewer/Adapter 路由，不替代业务 Authority；`.agents/skills/**` 表示 Skills / How，`.codex/agents/**` 表示 Agents / Who。
- 代码、DDL、OpenAPI、状态、权限、Runner、安全和验收实现必须服从相关 Authority。
- 角色、权限、状态/状态机、核心业务规则、生命周期、资源冲突、数据保留、正式安全规则、公开产品契约或正式能力删除属于产品主权；敏感实现变更由 `product_sovereignty_reviewer` 对照 Authority 判定是否需要用户裁决。

## 2. User Owned Git
- 治理标识：`USER_OWNS_GIT`。Git 提交与历史由用户负责。
- Git 仅是可选只读工程辅助，不是 Task 状态、变更识别、Impact、Product Sovereignty、Gate、Freshness、Final Reconciliation 或 SUCCESS 的权威事实源；无 Git 环境必须完整可运行。
- 可选 `git_readonly_adapter.py` 仅允许读取 `git status`、`git diff`、`git diff --stat`、`git rev-parse`、`git branch --show-current`、`git log`、`git show`，用于用户最终 Review 摘要；Git 不可用或失败不得阻断 Governance。
- 禁止自动执行：`git add`、`git commit`、`git push`、`git reset`、`git checkout`、`git switch`、`git merge`、`git rebase`、`git stash`、`git tag`、`git cherry-pick`、`git clean`。

## 3. Core Agents / Skills
仅保留 4 个 Core Agent：`default_coder`、`architecture_reviewer`、`product_sovereignty_reviewer`、`code_quality_reviewer`。Reviewer 按风险触发，不是固定全量流水线。

仅保留 4 个 Core Skill：
- `$context-efficiency`
- `$feature-orchestrator`
- `$product-sovereignty`
- `$code-quality`

## 4. Task Workflow
1. 读取本文件、`.governance/` Project Governance Profile 和必要 Authority。
2. 使用 `python tools/governance/task_governance.py start ...` 启动 Task：建立本地 Workspace Baseline（轻量 metadata），并执行唯一一次 Full Impact Scan；Task 变更事实来自 Baseline 与当前 Workspace，不读取 Git changed-files。
3. 执行 Product Decision Check；若 `product_decision_status=REQUIRED`，Required Gates 与 SUCCESS/COMPLETED 必须机械阻断，只有用户通过受控入口提供正式裁决后才可变为 RESOLVED。
4. `default_coder` 实施；发现新文件/依赖立即执行 Incremental Closure。
5. unknown edge：FILE/DOMAIN → MODULE → REPOSITORY；每次扩大后必须基于最终 `affected_files` 重算 Domain/Authority/Gate/Reviewer/Risk。
6. Gate 前必须完成 Final Reconciliation。推荐直接使用 `python tools/governance/task_governance.py gate --root . --task-id <id>`；该统一入口会先执行 Reconciliation，再运行 Required Gates。手工调用 Gate Runner 时，Runtime 也会机械阻断未完成或已过期的 Reconciliation；Product Decision REQUIRED 同样会阻断 Gate。
7. `code_quality_gate` 必须检查当前 `affected_files`，不能只跑治理自身 Contract Tests；项目完全未配置 Gate 时默认 `BLOCKED / NO_CONFIGURED_GATE`，只有 Profile 显式 `allow_no_gates: true` 才可例外。每次 Gate Result 必须绑定当前 Task 的 affected-file workspace digest。
8. Gate 后若 affected file 内容、新增/删除状态发生变化，旧 PASS 必须判为 `GATE_RESULT_STALE` 并重新执行必要 Gate；随后按风险触发 Reviewer。
9. 成功结束使用 `task_governance.py finish ... --outcome SUCCESS`。它必须同时确认 Reconciliation current、Product Decision 不阻断、所有 Required Gates 已执行且全部 PASS、结果属于当前 Task、Workspace Digest 未失效；失败、取消或中止分别使用 `FAILED`、`CANCELLED`、`ABORTED` 清理临时状态。SUCCESS 后如需 Git 信息，仅通过可选只读 Adapter 生成辅助 Review Summary，随后由用户人工 Review 并自行提交 Git。

`impact_scan.py` 仅为内部实现/Contract Test 辅助入口，不是 Agent 正式启动入口。

## 4.1 Workspace Writer Ownership
- 同一物理 Workspace 同一时刻只允许一个 Coding Writer Task。Writer Task 启动时必须原子取得 `.tmp/agent-governance/workspace-writer.lock`；第二个 Writer 必须返回 `WORKSPACE_WRITER_BUSY`。
- `architecture_reviewer`、`code_quality_reviewer`、`product_sovereignty_reviewer` 等只读 Reviewer 可与 Writer 并行读取，不取得 Writer Lock。
- Writer 正常 Finish/FAILED/CANCELLED/ABORTED 后释放锁；仅当锁记录的 owner PID 已不存在时才允许 stale recovery。不得引入 Lease/Fencing/分布式锁或 per-file ownership。

## 5. Generic Runtime + Project Profile
- `tools/governance/**`、`.codex/agents/**`、`.agents/skills/**` 为通用机制，不得写死本项目路径、业务对象、技术栈或产品事实。
- 当前项目的目录、Domain、Authority、Gate 命令、Reviewer 路由、技术 Adapter、行为判定扩展均进入 `.governance/**`。
- 新项目 Profile 不完整时必须显式返回 `NO_CONFIGURED_GATE` / `NO_AUTHORITY_CONFIGURED` 等状态，不得伪造 PASS 或自动创造产品规则。

## 6. Authority Single Writer
修改 `docs/authority/**` 前取得固定全局路径 `.tmp/agent-governance/authority.lock`。获取使用 `O_EXCL`；stale recovery 由跨进程 recovery mutex 串行化并在删除前复核锁实例。该机制仅是本地文件级编辑互斥，不扩展为 Lease/Fencing/Trust/Signature 协议。

## 7. 当前项目安全能力不可因治理精简删除
Password Hash、Login/Refresh、Credential Version、临时凭据、首次强制改密、Session Revocation、RBAC、SUPER_ADMIN/default admin 保护、Login/Refresh Rate Limit、Forwarded IP Trust、Secret/Credential、API Authentication 与数据权限继续由项目 Authority 和代码约束。

## 8. Governance 修改边界
普通业务 Task 默认不得修改 `AGENTS.md`、`.governance/**`、`.agents/**`、`.codex/**`、`tools/governance/**`。只有用户明确发起 Agent/Skill Governance Maintenance Task 时允许；不得恢复已退役的复杂安全治理链。

Governance 回归测试必须按稳定能力命名；长期测试文件/测试函数禁止使用发布版本号、`Final`、`Fixed`、`Closure` 作为版本标签。修复期间的临时复现测试必须在任务结束前迁移到 `test_governance_<capability>.py` 并删除临时文件。正式 `governance_contract_test` 必须通过自动发现覆盖完整 `test_governance_*.py` 套件，禁止维护手工版本化文件清单。

## 9. 本地数据库环境与 Codex 自主操作
- 本地开发的真实数据库 Secret 只允许保存在仓库根 `.env`；`.env.example` 仅提供占位模板。正式数据库连接变量只有 `ATP_DATABASE_URL`（应用业务库）与 `ATP_MYSQL_ADMIN_URL`（MySQL 实例/Schema Gate 管理连接）。
- API、Worker、Scheduler、数据库 Gate 与开发工具必须通过统一 Repository Environment Loader 读取根 `.env`；当前 Shell/CI 已显式设置的变量优先于 `.env`。不得要求必须从仓库根 cwd 启动。
- `PLATFORM_ENVIRONMENT=local` 时，Codex 可按当前开发任务自主执行必要的 SELECT/SHOW/DESCRIBE/EXPLAIN、带明确范围的 INSERT/UPDATE/DELETE、测试数据准备与清理、Migration、Seed、Schema/Index/Constraint 验证、`information_schema` 查询，以及创建/清理隔离 Gate DB。用户完成一次 `.env` 初始化后，不应在每次数据库任务重复询问用户名、密码或完整 DSN。
- 正式 Schema 变化必须落入 Migration 后再执行和验证；不得只手工 ALTER 开发库而不留下可复现 Migration。Full Schema / Auth MySQL Gate 的破坏性验证只允许使用各自唯一隔离临时库，禁止 DROP/TRUNCATE `ai_auto_test_platform_dev`。
- 本地开发数据 UPDATE/DELETE 必须有当前任务理由与明确作用范围；默认禁止无 WHERE 的 UPDATE/DELETE 或无任务依据的大范围数据清理。
- 完整 DSN、密码和连接异常中的 Secret 不得写入源码、README、`.governance`、Authority、Task Context、Gate Result、日志或正式 ZIP。诊断统一使用脱敏 URL/错误信息。
- 连接自检使用 `python tools/database/check_connection.py`；数据库密码包含 URL 特殊字符时必须 percent-encoding。
