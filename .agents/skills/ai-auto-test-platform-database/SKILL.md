---
name: ai-auto-test-platform-database
description: AI自动化测试执行平台 MySQL 8.4、当前 authority DDL、SQLAlchemy映射、事务、约束、索引与Migration执行Skill。
---

# Database & Persistence

## 当前事实

- 正式数据库：MySQL 8.4；
- 当前 authority P1 顺序：V3 → V4 → V5；
- V3/V4/V5 位于 `docs/authority/编码权威事实/DATABASE_DDL/`，当前事实受产品主权控制；不得未经裁决改变语义；
- admin bootstrap 在 Migration + RBAC Seed 之后独立执行；
- 不允许用 extension JSON 承载正式契约字段。

## 编码规则

- SQLAlchemy 映射服从当前 authority DDL；
- DB 唯一键/FK/CHECK/row version 要真实生效；
- 事务边界服从业务原子性；
- P1 已有 V5 时不得再自创一套认证表；
- 索引、批量查询、Repository 组织等纯工程优化可自主决定，但不能改变当前唯一性、生命周期、并发语义；
- 不运行破坏性数据库命令，除非任务明确授权并确认目标是可丢弃的开发/测试数据库。

## 验证

静态验证和真实 MySQL 验证分开报告。没有真实 MySQL 证据时不得声称数据库业务验收通过。
