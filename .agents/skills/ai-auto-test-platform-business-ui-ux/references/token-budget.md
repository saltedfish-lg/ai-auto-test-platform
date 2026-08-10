# UI/UX Token Budget

## 默认策略

UI_LOW：不生成独立文档，不启动Designer/Reviewer子Agent。

UI_MEDIUM：生成约10–20行Business UX Spec；优先由frontend_implementer同上下文完成。

UI_HIGH：现有页面先生成紧凑Pre-change Browser Baseline；独立Designer只接收Task Context Pack + 当前页面相关事实 + baseline摘要；Reviewer只接收Business UX Spec + Before/After浏览器证据 + 改动页面/组件 + 关键测试结果。

## 禁止

- Designer和Frontend分别完整通读同一批基线；
- Reviewer重新从零探索整个仓库；
- 为“美化”读取后端所有实现；
- 每个页面都调用独立Designer；
- 为UI审查生成长篇无结论报告。

## 正确性优先

若设计涉及权限、状态、危险动作或跨模块数据语义，必须扩大上下文；Token预算不得压过正确性。
