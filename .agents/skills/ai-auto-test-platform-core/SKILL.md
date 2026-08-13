---
name: ai-auto-test-platform-core
description: AI自动化测试执行平台Single Living Authority下的核心编码规则。
---

# 核心编码 Skill

当前权威模型：`AUTHORITY-MODEL-LIVING-001 / SINGLE_LIVING_AUTHORITY`。

- 唯一活动事实源：`docs/authority/**`；
- Codex 不创建 按历史发布号复制的整套 Authority 目录；
- 当前源文档允许在用户明确要求、既有明确用户裁决或不改变产品语义的一致性修复时受控更新；
- authority 更新后必须运行 validators 并重新 Product Gate；
- Git 历史与提交完全由用户在 IDEA 中管理，Codex `MUST_NOT_INVOKE_GIT`；
- 当前 `code_readiness=READY_FOR_P1_IMPLEMENTATION`，当前平台验收条目（数量由 `tools/current_facts.py` 派生）仍须以真实证据区分 `SPECIFIED` 与 `PASSED`。

P1认证必须读取 `docs/authority/编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml`。必须使用当前 OpenAPI 的 Login/Refresh/Logout/Me/Change Password Operation、V5 平台凭据与 Refresh Session 表、Argon2id 和安全 Bootstrap 输入；不得写死 admin 密码、持久化 Refresh 原值、把权限固化在 JWT 或用用户名绕过 RBAC。

Skill/Agent 负责执行流程，不得未经用户产品裁决改变当前 authority 的产品语义。
