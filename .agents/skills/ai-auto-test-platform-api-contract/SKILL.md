---
name: ai-auto-test-platform-api-contract
description: 当前 authority OpenAPI、ProblemDetails、生成TypeScript客户端与后端Operation/DTO对齐的契约守卫Skill。
---

# API Contract Guardian

## 目标

保证 `docs/authority/编码权威事实/OPENAPI/openapi.yaml`、后端实现和 `apps/web/src/generated/**` 同源，不出现“三套类型”。

## 规则

- 当前 authority OpenAPI 不得因实现方便擅自修改；只有用户请求或已确认的 Product/Authority 决策要求契约变化时，才允许在 `AUTHORITY_UPDATE_ONLY` 阶段同步修改；
- generated client/types 禁止手改；
- 后端路由 method/path/operation_id/request/response/error 与正式契约逐项对齐；
- 前端只消费 generated 类型；
- OpenAPI生成器必须从 `docs/authority` 解析唯一当前 authority；若生成器与当前 authority 不一致，视为阻断性实现工具漂移；
- 契约没有定义的公开行为不得自行增加。

## 验证

优先运行：

```text
python tools/openapi_client.py check
python tools/dev.py test-contract
npm run check:api
```

这些命令必须验证当前 authority 契约；历史记录或旧输出不能替代当前事实验证。
