"""Transactional P1 user, credential and UserRoleBinding command service."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext, AuthenticationAuditService
from platform_api.auth_hmac import AuthHmacKeyRing
from platform_api.auth_schemas import (
    CreateUserRequest,
    CreateUserRoleBindingRequest,
    OneTimeCredentialDeliveryResource,
    ResetUserCredentialRequest,
    RevokeUserRoleBindingRequest,
    UserResource,
    UserRoleBindingResource,
    UserStateCommandRequest,
)
from platform_api.auth_service import AuthenticationService
from platform_api.errors import PlatformError
from platform_api.idempotency import IdempotencyCoordinator
from platform_api.models import (
    Admin,
    AuthRefreshSession,
    DataScopeGrant,
    PlatformUser,
    PlatformUserCredential,
    Role,
    UserRoleBinding,
)
from platform_api.security import PasswordService, new_ulid, utc_now

ACTIVE = "ACTIVE"
SUPER_ADMIN_ROLE = "ROLE-SUPER-ADMIN"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    data: OneTimeCredentialDeliveryResource
    status_code: int


class UserAdministrationService:
    """Coordinate governed user commands without persisting recoverable credentials."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        passwords: PasswordService,
        authentication: AuthenticationService,
        audit: AuthenticationAuditService,
        hmac_keys: AuthHmacKeyRing,
    ) -> None:
        self._factory = factory
        self._passwords = passwords
        self._authentication = authentication
        self._audit = audit
        self._idempotency = IdempotencyCoordinator(hmac_keys)

    def create_user(
        self,
        token: str,
        body: CreateUserRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> DeliveryResult:
        # User creation is a platform operation, while every project-scoped initial
        # Role Binding is authorized separately against its realtime target project.
        actor = self._authentication.require_permissions(
            token, "create_user", ("USER_CREATE",), audit_context
        )
        platform_bindings = [item for item in body.role_bindings if item.project_id is None]
        if platform_bindings:
            platform_required = ("ROLE_BIND",) + (
                ("PROJECT_MEMBER_MANAGE",)
                if any(item.data_scope_grants for item in platform_bindings)
                else ()
            )
            self._authentication.require_permissions(
                token, "create_user", platform_required, audit_context
            )
        for project_id in sorted(
            {item.project_id for item in body.role_bindings if item.project_id is not None}
        ):
            self._authentication.require_project_permissions(
                token,
                "create_user",
                ("ROLE_BIND", "PROJECT_MEMBER_MANAGE"),
                project_id,
                audit_context,
            )
        temporary_password: str | None = None
        with self._factory.begin() as db:
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "create_user",
                idempotency_key,
                _canonical_payload(body),
            )
            if replay:
                return DeliveryResult(
                    OneTimeCredentialDeliveryResource(
                        user=_stored_user(record.response_json),
                        delivery_status="ALREADY_DELIVERED",
                        temporary_password=None,
                    ),
                    200,
                )
            if body.username.casefold() == "admin":
                raise _admin_immutable()
            if db.scalar(
                select(PlatformUser.user_id).where(PlatformUser.username == body.username)
            ):
                raise _concurrency_conflict("The username is already in use.")
            roles = list(
                db.scalars(
                    select(Role)
                    .where(Role.role_id.in_({item.role_id for item in body.role_bindings}))
                    .order_by(Role.role_id)
                    .with_for_update()
                )
            )
            roles_by_id = {role.role_id: role for role in roles if role.lifecycle_status == ACTIVE}
            if len(roles_by_id) != len({item.role_id for item in body.role_bindings}):
                raise _not_found("One or more roles do not exist or are inactive.")
            if any(role.role_code == SUPER_ADMIN_ROLE for role in roles):
                raise _protected_binding()
            now = utc_now()
            user_id = new_ulid()
            credential_id = new_ulid()
            temporary_password = self._temporary_password(body.username)
            user = PlatformUser(
                user_id=user_id,
                username=body.username,
                role_binding_id=None,
                lifecycle_status=ACTIVE,
                display_name=body.display_name,
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
                extension_json=None,
            )
            credential = PlatformUserCredential(
                credential_id=credential_id,
                user_id=user_id,
                credential_type="PASSWORD",
                password_hash=self._passwords.hash(temporary_password),
                password_algorithm="ARGON2ID_V19",
                credential_version=1,
                force_password_change=True,
                failed_login_count=0,
                failure_window_started_at=None,
                locked_until=None,
                last_failed_at=None,
                last_successful_login_at=None,
                password_changed_at=now,
                lifecycle_status=ACTIVE,
                row_version=0,
                created_at=now,
                updated_at=now,
                created_by=actor.user.user_id,
                updated_by=actor.user.user_id,
            )
            db.add_all([user, credential])
            db.flush()
            for assignment in body.role_bindings:
                binding = UserRoleBinding(
                    binding_id=new_ulid(),
                    user_id=user_id,
                    role_id=assignment.role_id,
                    project_id=assignment.project_id,
                    valid_from=now,
                    valid_to=None,
                    row_version=0,
                )
                db.add(binding)
                db.flush()
                for grant in assignment.data_scope_grants:
                    db.add(
                        DataScopeGrant(
                            grant_id=new_ulid(),
                            binding_id=binding.binding_id,
                            scope_type=grant.scope_type,
                            scope_id=grant.scope_id,
                            permission_code=grant.permission_code,
                            created_at=now,
                        )
                    )
                self._audit.append(
                    db,
                    audit_context,
                    action="ROLE_ASSIGNED",
                    operation_id="create_user",
                    result_code=roles_by_id[assignment.role_id].role_code or assignment.role_id,
                    actor_id=actor.user.user_id,
                    target_user_id=user_id,
                )
            self._audit.append(
                db,
                audit_context,
                action="USER_CREATED",
                operation_id="create_user",
                result_code="SUCCESS",
                actor_id=actor.user.user_id,
                target_user_id=user_id,
            )
            resource = _user_resource(user)
            self._idempotency.complete(record, 201, {"user": resource.model_dump(mode="json")})
        assert temporary_password is not None
        return DeliveryResult(
            OneTimeCredentialDeliveryResource(
                user=resource,
                delivery_status="ISSUED",
                temporary_password=temporary_password,
            ),
            201,
        )

    def reset_credential(
        self,
        token: str,
        user_id: str,
        body: ResetUserCredentialRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> DeliveryResult:
        actor = self._authentication.require_permissions(
            token, "reset_user_credential", ("USER_CREATE",), audit_context
        )
        temporary_password: str | None = None
        with self._factory.begin() as db:
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "reset_user_credential",
                idempotency_key,
                _canonical_payload(body, user_id),
            )
            if replay:
                return DeliveryResult(
                    OneTimeCredentialDeliveryResource(
                        user=_stored_user(record.response_json),
                        delivery_status="ALREADY_DELIVERED",
                        temporary_password=None,
                    ),
                    200,
                )
            user = self._locked_user(db, user_id)
            self._protect_admin(db, user_id)
            credential = db.scalar(
                select(PlatformUserCredential)
                .where(PlatformUserCredential.user_id == user_id)
                .with_for_update()
            )
            if credential is None:
                raise _not_found("The platform credential does not exist.")
            if credential.row_version != body.expected_version:
                raise _concurrency_conflict()
            now = utc_now()
            temporary_password = self._temporary_password(user.username or "")
            credential.password_hash = self._passwords.hash(temporary_password)
            credential.credential_version += 1
            credential.force_password_change = True
            credential.password_changed_at = now
            credential.failed_login_count = 0
            credential.failure_window_started_at = None
            credential.locked_until = None
            credential.last_failed_at = None
            credential.row_version += 1
            self._revoke_sessions(
                db, credential, "CREDENTIAL_RESET", actor.user.user_id, audit_context
            )
            self._audit.append(
                db,
                audit_context,
                action="CREDENTIAL_RESET",
                operation_id="reset_user_credential",
                result_code="SUCCESS",
                actor_id=actor.user.user_id,
                target_user_id=user_id,
            )
            resource = _user_resource(user)
            self._idempotency.complete(record, 200, {"user": resource.model_dump(mode="json")})
        assert temporary_password is not None
        return DeliveryResult(
            OneTimeCredentialDeliveryResource(
                user=resource,
                delivery_status="ISSUED",
                temporary_password=temporary_password,
            ),
            200,
        )

    def set_user_state(
        self,
        token: str,
        user_id: str,
        body: UserStateCommandRequest,
        idempotency_key: str,
        audit_context: AuditContext,
        *,
        enable: bool,
    ) -> UserResource:
        operation_id = "enable_user" if enable else "disable_user"
        actor = self._authentication.require_permissions(
            token, operation_id, ("USER_CREATE",), audit_context
        )
        with self._factory.begin() as db:
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                operation_id,
                idempotency_key,
                _canonical_payload(body, user_id),
            )
            if replay:
                return _stored_user(record.response_json)
            user = self._locked_user(db, user_id)
            self._protect_admin(db, user_id)
            if user.row_version != body.expected_version:
                raise _concurrency_conflict()
            allowed_states = {"DISABLED", "LOCKED"} if enable else {ACTIVE}
            if user.lifecycle_status not in allowed_states:
                raise PlatformError(
                    title="Operation forbidden for user state",
                    detail="The requested user state transition is not allowed.",
                    status=403,
                    code="AUTH_OPERATION_FORBIDDEN_FOR_STATE",
                )
            user.lifecycle_status = ACTIVE if enable else "DISABLED"
            user.row_version += 1
            user.updated_at = utc_now()
            user.updated_by = actor.user.user_id
            if not enable:
                credential = db.scalar(
                    select(PlatformUserCredential)
                    .where(PlatformUserCredential.user_id == user_id)
                    .with_for_update()
                )
                if credential is not None:
                    self._revoke_sessions(
                        db, credential, "USER_DISABLED", actor.user.user_id, audit_context
                    )
            self._audit.append(
                db,
                audit_context,
                action="USER_ENABLED" if enable else "USER_DISABLED_OR_LOCKED",
                operation_id=operation_id,
                result_code="SUCCESS",
                actor_id=actor.user.user_id,
                target_user_id=user_id,
            )
            resource = _user_resource(user)
            self._idempotency.complete(record, 200, {"user": resource.model_dump(mode="json")})
            return resource

    def create_role_binding(
        self,
        token: str,
        body: CreateUserRoleBindingRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> UserRoleBindingResource:
        if body.project_id is not None:
            actor = self._authentication.require_project_permissions(
                token,
                "create_user_role_binding",
                ("ROLE_BIND", "PROJECT_MEMBER_MANAGE"),
                body.project_id,
                audit_context,
            )
        else:
            required = ("ROLE_BIND",) + (
                ("PROJECT_MEMBER_MANAGE",) if body.data_scope_grants else ()
            )
            actor = self._authentication.require_permissions(
                token, "create_user_role_binding", required, audit_context
            )
        with self._factory.begin() as db:
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "create_user_role_binding",
                idempotency_key,
                _canonical_payload(body),
            )
            if replay:
                return _stored_binding(record.response_json)
            user = self._locked_user(db, body.user_id)
            if user.row_version != body.expected_user_version:
                raise _concurrency_conflict()
            role = db.scalar(select(Role).where(Role.role_id == body.role_id).with_for_update())
            if role is None or role.lifecycle_status != ACTIVE:
                raise _not_found("The role does not exist or is inactive.")
            if role.role_code == SUPER_ADMIN_ROLE:
                raise _protected_binding()
            now = utc_now()
            current = db.scalar(
                select(UserRoleBinding.binding_id).where(
                    UserRoleBinding.user_id == body.user_id,
                    UserRoleBinding.role_id == body.role_id,
                    UserRoleBinding.project_id.is_(None)
                    if body.project_id is None
                    else UserRoleBinding.project_id == body.project_id,
                    or_(UserRoleBinding.valid_to.is_(None), UserRoleBinding.valid_to > now),
                )
            )
            if current is not None:
                raise _concurrency_conflict("An effective role binding already exists.")
            binding = UserRoleBinding(
                binding_id=new_ulid(),
                user_id=body.user_id,
                role_id=body.role_id,
                project_id=body.project_id,
                valid_from=now,
                valid_to=None,
                row_version=0,
            )
            db.add(binding)
            db.flush()
            for grant in body.data_scope_grants:
                db.add(
                    DataScopeGrant(
                        grant_id=new_ulid(),
                        binding_id=binding.binding_id,
                        scope_type=grant.scope_type,
                        scope_id=grant.scope_id,
                        permission_code=grant.permission_code,
                        created_at=now,
                    )
                )
            user.row_version += 1
            user.updated_at = now
            user.updated_by = actor.user.user_id
            self._audit.append(
                db,
                audit_context,
                action="ROLE_ASSIGNED",
                operation_id="create_user_role_binding",
                result_code=role.role_code or role.role_id,
                actor_id=actor.user.user_id,
                target_user_id=body.user_id,
            )
            resource = _binding_resource(binding)
            self._idempotency.complete(record, 201, {"binding": resource.model_dump(mode="json")})
            return resource

    def revoke_role_binding(
        self,
        token: str,
        binding_id: str,
        body: RevokeUserRoleBindingRequest,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> UserRoleBindingResource:
        # Resolve the target binding before permission evaluation so a project-scoped write
        # is authorized only by the target project's live relationships, not by an aggregate
        # permission projection from another project. Authentication still happens before lookup.
        actor, _ = self._authentication.authenticate_access(
            token, "revoke_user_role_binding", audit_context
        )
        with self._factory.begin() as db:
            record, replay = self._idempotency.claim(
                db,
                actor.user.user_id,
                "revoke_user_role_binding",
                idempotency_key,
                _canonical_payload(body, binding_id),
            )
            if replay:
                return _stored_binding(record.response_json)
            binding_hint = db.get(UserRoleBinding, binding_id)
            if binding_hint is None:
                raise _not_found("The role binding does not exist.")
            self._locked_user(db, binding_hint.user_id)
            binding = db.scalar(
                select(UserRoleBinding)
                .where(UserRoleBinding.binding_id == binding_id)
                .with_for_update()
            )
            if binding is None:
                raise _not_found("The role binding does not exist.")
            if binding.project_id is not None:
                # The target binding determines the project authorization context;
                # permissions from another project must never authorize this write.
                actor = self._authentication.require_project_permissions(
                    token,
                    "revoke_user_role_binding",
                    ("ROLE_BIND", "PROJECT_MEMBER_MANAGE"),
                    binding.project_id,
                    audit_context,
                )
            else:
                actor = self._authentication.require_permissions(
                    token, "revoke_user_role_binding", ("ROLE_BIND",), audit_context
                )
            role = db.get(Role, binding.role_id)
            if role is not None and role.role_code == SUPER_ADMIN_ROLE:
                raise _protected_binding()
            if binding.row_version != body.expected_version:
                raise _concurrency_conflict()
            if binding.valid_to is not None:
                raise PlatformError(
                    title="Role binding is already inactive",
                    detail="The role binding has already been revoked.",
                    status=403,
                    code="AUTH_OPERATION_FORBIDDEN_FOR_STATE",
                )
            binding.valid_to = utc_now()
            binding.row_version += 1
            self._audit.append(
                db,
                audit_context,
                action="ROLE_REVOKED",
                operation_id="revoke_user_role_binding",
                result_code="SUCCESS",
                actor_id=actor.user.user_id,
                target_user_id=binding.user_id,
            )
            resource = _binding_resource(binding)
            self._idempotency.complete(record, 200, {"binding": resource.model_dump(mode="json")})
            return resource

    def _temporary_password(self, username: str) -> str:
        # 固定包含两类字符, 其余字符来自密码学随机源; 密码只活到已提交响应的内存对象。
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789-_"
        while True:
            candidate = "A7" + "".join(secrets.choice(alphabet) for _ in range(30))
            try:
                self._passwords.validate(candidate, username)
            except ValueError:
                continue
            return candidate

    @staticmethod
    def _locked_user(db: Session, user_id: str) -> PlatformUser:
        user = db.scalar(
            select(PlatformUser)
            .where(PlatformUser.user_id == user_id)
            .order_by(PlatformUser.user_id)
            .with_for_update()
        )
        if user is None:
            raise _not_found("The platform user does not exist.")
        return user

    @staticmethod
    def _protect_admin(db: Session, user_id: str) -> None:
        if db.scalar(select(Admin.admin_id).where(Admin.user_id == user_id)) is not None:
            raise _admin_immutable()

    def _revoke_sessions(
        self,
        db: Session,
        credential: PlatformUserCredential,
        reason: str,
        actor_id: str,
        audit_context: AuditContext,
    ) -> None:
        now = utc_now()
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
                operation_id="reset_user_credential"
                if reason == "CREDENTIAL_RESET"
                else "disable_user",
                result_code=reason,
                actor_id=actor_id,
                target_user_id=credential.user_id,
                session_id=refresh_session.session_id,
            )


