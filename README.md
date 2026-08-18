# AI自动化测试执行平台

本仓库是《AI自动化测试执行平台》的 Monorepo。项目采用 **Single Living Authority**：`docs/authority/**` 是唯一活动事实源，可在产品主权与验证门禁约束下持续完善。当前处于 **P1 身份认证 + 默认 admin + RBAC 正式实现准备/实施阶段**。

## 当前事实源与门禁原则

- 当前 Authority 输入可用于继续实现；是否可交付由当前任务真实 Gate 与验收结果决定。
- `FULL_SCHEMA_MYSQL84_RUNTIME_GATE` 以当前任务实际执行结果为准；静态验证不得冒充 MySQL 8.4 运行结果。
- `REAL_ACCEPTANCE_GATE` 仅表示当前 Task 的真实验收执行入口；Acceptance 当前状态仍由正式 Acceptance Closure 派生，不由 README 或 Gate Result 维护第二份状态。
- 当前正式验收规范数量由 `tools/current_facts.py#acceptance.count` 机械派生；OBJ-085 退役前历史闭包为 1691，退役条目只保留 provenance，治理验证、Migration 或工程测试不得冒充真实平台业务验收。
- `docs/authority/**` 是唯一活动事实源；不创建版本化整套复制目录、冻结副本或第二份当前状态源。
- Codex 只维护当前事实源并运行 Validators/Gates；Git 仅允许只读检查，提交、推送、回滚等写操作由用户在 IDE 中完成。

## Codex 扩展

目录认知模型：**Agent = Who，Skill = How，Governance Profile = Rules**。

- `.governance/**`：Project Governance Profile / Rules。
- `.agents/skills/**`：项目级 Skills / How。
- `.codex/agents/**`：项目级 Codex Custom Agents / Who。
- `.agents/agent-roles/**`：Role Card 文档/兼容回退说明，不作为原生 Agent 注册位置。
- 根 `AGENTS.md`：项目执行入口和边界。

跨前后端功能优先使用 `$feature-orchestrator`。Reviewer 仅按风险触发；普通任务默认由 `default_coder` 完成，不运行全部 Reviewer。

代码质量由 `$code-quality` 提供 Implementation/Review 两种使用方式；`code_quality_reviewer` 按风险做只读多 Lane 审查，避免重复 Review 循环。

Task 治理统一使用轻量入口。正式 SUCCESS 路径必须包含 Required Gates：

```powershell
python -m tools.governance.task_governance start --root . --task-id <task-id> --request "<task>" --seed-file <path>
# implementation / incremental closure
python -m tools.governance.task_governance gate --root . --task-id <task-id>
python -m tools.governance.task_governance finish --root . --task-id <task-id> --outcome SUCCESS
```

Canonical Lifecycle：`Task Governance Start → Workspace Baseline → Single Full Impact Scan → Shared Task Context → Product Sovereignty Check → Implementation → Workspace Change Detection → Incremental Closure → Final Reconciliation → Required Gates → Gate Freshness Verification → SUCCESS Finish → Optional Git Read-only Review Summary → 用户人工 Review → 用户自行 Git 提交`。

Workspace Baseline 是 Task 变更事实源，Task Context 是治理状态源，Authority 是规则事实源，Gate Result 是验证事实源。Git 仅为可选只读 Review 辅助，不参与 Task changed-files、Required Gate、Gate Freshness 或 SUCCESS 判定；项目没有 Git 时 GovernanceLite 仍必须完整运行。Workspace Tracking 假设本地编辑是 cooperative 的，不尝试防御主动伪造 `mtime_ns` 的对抗行为。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `apps/web` | Vue 3、TypeScript、Vite 前端应用 |
| `services/api` | FastAPI 控制面 API 与正式后端业务 |
| `workers/scheduler` | Scheduler 进程 |
| `workers/background` | Background Worker 进程 |
| `runner/agent` | 独立 Runner Agent |
| `packages/domain-kernel` | 通用领域内核 |
| `packages/contracts` | 当前 OpenAPI/事件 Schema 的加载与验证边界 |
| `packages/observability` | 结构化日志、correlation ID 与敏感字段过滤 |
| `tests` | 契约、集成和 E2E 测试入口 |
| `tools` | 生成、校验与门禁统一入口 |

顶层职责目录不是 Python 包；可安装 Python 代码只位于各项目的 `src/<package>/` 中。

## 环境要求

- Python 3.12.x
- Node.js 22 或 24（`package.json` 约束为 `>=22 <25`）
- npm 11
- MySQL 8.4.x

## 数据库连接配置

本地开发只在仓库根目录 `.env` 配置一次真实 Secret；`.env.example` 只提供可提交模板。所有 Python Runtime、数据库 Gate 和开发工具通过统一 Repository Environment Loader 定位根 `.env`，不依赖当前工作目录。Shell / CI 已显式设置的环境变量优先于 `.env`。

初始化只需要：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 填写两个正式 DSN：

```env
ATP_DATABASE_URL=mysql+pymysql://<user>:<password>@127.0.0.1:3306/ai_auto_test_platform_dev
ATP_MYSQL_ADMIN_URL=mysql+pymysql://<admin_user>:<admin_password>@127.0.0.1:3306/mysql
```

