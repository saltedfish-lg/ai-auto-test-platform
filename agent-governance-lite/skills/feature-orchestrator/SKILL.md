---
name: feature-orchestrator
description: Generic software-task orchestration using Project Profile routing, incremental closure, reconciliation, gates, and risk-triggered review.
---

# Feature Orchestrator

## Standard flow
`Task Start → Workspace Baseline → Load Project Profile → Full Impact Scan → Product Decision Check → default_coder → Workspace Change Detection → Incremental Closure → Final Workspace Reconciliation → Required Gates → Workspace Digest Freshness → Risk-triggered Reviewers → SUCCESS Finish → Optional Git Read-only Review Summary`

## Rules
- Domain, Authority, Gate, Reviewer, language, and framework routing comes from `.governance/` Project Profile and project-owned Authority; the Skill does not embed application-specific paths or business rules.
- Scope expansion happens before metadata finalization. Any MODULE/REPOSITORY expansion is followed by metadata recomputation from the final affected-file set.
- `default_coder` handles ordinary implementation. Reviewers are invoked only when Task Context risk triggers require them.
- Authority editing uses the local single-writer lock. The lock is a lightweight file mutex, not a distributed-consensus mechanism.
- Final Workspace Reconciliation is a mechanical prerequisite for Required Gates. Prefer `task_governance.py gate`, which reconciles first; direct Gate Runner calls are blocked with `FINAL_RECONCILIATION_REQUIRED` when the reconciliation is missing or stale.
- `PRODUCT_DECISION_REQUIRED` is a mechanical block: Gate execution and SUCCESS/COMPLETED Finish remain blocked until an explicit user resolution records `product_decision_status=RESOLVED`.
- Required Gates must execute for the current Task. Every required Gate needs a current PASS result; missing/failed results block SUCCESS. Gate results are bound to the current affected-file workspace digest, so later content/add/delete changes invalidate the old PASS.
- A project with no configured Gate is blocked by default with `NO_CONFIGURED_GATE`; only an explicit Project Profile `runtime.allow_no_gates: true` permits zero-Gate operation. `NO_AUTHORITY_CONFIGURED` is also reported explicitly rather than replaced by invented product rules.
- Workspace Baseline and Task Context are authoritative for Task changes; Gate Freshness uses affected-file content digest only. Git is an optional read-only review adapter and never a routing/closure/success dependency; all Git writes remain user-owned.
