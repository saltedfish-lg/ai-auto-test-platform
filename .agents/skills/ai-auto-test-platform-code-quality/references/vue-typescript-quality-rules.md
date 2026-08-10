# Vue / TypeScript Quality Rules

- Component聚焦展示和交互，不把复杂认证/业务编排全部塞进单个SFC。
- Store/Composable拥有明确职责，避免同一状态被多个位置各自维护。
- 禁止用`any`、重复本地DTO、魔法字符串绕过generated contract。
- 复杂Route Guard、Refresh队列、401/403恢复和权限UI必须解释关键原因/边界。
- 避免深层watch链、无清理副作用、重复请求和状态闪烁。
- 用户可见Loading/Error/Forbidden/Retry/Refresh行为变化必须有测试或浏览器证据。
