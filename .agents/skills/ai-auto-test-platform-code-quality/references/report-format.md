# Code Quality Review Report

按严重度输出，不需要为了凑数量制造finding。

每项格式：

```text
Q-001 [P1|P2|P3] [Lane]
位置: path:line 或 symbol
证据: ...
问题: ...
影响: ...
修复方向: ...
复查: ...
```

最后给出：

- Reviewed scope；
- 各Lane覆盖情况；
- Not covered / blind spots；
- 是否存在需要路由到Contract/Security/Database/UI Reviewer的问题；
- `CODE_QUALITY_GATE = PASS | PASS_WITH_P2_P3 | FAIL`。

P1表示会显著损害正确维护、造成高概率回归或依赖脆弱捷径；P2表示重要可维护性/测试缺口；P3表示低风险局部质量问题。纯风格偏好不应成为finding。
