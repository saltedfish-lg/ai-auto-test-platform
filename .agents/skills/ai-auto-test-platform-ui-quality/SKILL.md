---
name: ai-auto-test-platform-ui-quality
description: 用真实浏览器验证AI自动化测试执行平台页面视觉、交互、状态、Console/Network和权限体验的前端质量Skill。
---

# UI Quality & Browser Verification

## 范围

适用于已经有可运行页面的任务。优先使用 `apps/web` 已安装的 Playwright Test 与真实开发服务器。

## 检查清单

- 页面能进入且无明显布局溢出/遮挡；
- 表格、表单、Dialog/Drawer、分页、筛选、危险动作可操作；
- Loading / Empty / Error / Forbidden / Disabled / Conflict 状态有用户可理解反馈；
- Console 无未处理错误；Network 无被忽略的失败请求；
- 认证过期、401/403、强制改密、登出后的路由和缓存处理正确；
- 前端隐藏权限不替代后端授权；
- 关键状态标签来自正式枚举，不自行发明；
- 测试使用 mock 时明确标记为组件测试，不得声称真实业务闭环通过。

## 结果

输出实际验证路径、关键交互、发现的问题和已修复项。正式发布验收仍需对应 acceptance evidence，浏览器 smoke 不得冒充 1691 项验收通过。
