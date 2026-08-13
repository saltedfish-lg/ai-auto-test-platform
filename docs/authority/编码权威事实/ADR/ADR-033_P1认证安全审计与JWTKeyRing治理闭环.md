# ADR-033：P1认证安全审计与JWT Key Ring治理闭环

## 状态

ACCEPTED / CURRENT LIVING AUTHORITY

## 决策范围

本ADR仅承接已经确认并已经实现的两个P1治理决策：

- `GOV-P1-001`：认证安全审计使用独立结构化、append-only技术表 `atp_auth_security_audit`。
- `GOV-P1-004`：Access JWT使用 `ATP_JWT_KEY_RING_FILE` 加载JWT Key Ring，支持单一active signing key与previous verification keys的安全轮换。

本ADR形成时尚未裁决的`GOV-P1-002/003/005`已由用户在后续 Living Authority 任务中确认；其当前事实与架构边界由 Authentication Contract 和`ADR-034`承接。本段仅保留决策演进关系，不再构成待决阻断。

## GOV-P1-001：不可变认证安全审计

1. 新增技术表 `atp_auth_security_audit`，主键 `audit_id`。
2. 必须记录 `action`、`operation_id`、`result_code`、`correlation_id`、`occurred_at`、`source_context_hash`，并按已知上下文记录actor、target user和session标识。
3. 表只允许INSERT；数据库trigger必须拒绝UPDATE与DELETE。
4. 安全敏感状态变更与对应审计必须同事务提交；审计写入失败时业务变更整体回滚。
5. P1认证安全审计不创建新的认证领域Event或Outbox事件。
6. 密码、密码Hash、Access Token、Refresh Token、Cookie、Secret、数据库凭据不得写入审计。

## GOV-P1-004：JWT Key Ring

1. 部署配置使用 `ATP_JWT_KEY_RING_FILE`，不再使用独立的当前私钥/公钥文件作为正式运行契约。
2. Key Ring必须声明唯一 `active_signing_kid`；签名只允许使用active key。
3. previous key可以在受控验证窗口内继续校验旧Access Token。
4. 旧key的验证重叠窗口至少覆盖Access Token TTL 900秒 + clock skew 60秒，即不少于960秒。
5. unknown kid、尚未激活key、超过 `verify_until` 的retired key必须失败关闭。
6. Key Ring清单和私钥材料均属于部署秘密/受控配置，不得进入普通仓库样例或日志。

## 数据库与状态Owner

- Migration链：`V3 -> V4 -> V5 -> V6__p1_auth_governance_closure.sql`。
- 本ADR落地时表总数为85；后续V7新增来源限流技术表后的当前数量由 Database Schema 与 SYSTEM_DESIGN 维护。
- 本ADR新增 `AUTH-STATE-007 / AUTH_SECURITY_AUDIT_IMMUTABILITY`；后续状态Owner扩展由 State Owner Registry 与`ADR-034`维护。

## 一致性要求

当前实现、Authentication Contract、SYSTEM_DESIGN、DATABASE_DDL、STATE_OWNER_REGISTRY和P1实施追踪必须使用上述相同事实。历史R4.2/R4.3 Candidate仅可作为provenance，不得作为当前活动事实源。
