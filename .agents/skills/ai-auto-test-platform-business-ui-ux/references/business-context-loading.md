# Business Context Loading

UI设计只加载与当前页面相关的业务切片：

1. `用户角色、核心场景与模块菜单.yaml`：当前角色/菜单/场景/操作；
2. `核心对象、业务规则与生命周期.yaml`：当前对象与状态；
3. 权限/并发规则：当前页面动作所需 permission/data scope；
4. 当前 OpenAPI/generated types：页面真实可用字段与操作；
5. 当前 Vue 页面、相邻页面和共享组件；
6. 相关测试/E2E。

不要为了设计一个页面通读全部 43 场景、59 菜单和完整 OpenAPI。

如果页面跨多个核心业务域，先由 Context Efficiency 生成 Task Context Pack，再按需展开。

## UI_HIGH 现有页面额外输入

仅额外加载 `PRE_CHANGE_EVIDENCE` 的截图索引、viewport、关键业务状态和问题摘要；不要把完整 DOM、所有 Network 响应或大量截图 OCR 文本注入 Designer。
