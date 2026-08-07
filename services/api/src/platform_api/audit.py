"""Audit context boundary; persistence and business audit rules are not implemented in P0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuditContext:
    correlation_id: str
    actor_id: str | None = None
    project_id: str | None = None


class AuditContextProvider(Protocol):
    def current(self) -> AuditContext:
        """Return the audit context for the active command or request."""
