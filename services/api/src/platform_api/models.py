"""SQLAlchemy mappings for the current platform tables used by the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
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
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    role_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_role.role_id"))
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ProjectAudit(Base):
    """Append-only project command evidence owned by the caller transaction."""

    __tablename__ = "atp_project_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26))
    project_code: Mapped[str] = mapped_column(String(191))
    action: Mapped[str] = mapped_column(String(32))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    participant_user_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_user.user_id")
    )
    required_permission: Mapped[str] = mapped_column(String(128))
    scope_decision: Mapped[str] = mapped_column(String(64))
    previous_status: Mapped[str | None] = mapped_column(String(17))
    new_status: Mapped[str | None] = mapped_column(String(17))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


class Project(Base):
    __tablename__ = "atp_project"
    project_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_code: Mapped[str] = mapped_column(String(191), unique=True)
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Environment(Base):
    __tablename__ = "atp_environment"
    environment_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    environment_code: Mapped[str | None] = mapped_column(String(191))
    lifecycle_status: Mapped[str] = mapped_column(String(11))
    enablement_state: Mapped[str] = mapped_column(String(8))
    accessibility_state: Mapped[str] = mapped_column(String(11))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class EnvironmentAudit(Base):
    __tablename__ = "atp_environment_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    environment_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_environment.environment_id")
    )
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    environment_code: Mapped[str] = mapped_column(String(191))
    action: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    required_permission: Mapped[str] = mapped_column(String(128))
    scope_decision: Mapped[str] = mapped_column(String(64))
    previous_status: Mapped[str | None] = mapped_column(String(11))
    new_status: Mapped[str | None] = mapped_column(String(11))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


class BusinessTerminal(Base):
    __tablename__ = "atp_business_terminal"
    __table_args__ = (
        UniqueConstraint(
            "business_terminal_id",
            "project_id",
            "environment_id",
            name="uq_atp_business_terminal_scope",
        ),
        ForeignKeyConstraint(
            ["current_published_revision_id", "business_terminal_id"],
            [
                "atp_environment_terminal_access_revision.environment_terminal_access_revision_id",
                "atp_environment_terminal_access_revision.business_terminal_id",
            ],
            name="fk_atp_business_terminal_current_revision",
        ),
    )
    business_terminal_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    terminal_code: Mapped[str] = mapped_column(String(191))
    environment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_environment.environment_id")
    )
    terminal_type: Mapped[str] = mapped_column(String(16))
    current_published_revision_id: Mapped[str | None] = mapped_column(String(26))
    lifecycle_status: Mapped[str] = mapped_column(String(11))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AutomationAsset(Base):
    __tablename__ = "atp_automation_asset"
    __table_args__ = (
        UniqueConstraint("automation_asset_id", "project_id", name="uq_atp_automation_asset_scope"),
    )
    automation_asset_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class LoginStrategy(Base):
    __tablename__ = "atp_login_strategy"
    __table_args__ = (
        UniqueConstraint("login_strategy_id", "project_id", name="uq_atp_login_strategy_scope"),
        ForeignKeyConstraint(
            ["automation_asset_id", "project_id"],
            ["atp_automation_asset.automation_asset_id", "atp_automation_asset.project_id"],
            name="fk_atp_login_strategy_automation_asset_scope",
        ),
    )
    login_strategy_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    automation_asset_id: Mapped[str] = mapped_column(String(26))
    local_storage_presets: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    refresh_after_local_storage: Mapped[bool] = mapped_column(Boolean)
    captcha_policy: Mapped[str] = mapped_column(String(24))
    captcha_request_header_name: Mapped[str | None] = mapped_column(String(191))
    captcha_request_header_value: Mapped[str | None] = mapped_column(String(191))
    captcha_response_header_name: Mapped[str | None] = mapped_column(String(191))
    session_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class TerminalAccessRevision(Base):
    __tablename__ = "atp_environment_terminal_access_revision"
    __table_args__ = (
        UniqueConstraint(
            "business_terminal_id",
            "revision_no",
            name="uq_atp_terminal_access_revision_business",
        ),
        UniqueConstraint(
            "environment_terminal_access_revision_id",
            "business_terminal_id",
            name="uq_atp_terminal_access_revision_owner",
        ),
        ForeignKeyConstraint(
            ["business_terminal_id", "project_id", "environment_id"],
            [
                "atp_business_terminal.business_terminal_id",
                "atp_business_terminal.project_id",
                "atp_business_terminal.environment_id",
            ],
            name="fk_atp_terminal_access_revision_terminal_scope",
        ),
        ForeignKeyConstraint(
            ["login_strategy_id", "project_id"],
            ["atp_login_strategy.login_strategy_id", "atp_login_strategy.project_id"],
            name="fk_atp_terminal_access_revision_login_strategy_scope",
        ),
    )
    environment_terminal_access_revision_id: Mapped[str] = mapped_column(
        String(26), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    environment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_environment.environment_id")
    )
    business_terminal_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_business_terminal.business_terminal_id")
    )
    revision_no: Mapped[int] = mapped_column(BigInteger)
    entry_url: Mapped[str] = mapped_column(String(2048))
    login_url: Mapped[str | None] = mapped_column(String(2048))
    login_strategy_id: Mapped[str | None] = mapped_column(String(26))
    login_prerequisites: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    network_requirements: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    lifecycle_status: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class BusinessTerminalAudit(Base):
    __tablename__ = "atp_business_terminal_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    business_terminal_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_business_terminal.business_terminal_id")
    )
    environment_id: Mapped[str] = mapped_column(String(26))
    project_id: Mapped[str] = mapped_column(String(26))
    action: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    required_permission: Mapped[str] = mapped_column(String(128))
    previous_status: Mapped[str | None] = mapped_column(String(11))
    new_status: Mapped[str | None] = mapped_column(String(11))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


class TestAccount(Base):
    __tablename__ = "atp_test_account"
    __table_args__ = (
        ForeignKeyConstraint(
            ["environment_id", "project_id"],
            ["atp_environment.environment_id", "atp_environment.project_id"],
            name="fk_atp_test_account_environment_scope",
        ),
    )
    test_account_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    environment_id: Mapped[str] = mapped_column(String(26))
    account_identifier: Mapped[str] = mapped_column(String(191))
    sso_identity_id: Mapped[str | None] = mapped_column(String(26))
    login_qualification_id: Mapped[str | None] = mapped_column(String(26))
    lifecycle_status: Mapped[str] = mapped_column(String(18))
    credential_state: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class CredentialRevision(Base):
    __tablename__ = "atp_credential_revision"
    credential_revision_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    test_account_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_test_account.test_account_id")
    )
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    revision_no: Mapped[int] = mapped_column(BigInteger)
    secret_ref: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    superseded_by_revision_id: Mapped[str | None] = mapped_column(String(26))
    lifecycle_status: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class TestAccountSecret(Base):
    """Encrypted credential bytes; never projected through the public API."""

    __tablename__ = "atp_test_account_secret"
    credential_revision_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_credential_revision.credential_revision_id"), primary_key=True
    )
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary(16412))
    key_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AccountMappingRevision(Base):
    __tablename__ = "atp_account_mapping_revision"
    account_mapping_revision_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    test_account_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_test_account.test_account_id")
    )
    environment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_environment.environment_id")
    )
    business_terminal_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_business_terminal.business_terminal_id")
    )
    lifecycle_status: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class TestAccountAudit(Base):
    __tablename__ = "atp_test_account_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    test_account_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_test_account.test_account_id")
    )
    project_id: Mapped[str] = mapped_column(String(26))
    environment_id: Mapped[str] = mapped_column(String(26))
    business_terminal_ids: Mapped[list[str]] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    required_permission: Mapped[str] = mapped_column(String(128))
    previous_status: Mapped[str | None] = mapped_column(String(18))
    new_status: Mapped[str | None] = mapped_column(String(18))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    credential_changed: Mapped[bool] = mapped_column(Boolean)
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


class Runner(Base):
    __tablename__ = "atp_runner"
    __table_args__ = (
        UniqueConstraint("project_id", "runner_code", name="uq_atp_runner_business"),
        UniqueConstraint("runner_id", "project_id", name="uq_atp_runner_project_scope"),
    )
    runner_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    runner_code: Mapped[str] = mapped_column(String(191))
    health_status: Mapped[str] = mapped_column(String(9))
    scheduling_status: Mapped[str] = mapped_column(String(20))
    resource_status: Mapped[str] = mapped_column(String(20))
    version_compatibility: Mapped[str] = mapped_column(String(20))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    registered_at: Mapped[datetime] = mapped_column(DateTime)
    runtime_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    registration_status: Mapped[str] = mapped_column(String(12))
    connection_status: Mapped[str] = mapped_column(String(12))
    enable_status: Mapped[str] = mapped_column(String(8))
    project_binding_status: Mapped[str] = mapped_column(String(7))
    lifecycle_status: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RunnerEnrollment(Base):
    __tablename__ = "atp_runner_enrollment"
    enrollment_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    runner_code: Mapped[str] = mapped_column(String(191))
    display_name: Mapped[str | None] = mapped_column(String(255))
    credential_hash: Mapped[bytes] = mapped_column(MySQLBinary(32), unique=True)
    enrollment_status: Mapped[str] = mapped_column(String(8))
    consumed_runner_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_runner.runner_id")
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    updated_by: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    reason: Mapped[str] = mapped_column(String(1000))


class RunnerAgent(Base):
    __tablename__ = "atp_runner_agent"
    __table_args__ = (
        ForeignKeyConstraint(
            ["runner_id", "project_id"],
            ["atp_runner.runner_id", "atp_runner.project_id"],
            name="fk_atp_runner_agent_runner_scope",
        ),
    )
    runner_agent_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    runner_id: Mapped[str] = mapped_column(String(26), unique=True)
    token_hash: Mapped[bytes] = mapped_column(MySQLBinary(32), unique=True)
    token_status: Mapped[str] = mapped_column(String(7))
    token_version: Mapped[int] = mapped_column(BigInteger)
    machine_fingerprint_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))
    agent_version: Mapped[str] = mapped_column(String(64))
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime)
    credential_rotated_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    lifecycle_status: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RunnerCapability(Base):
    __tablename__ = "atp_runner_capability"
    __table_args__ = (
        ForeignKeyConstraint(
            ["runner_id", "project_id"],
            ["atp_runner.runner_id", "atp_runner.project_id"],
            name="fk_atp_runner_capability_runner_scope",
        ),
        UniqueConstraint("runner_id", "capability_code", name="uq_atp_runner_capability_business"),
    )
    runner_capability_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    runner_id: Mapped[str] = mapped_column(String(26))
    capability_code: Mapped[str] = mapped_column(String(64))
    capability_type: Mapped[str] = mapped_column(String(16))
    availability_status: Mapped[str] = mapped_column(String(14))
    validation_status: Mapped[str] = mapped_column(String(16))
    observed_version: Mapped[str | None] = mapped_column(String(64))
    observed_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reported_at: Mapped[datetime] = mapped_column(DateTime)
    lifecycle_status: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ExecutionSlot(Base):
    """Existing Runner-owned slot used only as a validated lease resource identity."""

    __tablename__ = "atp_execution_slot"
    execution_slot_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26))
    runner_id: Mapped[str | None] = mapped_column(String(26))
    lifecycle_status: Mapped[str] = mapped_column(String(17))


class RunnerAudit(Base):
    __tablename__ = "atp_runner_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    runner_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_runner.runner_id"))
    enrollment_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_runner_enrollment.enrollment_id")
    )
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    action: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_type: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(26))
    required_permission: Mapped[str | None] = mapped_column(String(128))
    previous_status: Mapped[str | None] = mapped_column(String(16))
    new_status: Mapped[str | None] = mapped_column(String(16))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    credential_changed: Mapped[bool] = mapped_column(Boolean)
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


class ExecutionAttempt(Base):
    """Minimal mapped projection used to lock an existing execution owner."""

    __tablename__ = "atp_execution_attempt"
    execution_attempt_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    execution_binding_snapshot_id: Mapped[str | None] = mapped_column(String(26))
    project_id: Mapped[str | None] = mapped_column(String(26))
    run_task_id: Mapped[str | None] = mapped_column(String(26))
    runner_id: Mapped[str] = mapped_column(String(26))
    execution_status: Mapped[str] = mapped_column(String(16))
    finalization_status: Mapped[str] = mapped_column(String(16))
    lifecycle_status: Mapped[str] = mapped_column(String(12))
    row_version: Mapped[int] = mapped_column(BigInteger)


class ProjectRuntimePolicyRevision(Base):
    __tablename__ = "atp_project_runtime_policy_revision"
    runtime_policy_revision_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    revision_no: Mapped[int] = mapped_column(BigInteger)
    browser_runtime: Mapped[str] = mapped_column(String(32))
    artifact_policy: Mapped[str] = mapped_column(String(32))
    timeout_seconds: Mapped[int] = mapped_column(Integer)
    max_steps: Mapped[int] = mapped_column(MySQLInteger(unsigned=True))
    total_exploration_timeout_seconds: Mapped[int] = mapped_column(MySQLInteger(unsigned=True))
    model_transient_retry_per_step: Mapped[int] = mapped_column(MySQLInteger(unsigned=True))
    allowed_origins: Mapped[list[str]] = mapped_column(JSON)
    authentication_redirect_origins: Mapped[list[str]] = mapped_column(JSON)
    retry_mode: Mapped[str] = mapped_column(String(32))
    network_requirement: Mapped[str] = mapped_column(String(32))
    serial_execution_policy: Mapped[str] = mapped_column(String(32))
    lifecycle_status: Mapped[str] = mapped_column(String(10))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))


class ResourceLeaseGeneration(Base):
    __tablename__ = "atp_resource_lease_generation"
    resource_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    resource_identity_hash: Mapped[bytes] = mapped_column(MySQLBinary(32), primary_key=True)
    current_generation: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ResourceLease(Base):
    __tablename__ = "atp_resource_lease"
    resource_lease_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    resource_type: Mapped[str] = mapped_column(String(16))
    resource_identity: Mapped[str] = mapped_column(String(512))
    resource_identity_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))
    owner_type: Mapped[str] = mapped_column(String(32))
    owner_id: Mapped[str] = mapped_column(String(26))
    status: Mapped[str] = mapped_column(String(8))
    acquired_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    fencing_generation: Mapped[int] = mapped_column(BigInteger)
    correlation_id: Mapped[str] = mapped_column(String(128))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ExecutionBindingSnapshot(Base):
    __tablename__ = "atp_execution_binding_snapshot"
    execution_binding_snapshot_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    execution_attempt_id: Mapped[str] = mapped_column(String(26), unique=True)
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    environment_id: Mapped[str] = mapped_column(String(26))
    business_terminal_id: Mapped[str] = mapped_column(String(26))
    terminal_access_revision_id: Mapped[str] = mapped_column(String(26))
    login_strategy_id: Mapped[str] = mapped_column(String(26))
    login_strategy_row_version: Mapped[int] = mapped_column(BigInteger)
    test_account_id: Mapped[str] = mapped_column(String(26))
    credential_revision_id: Mapped[str] = mapped_column(String(26))
    account_mapping_revision_id: Mapped[str] = mapped_column(String(26))
    runner_id: Mapped[str] = mapped_column(String(26))
    runner_row_version: Mapped[int] = mapped_column(BigInteger)
    runner_heartbeat_at: Mapped[datetime] = mapped_column(DateTime)
    runner_capability_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    runtime_policy_revision_id: Mapped[str] = mapped_column(String(26))
    identity_lease_id: Mapped[str] = mapped_column(String(26))
    identity_lease_generation: Mapped[int] = mapped_column(BigInteger)
    runner_lease_id: Mapped[str] = mapped_column(String(26))
    runner_lease_generation: Mapped[int] = mapped_column(BigInteger)
    owner_execution_identity: Mapped[str] = mapped_column(String(191))
    correlation_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(8))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(26))


class ExecutionBindingAudit(Base):
    __tablename__ = "atp_execution_binding_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    execution_binding_snapshot_id: Mapped[str | None] = mapped_column(String(26))
    project_id: Mapped[str] = mapped_column(String(26))
    execution_attempt_id: Mapped[str] = mapped_column(String(26))
    action: Mapped[str] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(26))
    previous_status: Mapped[str | None] = mapped_column(String(8))
    new_status: Mapped[str | None] = mapped_column(String(8))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    lease_generations_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


class LoginStrategyAudit(Base):
    __tablename__ = "atp_login_strategy_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    login_strategy_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_login_strategy.login_strategy_id")
    )
    automation_asset_id: Mapped[str] = mapped_column(String(26))
    project_id: Mapped[str] = mapped_column(String(26))
    action: Mapped[str] = mapped_column(String(64))
    operation_id: Mapped[str] = mapped_column(String(128))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    required_permission: Mapped[str] = mapped_column(String(128))
    previous_status: Mapped[str | None] = mapped_column(String(17))
    new_status: Mapped[str | None] = mapped_column(String(17))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


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


class ModelConfiguration(Base):
    __tablename__ = "atp_model_config"
    model_config_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    config_code: Mapped[str] = mapped_column(String(191), unique=True)
    provider_code: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(191))
    request_timeout_seconds: Mapped[int] = mapped_column(Integer)
    lifecycle_status: Mapped[str] = mapped_column(String(11))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ModelConfigurationSecret(Base):
    __tablename__ = "atp_model_config_secret"
    model_config_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_model_config.model_config_id"), primary_key=True
    )
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary(16412))
    key_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ModelCapabilityDefault(Base):
    __tablename__ = "atp_model_capability_default"
    capability_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_config_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_model_config.model_config_id"), unique=True
    )
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))


class ModelConfigurationAudit(Base):
    """Append-only model configuration and connection-test evidence."""

    __tablename__ = "atp_model_config_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    model_config_id: Mapped[str | None] = mapped_column(String(26))
    config_code: Mapped[str] = mapped_column(String(191))
    operation_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    required_permission: Mapped[str] = mapped_column(String(128))
    previous_status: Mapped[str | None] = mapped_column(String(11))
    new_status: Mapped[str | None] = mapped_column(String(11))
    result_code: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(String(1000))
    correlation_id: Mapped[str] = mapped_column(String(128))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AITask(Base):
    """AI Task aggregate root projection used by Foundation planning."""

    __tablename__ = "atp_ai_task"
    ai_task_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    ai_result_id: Mapped[str | None] = mapped_column(String(26))
    ai_call_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_ai_call.ai_call_id"))
    model_config_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_model_config.model_config_id")
    )
    status: Mapped[str] = mapped_column(String(13))
    lifecycle_status: Mapped[str] = mapped_column(String(17))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AICall(Base):
    """Model-call member owned by an AI Task aggregate."""

    __tablename__ = "atp_ai_call"
    ai_call_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    ai_task_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_ai_task.ai_task_id"))
    prompt_revision_id: Mapped[str | None] = mapped_column(String(26))
    lifecycle_status: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str | None] = mapped_column(String(255))
    row_version: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(26))
    updated_by: Mapped[str | None] = mapped_column(String(26))
    extension_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AIExplorationSession(Base):
    __tablename__ = "atp_ai_exploration_session"
    session_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    ai_task_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_ai_task.ai_task_id"), unique=True
    )
    ai_call_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_ai_call.ai_call_id"), unique=True
    )
    execution_attempt_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("atp_execution_attempt.execution_attempt_id"), unique=True
    )
    execution_binding_snapshot_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("atp_execution_binding_snapshot.execution_binding_snapshot_id"),
        unique=True,
    )
    browser_session_id: Mapped[str | None] = mapped_column(String(191))
    current_observation_id: Mapped[str | None] = mapped_column(String(26))
    current_step_sequence: Mapped[int] = mapped_column(BigInteger, default=0)
    max_steps: Mapped[int | None] = mapped_column(MySQLInteger(unsigned=True))
    total_timeout_seconds: Mapped[int | None] = mapped_column(MySQLInteger(unsigned=True))
    model_transient_retry_per_step: Mapped[int | None] = mapped_column(MySQLInteger(unsigned=True))
    row_version: Mapped[int] = mapped_column(BigInteger, default=1)
    idempotency_key: Mapped[str] = mapped_column(
        String(191), ForeignKey("atp_idempotency_record.idempotency_key"), unique=True
    )
    required_permission: Mapped[str] = mapped_column(String(128))
    permission_decision: Mapped[str] = mapped_column(String(64))
    data_scope_decision: Mapped[str] = mapped_column(String(128))
    project_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_project.project_id"))
    source_case_id: Mapped[str | None] = mapped_column(String(26))
    objective: Mapped[str] = mapped_column(String(4000))
    target_url: Mapped[str] = mapped_column(String(2048))
    lifecycle_status: Mapped[str] = mapped_column(String(16))
    resolved_model_config_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_model_config.model_config_id")
    )
    resolved_model_display_name: Mapped[str | None] = mapped_column(String(255))
    resolved_provider_code: Mapped[str] = mapped_column(String(32))
    resolved_model_name: Mapped[str] = mapped_column(String(191))
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(String(1000))
    planning_started_at: Mapped[datetime] = mapped_column(DateTime)
    planning_deadline_at: Mapped[datetime] = mapped_column(DateTime)
    total_deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AIExplorationStep(Base):
    """Ordered Browser Loop evidence owned by an AI exploration session."""

    __tablename__ = "atp_ai_exploration_step"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_atp_ai_exploration_step_sequence"),
    )
    ai_exploration_step_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_ai_exploration_session.session_id")
    )
    execution_attempt_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_execution_attempt.execution_attempt_id")
    )
    ai_call_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_ai_call.ai_call_id"))
    sequence: Mapped[int] = mapped_column(BigInteger)
    model_call_identity: Mapped[str] = mapped_column(String(191))
    observation_identity: Mapped[str] = mapped_column(String(26), unique=True)
    action_identity: Mapped[str] = mapped_column(String(26), unique=True)
    status: Mapped[str] = mapped_column(String(24))
    observation_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    action_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    action_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sanitized_reason: Mapped[str | None] = mapped_column(String(1000))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    state_version: Mapped[int] = mapped_column(BigInteger)
    identity_lease_generation: Mapped[int] = mapped_column(BigInteger)
    runner_lease_generation: Mapped[int] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AIExplorationAudit(Base):
    """Append-only lifecycle and model invocation evidence without credentials."""

    __tablename__ = "atp_ai_exploration_audit"
    audit_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("atp_ai_exploration_session.session_id")
    )
    ai_task_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_ai_task.ai_task_id"))
    ai_call_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_ai_call.ai_call_id"))
    operation_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[str] = mapped_column(String(26), ForeignKey("atp_user.user_id"))
    required_permission: Mapped[str] = mapped_column(String(128))
    permission_decision: Mapped[str] = mapped_column(String(64))
    data_scope_decision: Mapped[str] = mapped_column(String(128))
    participant_subjects: Mapped[list[str]] = mapped_column(JSON)
    model_config_id: Mapped[str] = mapped_column(String(26))
    provider_code: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(191))
    previous_status: Mapped[str | None] = mapped_column(String(16))
    new_status: Mapped[str] = mapped_column(String(16))
    result_code: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128))
    provider_request_id: Mapped[str | None] = mapped_column(String(191))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_context_hash: Mapped[bytes] = mapped_column(MySQLBinary(32))


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
