# Generic Review Lanes

Use only lanes relevant to the changed files and risk profile:
- Structure: boundaries, dependency direction, unnecessary coupling, complexity.
- Shortcut/Hack: hidden bypasses, duplicated logic, brittle constants, swallowed errors.
- Regression: compatibility, failure paths, state transitions, concurrency, rollback/recovery.
- Testing: changed behavior has proportionate tests and negative cases.
- Readability: names, comments explaining non-obvious reasons, maintainable control flow.
- Security-sensitive: only when the project profile marks the task as security-sensitive.
