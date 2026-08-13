-- Living Authority P1 remaining authentication closure.
-- Additive migration after immutable V3/V4/V5/V6.

CREATE TABLE atp_auth_source_rate_limit (
    source_key_hash BINARY(32) NOT NULL,
    operation_id VARCHAR(32) NOT NULL,
    window_started_at DATETIME(6) NOT NULL,
    request_count INT UNSIGNED NOT NULL DEFAULT 1,
    expires_at DATETIME(6) NOT NULL,
    row_version BIGINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (source_key_hash, operation_id, window_started_at),
    CONSTRAINT ck_atp_auth_source_rate_limit_operation
        CHECK (operation_id IN ('login_platform_user', 'refresh_platform_session')),
    CONSTRAINT ck_atp_auth_source_rate_limit_count
        CHECK (
            (operation_id = 'login_platform_user' AND request_count BETWEEN 1 AND 61)
            OR (operation_id = 'refresh_platform_session' AND request_count BETWEEN 1 AND 301)
        ),
    CONSTRAINT ck_atp_auth_source_rate_limit_expiry
        CHECK (expires_at = DATE_ADD(window_started_at, INTERVAL 300 SECOND)),
    CONSTRAINT ck_atp_auth_source_rate_limit_row_version
        CHECK (row_version >= 0)
) ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_atp_auth_source_rate_limit_expiry
    ON atp_auth_source_rate_limit (expires_at);

CREATE INDEX ix_atp_user_role_binding_current_lookup
    ON atp_user_role_binding (user_id, role_id, project_id, valid_to);

ALTER TABLE atp_idempotency_record
    ADD COLUMN contract_version SMALLINT UNSIGNED NOT NULL DEFAULT 1 AFTER idempotency_key,
    ADD COLUMN principal_id VARCHAR(26) NULL AFTER contract_version,
    ADD COLUMN completed_at DATETIME(6) NULL AFTER response_json,
    ADD INDEX ix_atp_idempotency_record_principal_operation_expiry
        (principal_id, operation_id, expires_at),
    ADD INDEX ix_atp_idempotency_record_expiry (expires_at),
    ADD CONSTRAINT ck_atp_idempotency_record_contract_version
        CHECK (contract_version IN (1, 2)),
    ADD CONSTRAINT ck_atp_idempotency_change_password_terminal
        CHECK (
            contract_version = 1
            OR operation_id <> 'change_current_user_password'
            OR (
                principal_id IS NOT NULL
                AND response_json IS NULL
                AND (
                    (response_status IS NULL AND completed_at IS NULL)
                    OR (
                        response_status = 204
                        AND completed_at IS NOT NULL
                        AND expires_at > completed_at
                    )
                )
            )
        );

-- Existing V3-V6 rows retain contract_version=1. New writes fail closed into the
-- V7 contract even if an application insert accidentally omits the column.
ALTER TABLE atp_idempotency_record
    ALTER COLUMN contract_version SET DEFAULT 2;

ALTER TABLE atp_auth_security_audit
    ADD CONSTRAINT ck_atp_auth_security_audit_action
        CHECK (
            action IN (
                'LOGIN_SUCCEEDED',
                'LOGIN_FAILED',
                'REFRESH_SUCCEEDED',
                'REFRESH_FAILED',
                'LOGOUT',
                'PASSWORD_CHANGED',
                'CREDENTIAL_RESET',
                'SESSION_REVOKED',
                'USER_CREATED',
                'USER_ENABLED',
                'USER_DISABLED_OR_LOCKED',
                'ROLE_ASSIGNED',
                'ROLE_REVOKED',
                'PERMISSION_DENIED'
            )
        );
