---
name: product-sovereignty
description: Protect project-owned product decisions from being silently invented or changed by implementation agents.
---

# Product Sovereignty

## Principle
Existing project Authority outranks Agent inference. Concrete product facts are loaded from the current project's Authority/Profile and are not embedded in this Skill.

## Required behavior
1. If the task only restores an already-decided rule, performs equivalent refactoring, or adds tests, return `PRODUCT_DECISION_NOT_REQUIRED`.
2. If implementation would add, delete, relax, tighten, or otherwise change an authoritative product rule, return `PRODUCT_DECISION_REQUIRED` and surface the current fact, proposed difference, impact, and decision needed. Runtime must mechanically block Required Gates and SUCCESS/COMPLETED while this status remains REQUIRED.
3. If Authority is missing or contradictory, keep `PRODUCT_SOVEREIGNTY_REVIEW_REQUIRED`; do not invent a key product rule.
4. Only an explicit user decision may move a REQUIRED decision to RESOLVED. Reviewer, Coder, test PASS, or missing Authority must never auto-resolve it.

The routing categories are generic; project-specific product facts stay outside the Skill.
