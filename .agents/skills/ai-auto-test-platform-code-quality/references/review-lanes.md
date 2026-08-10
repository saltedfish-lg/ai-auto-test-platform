# Review Lanes

## Structure / Thermo

- 先识别canonical owner，再判断是否存在职责漂移或重复owner。
- 约350行的维护源文件只触发职责、依赖、耦合、ownership深查；不得因行数本身判错。
- 重点识别God Service/Component、无收益转发层、跨层依赖、隐式全局状态和难以测试的耦合。

## Hack / Shortcut

重点寻找：

- `except Exception: pass`、裸catch或返回空值掩盖失败；
- fallback掩盖不变量破坏；
- 硬编码用户/角色/权限/状态；
- 绕过正式Repository/Service边界；
- 平行重复DTO、状态或授权模型；
- test-only分支进入生产逻辑；
- `sleep`/无界retry掩盖竞态或同步缺陷；
- 没有退出条件的“临时兼容”。

必要的边界guard、受控降级和正式兼容策略不是自动缺陷，必须结合契约和调用链判断。

## Regression

对受影响表面建立最小行为链：

`输入 → guard → 状态/数据变化 → 外部效果 → 错误处理 → 用户可见结果`

比较改动前后的默认值、顺序、Loading/Error/Forbidden、Retry/Refresh/Logout、重复提交、刷新恢复和导出/返回结果。

## Testing

- 重大逻辑或用户行为变化必须有测试。
- 跨层行为优先contract/integration/E2E；unit test用于局部纯逻辑。
- 避免为了测试在生产代码中增加test-only接口。
- 测试必须覆盖关键失败路径、边界值和回归行为，而非只验证内部实现步骤。

## Comments / Readability

- 注释优先解释原因、不变量、状态影响和框架限制。
- 避免“给变量赋值”“调用接口”之类机械注释。
- 注释和代码冲突时，注释本身是缺陷。

## Maintainability

检查命名、复杂条件、重复逻辑、异常语义、资源生命周期、潜在N+1/重复请求、无界集合和长期维护成本。
