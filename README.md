# AI自动化测试执行平台

本仓库是《AI自动化测试执行平台》的 Monorepo。项目采用 **Single Living Authority**：`docs/authority/**` 是唯一活动事实源，可在产品主权与验证门禁约束下持续完善。当前处于 **P1 身份认证 + 默认 admin + RBAC 正式实现准备/实施阶段**。

## 当前事实源与门禁状态

- `CODE_BASELINE_READINESS = READY_FOR_P1_IMPLEMENTATION`
- `MYSQL_8_4_RUNTIME_GATE` 以当前环境实际执行结果为准；静态验证不得冒充 MySQL 8.4 运行时证据。
- `REAL_PLATFORM_ACCEPTANCE = NOT_COMPLETED`
- 1691 项正式验收规范仍为 `SPECIFIED/NOT_STARTED`；治理验证、Migration 或工程测试不得冒充真实平台业务验收。
- `docs/authority/**` 是唯一活动事实源；不创建 R4.x/R5.x 整套复制目录，不维护 CURRENT marker、Baseline Manifest 或 Release Snapshot。
- Codex 只维护当前事实源并运行 Validators；Git 对 Codex 禁用，提交、推送、回滚与历史查看由用户在 IDEA 中完成。

## Codex 扩展

- `.agents/skills/**`：项目级 Skills。
- `.codex/agents/**`：项目级 Codex Custom Agents。
- `.agents/agent-roles/**`：Role Card 文档/兼容回退说明，不作为原生 Agent 注册位置。
- 根 `AGENTS.md`：项目执行入口和边界。

跨前后端功能优先使用 `$ai-auto-test-platform-feature-orchestrator`。支持 subagent 时，Orchestrator 可调用 `.codex/agents/**` 中的专用 Agent；不支持时由主 Agent 按相同 Skill/Role 规则串行执行。

代码质量由 `$ai-auto-test-platform-code-quality` 提供双模式规则：实现 Agent 使用 **Implementation Standards Mode**，`code_quality_reviewer` 使用 **Review Mode** 做只读多Lane审查；最终 `independent_code_reviewer` 优先复用同一workspace/scope的专项审查结果，避免重复Review循环。

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

`python tools/dev.py verify` 是本地和 CI 的全量工程验证入口。当前事实源也可直接验证：

```powershell
python tools/verify_authority.py
python docs/authority/validation/validate_all.py --root docs/authority
python docs/authority/validation/validate_governance.py --root docs/authority
python docs/authority/validation/validate_auth_contract.py --root docs/authority
```

## MySQL 8.4 门禁

查看当前 authority 记录的门禁状态：

```powershell
python tools/mysql84_gate.py
```

在当前机器重新执行真实门禁：

```powershell
python tools/mysql84_gate.py --execute
```

重新执行需要可用的 MySQL 8.4 环境或正式容器环境；工具不得伪造 PASS，也不得把真实数据库秘密写入仓库。
