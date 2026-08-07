# AI自动化测试执行平台

本仓库是《AI自动化测试执行平台》的 Monorepo。当前正式编码基线由 `docs/baseline/CURRENT` 导航，当前值为 **R4.2**，对应 Release `PDBR-2026.08.07-R4.2`。当前处于 **P1 身份认证 + 默认 admin + RBAC 正式实现准备/实施阶段**。

## 基线与门禁状态

- `CODE_BASELINE_READINESS = READY_FOR_P1_IMPLEMENTATION`
- `MYSQL_8_4_RUNTIME_GATE = PASS`（R4.2 已绑定 MySQL 8.4.11 空库安装与 R4.1→R4.2 升级证据）
- `REAL_PLATFORM_ACCEPTANCE = NOT_COMPLETED`
- 1691 项正式验收规范仍为 `SPECIFIED/NOT_STARTED`；治理验证、Migration 或工程测试不得冒充真实平台业务验收。
- `docs/baseline/R4.2/**` 是当前只读冻结基线；`docs/baseline/R4.1/**` 仅保留为历史父基线和升级溯源。
- 活动工具必须通过 `docs/baseline/CURRENT` 解析当前基线；不得用历史版本常量覆盖当前契约。

## Codex 扩展

- `.agents/skills/**`：项目级 Skills。
- `.codex/agents/**`：项目级 Codex Custom Agents。
- `.agents/agent-roles/**`：Role Card 文档/兼容回退说明，不作为原生 Agent 注册位置。
- 根 `AGENTS.md`：项目执行入口和边界。

跨前后端功能优先使用 `$ai-auto-test-platform-feature-orchestrator`。支持 subagent 时，Orchestrator 可调用 `.codex/agents/**` 中的专用 Agent；不支持时由主 Agent 按相同 Skill/Role 规则串行执行。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `apps/web` | Vue 3、TypeScript、Vite 前端应用 |
| `services/api` | FastAPI 控制面 API 与正式后端业务 |
| `workers/scheduler` | Scheduler 进程 |
| `workers/background` | Background Worker 进程 |
| `runner/agent` | 独立 Runner Agent |
| `packages/domain-kernel` | 通用领域内核 |
| `packages/contracts` | 当前冻结 OpenAPI/事件 Schema 的加载与验证边界 |
| `packages/observability` | 结构化日志、correlation ID 与敏感字段过滤 |
| `tests` | 契约、集成和 E2E 测试入口 |
| `tools` | 生成、校验与门禁统一入口 |

顶层职责目录不是 Python 包；可安装 Python 代码只位于各项目的 `src/<package>/` 中。

## 环境要求

- Python 3.12.x
- Node.js 22 或 24（`package.json` 约束为 `>=22 <25`）
- npm 11
- MySQL 8.4.x（R4.2 运行证据使用 MySQL 8.4.11）

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

# API；正式公共路由只能来自当前冻结 OpenAPI
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

Runner 当前底座不会因为 R4.2 切换而自动实现后续 Runner 注册、心跳、领取任务或正式执行；这些能力仍按后续业务阶段和冻结契约实现。

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
python tools/dev.py baseline
python tools/dev.py verify
```

`python tools/dev.py verify` 是本地和 CI 的全量工程验证入口。基线相关工具均从 `docs/baseline/CURRENT` 解析当前冻结版本。

当前 R4.2 基线也可直接验证：

```powershell
python tools/verify_baseline.py
python docs/baseline/R4.2/编码冻结基线/RELEASE/validation/validate_all.py --root docs/baseline/R4.2
python docs/baseline/R4.2/编码冻结基线/RELEASE/validation/validate_governance.py --root docs/baseline/R4.2
python docs/baseline/R4.2/编码冻结基线/RELEASE/validation/validate_auth_contract.py --root docs/baseline/R4.2
```

## MySQL 8.4 门禁

查看当前冻结基线已经记录的门禁状态：

```powershell
python tools/mysql84_gate.py
```

在当前机器重新执行真实门禁：

```powershell
python tools/mysql84_gate.py --execute
```

重新执行需要可用的 MySQL 8.4 环境或正式容器环境；工具不得伪造 PASS，也不得把真实数据库秘密写入仓库。
