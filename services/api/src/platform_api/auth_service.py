"""Transactional P1 platform authentication and realtime relational RBAC service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Select, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

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
    ) -> None:
        self._session_factory = session_factory
        self._passwords = passwords
        self._jwt = jwt_service

    def login(
        self, username: str, password: str, source_context: str | None
    ) -> AuthenticationResult:
        with self._session_factory() as db:
            user = db.scalar(
                select(PlatformUser).where(PlatformUser.username == username).with_for_update()
            )
            if user is None:
                self._passwords.verify_dummy(password)
                raise self._invalid_credentials()
            credential = db.scalar(
                select(PlatformUserCredential)
                .where(PlatformUserCredential.user_id == user.user_id)
                .with_for_update()
            )
            if credential is None or credential.lifecycle_status != ACTIVE:
                self._passwords.verify_dummy(password)
                raise self._invalid_credentials()
            try:
                self._require_login_user_state(user, db, credential)
            except PlatformError:
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
                    db.commit()
                raise self._invalid_credentials()
            if temporarily_locked:
                raise PlatformError(
                    title="Account temporarily locked",
                    detail="The account is temporarily locked.",
                    status=403,
                    code="AUTH_ACCOUNT_TEMPORARILY_LOCKED",
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
                db, credential, source_context, family_id=None
            )
            current_user = self._current_user(db, user, credential)
            db.commit()
        return self._result(
            user.user_id, credential.credential_version, session, refresh_token, current_user
        )

    def authenticate_access(
        self, token: str, operation_id: str
    ) -> tuple[AuthenticatedIdentity, CurrentUserResource]:
        claims = self._jwt.decode(token)
        with self._session_factory() as db:
            try:
                identity = self._load_access_identity(db, claims)
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

    def refresh(self, token: str, source_context: str | None) -> AuthenticationResult:
        try:
            token_digest = refresh_token_hash(token)
        except ValueError:
            raise self._session_revoked() from None
        with self._session_factory() as db:
            session_hint = db.scalar(
                select(AuthRefreshSession).where(AuthRefreshSession.token_hash == token_digest)
            )
            if session_hint is None:
                raise self._session_revoked()
            credential_hint = db.get(PlatformUserCredential, session_hint.credential_id)
            if credential_hint is None:
                raise self._session_revoked()
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
                raise self._session_revoked()
            now = utc_now()
            if old.lifecycle_status == "ROTATED":
                self._compromise_family(db, old.family_id, now)
                db.commit()
                raise self._session_revoked()
            if old.lifecycle_status != ACTIVE:
                raise self._session_revoked()
            if old.expires_at <= now:
                old.lifecycle_status = "EXPIRED"
                old.row_version += 1
                db.commit()
                raise self._session_revoked()
            if credential.lifecycle_status != ACTIVE:
                raise self._session_revoked()
            try:
                self._require_login_user_state(user, db, credential)
            except PlatformError:
                db.commit()
                raise
            if credential.force_password_change:
                raise PlatformError(
                    title="Password change required",
                    detail="Refresh is unavailable until the password is changed.",
                    status=403,
                    code="AUTH_PASSWORD_CHANGE_REQUIRED",
                )
            if old.credential_version != credential.credential_version:
                raise self._session_revoked()
            replacement, refresh_token = self._create_session(
                db,
                credential,
                source_context,
                family_id=old.family_id,
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
    ) -> AuthenticatedIdentity:
        """Intersect realtime permission, project membership, data scope and object state."""
        identity, _ = self.authenticate_access(token, operation_id)
        if context.scope_type not in FROZEN_DATA_SCOPE_TYPES:
            self._raise_permission_denied()
        if context.scope_type in PROJECT_ID_SCOPE_TYPES and (
            context.project_id is None or context.scope_id != context.project_id
        ):
            self._raise_permission_denied()
        allowed = False
        with self._session_factory() as db:
            now = utc_now()
            rows = db.execute(
                select(
                    UserRoleBinding.binding_id,
                    UserRoleBinding.project_id,
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
            applicable: list[tuple[str, str]] = []
            for binding_id, project_id, role_code, decision, conditions in rows:
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
                applicable.append((role_code, decision))

            if any(decision in {"DENIED", "FORBIDDEN"} for _, decision in applicable):
                self._raise_permission_denied()

            project_member_id = None
            if context.project_id is not None:
                project_member_id = db.scalar(
                    select(ProjectMember.project_member_id).where(
                        ProjectMember.user_id == identity.user.user_id,
                        ProjectMember.project_id == context.project_id,
                        ProjectMember.lifecycle_status == ACTIVE,
                    )
                )

            if context.object_state_allowed:
                for role_code, decision in applicable:
                    if decision != "ALLOWED":
                        continue
                    if role_code == "ROLE-SUPER-ADMIN":
                        allowed = True
                        break
                    if (
                        context.project_id is not None
                        and role_code != "ROLE-PLATFORM-ADMIN"
                        and project_member_id is None
                    ):
                        continue
                    allowed = True
                    break
        if not allowed:
            self._raise_permission_denied()
        return identity

    @staticmethod
    def _condition_satisfied(
        condition: str | None,
        actor_user_id: str,
        context: AuthorizationContext,
    ) -> bool:
        del actor_user_id, context
        if condition == GENERIC_RBAC_CONDITION:
            return True
        # The review and super-admin conditions require an immutable audit record
        # committed atomically with the protected business mutation. P1's frozen
        # physical audit model cannot represent that evidence, so these conditions
        # remain fail-closed instead of trusting caller-supplied booleans.
        if condition in {REVIEW_RBAC_CONDITION, SUPER_ADMIN_RBAC_CONDITION}:
            return False
        return False

    @staticmethod
    def _raise_permission_denied() -> None:
        raise PlatformError(
            title="Permission denied",
            detail="The current identity is not permitted to perform this operation.",
            status=403,
            code="AUTH_PERMISSION_DENIED",
        )

    def logout(self, token: str | None) -> None:
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
            if refresh_session is not None and refresh_session.lifecycle_status == ACTIVE:
                refresh_session.lifecycle_status = "REVOKED"
                refresh_session.revoked_at = utc_now()
                refresh_session.revoke_reason = "LOGOUT"
                refresh_session.row_version += 1
                db.commit()

    def change_password(
        self,
        access_token: str,
        current_password: str,
        new_password: str,
        idempotency_key: str,
        source_context: str | None,
    ) -> AuthenticationResult:
        claims = self._jwt.decode(access_token)
        with self._session_factory.begin() as db:
            existing = db.get(IdempotencyRecord, idempotency_key)
            if existing is not None:
                raise PlatformError(
                    title="Idempotency key conflict",
                    detail="The idempotency key has already been used.",
                    status=409,
                    code="AUTH_OPERATION_FORBIDDEN_FOR_STATE",
                )
            try:
                identity = self._load_access_identity(db, claims, for_update=True)
            except PlatformError:
                db.commit()
                raise
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
            self._revoke_active_sessions(db, credential.credential_id, "PASSWORD_CHANGED", now)
            replacement, refresh_token = self._create_session(
                db, credential, source_context, family_id=None, enforce_limit=False
            )
            db.add(
                IdempotencyRecord(
                    idempotency_key=idempotency_key,
                    operation_id="change_current_user_password",
                    request_hash=hashlib.sha256(
                        f"{identity.user.user_id}:{claims.credential_version}".encode()
                    ).hexdigest(),
                    response_status=200,
                    response_json=None,
                    expires_at=now + timedelta(days=1),
                )
            )
            current_user = self._current_user(db, identity.user, credential)
            db.commit()
        return self._result(
            identity.user.user_id,
            credential.credential_version,
            replacement,
            refresh_token,
            current_user,
        )

    def _load_access_identity(
        self, db: Session, claims: AccessClaims, *, for_update: bool = False
    ) -> AuthenticatedIdentity:
        user_query = select(PlatformUser).where(PlatformUser.user_id == claims.user_id)
        if for_update:
            user_query = user_query.with_for_update()
        user = db.scalar(user_query)
        if user is None:
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
            raise self._session_revoked()
        self._require_login_user_state(user, db, credential)
        now = utc_now()
        if refresh_session.lifecycle_status == ACTIVE and refresh_session.expires_at <= now:
            refresh_session.lifecycle_status = "EXPIRED"
            refresh_session.row_version += 1
            raise self._session_revoked()
        if (
            credential.lifecycle_status != ACTIVE
            or credential.credential_version != claims.credential_version
            or refresh_session.credential_id != credential.credential_id
            or refresh_session.credential_version != credential.credential_version
            or refresh_session.lifecycle_status != ACTIVE
        ):
            raise self._session_revoked()
        return AuthenticatedIdentity(user, credential, refresh_session)

    def _require_login_user_state(
        self, user: PlatformUser, db: Session, credential: PlatformUserCredential
    ) -> None:
        if user.lifecycle_status == ACTIVE:
            return
        self._revoke_active_sessions(db, credential.credential_id, "USER_STATE_CHANGED", utc_now())
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
        raise PlatformError(title=title, detail=title + ".", status=403, code=code)

    def _record_login_failure(self, credential: PlatformUserCredential, now: datetime) -> None:
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
        source_context: str | None,
        family_id: str | None,
        *,
        expires_at: datetime | None = None,
        enforce_limit: bool = True,
    ) -> tuple[AuthRefreshSession, str]:
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
            client_context_hash=client_context_hash(source_context),
            row_version=0,
            created_at=now,
            updated_at=now,
        )
        db.add(refresh_session)
        return refresh_session, raw_token

    def _compromise_family(self, db: Session, family_id: str, now: datetime) -> None:
        current = now
        db.execute(
            update(AuthRefreshSession)
            .where(AuthRefreshSession.family_id == family_id)
            .values(
                lifecycle_status="COMPROMISED",
                revoked_at=current,
                revoke_reason="REFRESH_REPLAY",
                row_version=AuthRefreshSession.row_version + 1,
            )
        )

    def _revoke_active_sessions(
        self, db: Session, credential_id: str, reason: str, now: datetime
    ) -> None:
        current = now
        db.execute(
            update(AuthRefreshSession)
            .where(
                AuthRefreshSession.credential_id == credential_id,
                AuthRefreshSession.lifecycle_status == ACTIVE,
            )
            .values(
                lifecycle_status="REVOKED",
                revoked_at=current,
                revoke_reason=reason,
                row_version=AuthRefreshSession.row_version + 1,
            )
        )

    def _current_user(
        self, db: Session, user: PlatformUser, credential: PlatformUserCredential
    ) -> CurrentUserResource:
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
        access_token = self._jwt.issue(
            AccessClaims(user_id, refresh_session.session_id, credential_version)
        )
        return AuthenticationResult(access_token, refresh_token, current_user)

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
