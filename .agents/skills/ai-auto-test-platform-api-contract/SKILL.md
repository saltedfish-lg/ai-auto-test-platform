---
name: ai-auto-test-platform-api-contract
description: 冻结OpenAPI、ProblemDetails、生成TypeScript客户端与后端Operation/DTO对齐的契约守卫Skill。
---

# API Contract Guardian

## 目标

保证 `docs/baseline/R4.2/编码冻结基线/OPENAPI/openapi.yaml`、后端实现和 `apps/web/src/generated/**` 同源，不出现“三套类型”。

## 规则

- 冻结 OpenAPI 只读，不因实现方便而修改；
- generated client/types 禁止手改；
- 后端路由 method/path/operation_id/request/response/error 与正式契约逐项对齐；
- 前端只消费 generated 类型；
- OpenAPI生成器必须从 `docs/baseline/CURRENT` 解析当前冻结版本；若生成器与CURRENT不一致，视为阻断性实现工具漂移；
- 契约没有定义的公开行为不得自行增加。

## 验证

优先运行：

```text
python tools/openapi_client.py check
python tools/dev.py test-contract
npm run check:api
```

这些命令必须验证 CURRENT 对应冻结契约；任何历史基线 PASS 都不能替代当前基线契约验证。
