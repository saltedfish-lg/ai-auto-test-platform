"""Explicit, transactional default-admin bootstrap after V3 -> V4 -> V5."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.models import (
    Admin,
    DataScopeGrant,
    IdempotencyRecord,
    OutboxEvent,
    PlatformUser,
    PlatformUserCredential,
    Role,
    RoleBinding,
    UserRoleBinding,
)
from platform_api.security import PasswordService, new_ulid, utc_now

BOOTSTRAP_KEY = "SYSTEM_BOOTSTRAP_ADMIN_V1"
SUPER_ADMIN_ROLE = "ROLE-SUPER-ADMIN"


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    status: Literal["INITIALIZED", "ALREADY_INITIALIZED"]
    user_id: str | None
    admin_id: str | None
    password_algorithm: str

    def safe_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdminBootstrapService:
    def __init__(
        self, session_factory: sessionmaker[Session], password_service: PasswordService
    ) -> None:
        self._session_factory = session_factory
        self._passwords = password_service

    def bootstrap(self, password: str, correlation_id: str) -> BootstrapResult:
        self._passwords.validate(password, "admin")
        try:
            with self._session_factory.begin() as db:
                existing_record = db.get(IdempotencyRecord, BOOTSTRAP_KEY)
                existing_user = db.scalar(
                    select(PlatformUser).where(PlatformUser.username == "admin")
                )
                if existing_record is not None or existing_user is not None:
                    return BootstrapResult("ALREADY_INITIALIZED", None, None, "ARGON2ID_V19")
                now = utc_now()
                db.add(
                    IdempotencyRecord(
                        idempotency_key=BOOTSTRAP_KEY,
                        operation_id="bootstrap_admin",
                        request_hash=hashlib.sha256(b"bootstrap-admin-v1").hexdigest(),
                        response_status=200,
                        response_json=None,
                        expires_at=now + timedelta(days=36500),
                    )
                )
                db.flush()
                role = db.scalar(select(Role).where(Role.role_code == SUPER_ADMIN_ROLE))
                if role is None or role.lifecycle_status != "ACTIVE":
                    raise RuntimeError("ROLE-SUPER-ADMIN seed is missing or inactive")
                user_id = new_ulid()
                admin_id = new_ulid()
                credential_id = new_ulid()
                binding_id = new_ulid()
                user = PlatformUser(
                    user_id=user_id,
                    username="admin",
                    role_binding_id=None,
                    lifecycle_status="ACTIVE",
                    display_name="Platform Administrator",
                    row_version=1,
                    created_at=now,
                    updated_at=now,
                    created_by=user_id,
                    updated_by=user_id,
                    extension_json=None,
                )
                db.add(user)
                db.flush()
                db.add(
                    RoleBinding(
                        role_binding_id=binding_id,
                        project_id=None,
                        subject_id=user_id,
                        role_id=role.role_id,
                        effective_at=now.replace(tzinfo=UTC).isoformat(),
                        user_id=user_id,
                        audit_log_id=None,
                        lifecycle_status="ACTIVE",
                        display_name="Default admin super-admin binding",
                        row_version=1,
                        created_at=now,
                        updated_at=now,
                        created_by=user_id,
                        updated_by=user_id,
                        extension_json=None,
                    )
                )
                db.flush()
                user.role_binding_id = binding_id
                db.add(
                    UserRoleBinding(
                        binding_id=binding_id,
                        user_id=user_id,
                        role_id=role.role_id,
                        project_id=None,
                        valid_from=now,
                        valid_to=None,
                        row_version=0,
                    )
                )
                db.flush()
                db.add_all(
                    [
                        Admin(
                            admin_id=admin_id,
                            username="admin",
                            user_id=user_id,
                            lifecycle_status="ACTIVE",
                            display_name="Platform Administrator",
                            row_version=1,
                            created_at=now,
                            updated_at=now,
                            created_by=user_id,
                            updated_by=user_id,
                            extension_json=None,
                        ),
                        PlatformUserCredential(
                            credential_id=credential_id,
                            user_id=user_id,
                            credential_type="PASSWORD",
                            password_hash=self._passwords.hash(password),
                            password_algorithm="ARGON2ID_V19",
                            credential_version=1,
                            force_password_change=True,
                            failed_login_count=0,
                            failure_window_started_at=None,
                            locked_until=None,
                            last_failed_at=None,
                            last_successful_login_at=None,
                            password_changed_at=now,
                            lifecycle_status="ACTIVE",
                            row_version=0,
                            created_at=now,
                            updated_at=now,
                            created_by=user_id,
                            updated_by=user_id,
                        ),
                        DataScopeGrant(
                            grant_id=new_ulid(),
                            binding_id=binding_id,
                            scope_type="PLATFORM_ALL",
                            scope_id=None,
                            permission_code=None,
                            created_at=now,
                        ),
                    ]
                )
                for event_type, aggregate_id, object_id in (
                    ("user.active", user_id, user_id),
                    ("admin.active", admin_id, admin_id),
                    ("role_binding.active", binding_id, binding_id),
                ):
                    db.add(
                        self._outbox_event(
                            event_type,
                            aggregate_id,
                            object_id,
                            correlation_id,
                            user_id,
                            now,
                        )
                    )
        except IntegrityError:
            with self._session_factory() as db:
                existing_record = db.get(IdempotencyRecord, BOOTSTRAP_KEY)
                existing_user = db.scalar(
                    select(PlatformUser).where(PlatformUser.username == "admin")
                )
                if existing_record is not None or existing_user is not None:
                    return BootstrapResult("ALREADY_INITIALIZED", None, None, "ARGON2ID_V19")
            raise
        return BootstrapResult("INITIALIZED", user_id, admin_id, "ARGON2ID_V19")

    @staticmethod
    def _outbox_event(
        event_type: str,
        aggregate_id: str,
        object_id: str,
        correlation_id: str,
        actor_id: str,
        now: datetime,
    ) -> OutboxEvent:
        occurred = now
        event_id = new_ulid()
        object_field = {
            "user.active": "user_id",
            "admin.active": "admin_id",
            "role_binding.active": "role_binding_id",
        }[event_type]
        envelope = {
            "event_id": event_id,
            "event_type": event_type,
            "event_version": "1.0.0",
            "occurred_at": occurred.replace(tzinfo=UTC).isoformat(),
            "aggregate_id": aggregate_id,
            "sequence": 1,
            "correlation_id": correlation_id,
            "causation_id": BOOTSTRAP_KEY,
            "project_id": None,
            "payload": {
                object_field: object_id,
                "from_state": None,
                "to_state": "ACTIVE",
                "expected_version": 0,
                "new_version": 1,
                "changed_by": actor_id,
                "change_summary": {"reason": "SYSTEM_BOOTSTRAP_ADMIN_V1"},
            },
        }
        return OutboxEvent(
            event_id=event_id,
            aggregate_id=aggregate_id,
            sequence=1,
            event_type=event_type,
            payload_json=envelope,
            occurred_at=occurred,
            published_at=None,
            attempt_count=0,
        )
