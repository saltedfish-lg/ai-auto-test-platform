---
name: context-efficiency
description: Build minimal sufficient task context from a Project Profile and project-owned Authority.
---

# Context Efficiency

## Purpose
Select only the files, Authority, dependencies, tests, gates, and reviewers needed by the current task.

## Workflow
1. Read the root project instructions and `.governance/` Project Profile when present.
2. Start a task through `python tools/governance/task_governance.py start --root . --task-id <id> --request <text>`.
3. Treat `impact_scan.py` as an internal implementation/Contract Test helper, not the formal Agent entrypoint（内部实现/Contract Test 辅助入口）.
4. Reuse `.tmp/agent-governance/<task-id>/context.json` for all agents and reviewers in the task.
5. When a new dependency or affected file is discovered, use Incremental Closure. Unknown local impact expands to module scope; unresolved module impact expands to repository scope.
6. Before gates and review, complete Final Reconciliation. Prefer `task_governance.py gate` for the success path because it reconciles first and then invokes Required Gates; direct Gate Runner use is mechanically blocked until reconciliation is current.
7. If Product Decision is REQUIRED, stop formal closure until the user explicitly resolves it. SUCCESS also requires all Required Gates to have current PASS results whose workspace digest still matches the affected files.

Task Context is temporary engineering state, not product Authority. It is deleted at task finish.
