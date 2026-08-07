# AI自动化测试执行平台

本仓库是《AI自动化测试执行平台》的 Monorepo。当前唯一正式输入基线为
`PDBR-2026.08.06-R4.1`，当前阶段是 **P0 工程底座初始化**：只建立可安装、可启动、
可构建、可测试的工程能力，不包含身份权限、项目、Runner 注册、任务调度、AI 流程、
正式执行、报告或制品等业务实现。

## 基线与门禁状态

- `CODE_BASELINE_READINESS = READY_WITH_RUNTIME_DB_VALIDATION_PENDING`
- `MYSQL_8_4_RUNTIME_GATE = NOT_EXECUTED`
- `REAL_PLATFORM_ACCEPTANCE = NOT_EXECUTED`
- 1691 项正式验收规范仍为 `SPECIFIED/NOT_STARTED`，不能用本仓库的工程测试替代。
- `docs/baseline/R4.1/**` 是只读冻结基线；任何正式校验必须读取 Release 和 Manifest，
  不能只依赖 `docs/baseline/CURRENT`。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `apps/web` | Vue 3、TypeScript、Vite 的最小前端启动壳 |
| `services/api` | FastAPI 进程、配置、日志、错误与请求上下文底座 |
| `workers/scheduler` | Scheduler 进程生命周期底座，不含正式调度策略 |
| `workers/background` | Background Worker 进程生命周期底座，不含任务消费 |
| `runner/agent` | 独立 Runner Agent CLI 和可替换适配器边界 |
| `packages/domain-kernel` | 极小通用领域内核，不含具体业务对象 |
| `packages/contracts` | R4.1 OpenAPI/事件 Schema 的加载与验证边界 |
| `packages/observability` | 结构化日志、correlation ID 与敏感字段过滤 |
| `tests` | 仓库级契约、集成和后续 E2E 测试入口 |
| `tools` | 跨平台开发、生成、校验和门禁统一入口 |

顶层职责目录不是 Python 包；可安装 Python 代码只位于各项目的 `src/<package>/` 中。

## 环境要求

- Python 3.12.x
- Node.js 22 或 24（`package.json` 约束为 `>=22 <25`）
- npm 11
- MySQL 8.4.10 仅用于后续运行门禁；P0 验证不会伪造或替代该结果

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

# API（不会增加 R4.1 OpenAPI 未定义的公共健康端点）
platform-api

# 进程配置与装配自检
platform-api --check
platform-scheduler --check
platform-worker --check
platform-runner --check

# 长驻进程
platform-scheduler
platform-worker
platform-runner
```

Runner 的 P0 启动只验证配置、日志、生命周期和适配器边界，不执行注册、认证、心跳、
领取任务、Playwright 正式执行或制品上传。后续需要真实浏览器环境时再执行
`python -m playwright install chromium`。

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

`python tools/dev.py verify` 是本地和 CI 的唯一全量入口，覆盖 R4.1 Manifest、静态与治理
验证、Python 格式/Lint/类型/测试、前端格式/Lint/类型/测试/构建，以及 OpenAPI 客户端
再生成差异检查。

R4.1 原始基线验证也可直接执行：

```powershell
python tools/verify_baseline.py
python docs/baseline/R4.1/编码冻结基线/RELEASE/validation/validate_all.py --root docs/baseline/R4.1
python docs/baseline/R4.1/编码冻结基线/RELEASE/validation/validate_governance.py --root docs/baseline/R4.1
```

## 数据库运行门禁

P0 只提供门禁入口，不执行或宣称通过：

```powershell
python tools/mysql84_gate.py
# 在具备 Docker/Podman 或正式 MySQL 8.4 环境后，由受控流程显式执行：
python tools/mysql84_gate.py --execute
```

在真实执行完成并绑定证据前，数据库模块不得标记完成或正式合并。
