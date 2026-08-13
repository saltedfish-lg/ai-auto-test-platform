"""SQLAlchemy mappings for the current P1 authentication tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as MySQLBigInteger,
)
from sqlalchemy.dialects.mysql import (
    BINARY as MySQLBinary,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as MySQLInteger,
)
from sqlalchemy.dialects.mysql import (
    SMALLINT as MySQLSmallInteger,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlatformUser(Base):
    __tablename__ = "atp_user"
    user_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(191), unique=True)
    role_binding_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_role_binding.role_binding_id")
    )
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Admin(Base):
    __tablename__ = "atp_admin"
    admin_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(191), unique=True)
    user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    lifecycle_status: Mapped[str] = mapped_column(String(11))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Role(Base):
    __tablename__ = "atp_role"
    role_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    role_code: Mapped[str | None] = mapped_column(String(191), unique=True)
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PermissionCode(Base):
    __tablename__ = "atp_permission_code"
    permission_code_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    permission_code: Mapped[str] = mapped_column(String(191), unique=True)
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RolePermission(Base):
    __tablename__ = "atp_role_permission"
    role_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_role.role_id"), primary_key=True
    )
    permission_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_permission_code.permission_code_id"), primary_key=True
    )
    decision: Mapped[str] = mapped_column(String(16))
    conditions: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class UserRoleBinding(Base):
    __tablename__ = "atp_user_role_binding"
    binding_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    role_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_role.role_id"))
    project_id: Mapped[str | None] = mapped_column(String(26))
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)
    row_version: Mapped[int] = mapped_column(BigInteger)


class DataScopeGrant(Base):
    __tablename__ = "atp_data_scope_grant"
    grant_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    binding_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_user_role_binding.binding_id")
    )
    scope_type: Mapped[str] = mapped_column(String(32))
    scope_id: Mapped[str | None] = mapped_column(String(26))
    permission_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ProjectMember(Base):
    __tablename__ = "atp_project_member"
    project_member_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    role_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_role.role_id"))
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Project(Base):
    __tablename__ = "atp_project"
    project_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_code: Mapped[str | None] = mapped_column(String(191), unique=True)
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RoleBinding(Base):
    __tablename__ = "atp_role_binding"
    role_binding_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26))
    subject_id: Mapped[str | None] = mapped_column(String(26))
    role_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_role.role_id"))
    effective_at: Mapped[str | None] = mapped_column(String(191))
    user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    audit_log_id: Mapped[str | None] = mapped_column(String(26))
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PlatformUserCredential(Base):
    __tablename__ = "atp_platform_user_credential"
    credential_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"), unique=True)
    credential_type: Mapped[str] = mapped_column(String(16))
    password_hash: Mapped[str] = mapped_column(String(512))
    password_algorithm: Mapped[str] = mapped_column(String(32))
    credential_version: Mapped[int] = mapped_column(BigInteger)
    force_password_change: Mapped[bool]
    failed_login_count: Mapped[int] = mapped_column(Integer)
    failure_window_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_successful_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime)
    lifecycle_status: Mapped[str] = mapped_column(String(16))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))


class AuthRefreshSession(Base):
    __tablename__ = "atp_auth_refresh_session"
    session_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    credential_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_platform_user_credential.credential_id")
    )
    family_id: Mapped[str] = mapped_column(String(26))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    session_version: Mapped[int] = mapped_column(BigInteger)
    credential_version: Mapped[int] = mapped_column(BigInteger)
    lifecycle_status: Mapped[str] = mapped_column(String(16))
    issued_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(64))
    replaced_by_session_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_auth_refresh_session.session_id")
    )
    client_context_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AuthSecurityAudit(Base):
    __tablename__ = "atp_auth_security_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    action: Mapped[str] = mapped_column(String(32))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_id: Mapped[str | None] = mapped_column(String(26))
    target_user_id: Mapped[str | None] = mapped_column(String(26))
    session_id: Mapped[str | None] = mapped_column(String(26))
    result_code: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(LargeBinary(32))


class IdempotencyRecord(Base):
    __tablename__ = "atp_idempotency_record"
    idempotency_key: Mapped[str] = mapped_column(String(191), primary_key=True)
    contract_version: Mapped[int] = mapped_column(MySQLSmallInteger(unsigned=True), default=2)
    principal_id: Mapped[str | None] = mapped_column(String(26))
    operation_id: Mapped[str] = mapped_column(String(191))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AuthSourceRateLimit(Base):
    __tablename__ = "atp_auth_source_rate_limit"
    source_key_hash: Mapped[bytes] = mapped_column(MySQLBinary(32), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    request_count: Mapped[int] = mapped_column(MySQLInteger(unsigned=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    row_version: Mapped[int] = mapped_column(MySQLBigInteger(unsigned=True))


class OutboxEvent(Base):
    __tablename__ = "atp_outbox_event"
    event_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String(26))
    sequence: Mapped[int] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(191))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    attempt_count: Mapped[int] = mapped_column(Integer)
