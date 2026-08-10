---
name: ai-auto-test-platform-ui-quality
description: 用真实浏览器验证AI自动化测试执行平台页面视觉、交互、状态、Console/Network、权限体验与业务UI落地质量的前端验证Skill。
---

# UI Quality & Browser Verification

## 范围

适用于已经有可运行页面的任务。优先使用 `apps/web` 已安装的 Playwright Test 与真实开发服务器。

本 Skill 主要验证“页面真实运行是否正确”；业务信息架构与反机械化设计由 `$ai-auto-test-platform-business-ui-ux` 定义，UI_HIGH时由 `ui_ux_reviewer` 做独立只读体验审查。

## 验证前

优先消费：

- Task Context Pack；
- UI_MEDIUM/UI_HIGH 的 Business UX Spec；
- 当前改动页面/组件；
- 已知测试账号/权限态和验证路径。

不要重新通读完整业务基线。

## BASELINE_CAPTURE 模式（UI_HIGH 现有页面改造前）

在任何重设计代码写入前，以只读方式记录当前页面真实表现：

1. 使用固定常用桌面 viewport；
2. 记录首屏、核心业务状态、主要操作入口；
3. 记录现有 Loading/Error/Forbidden/Conflict 等与任务相关状态；
4. 记录 Console/Network 明显异常；
5. 输出 `PRE_CHANGE_BASELINE = CAPTURED` 与紧凑截图/路径索引。

不得在该模式修改页面。新页面输出 `PRE_CHANGE_BASELINE = NOT_APPLICABLE_NEW_PAGE`。该证据供 `business_ui_ux_designer` 和最终 `ui_ux_reviewer` 使用，不要求像素级 diff。

若真实 Before 因环境条件无法取得，输出 `PRE_CHANGE_BASELINE = BLOCKED_BY_ENVIRONMENT`，并记录具体阻断原因。此时不得伪造 screenshot；上游可退化到 `SOURCE_BASED_CURRENT_UI_BASELINE`，同时标记 `VISUAL_BASELINE_CONFIDENCE = LIMITED` 和 `POST_CHANGE_BROWSER_VERIFY = REQUIRED`。环境恢复后，Post-change Browser Verify 仍为强制验证债务。


## 检查清单

- 页面能进入且无明显布局溢出/遮挡；
- 表格、表单、Dialog/Drawer、分栏、分页、筛选、危险动作可操作；
- Loading / Empty / Error / Forbidden / Disabled / Conflict / Running / Partial Failure 状态有用户可理解、可行动反馈；
- Console 无未处理错误；Network 无被忽略的失败请求；
- 认证过期、401/403、强制改密、登出后的路由和缓存处理正确；
- 前端隐藏权限不替代后端授权；
- 关键状态标签来自正式枚举，不自行发明；
- 关键首屏信息和主操作与 Business UX Spec 一致；
- 不因视觉实现导致核心表格/状态/证据在常见桌面宽度不可见；
- 测试使用 mock 时明确标记为组件测试，不得声称真实业务闭环通过。

## POST_CHANGE_VERIFY 模式

实现完成后按下述检查执行真实交互验证。现有页面重设计应尽量复用 BASELINE_CAPTURE 的 viewport、关键状态与路径，形成业务级 Before/After 对比。

## UI_HIGH证据

至少保留/报告：

- 主工作台首屏；
- 一个关键操作路径；
- 一个异常/失败/权限/冲突状态（按任务相关性选择）；
- Console/Network结论；
- 与Business UX Spec不一致的地方。

## 结果

输出实际验证路径、关键交互、发现的问题和已修复项。正式发布验收仍需对应 acceptance evidence，浏览器 smoke 不得冒充 1691 项验收通过。
