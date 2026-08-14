"""Refresh-session lifecycle owner for P1 authentication flows."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.audit import AuditContext, AuthenticationAuditService
from platform_api.models import AuthRefreshSession, PlatformUserCredential
from platform_api.security import (
    client_context_hash,
    new_refresh_token,
    new_ulid,
    refresh_token_hash,
    utc_now,
)

ACTIVE = "ACTIVE"


class SessionService:
    """Own every refresh-session lifecycle mutation inside caller-owned transactions."""

    def __init__(self, audit: AuthenticationAuditService) -> None:
        self._audit = audit

    def create(
        self,
        db: Session,
        credential: PlatformUserCredential,
        audit_context: AuditContext,
        family_id: str | None,
        operation_id: str,
        actor_id: str,
        *,
        expires_at: datetime | None = None,
        enforce_limit: bool = True,
    ) -> tuple[AuthRefreshSession, str]:
        """创建会话时先串行清理过期项并执行数量上限, 避免并发登录突破五会话约束。"""
        now = utc_now()
        if enforce_limit:
            active = list(
                db.scalars(
                    select(AuthRefreshSession)
                    .where(
                        AuthRefreshSession.credential_id == credential.credential_id,
                        AuthRefreshSession.lifecycle_status == ACTIVE,
                    )
                    .order_by(AuthRefreshSession.issued_at)
                    .with_for_update()
                )
            )
            unexpired: list[AuthRefreshSession] = []
            for candidate in active:
                if candidate.expires_at <= now:
                    self._mark_expired(candidate, now)
                else:
                    unexpired.append(candidate)
            while len(unexpired) >= 5:
                oldest = unexpired.pop(0)
                self.revoke(
                    db,
                    oldest,
                    "SESSION_LIMIT",
                    now,
                    audit_context,
                    actor_id=actor_id,
                    target_user_id=credential.user_id,
                    operation_id=operation_id,
                )

        raw_token = new_refresh_token()
        session_id = new_ulid()
        refresh_session = AuthRefreshSession(
            session_id=session_id,
            credential_id=credential.credential_id,
            family_id=family_id or session_id,
            token_hash=refresh_token_hash(raw_token),
            session_version=1,
            credential_version=credential.credential_version,
            lifecycle_status=ACTIVE,
            issued_at=now,
            expires_at=expires_at or now + timedelta(seconds=604800),
            last_used_at=None,
            rotated_at=None,
            revoked_at=None,
            revoke_reason=None,
            replaced_by_session_id=None,
            client_context_hash=client_context_hash(audit_context.source_context),
            row_version=0,
            created_at=now,
            updated_at=now,
        )
        db.add(refresh_session)
        return refresh_session, raw_token

    def rotate(
        self,
        db: Session,
        current: AuthRefreshSession,
        credential: PlatformUserCredential,
        audit_context: AuditContext,
        *,
        actor_id: str,
        operation_id: str,
        now: datetime,
    ) -> tuple[AuthRefreshSession, str]:
        """旋转必须在旧会话行锁所在事务内创建替代项并建立单向替代关系。"""
        replacement, raw_token = self.create(
            db,
            credential,
            audit_context,
            family_id=current.family_id,
            operation_id=operation_id,
            actor_id=actor_id,
            expires_at=current.expires_at,
            enforce_limit=False,
        )
        # 自引用外键要求替代会话先物化, 之后才能把旧会话指向它。
        db.flush()
        current.lifecycle_status = "ROTATED"
        current.last_used_at = now
        current.rotated_at = now
        current.replaced_by_session_id = replacement.session_id
        current.row_version += 1
        return replacement, raw_token

    def expire_if_due(
        self,
        db: Session,
        refresh_session: AuthRefreshSession,
        now: datetime,
        audit_context: AuditContext,
        *,
        actor_id: str,
        operation_id: str,
    ) -> bool:
        """仅活动且已到期的会话发生 EXPIRED 转换, 确保并发请求不重复递增或审计。"""
        if refresh_session.lifecycle_status != ACTIVE or refresh_session.expires_at > now:
            return False
        self._mark_expired(refresh_session, now)
        self._audit.append(
            db,
            audit_context,
            action="SESSION_REVOKED",
            operation_id=operation_id,
            result_code="EXPIRED",
            actor_id=actor_id,
            target_user_id=actor_id,
            session_id=refresh_session.session_id,
        )
        return True

    def compromise_family(
        self,
        db: Session,
        family_id: str,
        now: datetime,
        audit_context: AuditContext,
        *,
        actor_id: str,
        operation_id: str,
    ) -> None:
        """检测刷新令牌重放后锁定并失陷整个家族, 避免同族替代令牌继续使用。"""
        sessions = list(
            db.scalars(
                select(AuthRefreshSession)
                .where(AuthRefreshSession.family_id == family_id)
                .order_by(AuthRefreshSession.session_id)
                .with_for_update()
            )
        )
        for refresh_session in sessions:
            refresh_session.lifecycle_status = "COMPROMISED"
            refresh_session.revoked_at = now
            refresh_session.revoke_reason = "REFRESH_REPLAY"
            refresh_session.row_version += 1
            self._audit.append(
                db,
                audit_context,
                action="SESSION_REVOKED",
                operation_id=operation_id,
                result_code="REFRESH_REPLAY",
                actor_id=actor_id,
                target_user_id=actor_id,
                session_id=refresh_session.session_id,
            )

    def revoke_active_for_credential(
        self,
        db: Session,
        credential: PlatformUserCredential,
        reason: str,
        now: datetime,
        audit_context: AuditContext,
        *,
        actor_id: str | None,
        operation_id: str,
    ) -> None:
        """安全敏感变更按固定顺序锁定并撤销全部活动会话, 防止旧凭据继续生效。"""
        sessions = list(
            db.scalars(
                select(AuthRefreshSession)
                .where(
                    AuthRefreshSession.credential_id == credential.credential_id,
                    AuthRefreshSession.lifecycle_status == ACTIVE,
                )
                .order_by(AuthRefreshSession.session_id)
                .with_for_update()
            )
        )
        for refresh_session in sessions:
            self.revoke(
                db,
                refresh_session,
                reason,
                now,
                audit_context,
                actor_id=actor_id,
                target_user_id=credential.user_id,
                operation_id=operation_id,
            )

    def revoke(
        self,
        db: Session,
        refresh_session: AuthRefreshSession,
        reason: str,
        now: datetime,
        audit_context: AuditContext,
        *,
        actor_id: str | None,
        target_user_id: str | None,
        operation_id: str,
    ) -> bool:
        """活动会话只转换一次; 重复撤销保持原终态且不重复 SESSION_REVOKED 审计。"""
        if refresh_session.lifecycle_status != ACTIVE:
            return False
        refresh_session.lifecycle_status = "REVOKED"
        refresh_session.revoked_at = now
        refresh_session.revoke_reason = reason
        refresh_session.row_version += 1
        self._audit.append(
            db,
            audit_context,
            action="SESSION_REVOKED",
            operation_id=operation_id,
            result_code=reason,
            actor_id=actor_id,
            target_user_id=target_user_id,
            session_id=refresh_session.session_id,
        )
        return True

    @staticmethod
    def _mark_expired(refresh_session: AuthRefreshSession, now: datetime) -> None:
        refresh_session.lifecycle_status = "EXPIRED"
        refresh_session.row_version += 1
        refresh_session.updated_at = now
