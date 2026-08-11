-- PDBR-2026.08.07-R4.2 P1 authentication contract migration.
-- This migration is additive. It must run after V3 schema and V4 RBAC seed.

CREATE TABLE atp_platform_user_credential (
    credential_id VARCHAR(26) NOT NULL,
    user_id VARCHAR(26) NOT NULL,
    credential_type VARCHAR(16) NOT NULL DEFAULT 'PASSWORD',
    password_hash VARCHAR(512) NOT NULL,
    password_algorithm VARCHAR(32) NOT NULL DEFAULT 'ARGON2ID_V19',
    credential_version BIGINT NOT NULL DEFAULT 1,
    force_password_change BOOLEAN NOT NULL DEFAULT TRUE,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    failure_window_started_at DATETIME(6),
    locked_until DATETIME(6),
    last_failed_at DATETIME(6),
    last_successful_login_at DATETIME(6),
    password_changed_at DATETIME(6) NOT NULL,
    lifecycle_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    row_version BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by VARCHAR(26),
    updated_by VARCHAR(26),
    PRIMARY KEY (credential_id),
    CONSTRAINT uq_atp_platform_user_credential_user UNIQUE (user_id),
    CONSTRAINT ck_atp_platform_user_credential_type CHECK (credential_type IN ('PASSWORD')),
    CONSTRAINT ck_atp_platform_user_credential_algorithm CHECK (password_algorithm IN ('ARGON2ID_V19')),
    CONSTRAINT ck_atp_platform_user_credential_version CHECK (credential_version >= 1),
    CONSTRAINT ck_atp_platform_user_credential_failed_count CHECK (failed_login_count >= 0 AND failed_login_count <= 5),
    CONSTRAINT ck_atp_platform_user_credential_lifecycle CHECK (lifecycle_status IN ('ACTIVE', 'REVOKED')),
    CONSTRAINT ck_atp_platform_user_credential_row_version CHECK (row_version >= 0)
) ENGINE=InnoDB CHARSET=utf8mb4;

CREATE TABLE atp_auth_refresh_session (
    session_id VARCHAR(26) NOT NULL,
    credential_id VARCHAR(26) NOT NULL,
    family_id VARCHAR(26) NOT NULL,
    token_hash BINARY(32) NOT NULL,
    session_version BIGINT NOT NULL DEFAULT 1,
    credential_version BIGINT NOT NULL,
    lifecycle_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    issued_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    last_used_at DATETIME(6),
    rotated_at DATETIME(6),
    revoked_at DATETIME(6),
    revoke_reason VARCHAR(64),
    replaced_by_session_id VARCHAR(26),
    client_context_hash BINARY(32),
    row_version BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (session_id),
    CONSTRAINT uq_atp_auth_refresh_session_token_hash UNIQUE (token_hash),
    CONSTRAINT ck_atp_auth_refresh_session_version CHECK (session_version >= 1),
    CONSTRAINT ck_atp_auth_refresh_session_credential_version CHECK (credential_version >= 1),
    CONSTRAINT ck_atp_auth_refresh_session_lifecycle CHECK (lifecycle_status IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED', 'COMPROMISED')),
    CONSTRAINT ck_atp_auth_refresh_session_expiry CHECK (expires_at > issued_at),
    CONSTRAINT ck_atp_auth_refresh_session_row_version CHECK (row_version >= 0),
    CONSTRAINT ck_atp_auth_refresh_session_rotation CHECK ((lifecycle_status = 'ROTATED' AND rotated_at IS NOT NULL AND replaced_by_session_id IS NOT NULL) OR lifecycle_status <> 'ROTATED'),
    CONSTRAINT ck_atp_auth_refresh_session_revocation CHECK (lifecycle_status NOT IN ('REVOKED', 'COMPROMISED') OR revoked_at IS NOT NULL)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_platform_user_credential
    ADD CONSTRAINT fk_atp_platform_user_credential_user
    FOREIGN KEY (user_id) REFERENCES atp_user (user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_auth_refresh_session
    ADD CONSTRAINT fk_atp_auth_refresh_session_credential
    FOREIGN KEY (credential_id) REFERENCES atp_platform_user_credential (credential_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_auth_refresh_session
    ADD CONSTRAINT fk_atp_auth_refresh_session_replacement
    FOREIGN KEY (replaced_by_session_id) REFERENCES atp_auth_refresh_session (session_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX ix_atp_auth_refresh_session_credential_status
    ON atp_auth_refresh_session (credential_id, lifecycle_status, expires_at);

CREATE INDEX ix_atp_auth_refresh_session_family_status
    ON atp_auth_refresh_session (family_id, lifecycle_status);
