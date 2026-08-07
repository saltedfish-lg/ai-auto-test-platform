# AGENTS.md — AI自动化测试执行平台 R4.2

## 当前发布

- release_id: `PDBR-2026.08.07-R4.2`
- release_status: `P1_AUTHENTICATION_CONTRACT_COMPLETED`
- code_readiness: `READY_FOR_P1_IMPLEMENTATION`
- implementation_release_readiness: `NOT_EVALUATED_IMPLEMENTATION_NOT_PRESENT`
- pending_user_decisions: `0`

Codex可以基于R4.2恢复P1“身份认证 + 默认admin + RBAC”编码。MySQL 8.4空库安装和R4.1升级门禁已通过；1691项验收规范仍保持`SPECIFIED/NOT_STARTED`，不得把治理或Migration验证冒充平台业务验收。

## 按职责域确定权威

1. Release/Manifest只负责当前发布身份、成员、版本、状态和哈希，不改写业务语义。
2. 六份核心YAML负责产品范围、角色场景、对象规则、权限并发、AI/Runner和安全验收业务语义。
3. SYSTEM_DESIGN及DDL、OpenAPI、事件、状态Owner、权限与验收契约负责技术和物理实现，必须服从核心YAML。
4. ADR负责决策和理由；只有同步核心YAML及工程契约后才成为当前实施依据。
5. AGENTS和Skill负责Codex流程、边界和门禁，不得自行改变产品或工程契约。
6. 导航Markdown、DOCX和图形为非权威投影。

权威模型ID：`AUTHORITY-MODEL-R4.2-001`。

## P1认证编码强制规则

- 必须使用`编码冻结基线/AUTHENTICATION_CONTRACT/authentication-contract.yaml`、正式OpenAPI和V5 Migration。
- 不得自创认证Operation、DTO、状态、Cookie、Token或密码政策。
- admin初始化只能使用无回显TTY输入或`ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE`；不得写死、输出或记录密码。
- Access Token不得持久化到Browser存储；Refresh Token不得进入JSON、数据库原值、日志或仓库。
- 权限不得写入JWT作为长期授权事实；每个受保护请求按数据库当前关系实时授权。
- 不得使用`if username == "admin"`绕过正式`ROLE-SUPER-ADMIN` Mapping。
- Migration顺序固定为V3 → V4 → V5；admin初始化在Migration和RBAC Seed之后独立执行。

## 门禁范围

- `MYSQL84_EMPTY_DATABASE_EXECUTION`: `PASS`。
- `REAL_ACCEPTANCE_EVIDENCE`: `IMPLEMENTATION_RELEASE_READINESS`。
- 两项均不阻断工程初始化。

## 当前基线与 Codex 执行层

- `docs/baseline/CURRENT` 必须指向 `R4.2`；活动工具从 CURRENT 解析冻结版本。
- `docs/baseline/R4.1/**` 是历史父基线，只用于溯源和 R4.1→R4.2 升级验证。
- `docs/baseline/R4.2/**` 是只读正式契约；其中打包的 `核心CodexSkill` 属于发布制品，不作为本地运行时 Skill 注册位置。
- 本地运行时 Skill 只使用 `.agents/skills/**`；不得用冻结包内历史 reference 覆盖活动 Skill 与当前 Release。

## Git操作限制

本项目的Git版本管理由用户负责。除非用户在**当前任务中明确授权具体Git操作**，Codex及其所有Custom Agent、Skill不得执行任何会改变Git仓库状态、分支、提交历史、标签、暂存区或远程仓库的Git写操作。

默认禁止包括但不限于：

- `git add`
- `git commit`
- `git push`
- `git pull`
- `git fetch`（除非当前任务明确授权）
- `git checkout`
- `git switch`
- `git branch` 的创建、删除或修改
- `git merge`
- `git rebase`
- `git reset`
- `git revert`
- `git cherry-pick`
- `git stash`
- `git tag` 的创建、删除或修改
- `git remote` 的新增、删除或修改
- 创建或提交Pull Request / Merge Request
- 修改、删除或重建 `.git/**`
- 任何等价的Git历史重写、分支切换、暂存或远程写入行为

仅在只读诊断确有必要时允许使用不会改变仓库状态的命令，例如：

- `git status`
- `git diff`
- `git log`
- `git show`

即使Git仓库存在，Codex也不得因为完成编码任务而自动建分支、暂存、提交、推送或创建PR。若任务需要Git写操作，必须先取得用户在当前任务中的明确授权，并仅执行被授权的具体操作。

## 项目级 Custom Agents

Codex 项目级原生 Agent 位于 `.codex/agents/*.toml`。跨前后端任务由 `$ai-auto-test-platform-feature-orchestrator` 编排，优先使用：

- `contract_guardian`
- `backend_implementer`
- `database_integrity_reviewer`
- `security_rbac_reviewer`
- `frontend_implementer`
- `ui_verifier`
- `independent_code_reviewer`

只读审查 Agent 不得修改工作区；实现 Agent 必须遵循根 AGENTS、对应 Skill 和 R4.2 正式契约。`.agents/agent-roles/**` 仅为角色文档/兼容回退。