- `ATP_DATABASE_URL` 是 API、Worker、Scheduler 与本地业务数据操作的应用连接。
- `ATP_MYSQL_ADMIN_URL` 是唯一实例级管理连接；Full Schema MySQL Gate 与认证 MySQL Gate 通过它创建/删除隔离 Gate 数据库并执行 Migration/约束验证。
- `PLATFORM_DATABASE_URL` 仅作为 Worker/Scheduler 的旧兼容别名存在，不是正式配置事实源；同时存在时 `ATP_DATABASE_URL` 必须获胜。
- 认证 Runtime Gate 始终创建 `ai_auto_test_platform_gate_auth_<unique>` 临时库；Full Schema Gate 使用 `atp_authority_*_<unique>` 隔离库，不会把破坏性验证指向开发业务库。
- 数据库密码如果包含 `@ : / # % ? &` 等 URL 特殊字符，必须在 DSN 中进行 percent-encoding，例如 `@` → `%40`、`#` → `%23`；不要通过弱化密码来规避 URL 编码。
- 真实 `.env`、完整 DSN 和密码不得进入源码、`.governance`、Authority、Task Context、Gate Result、日志或正式 ZIP。

连接自检：

```powershell
python tools/database/check_connection.py
# 或
python tools/dev.py database-preflight
```

成功时分别输出 `APP_DATABASE_CONNECTION=PASS` 与 `MYSQL_ADMIN_CONNECTION=PASS`，诊断信息只显示脱敏目标。

## 安装依赖

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python tools/dev.py bootstrap
Copy-Item .env.example .env
```

Linux/macOS：

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python tools/dev.py bootstrap
cp .env.example .env
```

## 本地启动

```powershell
# 前端
npm run dev:web

# API；正式公共路由只能来自当前 authority OpenAPI
platform-api

# 进程装配自检
platform-api --check
platform-scheduler --check
platform-worker --check
platform-runner --check

# 长驻进程
platform-scheduler
platform-worker
platform-runner
```

Runner 当前底座不会因为 authority 文档调整而自动实现后续 Runner 注册、心跳、领取任务或正式执行；这些能力仍按后续业务阶段和当前权威契约实现。

## 统一验证命令

```powershell
python tools/dev.py format-check
python tools/dev.py lint
python tools/dev.py typecheck
python tools/dev.py test-unit
python tools/dev.py test-contract
python tools/dev.py test-integration
python tools/dev.py verify-migrations
python tools/dev.py generate-openapi
python tools/dev.py check-openapi
python tools/dev.py build
python tools/dev.py authority
python tools/dev.py verify
```

`python tools/dev.py verify` 是本地和 CI 的全量工程验证入口。`tools/authority_validation.py` 是 Canonical Authority Validator Registry 的唯一事实源；`python tools/dev.py authority` 与正式 `authority_validators` Required Gate 都调用 `docs/authority/validation/run_all_validation.py`，由该聚合器执行完整 Registry，并对每个 Validator 应用 `ATP_AUTHORITY_VALIDATOR_TIMEOUT_SECONDS`。`tools/verify_authority.py` 只是该集合中的一个成员。当前事实源也可单项验证：

```powershell
python docs/authority/validation/run_all_validation.py
# 单项诊断：
python tools/verify_authority.py
python docs/authority/validation/validate_all.py --root docs/authority
python docs/authority/validation/validate_governance.py --root docs/authority
python docs/authority/validation/validate_auth_contract.py --root docs/authority
python docs/authority/validation/validate_acceptance_evidence.py --root docs/authority
python tools/authority_projection.py check
python tools/current_facts.py check
python tools/authority_referential_integrity.py check
python tools/openapi_client.py check
```

## MySQL 8.4 门禁

查看本次 Gate 的未执行说明：

```powershell
python tools/mysql84_gate.py
```

在当前机器重新执行真实门禁：

```powershell
python tools/mysql84_gate.py --execute
```

Full Schema Gate 的本机 MySQL 模式只读取 `ATP_MYSQL_ADMIN_URL`，不再接受拆分式管理员连接变量。需要暂存本次任务的结构化 Gate 结果时：

```powershell
python tools/mysql84_gate.py --execute --result-output .tmp/agent-governance/<task-id>/mysql84-full-schema.json
```

stdout 与 `--result-output` 均为当前 Task 的 secret-free JSON 运行结果；任务结束随 `.tmp/agent-governance/<task-id>/` 清理，不形成长期 Evidence Store。工具不得伪造 PASS，也不得输出真实数据库秘密或完整 DSN。

认证域的长期 Runtime Gate 按能力域命名：

```powershell
python tools/gates/auth_mysql_gate.py
python tools/gates/auth_browser_gate.py

# 等价聚合入口
python tools/dev.py auth-mysql-gate
python tools/dev.py auth-browser-gate
```

输出状态分别为 `AUTH_MYSQL_RUNTIME_GATE` 与 `AUTH_BROWSER_RUNTIME_GATE`。MySQL Gate 会动态创建并清理隔离临时库；Browser Gate 只接受真实 Chromium 结果。Browser Gate 默认由当前项目 `@playwright/test` 解析自身匹配的 Chromium revision，不再扫描 `%LOCALAPPDATA%/ms-playwright/chromium-*` 猜版本；若当前 revision 未安装会 fail-closed，并提示在本项目执行 `npx playwright install chromium`。`PLAYWRIGHT_CHROMIUM_EXECUTABLE` 仅作为显式 override。

## 正式源码交付包

正式源码 ZIP 使用受治理打包入口，自动排除依赖、缓存、构建产物、临时 Runtime/Test Result，并校验 CRC 与 Unicode UTF-8 文件名标记：

```powershell
python tools/package_delivery.py create --output ..\ai-auto-test-platform-delivery.zip
python tools/package_delivery.py verify --archive ..\ai-auto-test-platform-delivery.zip
```
