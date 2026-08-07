"""Business-neutral domain exception hierarchy."""


class DomainError(Exception):
    """Base class for deterministic domain failures."""


class InvariantViolation(DomainError):
    """Raised when a value violates a declared invariant."""
