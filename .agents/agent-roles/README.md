# Agent Role Cards

这些文件保留为人类可读角色规范与兼容回退说明。Codex 原生项目级 Custom Agents 已注册在：

```text
.codex/agents/*.toml
```

对应关系：

- `frontend-implementer.md` → `frontend_implementer`
- `backend-implementer.md` → `backend_implementer`
- `contract-guardian.md` → `contract_guardian`
- `database-integrity-reviewer.md` → `database_integrity_reviewer`
- `security-rbac-reviewer.md` → `security_rbac_reviewer`
- `ui-verifier.md` → `ui_verifier`
- `independent-code-reviewer.md` → `independent_code_reviewer`

支持 subagent 时，优先调用 `.codex/agents` 中的原生 Agent；不支持时，由主 Agent 按这些 Role Card 与对应 Skill 串行执行。