def _canonical_payload(body: BaseModel, resource_id: str | None = None) -> bytes:
    value: dict[str, object] = body.model_dump(mode="json", exclude_none=False)
    if resource_id is not None:
        value["resource_id"] = resource_id
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _user_resource(user: PlatformUser) -> UserResource:
    return UserResource(
        user_id=user.user_id,
        display_name=user.display_name,
        row_version=user.row_version,
        created_at=user.created_at,
        updated_at=user.updated_at,
        username=user.username,
        role_binding_id=user.role_binding_id,
        lifecycle_status=user.lifecycle_status,
    )


def _stored_user(value: dict[str, object] | None) -> UserResource:
    if not isinstance(value, dict) or not isinstance(value.get("user"), dict):
        raise RuntimeError("terminal idempotency user projection is invalid")
    return UserResource.model_validate(value["user"])


def _binding_resource(binding: UserRoleBinding) -> UserRoleBindingResource:
    return UserRoleBindingResource(
        binding_id=binding.binding_id,
        user_id=binding.user_id,
        role_id=binding.role_id,
        project_id=binding.project_id,
        valid_from=binding.valid_from,
        valid_to=binding.valid_to,
        row_version=binding.row_version,
    )


def _stored_binding(value: dict[str, object] | None) -> UserRoleBindingResource:
    if not isinstance(value, dict) or not isinstance(value.get("binding"), dict):
        raise RuntimeError("terminal idempotency binding projection is invalid")
    return UserRoleBindingResource.model_validate(value["binding"])


def _not_found(detail: str) -> PlatformError:
    return PlatformError(
        title="Resource not found",
        detail=detail,
        status=404,
        code="AUTH_IDENTITY_NOT_FOUND",
    )


def _concurrency_conflict(detail: str = "The expected version no longer matches.") -> PlatformError:
    return PlatformError(
        title="Concurrency conflict",
        detail=detail,
        status=409,
        code="AUTH_CONCURRENCY_CONFLICT",
    )


def _admin_immutable() -> PlatformError:
    return PlatformError(
        title="Default administrator is immutable",
        detail="The default administrator cannot be changed by this operation.",
        status=409,
        code="AUTH_ADMIN_IMMUTABLE",
    )


def _protected_binding() -> PlatformError:
    return PlatformError(
        title="Protected role binding",
        detail="The ROLE-SUPER-ADMIN binding cannot be assigned or revoked here.",
        status=409,
        code="AUTH_ROLE_BINDING_PROTECTED",
    )
