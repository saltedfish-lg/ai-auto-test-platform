"""Replaceable clocks, identifiers, and a generic immutable value object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from platform_domain.errors import InvariantViolation


class Clock(Protocol):
    def now(self) -> datetime:
        """Return an aware UTC timestamp."""


class IdGenerator(Protocol):
    def new_id(self) -> str:
        """Return a new opaque identifier."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UuidGenerator:
    def new_id(self) -> str:
        return str(uuid4())


@dataclass(frozen=True, slots=True)
class NonBlankText:
    """Generic immutable text primitive; it carries no platform business semantics."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise InvariantViolation("text must not be blank")
        object.__setattr__(self, "value", normalized)
