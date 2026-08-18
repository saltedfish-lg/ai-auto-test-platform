# GovernanceLite integration snippet

Merge this section into the target repository's existing `AGENTS.md`; do not replace project-specific instructions.

## Canonical task lifecycle

For governed implementation work, use the GovernanceLite task lifecycle as the mechanical success path:

1. Start with `python tools/governance/task_governance.py start ...`. This is the single Task Start entry: it captures a local Workspace Baseline, then performs the one Full Impact Scan. Git changed-files are not a Governance input.
2. Consume the shared Task Context produced under `.tmp/agent-governance/<task-id>/`.
3. Product Sovereignty: if `product_decision_status=REQUIRED`, stop implementation closure. A user must resolve it through `resolve-product-decision`; agents and reviewers must not invent the product rule.
4. Implement within the current Task Context. If new impact is discovered, use Incremental Closure; do not run another Full Repository Scan.
5. Use the existing Feature Orchestrator / routing metadata to load only relevant Authorities, Gates, and risk-triggered Reviewers.
6. Run `task_governance.py gate`. It performs Final Reconciliation first and then Required Gates.
7. Treat Gate PASS as valid only for the recorded current workspace state. Any later affected-file change requires the necessary gates to run again.
8. `SUCCESS` / `COMPLETED` finish is allowed only when Final Reconciliation is current, Product Decision is not blocked, every Required Gate has a current PASS result, and no required result is missing.
9. Git is user-owned and optional. Workspace Baseline/Task Context/Gate Results determine Governance. Git may be read only through optional diagnostics after or alongside review; Git absence/failure never blocks the task. Agents must not automatically add, commit, push, reset, checkout, switch, merge, rebase, stash, tag, cherry-pick, or clean.
10. One physical workspace permits only one coding writer task. Writer start must acquire the atomic Workspace Writer Lock; readonly reviewers may coexist. A second writer is blocked with `WORKSPACE_WRITER_BUSY`.

Canonical flow: `Task Start → Workspace Baseline → Single Full Impact Scan → Shared Task Context → Product Sovereignty → Implementation → Workspace Change Detection → Incremental Closure → Final Reconciliation → Required Gates → Workspace Digest Freshness → SUCCESS → Optional Git Read-only Review Summary → User Git Commit`.

Generic Runtime contains no project business rules. Define project Domains, Authorities, Gates, Reviewers, Technology, and Policies in `.governance/` and project Authority files.
## Governance contract test naming

Governance regression tests use stable capability names such as `test_governance_required_gates.py`. Do not keep release-version, Final, Fixed, or Closure labels as long-term test file/function version tags. Temporary reproduction tests must be migrated to capability-named tests before task completion. `governance_contract_test` auto-discovers the stable Governance suite; do not maintain a manual release-file list.


Directory roles: `.governance/ = Project Governance Profile / Rules`, `.agents/skills/ = Skills / How`, `.codex/agents/ = Agent Definitions / Who`. The legacy `.agent/` profile directory is deprecated and must not coexist with `.governance/`.
