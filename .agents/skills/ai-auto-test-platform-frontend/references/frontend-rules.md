# Frontend Project Rules

## 已有路径

```text
apps/web/src/
├─ api/client.ts
├─ components/PlatformShell.vue
├─ config.ts
├─ generated/client.ts
├─ generated/types.ts
├─ router/index.ts
├─ tests/
└─ styles.css
```

现状是最小壳，不要求永远保持扁平。随着正式模块实现，可在 `src/` 内自主建立 `views/`、`features/`、`stores/`、`composables/`、`components/` 等内部结构，只要职责清晰且不与正式业务模块语义冲突。

## API

- 优先通过 `src/api/client.ts` 和 generated client 调用正式 API；
- 不直接复制 generated DTO；
- 契约改变时运行 `python tools/openapi_client.py generate`，再审查生成差异；
- API 错误统一识别 `application/problem+json` / `ProblemDetails`。

## 认证 UI

当前 authority P1：

- 登录：`POST /api/v1/auth/login`；
- 刷新：`POST /api/v1/auth/refresh`；
- 登出：`POST /api/v1/auth/logout`；
- 当前用户：`GET /api/v1/auth/me`；
- 改密：`POST /api/v1/auth/change-password`；
- Access JWT 只在内存；`atp_refresh` 由 HttpOnly Cookie 承载；
- bootstrap admin 不得从 Vue 页面触发；
- `force_password_change` 时只允许契约规定的有限操作，前端应导向改密而不是绕过。

## 视觉

这是企业级测试平台后台，不追求营销页动画。优先：清晰信息层级、密度可控、状态可辨识、复杂表格可操作、危险动作清晰确认、错误可恢复、长任务进度可观察。
