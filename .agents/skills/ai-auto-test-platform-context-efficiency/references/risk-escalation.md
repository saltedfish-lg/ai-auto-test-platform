# Risk Escalation Matrix

出现以下任一信号，自动把影响检索扩大到对应域：

| 信号 | 必查扩张域 |
|---|---|
| API path / DTO / operationId | OpenAPI、generated client、backend handler、frontend consumer、contract tests |
| 表/列/FK/UNIQUE/CHECK | DDL/Migration、ORM、repository、transaction、fixtures、integration tests |
| permission / role / data scope | RBAC seed/mapping、backend guards、frontend PermissionGate、菜单/路由、403 tests |
| status / lifecycle | owner、transition guard、API schema、UI status、filter/report、tests |
| event / outbox | producer、consumer、schema、idempotency、retry、audit、tests |
| Runner/Worker | scheduler、lease、lock、fencing、heartbeat、task state、observability、E2E |
| auth/session/token/password | auth contract、security、cookies、session store、401/403、revocation、E2E |
| destructive/high-risk action | permission、confirmation、audit、idempotency、rollback/error state、UI hierarchy |
| generated file | generator source、formal contract、generation report、all consumers |
| shared package/domain-kernel | all importers and public API consumers |

风险扩张不能被“当前任务只要求改一个页面/函数”覆盖。
