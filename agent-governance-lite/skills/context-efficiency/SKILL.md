---
name: context-efficiency
description: Load the minimum relevant context first, then expand precisely until coding facts are sufficient; reuse unchanged reads.
---

# Context Efficiency / Adaptive Context Loading

1. Read only the minimal AGENTS / Governance Profile required to start the Task.
2. Run `task_governance start` first. Consume its one Impact Scan and Task Context; do not perform another full-repository scan.
3. Prefer `authority_refs` and the initial precise `authority_slice`, but treat them as locators, not loaded facts. Required facts are the union of explicit strong-anchor facts, generic relationship-closure facts, and at least one high-relevance concrete fact from every routed core Authority. Generic/domain relevance alone is only a weak candidate and must not invent a concrete anchor for a broad task.
4. `CONTEXT_SUFFICIENT` is valid only after every routed core Authority has required-fact coverage and every `required_authority_ref` has a matching full-record read in Task `context_history` (consumer/epoch + path + selector + current SHA). Relationship closure only proves the relationship path is resolved; it does not prove the facts were loaded. If a new consumer/epoch resumes the Task, previous loaded facts are not assumed to remain in that consumer unless reloaded; when no consumer/epoch is supplied the runtime explicitly operates under `SINGLE_CONTINUOUS_CONTEXT_CONSUMER_ASSUMPTION`.
5. Never stop necessary reads because of a character/token quota. Initial record counts and result limits are per-call loading batches, not Task caps.
6. For an Authority ref use `python -m tools.context.authority_query --root . --id <ID> --expand --task-id <TASK_ID>`. Repeating an unchanged path+selector+sha reuses Task read history; use `--force-expand` only when a deliberate reread/larger context is required.
7. Project source/test/tool context with `python -m tools.context.context_record ...`; unchanged locator+scope+sha is reused. Tool output uses diagnostic-preserving projection (head + errors/failures + tail) first and can expand to raw without `force`; `force` is only for rereading already-full unchanged content.
8. `CONTEXT_UNAVAILABLE` means a required fact is genuinely missing/unreadable; stop guessing and report the missing fact.
9. Repo Intelligence remains code-location assistance only. It cannot read Authority/Secrets or override Governance facts.
10. Preserve complete raw logs/artifacts outside model context when useful; only the model-facing representation should be projected/deduplicated. Source-code `symbol-first` and test `relevant-first` are Agent/tool guidance in Phase 1; the Runtime does not claim automatic AST/LSP symbol slicing or automatic relevant-test extraction.
