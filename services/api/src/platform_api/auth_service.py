"""Transactional P1 platform authentication and realtime relational RBAC service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import (
    AuditContext,
    AuthenticationAuditAction,
    AuthenticationAuditService,
)
from platform_api.auth_schemas import CurrentUserResource
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    AuthRefreshSession,
    DataScopeGrant,
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
    refresh_token_hash,
    utc_now,
)
from platform_api.session_service import SessionService

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
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
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
        rate_limits: AuthenticationRateLimitService,
        sessions: SessionService,
        idempotency: IdempotencyCoordinator,
    ) -> None:
        """认证服务统一持有密码、JWT与审计依赖，确保同一业务事务不会绕过既定安全组件。"""
        self._session_factory = session_factory
        self._passwords = passwords
        self._jwt = jwt_service
        self._audit = audit_service
        self._rate_limits = rate_limits
        self._sessions = sessions
        self._idempotency = idempotency

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
            session, refresh_token = self._sessions.create(
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
        """平台命令只接受实时平台Binding与数据范围交集, 避免复用``/me``权限并集越权。"""
        if not permission_codes:
            raise ValueError("permission_codes must not be empty")
        identity, _ = self.authenticate_access(token, operation_id, audit_context)
        with self._session_factory() as db:
            self.require_platform_permissions_in_transaction(
                db, identity, operation_id, permission_codes, audit_context
            )
        return identity

    def require_platform_permissions_in_transaction(
        self,
        db: Session,
        identity: AuthenticatedIdentity,
        operation_id: str,
        permission_codes: tuple[str, ...],
        audit_context: AuditContext,
    ) -> None:
        """平台授权在调用方事务中重算Binding与Grant, 避免项目级权限投影授权平台写入。"""
        now = utc_now()
        context = AuthorizationContext(None, "PLATFORM_TECHNICAL", None, True)
        for permission_code in permission_codes:
            mappings = list(
                db.execute(
                    select(
                        UserRoleBinding.binding_id,
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
                        UserRoleBinding.project_id.is_(None),
                        UserRoleBinding.valid_from <= now,
                        or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                        Role.lifecycle_status == ACTIVE,
                        PermissionCode.lifecycle_status == ACTIVE,
                        PermissionCode.permission_code == permission_code,
                    )
                )
            )
            applicable: list[tuple[str, str | None, str]] = []
            for binding_id, role_code, decision, conditions in mappings:
                if role_code != "ROLE-SUPER-ADMIN":
                    grant = db.scalar(
                        select(DataScopeGrant.grant_id).where(
                            DataScopeGrant.binding_id == binding_id,
                            DataScopeGrant.scope_type.in_(("PLATFORM_ALL", "PLATFORM_TECHNICAL")),
                            DataScopeGrant.scope_id.is_(None),
                            or_(
                                DataScopeGrant.permission_code.is_(None),
                                DataScopeGrant.permission_code == permission_code,
                            ),
                        )
                    )
                    if grant is None:
                        continue
                applicable.append((decision, conditions, role_code))
            if any(decision in {"DENIED", "FORBIDDEN"} for decision, _, _ in applicable):
                self._raise_permission_denied(identity, operation_id, audit_context, db=db)
            if not any(
                decision == "ALLOWED"
                and self._condition_satisfied(conditions, identity.user.user_id, context)
                for decision, conditions, _ in applicable
            ):
                self._raise_permission_denied(identity, operation_id, audit_context, db=db)

    def authenticate_access_in_transaction(
        self,
        db: Session,
        token: str,
        operation_id: str,
        audit_context: AuditContext,
    ) -> AuthenticatedIdentity:
        """目标敏感命令在caller事务内重新装载身份, 避免授权与写入之间出现状态竞态。"""
        claims = self._jwt.decode(token)
        try:
            identity = self._load_access_identity(
                db,
                claims,
                audit_context=audit_context,
                operation_id=operation_id,
            )
        except PlatformError:
            # 调用点均在幂等claim之前。到期/撤销等安全终态及其审计必须先提交,
            # 不能被随后抛出的认证错误随外层命令事务一起回滚。
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
        return identity

    def require_project_permissions_in_transaction(
        self,
        db: Session,
        identity: AuthenticatedIdentity,
        operation_id: str,
        permission_codes: tuple[str, ...],
        project_id: str,
        audit_context: AuditContext,
    ) -> str:
        """项目写授权重算Binding、Grant与项目职责交集, 避免跨项目权限被聚合复用。"""
        now = utc_now()
        context = AuthorizationContext(project_id, "AUTHORIZED_PROJECT_ACTIVE", project_id, True)
        scope_decisions: list[str] = []
        for permission_code in permission_codes:
            mappings = list(
                db.execute(
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
            )
            applicable: list[tuple[str, str | None, str]] = []
            for (
                binding_id,
                binding_project_id,
                role_id,
                role_code,
                decision,
                conditions,
            ) in mappings:
                if role_code != "ROLE-SUPER-ADMIN":
                    if binding_project_id is not None and binding_project_id != project_id:
                        continue
                    if role_code == "ROLE-PLATFORM-ADMIN":
                        # PLATFORM_TECHNICAL never grants project business access. A
                        # Platform Admin needs an explicit target-project grant, but
                        # that platform duty does not require a same-role ProjectMember.
                        grant = db.scalar(
                            select(DataScopeGrant.grant_id).where(
                                DataScopeGrant.binding_id == binding_id,
                                DataScopeGrant.scope_type.in_(
                                    ("AUTHORIZED_PROJECT_ACTIVE", "SPECIFIED_PROJECT_IDS")
                                ),
                                DataScopeGrant.scope_id == project_id,
                                or_(
                                    DataScopeGrant.permission_code.is_(None),
                                    DataScopeGrant.permission_code == permission_code,
                                ),
                            )
                        )
                    else:
                        grant = db.scalar(
                            select(DataScopeGrant.grant_id).where(
                                DataScopeGrant.binding_id == binding_id,
                                DataScopeGrant.scope_type.in_(
                                    ("AUTHORIZED_PROJECT_ACTIVE", "SPECIFIED_PROJECT_IDS")
                                ),
                                DataScopeGrant.scope_id == project_id,
                                or_(
                                    DataScopeGrant.permission_code.is_(None),
                                    DataScopeGrant.permission_code == permission_code,
                                ),
                            )
                        )
                    if grant is None:
                        continue
                    if role_code != "ROLE-PLATFORM-ADMIN" and not self._has_matching_project_duty(
                        db, identity.user.user_id, project_id, role_id
                    ):
                        continue
                applicable.append((decision, conditions, role_code))

            binding_applicable = list(applicable)
            # Product Owner scope is deliberately not persisted as seven duplicate
            # DataScopeGrant rows. The ACTIVE membership duty itself is the live
            # project boundary and disappears immediately when membership/role ends.
            owner_mappings = list(
                db.execute(
                    select(
                        RolePermission.decision,
                        RolePermission.conditions,
                        Role.role_code,
                    )
                    .select_from(ProjectMember)
                    .join(Role, Role.role_id == ProjectMember.role_id)
                    .join(RolePermission, RolePermission.role_id == Role.role_id)
                    .join(
                        PermissionCode,
                        PermissionCode.permission_code_id == RolePermission.permission_id,
                    )
                    .where(
                        ProjectMember.user_id == identity.user.user_id,
                        ProjectMember.project_id == project_id,
                        ProjectMember.lifecycle_status == ACTIVE,
                        Role.lifecycle_status == ACTIVE,
                        Role.role_code == "ROLE-PROJECT-OWNER-DUTY",
                        PermissionCode.lifecycle_status == ACTIVE,
                        PermissionCode.permission_code == permission_code,
                    )
                )
            )
            applicable.extend(
                (decision, conditions, role_code or "")
                for decision, conditions, role_code in owner_mappings
            )
            if any(decision in {"DENIED", "FORBIDDEN"} for decision, _, _ in applicable):
                self._raise_permission_denied(identity, operation_id, audit_context, db=db)
            binding_allowed = any(
                decision == "ALLOWED"
                and self._condition_satisfied(conditions, identity.user.user_id, context)
                for decision, conditions, _ in binding_applicable
            )
            owner_allowed = any(
                decision == "ALLOWED"
                and self._condition_satisfied(conditions, identity.user.user_id, context)
                for decision, conditions, _ in owner_mappings
            )
            if not binding_allowed and not owner_allowed:
                self._raise_permission_denied(identity, operation_id, audit_context, db=db)
            scope_decisions.append(
                "DYNAMIC_PROJECT_OWNER_ALL" if owner_allowed and not binding_allowed else "ALLOWED"
            )
        return (
            "DYNAMIC_PROJECT_OWNER_ALL"
            if scope_decisions
            and all(item == "DYNAMIC_PROJECT_OWNER_ALL" for item in scope_decisions)
            else "ALLOWED"
        )

    def user_has_permission_qualification_in_transaction(
        self,
        db: Session,
        user_id: str,
        permission_code: str,
    ) -> bool:
        """Evaluate a subject qualification without deriving a resource data scope."""
        now = utc_now()
        rows = list(
            db.execute(
                select(RolePermission.decision, RolePermission.conditions)
                .select_from(UserRoleBinding)
                .join(Role, Role.role_id == UserRoleBinding.role_id)
                .join(RolePermission, RolePermission.role_id == Role.role_id)
                .join(
                    PermissionCode,
                    PermissionCode.permission_code_id == RolePermission.permission_id,
                )
                .where(
                    UserRoleBinding.user_id == user_id,
                    UserRoleBinding.valid_from <= now,
                    or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                    Role.lifecycle_status == ACTIVE,
                    PermissionCode.lifecycle_status == ACTIVE,
                    PermissionCode.permission_code == permission_code,
                )
            )
        )
        rows.extend(
            db.execute(
                select(RolePermission.decision, RolePermission.conditions)
                .select_from(ProjectMember)
                .join(Role, Role.role_id == ProjectMember.role_id)
                .join(RolePermission, RolePermission.role_id == Role.role_id)
                .join(
                    PermissionCode,
                    PermissionCode.permission_code_id == RolePermission.permission_id,
                )
                .where(
                    ProjectMember.user_id == user_id,
                    ProjectMember.lifecycle_status == ACTIVE,
                    Role.lifecycle_status == ACTIVE,
                    PermissionCode.lifecycle_status == ACTIVE,
                    PermissionCode.permission_code == permission_code,
                )
            )
        )
        context = AuthorizationContext(None, "QUALIFICATION", None, True)
        applicable = [
            decision
            for decision, conditions in rows
            if self._condition_satisfied(conditions, user_id, context)
        ]
        if any(decision in {"DENIED", "FORBIDDEN"} for decision in applicable):
            return False
        return any(decision == "ALLOWED" for decision in applicable)

    def authorized_project_ids_in_transaction(
        self,
        db: Session,
        identity: AuthenticatedIdentity,
        permission_code: str,
    ) -> set[str] | None:
        """Return visible project ids, or ``None`` for explicit platform-wide access."""
        now = utc_now()
        context = AuthorizationContext(None, "PLATFORM_TECHNICAL", None, True)
        bindings = list(
            db.execute(
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
        )
        global_decisions: list[str] = []
        allowed: set[str] = set()
        denied: set[str] = set()
        for binding_id, binding_project_id, role_id, role_code, decision, conditions in bindings:
            if not self._condition_satisfied(conditions, identity.user.user_id, context):
                continue
            if role_code == "ROLE-SUPER-ADMIN":
                global_decisions.append(decision)
                continue
            scope_ids = set(
                db.scalars(
                    select(DataScopeGrant.scope_id).where(
                        DataScopeGrant.binding_id == binding_id,
                        DataScopeGrant.scope_type.in_(
                            ("AUTHORIZED_PROJECT_ACTIVE", "SPECIFIED_PROJECT_IDS")
                        ),
                        DataScopeGrant.scope_id.is_not(None),
                        or_(
                            DataScopeGrant.permission_code.is_(None),
                            DataScopeGrant.permission_code == permission_code,
                        ),
                    )
                )
            )
            if binding_project_id is not None:
                scope_ids &= {binding_project_id}
            for project_id in scope_ids:
                if project_id is None:
                    continue
                if role_code != "ROLE-PLATFORM-ADMIN" and not self._has_matching_project_duty(
                    db, identity.user.user_id, project_id, role_id
                ):
                    continue
                (allowed if decision == "ALLOWED" else denied).add(project_id)

        if any(decision in {"DENIED", "FORBIDDEN"} for decision in global_decisions):
            return set()
        if any(decision == "ALLOWED" for decision in global_decisions):
            return None

        owner_rows = list(
            db.execute(
                select(
                    ProjectMember.project_id,
                    RolePermission.decision,
                    RolePermission.conditions,
                )
                .select_from(ProjectMember)
                .join(Role, Role.role_id == ProjectMember.role_id)
                .join(RolePermission, RolePermission.role_id == Role.role_id)
                .join(
                    PermissionCode,
                    PermissionCode.permission_code_id == RolePermission.permission_id,
                )
                .where(
                    ProjectMember.user_id == identity.user.user_id,
                    ProjectMember.lifecycle_status == ACTIVE,
                    Role.lifecycle_status == ACTIVE,
                    Role.role_code == "ROLE-PROJECT-OWNER-DUTY",
                    PermissionCode.lifecycle_status == ACTIVE,
                    PermissionCode.permission_code == permission_code,
                )
            )
        )
        for project_id, decision, conditions in owner_rows:
            owner_context = AuthorizationContext(
                project_id, "AUTHORIZED_PROJECT_ACTIVE", project_id, True
            )
            if not self._condition_satisfied(
                conditions, identity.user.user_id, owner_context
            ):
                continue
            (allowed if decision == "ALLOWED" else denied).add(project_id)
        return allowed - denied

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
                self._sessions.compromise_family(
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
                self._sessions.expire_if_due(
                    db,
                    old,
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
            replacement, refresh_token = self._sessions.rotate(
                db,
                old,
                credential,
                audit_context,
                actor_id=user.user_id,
                operation_id="refresh_platform_session",
                now=now,
            )
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
                    if (
                        context.project_id is not None
                        and role_code != "ROLE-PLATFORM-ADMIN"
                        and not self._has_matching_project_duty(
                            db,
                            identity.user.user_id,
                            context.project_id,
                            binding_role_id,
                        )
                    ):
                        # Project-scoped realtime authorization is the intersection of
                        # the effective UserRoleBinding and the current project duty.
                        # Merely being a member of the project is insufficient: the
                        # ProjectMember duty must carry the same role as the binding.
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
        """拒绝权限前统一写入安全审计, 同时禁止提交调用方未完成的命令状态。"""
        error = PlatformError(
            title="Permission denied",
            detail="The current identity is not permitted to perform this operation.",
            status=403,
            code="AUTH_PERMISSION_DENIED",
        )
        if db is not None:
            # 授权可能发生在调用方已经claim幂等键或锁定目标的事务中。拒绝时必须先
            # 回滚整笔命令, 再用独立审计事务落证据; 禁止把未完成幂等记录提交成毒化状态。
            actor_id = identity.user.user_id
            session_id = identity.session.session_id
            db.rollback()
        else:
            actor_id = identity.user.user_id
            session_id = identity.session.session_id
        with self._session_factory() as audit_db:
            self._audit.append(
                audit_db,
                audit_context,
                action="PERMISSION_DENIED",
                operation_id=operation_id,
                result_code=error.code,
                actor_id=actor_id,
                target_user_id=actor_id,
                session_id=session_id,
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
            if self._sessions.revoke(
                    db,
                    refresh_session,
                    "LOGOUT",
                    utc_now(),
                    audit_context,
                    actor_id=user_id,
                    target_user_id=user_id,
                    operation_id="logout_platform_user",
                ):
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
            record, replay = self._idempotency.claim_change_password(
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
                    code="AUTH_CURRENT_PASSWORD_INVALID",
                )
            try:
                self._passwords.validate(new_password, identity.user.username or "")
            except PasswordPolicyError as error:
                raise PlatformError(
                    title="New password is invalid",
                    detail=str(error),
                    status=400,
                    code="AUTH_PASSWORD_POLICY_VIOLATION",
                ) from error
            if self._passwords.verify(credential.password_hash, new_password):
                raise PlatformError(
                    title="New password is unchanged",
                    detail="The new password must differ from the current password.",
                    status=400,
                    code="AUTH_PASSWORD_UNCHANGED",
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
            self._sessions.revoke_active_for_credential(
                db,
                credential,
                "PASSWORD_CHANGED",
                now,
                audit_context,
                actor_id=identity.user.user_id,
                operation_id="change_current_user_password",
            )
            self._idempotency.complete(record, 204, None)
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
        was_due_candidate = (
            refresh_session.lifecycle_status == ACTIVE and refresh_session.expires_at <= now
        )
        if was_due_candidate and not for_update:
            locked_session = db.scalar(
                select(AuthRefreshSession)
                .where(AuthRefreshSession.session_id == claims.session_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if locked_session is None:
                raise self._session_revoked()
            refresh_session = locked_session
            # 竞争请求等待首个到期事务提交后会看到终态; 该转换已经有唯一审计,
            # 后到请求只返回撤销语义, 不重复写 SESSION_REVOKED。
            if refresh_session.lifecycle_status != ACTIVE:
                raise self._session_revoked()
        if self._sessions.expire_if_due(
            db,
            refresh_session,
            now,
            audit_context,
            actor_id=user.user_id,
            operation_id=operation_id,
        ):
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
        self._sessions.revoke_active_for_credential(
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
