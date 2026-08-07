# Backend Project Rules

## 当前 API 底座

`services/api/src/platform_api/` 目前主要包含：

- `app.py`：FastAPI assembly；
- `config.py`：Pydantic Settings；
- `middleware.py`：correlation id；
- `errors.py`：ProblemDetails / PlatformError；
- `audit.py`：审计上下文边界；
- `cli.py` / `health.py`：进程入口与内部自检。

不要假设 Controller/Service/Repository 已存在；可以在不改变业务语义的前提下渐进建立内部结构。

## Python 质量门禁

- Python 3.12；
- Ruff line length 100，严格 lint；
- mypy strict；
- pytest strict markers/config；
- 项目使用 src-layout + Hatchling；新增 package/module 要保持安装和类型检查可发现。

## 数据库

- MySQL + PyMySQL；`ApiSettings` 已拒绝 SQLite；
- SQLAlchemy 2.x；
- 使用真实约束，不把业务唯一性只放在 Python if 中；
- 正式 DDL 已存在时实现必须适配 DDL，不应修改冻结 SQL 来迁就代码。

## API 错误

- 受保护 Operation 的 401/403 使用正式 `ProblemDetails`；
- correlation id 应贯穿错误响应、日志和审计上下文；
- 不向调用者泄露认证枚举、数据库错误、Secret 或内部堆栈。
