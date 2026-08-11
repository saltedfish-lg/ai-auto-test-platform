"""Synchronous append-only P1 authentication audit boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from platform_api.middleware import canonicalize_correlation_id
from platform_api.models import AuthSecurityAudit
from platform_api.security import new_ulid, utc_now

AuthenticationAuditAction = Literal[
    "LOGIN_SUCCEEDED",
    "LOGIN_FAILED",
    "REFRESH_SUCCEEDED",
    "REFRESH_FAILED",
    "LOGOUT",
    "PASSWORD_CHANGED",
    "CREDENTIAL_RESET",
    "SESSION_REVOKED",
    "USER_DISABLED_OR_LOCKED",
    "ROLE_ASSIGNED",
    "PERMISSION_DENIED",
]


@dataclass(frozen=True, slots=True)
class AuditContext:
    correlation_id: str
    source_context: str
    actor_id: str | None = None
    project_id: str | None = None

    def __post_init__(self) -> None:
        # 即使非 HTTP 调用方误传凭据形态, 审计边界也不会持久化原始秘密值.
        object.__setattr__(
            self,
            "correlation_id",
            canonicalize_correlation_id(self.correlation_id),
        )


class AuditContextProvider(Protocol):
    def current(self) -> AuditContext:
        """Return the audit context for the active command or request."""


class AuthenticationAuditService:
    """Append structured audit rows to the caller-owned SQLAlchemy transaction."""

    def append(
        self,
        db: Session,
        context: AuditContext,
        *,
        action: AuthenticationAuditAction,
        operation_id: str,
        result_code: str,
        actor_id: str | None = None,
        target_user_id: str | None = None,
        session_id: str | None = None,
    ) -> AuthSecurityAudit:
        if not 1 <= len(operation_id) <= 128:
            raise ValueError("audit operation id length must be between 1 and 128")
        if not 1 <= len(result_code) <= 64:
            raise ValueError("audit result code length must be between 1 and 64")
        row = AuthSecurityAudit(
            audit_id=new_ulid(),
            action=action,
            operation_id=operation_id,
            actor_id=actor_id,
            target_user_id=target_user_id,
            session_id=session_id,
            result_code=result_code,
            correlation_id=context.correlation_id,
            occurred_at=utc_now(),
            source_context_hash=hashlib.sha256(context.source_context.encode("utf-8")).digest(),
        )
        db.add(row)
        return row
