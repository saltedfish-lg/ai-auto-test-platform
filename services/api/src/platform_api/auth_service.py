"""Transactional P1 platform authentication and realtime relational RBAC service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy import Select, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import (
    AuditContext,
    AuthenticationAuditAction,
    AuthenticationAuditService,
)
from platform_api.auth_hmac import AuthHmacKeyRing
from platform_api.auth_schemas import CurrentUserResource
from platform_api.errors import PlatformError
from platform_api.models import (
    AuthRefreshSession,
    DataScopeGrant,
    IdempotencyRecord,
    PermissionCode,
    PlatformUser,
    PlatformUserCredential,
    ProjectMember,
    Role,
    RolePermission,
    UserRoleBinding,
)
from platform_api.rate_limit import AuthenticationRateLimitService
from platform_api.security import (
    AccessClaims,
    JwtService,
    PasswordPolicyError,
    PasswordService,
    client_context_hash,
    new_refresh_token,
    new_ulid,
    refresh_token_hash,
    utc_now,
)

ACTIVE = "ACTIVE"
FROZEN_DATA_SCOPE_TYPES = {
    "PLATFORM_ALL",
    "PLATFORM_TECHNICAL",
    "AUTHORIZED_PROJECT_ACTIVE",
    "AUTHORIZED_PROJECT_HISTORY",
    "SPECIFIED_PROJECT_IDS",
    "DYNAMIC_ALL_PROJECTS",
    "SELF_CREATED",
    "SELF_INITIATED",
    "REPORT_ACTIVE_HISTORY",
    "ARTIFACT_SEPARATE",
    "MANUAL_RECORDING_EVIDENCE",
    "MODEL_TECHNICAL_METADATA",
    "SENSITIVE_FIELD",
    "ARCHIVED_OBJECT_HISTORY",
    "REMOVED_MEMBER_HISTORY",
    "SERVICE_IDENTITY_SCOPE",
    "INTERFACE_SCOPE_PARITY",
    "EXPORT_SCOPE",
}
PROJECT_ID_SCOPE_TYPES = {
    "AUTHORIZED_PROJECT_ACTIVE",
    "AUTHORIZED_PROJECT_HISTORY",
    "SPECIFIED_PROJECT_IDS",
    "REPORT_ACTIVE_HISTORY",
    "REMOVED_MEMBER_HISTORY",
}
GENERIC_RBAC_CONDITION = "仍受数据范围、对象状态和接口鉴权约束"
REVIEW_RBAC_CONDITION = "提交人不得批准本人提交；高风险操作必须审计"  # noqa: RUF001
SUPER_ADMIN_RBAC_CONDITION = (
    "强制二次确认、填写原因、写入不可变审计；不得向其他主体分配SUPER_ADMIN；"  # noqa: RUF001
    "仍执行敏感数据和对象状态校验"
)
AUTH_PATHS_ALLOWED_DURING_PASSWORD_CHANGE = {
    "get_current_user",
    "change_current_user_password",
    "logout_platform_user",
}


def _framed(*values: str) -> bytes:
    encoded = [value.encode("utf-8") for value in values]
    return b"".join(len(value).to_bytes(4, "big") + value for value in encoded)


def _idempotency_conflict() -> PlatformError:
    return PlatformError(
        title="Idempotency key conflict",
        detail="The idempotency key was reused with a different request.",
        status=409,
        code="AUTH_IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST",
    )


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    user: PlatformUser
    credential: PlatformUserCredential
    session: AuthRefreshSession


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    access_token: str
    refresh_token: str
    current_user: CurrentUserResource


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    project_id: str | None
    scope_type: str
    scope_id: str | None
    object_state_allowed: bool


class AuthenticationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        passwords: PasswordService,
        jwt_service: JwtService,
        audit_service: AuthenticationAuditService,
        auth_hmac: AuthHmacKeyRing,
        rate_limits: AuthenticationRateLimitService,
    ) -> None:
        """认证服务统一持有密码、JWT与审计依赖，确保同一业务事务不会绕过既定安全组件。"""
        self._session_factory = session_factory
        self._passwords = passwords
        self._jwt = jwt_service
        self._audit = audit_service
        self._auth_hmac = auth_hmac
        self._rate_limits = rate_limits

    def login(
        self,
        username: str,
        password: str,
        audit_context: AuditContext,
        source_ip: str,
    ) -> AuthenticationResult:
        """登录失败计数、会话创建与安全审计必须共享同一事务，避免部分提交留下可绕过的认证状态。"""
        self._rate_limits.consume("login_platform_user", source_ip, audit_context)
        with self._session_factory() as db:
            user = db.scalar(
                select(PlatformUser).where(PlatformUser.username == username).with_for_update()
            )
            if user is None:
                self._passwords.verify_dummy(password)
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="LOGIN_FAILED",
                    operation_id="login_platform_user",
                    error=self._invalid_credentials(),
                )
            credential = db.scalar(
                select(PlatformUserCredential)
                .where(PlatformUserCredential.user_id == user.user_id)
                .with_for_update()
            )
            if credential is None or credential.lifecycle_status != ACTIVE:
                self._passwords.verify_dummy(password)
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="LOGIN_FAILED",
                    operation_id="login_platform_user",
                    error=self._invalid_credentials(),
                    target_user_id=user.user_id,
                )
            try:
                self._require_login_user_state(
                    user,
                    db,
                    credential,
                    audit_context,
                    "login_platform_user",
                    actor_id=None,
                )
            except PlatformError as error:
                self._audit.append(
                    db,
                    audit_context,
                    action="LOGIN_FAILED",
                    operation_id="login_platform_user",
                    result_code=error.code,
                    target_user_id=user.user_id,
                )
                db.commit()
                raise
            valid_password = self._passwords.verify(credential.password_hash, password)
            now = utc_now()
            temporarily_locked = (
                credential.locked_until is not None and credential.locked_until > now
            )
            if not valid_password:
                if not temporarily_locked:
                    self._record_login_failure(credential, now)
                    if credential.locked_until is not None:
                        self._audit.append(
                            db,
                            audit_context,
                            action="USER_DISABLED_OR_LOCKED",
                            operation_id="login_platform_user",
                            result_code="AUTH_ACCOUNT_TEMPORARILY_LOCKED",
                            target_user_id=user.user_id,
                        )
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="LOGIN_FAILED",
                    operation_id="login_platform_user",
                    error=self._invalid_credentials(),
                    target_user_id=user.user_id,
                )
            if temporarily_locked:
                lock_error = PlatformError(
                    title="Account temporarily locked",
                    detail="The account is temporarily locked.",
                    status=403,
                    code="AUTH_ACCOUNT_TEMPORARILY_LOCKED",
                )
                self._audit.append(
                    db,
                    audit_context,
                    action="USER_DISABLED_OR_LOCKED",
                    operation_id="login_platform_user",
                    result_code=lock_error.code,
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                )
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="LOGIN_FAILED",
                    operation_id="login_platform_user",
                    error=lock_error,
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                )
            if self._passwords.needs_rehash(credential.password_hash):
                credential.password_hash = self._passwords.hash(password)
            credential.failed_login_count = 0
            credential.failure_window_started_at = None
            credential.locked_until = None
            credential.last_failed_at = None
            credential.last_successful_login_at = now
            credential.row_version += 1
            session, refresh_token = self._create_session(
                db,
                credential,
                audit_context,
                family_id=None,
                operation_id="login_platform_user",
                actor_id=user.user_id,
            )
            current_user = self._current_user(db, user, credential)
            self._audit.append(
                db,
                audit_context,
                action="LOGIN_SUCCEEDED",
                operation_id="login_platform_user",
                result_code="SUCCESS",
                actor_id=user.user_id,
                target_user_id=user.user_id,
                session_id=session.session_id,
            )
            db.commit()
        return self._result(
            user.user_id, credential.credential_version, session, refresh_token, current_user
        )

    def authenticate_access(
        self, token: str, operation_id: str, audit_context: AuditContext
    ) -> tuple[AuthenticatedIdentity, CurrentUserResource]:
        """访问令牌校验必须同时绑定凭据版本和会话状态，防止改密或撤销后旧令牌继续生效。"""
        claims = self._jwt.decode(token)
        with self._session_factory() as db:
            try:
                identity = self._load_access_identity(
                    db,
                    claims,
                    audit_context=audit_context,
                    operation_id=operation_id,
                )
            except PlatformError:
                db.commit()
                raise
            if (
                identity.credential.force_password_change
                and operation_id not in AUTH_PATHS_ALLOWED_DURING_PASSWORD_CHANGE
            ):
                raise PlatformError(
                    title="Password change required",
                    detail="The password must be changed before this operation.",
                    status=403,
                    code="AUTH_PASSWORD_CHANGE_REQUIRED",
                )
            current_user = self._current_user(db, identity.user, identity.credential)
            db.expunge(identity.user)
            db.expunge(identity.credential)
            db.expunge(identity.session)
            db.commit()
        return identity, current_user

    def require_permissions(
        self,
        token: str,
        operation_id: str,
        permission_codes: tuple[str, ...],
        audit_context: AuditContext,
    ) -> AuthenticatedIdentity:
        """权限判断统一基于当前关系映射，确保RBAC变更后不会沿用过期授权结果。"""
        identity, current_user = self.authenticate_access(token, operation_id, audit_context)
        if not set(permission_codes).issubset(current_user.permissions):
            self._raise_permission_denied(identity, operation_id, audit_context)
        return identity

    def require_project_permissions(
        self,
        token: str,
        operation_id: str,
        permission_codes: tuple[str, ...],
        project_id: str,
        audit_context: AuditContext,
    ) -> AuthenticatedIdentity:
        """Write authorization must be evaluated against the realtime target project.

        Project-scoped commands must not reuse the aggregate ``/me`` permission projection:
        every required permission is authorized with the target project as both project and
        scope identifier, which reuses the live RoleBinding/DataScopeGrant/ProjectMember
        intersection enforced by :meth:`authorize_access`.
        """
        if not permission_codes:
            raise ValueError("permission_codes must not be empty")
        identity: AuthenticatedIdentity | None = None
        context = AuthorizationContext(
            project_id=project_id,
            scope_type="AUTHORIZED_PROJECT_ACTIVE",
            scope_id=project_id,
            object_state_allowed=True,
        )
        for permission_code in permission_codes:
            identity = self.authorize_access(
                token,
                operation_id,
                permission_code,
                context,
                audit_context,
            )
        assert identity is not None
        return identity

    def refresh(
        self,
        token: str | None,
        audit_context: AuditContext,
        source_ip: str,
    ) -> AuthenticationResult:
        """刷新令牌采用旋转和家族重放检测，异常时必须失效相关会话，避免旧令牌继续换取访问权。"""
        self._rate_limits.consume("refresh_platform_session", source_ip, audit_context)
        with self._session_factory() as db:
            if token is None:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                )
            try:
                token_digest = refresh_token_hash(token)
            except ValueError:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                )
            session_hint = db.scalar(
                select(AuthRefreshSession).where(AuthRefreshSession.token_hash == token_digest)
            )
            if session_hint is None:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                )
            credential_hint = db.get(PlatformUserCredential, session_hint.credential_id)
            if credential_hint is None:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    session_id=session_hint.session_id,
                )
            user = db.scalar(
                select(PlatformUser)
                .where(PlatformUser.user_id == credential_hint.user_id)
                .with_for_update()
            )
            credential = db.scalar(
                select(PlatformUserCredential)
                .where(
                    PlatformUserCredential.credential_id == session_hint.credential_id,
                    PlatformUserCredential.user_id == credential_hint.user_id,
                )
                .with_for_update()
            )
            old = db.scalar(
                select(AuthRefreshSession)
                .where(
                    AuthRefreshSession.session_id == session_hint.session_id,
                    AuthRefreshSession.token_hash == token_digest,
                )
                .with_for_update()
            )
            if user is None or credential is None or old is None:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    target_user_id=credential_hint.user_id,
                    session_id=session_hint.session_id,
                )
            now = utc_now()
            if old.lifecycle_status == "ROTATED":
                self._compromise_family(
                    db,
                    old.family_id,
                    now,
                    audit_context,
                    actor_id=user.user_id,
                    operation_id="refresh_platform_session",
                )
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
            if old.lifecycle_status != ACTIVE:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
            if old.expires_at <= now:
                old.lifecycle_status = "EXPIRED"
                old.row_version += 1
                self._audit.append(
                    db,
                    audit_context,
                    action="SESSION_REVOKED",
                    operation_id="refresh_platform_session",
                    result_code="EXPIRED",
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
            if credential.lifecycle_status != ACTIVE:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
            try:
                self._require_login_user_state(
                    user,
                    db,
                    credential,
                    audit_context,
                    "refresh_platform_session",
                    actor_id=user.user_id,
                )
            except PlatformError as error:
                self._audit.append(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    result_code=error.code,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
                db.commit()
                raise
            if credential.force_password_change:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=PlatformError(
                        title="Password change required",
                        detail="Refresh is unavailable until the password is changed.",
                        status=403,
                        code="AUTH_PASSWORD_CHANGE_REQUIRED",
                    ),
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
            if old.credential_version != credential.credential_version:
                self._raise_audited_failure(
                    db,
                    audit_context,
                    action="REFRESH_FAILED",
                    operation_id="refresh_platform_session",
                    error=self._session_revoked(),
                    actor_id=user.user_id,
                    target_user_id=user.user_id,
                    session_id=old.session_id,
                )
            replacement, refresh_token = self._create_session(
                db,
                credential,
                audit_context,
                family_id=old.family_id,
                operation_id="refresh_platform_session",
                actor_id=user.user_id,
                expires_at=old.expires_at,
                enforce_limit=False,
            )
            db.flush()
            old.lifecycle_status = "ROTATED"
            old.last_used_at = now
            old.rotated_at = now
            old.replaced_by_session_id = replacement.session_id
            old.row_version += 1
            current_user = self._current_user(db, user, credential)
            self._audit.append(
                db,
                audit_context,
                action="REFRESH_SUCCEEDED",
                operation_id="refresh_platform_session",
                result_code="SUCCESS",
                actor_id=user.user_id,
                target_user_id=user.user_id,
                session_id=replacement.session_id,
            )
            db.commit()
        return self._result(
            user.user_id,
            credential.credential_version,
            replacement,
            refresh_token,
            current_user,
        )

    def authorize_access(
        self,
        token: str,
        operation_id: str,
        permission_code: str,
        context: AuthorizationContext,
        audit_context: AuditContext,
    ) -> AuthenticatedIdentity:
        """授权必须实时交叉校验权限、项目成员、数据范围与对象状态，避免单一缓存事实造成越权。"""
        identity, _ = self.authenticate_access(token, operation_id, audit_context)
        if context.scope_type not in FROZEN_DATA_SCOPE_TYPES:
            self._raise_permission_denied(identity, operation_id, audit_context)
        if context.scope_type in PROJECT_ID_SCOPE_TYPES and (
            context.project_id is None or context.scope_id != context.project_id
        ):
            self._raise_permission_denied(identity, operation_id, audit_context)
        allowed = False
        with self._session_factory() as db:
            now = utc_now()
            rows = db.execute(
                select(
                    UserRoleBinding.binding_id,
                    UserRoleBinding.project_id,
                    UserRoleBinding.role_id,
                    Role.role_code,
                    RolePermission.decision,
                    RolePermission.conditions,
                )
                .join(Role, Role.role_id == UserRoleBinding.role_id)
                .join(RolePermission, RolePermission.role_id == Role.role_id)
                .join(
                    PermissionCode,
                    PermissionCode.permission_code_id == RolePermission.permission_id,
                )
                .where(
                    UserRoleBinding.user_id == identity.user.user_id,
                    UserRoleBinding.valid_from <= now,
                    or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                    Role.lifecycle_status == ACTIVE,
                    PermissionCode.lifecycle_status == ACTIVE,
                    PermissionCode.permission_code == permission_code,
                )
            )
            applicable: list[tuple[str, str, str]] = []
            for binding_id, project_id, binding_role_id, role_code, decision, conditions in rows:
                is_super_admin = role_code == "ROLE-SUPER-ADMIN"
                if not is_super_admin:
                    if context.project_id is None and project_id is not None:
                        continue
                    if (
                        context.project_id is not None
                        and project_id is not None
                        and project_id != context.project_id
                    ):
                        continue
                    if context.scope_type in PROJECT_ID_SCOPE_TYPES:
                        scope_id_matches = DataScopeGrant.scope_id == context.project_id
                    elif project_id is None and context.project_id is not None:
                        # A platform-level binding must carry the explicit project
                        # identifier; NULL must never become dynamic-all access.
                        scope_id_matches = DataScopeGrant.scope_id == context.project_id
                    elif context.scope_id is None:
                        scope_id_matches = DataScopeGrant.scope_id.is_(None)
                    else:
                        scope_id_matches = or_(
                            DataScopeGrant.scope_id.is_(None),
                            DataScopeGrant.scope_id == context.scope_id,
                        )
                    grant = db.scalar(
                        select(DataScopeGrant.grant_id).where(
                            DataScopeGrant.binding_id == binding_id,
                            DataScopeGrant.scope_type == context.scope_type,
                            scope_id_matches,
                            or_(
                                DataScopeGrant.permission_code.is_(None),
                                DataScopeGrant.permission_code == permission_code,
                            ),
                        )
                    )
                    if grant is None:
                        continue
                if decision == "ALLOWED" and not self._condition_satisfied(
                    conditions,
                    identity.user.user_id,
                    context,
                ):
                    continue
                applicable.append((binding_role_id, role_code, decision))

            if any(decision in {"DENIED", "FORBIDDEN"} for _, _, decision in applicable):
                self._raise_permission_denied(identity, operation_id, audit_context, db=db)

            if context.object_state_allowed:
                for binding_role_id, role_code, decision in applicable:
                    if decision != "ALLOWED":
                        continue
                    if role_code == "ROLE-SUPER-ADMIN":
                        allowed = True
                        break
                    if context.project_id is not None and role_code != "ROLE-PLATFORM-ADMIN":
                        # Project-scoped realtime authorization is the intersection of
                        # the effective UserRoleBinding and the current project duty.
                        # Merely being a member of the project is insufficient: the
                        # ProjectMember duty must carry the same role as the binding.
                        if not self._has_matching_project_duty(
                            db,
                            identity.user.user_id,
                            context.project_id,
                            binding_role_id,
                        ):
                            continue
                    allowed = True
                    break
        if not allowed:
            self._raise_permission_denied(identity, operation_id, audit_context)
        return identity

    @staticmethod
    def _has_matching_project_duty(
        db: Session,
        user_id: str,
        project_id: str,
        binding_role_id: str,
    ) -> bool:
        """项目级授权要求实时项目职责与当前Role Binding角色完全一致。"""
        return (
            db.scalar(
                select(ProjectMember.project_member_id).where(
                    ProjectMember.user_id == user_id,
                    ProjectMember.project_id == project_id,
                    ProjectMember.role_id == binding_role_id,
                    ProjectMember.lifecycle_status == ACTIVE,
                )
            )
            is not None
        )

    @staticmethod
    def _condition_satisfied(
        condition: str | None,
        actor_user_id: str,
        context: AuthorizationContext,
    ) -> bool:
        del actor_user_id, context
        if condition == GENERIC_RBAC_CONDITION:
            return True
        # REVIEW/SUPER_ADMIN还要求二次确认、原因及受保护业务变更与审计的原子证据;
        # 当前认证审计表本身不能证明这些跨域前置条件, 因此继续失败关闭。
        if condition in {REVIEW_RBAC_CONDITION, SUPER_ADMIN_RBAC_CONDITION}:
            return False
        return False

    def _raise_permission_denied(
        self,
        identity: AuthenticatedIdentity,
        operation_id: str,
        audit_context: AuditContext,
        *,
        db: Session | None = None,
    ) -> NoReturn:
        """拒绝权限前统一写入安全审计，确保失败路径与成功路径具有可追溯的授权证据。"""
        error = PlatformError(
            title="Permission denied",
            detail="The current identity is not permitted to perform this operation.",
            status=403,
            code="AUTH_PERMISSION_DENIED",
        )
        if db is not None:
            self._audit.append(
                db,
                audit_context,
                action="PERMISSION_DENIED",
                operation_id=operation_id,
                result_code=error.code,
                actor_id=identity.user.user_id,
                target_user_id=identity.user.user_id,
                session_id=identity.session.session_id,
            )
            db.commit()
            raise error
        with self._session_factory() as audit_db:
            self._audit.append(
                audit_db,
                audit_context,
                action="PERMISSION_DENIED",
                operation_id=operation_id,
                result_code=error.code,
                actor_id=identity.user.user_id,
                target_user_id=identity.user.user_id,
                session_id=identity.session.session_id,
            )
            audit_db.commit()
        raise error

    def logout(self, token: str | None, audit_context: AuditContext) -> None:
        """登出必须同时撤销刷新会话并记录审计，避免客户端退出后服务端会话仍可继续使用。"""
        if not token:
            return
        try:
            token_digest = refresh_token_hash(token)
        except ValueError:
            return
        with self._session_factory() as db:
            refresh_session = db.scalar(
                select(AuthRefreshSession)
                .where(AuthRefreshSession.token_hash == token_digest)
                .with_for_update()
            )
            if refresh_session is None:
                return
            credential = db.get(PlatformUserCredential, refresh_session.credential_id)
            user_id = credential.user_id if credential is not None else None
            if refresh_session is not None and refresh_session.lifecycle_status == ACTIVE:
                refresh_session.lifecycle_status = "REVOKED"
                refresh_session.revoked_at = utc_now()
                refresh_session.revoke_reason = "LOGOUT"
                refresh_session.row_version += 1
                self._audit.append(
                    db,
                    audit_context,
                    action="SESSION_REVOKED",
                    operation_id="logout_platform_user",
                    result_code="LOGOUT",
                    actor_id=user_id,
                    target_user_id=user_id,
                    session_id=refresh_session.session_id,
                )
                result_code = "SUCCESS"
            else:
                result_code = "ALREADY_INACTIVE"
            self._audit.append(
                db,
                audit_context,
                action="LOGOUT",
                operation_id="logout_platform_user",
                result_code=result_code,
                actor_id=user_id,
                target_user_id=user_id,
                session_id=refresh_session.session_id,
            )
            db.commit()

    def change_password(
        self,
        access_token: str,
        current_password: str,
        new_password: str,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> None:
        """改密必须在同一事务中更新凭据版本、撤销会话并写审计，避免旧凭据或旧令牌继续有效。"""
        claims = self._jwt.decode(access_token)
        with self._session_factory() as db:
            record, replay = self._claim_change_password(
                db,
                claims.user_id,
                idempotency_key,
                current_password,
                new_password,
            )
            if replay:
                return
            identity = self._load_access_identity(
                db,
                claims,
                for_update=True,
                audit_context=audit_context,
                operation_id="change_current_user_password",
            )
            credential = identity.credential
            if not self._passwords.verify(credential.password_hash, current_password):
                raise PlatformError(
                    title="Current password is invalid",
                    detail="The current password is invalid.",
                    status=400,
                    code="AUTH_INVALID_CREDENTIALS",
                )
            try:
                self._passwords.validate(new_password, identity.user.username or "")
            except PasswordPolicyError as error:
                raise PlatformError(
                    title="New password is invalid",
                    detail=str(error),
                    status=400,
                    code="AUTH_OPERATION_FORBIDDEN_FOR_STATE",
                ) from error
            if self._passwords.verify(credential.password_hash, new_password):
                raise PlatformError(
                    title="New password is unchanged",
                    detail="The new password must differ from the current password.",
                    status=400,
                    code="AUTH_OPERATION_FORBIDDEN_FOR_STATE",
                )
            now = utc_now()
            credential.password_hash = self._passwords.hash(new_password)
            credential.credential_version += 1
            credential.force_password_change = False
            credential.password_changed_at = now
            credential.failed_login_count = 0
            credential.failure_window_started_at = None
            credential.locked_until = None
            credential.last_failed_at = None
            credential.row_version += 1
            self._revoke_active_sessions(
                db,
                credential,
                "PASSWORD_CHANGED",
                now,
                audit_context,
                actor_id=identity.user.user_id,
                operation_id="change_current_user_password",
            )
            record.response_status = 204
            record.response_json = None
            record.completed_at = now
            record.expires_at = now + timedelta(days=1)
            self._audit.append(
                db,
                audit_context,
                action="PASSWORD_CHANGED",
                operation_id="change_current_user_password",
                result_code="SUCCESS",
                actor_id=identity.user.user_id,
                target_user_id=identity.user.user_id,
                session_id=identity.session.session_id,
            )
            db.commit()

    def _claim_change_password(
        self,
        db: Session,
        principal_id: str,
        raw_key: str,
        current_password: str,
        new_password: str,
    ) -> tuple[IdempotencyRecord, bool]:
        """幂等声明必须先于聚合锁完成并收敛并发重试，避免同一改密意图产生重复或冲突副作用。"""
        operation_id = "change_current_user_password"
        storage_payload = _framed(principal_id, operation_id, raw_key)
        storage_keys = self._auth_hmac.hex_digests("idempotency-storage-key", storage_payload)
        fingerprint_payload = _framed(current_password, new_password)
        fingerprints = self._auth_hmac.hex_digests(
            "change-password-fingerprint", fingerprint_payload
        )
        now = utc_now()
        candidates = (raw_key, *storage_keys)
        existing_rows = list(
            db.scalars(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key.in_(candidates))
                .order_by(IdempotencyRecord.idempotency_key)
                .with_for_update()
            )
        )
        existing = next((row for row in existing_rows if row.expires_at > now), None)
        if existing is not None:
            if existing.contract_version == 1:
                raise _idempotency_conflict()
            if (
                existing.operation_id != operation_id
                or existing.principal_id != principal_id
                or existing.request_hash not in fingerprints
            ):
                raise _idempotency_conflict()
            if existing.response_status == 204 and existing.completed_at is not None:
                return existing, True
            raise PlatformError(
                title="Concurrent idempotent request is incomplete",
                detail="The idempotent command has not reached a terminal state.",
                status=409,
                code="AUTH_CONCURRENCY_CONFLICT",
            )

        active_storage_key = storage_keys[0]
        active_fingerprint = fingerprints[0]
        expired_active = next(
            (
                row
                for row in existing_rows
                if row.idempotency_key == active_storage_key and row.contract_version == 2
            ),
            None,
        )
        if expired_active is not None:
            expired_active.principal_id = principal_id
            expired_active.operation_id = operation_id
            expired_active.request_hash = active_fingerprint
            expired_active.response_status = None
            expired_active.response_json = None
            expired_active.completed_at = None
            expired_active.expires_at = now + timedelta(days=1)
            return expired_active, False
        statement = mysql_insert(IdempotencyRecord).values(
            idempotency_key=active_storage_key,
            contract_version=2,
            principal_id=principal_id,
            operation_id=operation_id,
            request_hash=active_fingerprint,
            response_status=None,
            response_json=None,
            completed_at=None,
            expires_at=now + timedelta(days=1),
        )
        db.execute(
            statement.on_duplicate_key_update(idempotency_key=IdempotencyRecord.idempotency_key)
        )
        claimed = db.scalar(
            select(IdempotencyRecord)
            .where(IdempotencyRecord.idempotency_key == active_storage_key)
            .with_for_update()
        )
        if claimed is None:
            raise RuntimeError("idempotency claim was not materialized")
        if (
            claimed.operation_id != operation_id
            or claimed.principal_id != principal_id
            or claimed.request_hash not in fingerprints
        ):
            raise _idempotency_conflict()
        if claimed.response_status == 204 and claimed.completed_at is not None:
            return claimed, True
        return claimed, False

    def _load_access_identity(
        self,
        db: Session,
        claims: AccessClaims,
        *,
        audit_context: AuditContext,
        operation_id: str,
        for_update: bool = False,
    ) -> AuthenticatedIdentity:
        """访问身份装载必须交叉校验令牌声明与数据库当前状态，防止仅信任JWT造成撤销状态失效。"""
        user_query = select(PlatformUser).where(PlatformUser.user_id == claims.user_id)
        if for_update:
            user_query = user_query.with_for_update()
        user = db.scalar(user_query)
        if user is None:
            self._audit.append(
                db,
                audit_context,
                action="SESSION_REVOKED",
                operation_id=operation_id,
                result_code="AUTH_IDENTITY_NOT_FOUND",
                target_user_id=claims.user_id,
                session_id=claims.session_id,
            )
            raise PlatformError(
                title="Identity not found",
                detail="The authenticated identity no longer exists.",
                status=401,
                code="AUTH_IDENTITY_NOT_FOUND",
            )
        credential_query = select(PlatformUserCredential).where(
            PlatformUserCredential.user_id == user.user_id
        )
        if for_update:
            credential_query = credential_query.with_for_update()
        credential = db.scalar(credential_query)
        session_query = select(AuthRefreshSession).where(
            AuthRefreshSession.session_id == claims.session_id
        )
        if for_update:
            session_query = session_query.with_for_update()
        refresh_session = db.scalar(session_query)
        if credential is None or refresh_session is None:
            self._audit.append(
                db,
                audit_context,
                action="SESSION_REVOKED",
                operation_id=operation_id,
                result_code="AUTH_SESSION_REVOKED",
                actor_id=user.user_id,
                target_user_id=user.user_id,
                session_id=claims.session_id,
            )
            raise self._session_revoked()
        self._require_login_user_state(
            user,
            db,
            credential,
            audit_context,
            operation_id,
            actor_id=user.user_id,
        )
        now = utc_now()
        if refresh_session.lifecycle_status == ACTIVE and refresh_session.expires_at <= now:
            refresh_session.lifecycle_status = "EXPIRED"
            refresh_session.row_version += 1
            self._audit.append(
                db,
                audit_context,
                action="SESSION_REVOKED",
                operation_id=operation_id,
                result_code="EXPIRED",
                actor_id=user.user_id,
                target_user_id=user.user_id,
                session_id=refresh_session.session_id,
            )
            raise self._session_revoked()
        if (
            credential.lifecycle_status != ACTIVE
            or credential.credential_version != claims.credential_version
            or refresh_session.credential_id != credential.credential_id
            or refresh_session.credential_version != credential.credential_version
            or refresh_session.lifecycle_status != ACTIVE
        ):
            self._audit.append(
                db,
                audit_context,
                action="SESSION_REVOKED",
                operation_id=operation_id,
                result_code="AUTH_SESSION_REVOKED",
                actor_id=user.user_id,
                target_user_id=user.user_id,
                session_id=refresh_session.session_id,
            )
            raise self._session_revoked()
        return AuthenticatedIdentity(user, credential, refresh_session)

    def _require_login_user_state(
        self,
        user: PlatformUser,
        db: Session,
        credential: PlatformUserCredential,
        audit_context: AuditContext,
        operation_id: str,
        *,
        actor_id: str | None,
    ) -> None:
        """登录前集中校验用户与凭据可用状态，确保禁用、锁定或强制改密规则不会被入口绕过。"""
        if user.lifecycle_status == ACTIVE:
            return
        self._revoke_active_sessions(
            db,
            credential,
            "USER_STATE_CHANGED",
            utc_now(),
            audit_context,
            actor_id=actor_id,
            operation_id=operation_id,
        )
        mapping = {
            "LOCKED": ("Account locked", "AUTH_ACCOUNT_LOCKED"),
            "DISABLED": ("Account disabled", "AUTH_ACCOUNT_DISABLED"),
            "ARCHIVED": ("Account archived", "AUTH_ACCOUNT_ARCHIVED"),
            "LOGICALLY_DELETED": ("Account archived", "AUTH_ACCOUNT_ARCHIVED"),
        }
        title, code = mapping.get(
            user.lifecycle_status,
            ("Operation forbidden for account state", "AUTH_OPERATION_FORBIDDEN_FOR_STATE"),
        )
        self._audit.append(
            db,
            audit_context,
            action="USER_DISABLED_OR_LOCKED",
            operation_id=operation_id,
            result_code=code,
            actor_id=actor_id,
            target_user_id=user.user_id,
        )
        raise PlatformError(title=title, detail=title + ".", status=403, code=code)

    def _record_login_failure(self, credential: PlatformUserCredential, now: datetime) -> None:
        """失败计数在锁定凭据后更新，避免并发登录竞争导致阈值计算丢失或锁定状态不一致。"""
        current = now
        window = credential.failure_window_started_at
        if window is None or current - window > timedelta(seconds=900):
            credential.failure_window_started_at = current
            credential.failed_login_count = 1
        else:
            credential.failed_login_count = min(5, credential.failed_login_count + 1)
        credential.last_failed_at = current
        if credential.failed_login_count >= 5:
            credential.locked_until = current + timedelta(seconds=900)
        credential.row_version += 1

    def _create_session(
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
        """会话创建统一生成令牌家族和审计关联，确保刷新旋转、撤销与追踪使用同一身份边界。"""
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
                    candidate.lifecycle_status = "EXPIRED"
                    candidate.row_version += 1
                else:
                    unexpired.append(candidate)
            active = unexpired
            while len(active) >= 5:
                oldest = active.pop(0)
                oldest.lifecycle_status = "REVOKED"
                oldest.revoked_at = now
                oldest.revoke_reason = "SESSION_LIMIT"
                oldest.row_version += 1
                self._audit.append(
                    db,
                    audit_context,
                    action="SESSION_REVOKED",
                    operation_id=operation_id,
                    result_code="SESSION_LIMIT",
                    actor_id=actor_id,
                    target_user_id=credential.user_id,
                    session_id=oldest.session_id,
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

    def _compromise_family(
        self,
        db: Session,
        family_id: str,
        now: datetime,
        audit_context: AuditContext,
        *,
        actor_id: str,
        operation_id: str,
    ) -> None:
        """检测刷新令牌重放后必须标记整个令牌家族失陷，避免攻击者继续使用同族旧令牌。"""
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

    def _revoke_active_sessions(
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
        """安全敏感变更后统一撤销活动会话，确保旧刷新凭据不能绕过新的用户或凭据状态。"""
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
                target_user_id=credential.user_id,
                session_id=refresh_session.session_id,
            )

    def _current_user(
        self, db: Session, user: PlatformUser, credential: PlatformUserCredential
    ) -> CurrentUserResource:
        """当前用户投影统一从已验证身份构造，避免接口层自行拼装造成权限或凭据状态遗漏。"""
        now = utc_now()
        role_query: Select[tuple[str | None]] = (
            select(Role.role_code)
            .join(UserRoleBinding, UserRoleBinding.role_id == Role.role_id)
            .where(
                UserRoleBinding.user_id == user.user_id,
                UserRoleBinding.valid_from <= now,
                or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                Role.lifecycle_status == ACTIVE,
            )
            .distinct()
            .order_by(Role.role_code)
        )
        permission_decision_query: Select[tuple[str, str]] = (
            select(PermissionCode.permission_code, RolePermission.decision)
            .join(RolePermission, RolePermission.permission_id == PermissionCode.permission_code_id)
            .join(UserRoleBinding, UserRoleBinding.role_id == RolePermission.role_id)
            .join(Role, Role.role_id == UserRoleBinding.role_id)
            .where(
                UserRoleBinding.user_id == user.user_id,
                UserRoleBinding.valid_from <= now,
                or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                Role.lifecycle_status == ACTIVE,
                PermissionCode.lifecycle_status == ACTIVE,
            )
        )
        allowed_permissions: set[str] = set()
        denied_permissions: set[str] = set()
        for permission_code, decision in db.execute(permission_decision_query):
            if decision == "ALLOWED":
                allowed_permissions.add(permission_code)
            elif decision in {"DENIED", "FORBIDDEN"}:
                denied_permissions.add(permission_code)
        return CurrentUserResource(
            user_id=user.user_id,
            username=user.username or "",
            display_name=user.display_name,
            lifecycle_status="ACTIVE",
            roles=[role for role in db.scalars(role_query) if role is not None],
            permissions=sorted(allowed_permissions - denied_permissions),
            force_password_change=credential.force_password_change,
        )

    def _result(
        self,
        user_id: str,
        credential_version: int,
        refresh_session: AuthRefreshSession,
        refresh_token: str,
        current_user: CurrentUserResource,
    ) -> AuthenticationResult:
        """认证结果统一封装令牌与用户投影，确保各认证入口返回一致且受控的安全字段集合。"""
        access_token = self._jwt.issue(
            AccessClaims(user_id, refresh_session.session_id, credential_version)
        )
        return AuthenticationResult(access_token, refresh_token, current_user)

    def _raise_audited_failure(
        self,
        db: Session,
        audit_context: AuditContext,
        *,
        action: AuthenticationAuditAction,
        operation_id: str,
        error: PlatformError,
        actor_id: str | None = None,
        target_user_id: str | None = None,
        session_id: str | None = None,
    ) -> NoReturn:
        """认证失败必须先同步落审计再暴露错误，确保异常路径不会丢失安全追踪证据。"""
        if action not in {"LOGIN_FAILED", "REFRESH_FAILED"}:
            raise ValueError("unsupported audited failure action")
        self._audit.append(
            db,
            audit_context,
            action=action,
            operation_id=operation_id,
            result_code=error.code,
            actor_id=actor_id,
            target_user_id=target_user_id,
            session_id=session_id,
        )
        db.commit()
        raise error

    @staticmethod
    def _invalid_credentials() -> PlatformError:
        return PlatformError(
            title="Invalid credentials",
            detail="The username or password is invalid.",
            status=401,
            code="AUTH_INVALID_CREDENTIALS",
        )

    @staticmethod
    def _session_revoked() -> PlatformError:
        return PlatformError(
            title="Session revoked",
            detail="The authentication session is unavailable.",
            status=401,
            code="AUTH_SESSION_REVOKED",
        )
