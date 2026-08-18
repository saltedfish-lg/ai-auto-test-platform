---
name: code-quality
description: Language/framework-aware quality workflow scoped to the current Task affected files.
---

# Code Quality

## Lightweight self-check
All implementation work gets a small correctness/readability/error-handling/test sanity check. Full review remains risk-triggered.

## Task Code Quality Gate
The executable gate reads the current Task Context and checks the actual `affected_files`. It is distinct from Governance Contract Tests, which only validate the governance runtime itself.

Language/framework behavior is selected through `.governance/technology.yaml`. Built-in lightweight checks may be combined with project-defined commands. No language, framework, repository path, or application-specific rule is hardcoded in this Skill.

## Risk-triggered review
`code_quality_reviewer` may use the generic lanes in `references/review-lanes.md` and the UI-specific checklist in `references/business-ui-review.md` when the current Task Context calls for them.
