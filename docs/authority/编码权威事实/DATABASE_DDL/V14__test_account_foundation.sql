-- Test Account Foundation: Environment-scoped login identities, immutable terminal
-- mapping revisions, encrypted credential revisions, audit, and outbox-ready lifecycle.

ALTER TABLE atp_test_account
    DROP FOREIGN KEY fk_atp_test_account_project_id,
    DROP FOREIGN KEY fk_atp_test_account_sso_identity_id,
    DROP FOREIGN KEY fk_atp_test_account_login_qualification_id;

ALTER TABLE atp_test_account
    DROP INDEX uq_atp_test_account_business,
    MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN environment_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN account_identifier VARCHAR(191) NOT NULL,
    MODIFY COLUMN sso_identity_id VARCHAR(26) NULL,
    MODIFY COLUMN login_qualification_id VARCHAR(26) NULL,
    ADD CONSTRAINT uq_atp_test_account_business
        UNIQUE (project_id, environment_id, account_identifier),
    ADD CONSTRAINT uq_atp_test_account_project_scope
        UNIQUE (test_account_id, project_id),
    ADD CONSTRAINT uq_atp_test_account_environment_scope
        UNIQUE (test_account_id, project_id, environment_id),
    ADD INDEX ix_atp_test_account_project_environment_status
        (project_id, environment_id, lifecycle_status);

ALTER TABLE atp_test_account
    ADD CONSTRAINT fk_atp_test_account_project_id
        FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_test_account_environment_scope
        FOREIGN KEY (environment_id, project_id)
        REFERENCES atp_environment (environment_id, project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_test_account_sso_identity_id
        FOREIGN KEY (sso_identity_id) REFERENCES atp_sso_identity (sso_identity_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_test_account_login_qualification_id
        FOREIGN KEY (login_qualification_id) REFERENCES atp_login_qualification (login_qualification_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_account_mapping_revision
    DROP FOREIGN KEY fk_atp_account_mapping_revision_project_id;

ALTER TABLE atp_account_mapping_revision
    MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
    ADD INDEX ix_atp_account_mapping_account_status
        (test_account_id, lifecycle_status),
    ADD INDEX ix_atp_account_mapping_terminal_status
        (business_terminal_id, lifecycle_status),
    ADD CONSTRAINT fk_atp_account_mapping_test_account_scope
        FOREIGN KEY (test_account_id, project_id, environment_id)
        REFERENCES atp_test_account (test_account_id, project_id, environment_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_account_mapping_terminal_scope
        FOREIGN KEY (business_terminal_id, project_id, environment_id)
        REFERENCES atp_business_terminal (business_terminal_id, project_id, environment_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_account_mapping_revision_project_id
        FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_credential_revision
    ADD INDEX ix_atp_credential_revision_account_status
        (test_account_id, lifecycle_status, revision_no),
    ADD CONSTRAINT fk_atp_credential_revision_account_scope
        FOREIGN KEY (test_account_id, project_id)
        REFERENCES atp_test_account (test_account_id, project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE atp_test_account_secret (
    credential_revision_id VARCHAR(26) NOT NULL,
    -- 4096 UTF-8 characters require up to 16384 bytes; AES-GCM adds a
    -- 12-byte nonce and 16-byte authentication tag.
    encrypted_secret VARBINARY(16412) NOT NULL,
    key_id VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (credential_revision_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_test_account_secret
    ADD CONSTRAINT fk_atp_test_account_secret_credential_revision
    FOREIGN KEY (credential_revision_id)
    REFERENCES atp_credential_revision (credential_revision_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE atp_test_account_audit (
    audit_id VARCHAR(26) NOT NULL,
    test_account_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    environment_id VARCHAR(26) NOT NULL,
    business_terminal_ids JSON NOT NULL,
    action VARCHAR(64) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    actor_user_id VARCHAR(26) NOT NULL,
    required_permission VARCHAR(128) NOT NULL,
    previous_status VARCHAR(18) NULL,
    new_status VARCHAR(18) NULL,
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000) NULL,
    before_json JSON NULL,
    after_json JSON NULL,
    credential_changed BOOLEAN NOT NULL DEFAULT FALSE,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_test_account_audit
    ADD INDEX ix_atp_test_account_audit_account_time (test_account_id, occurred_at),
    ADD CONSTRAINT fk_atp_test_account_audit_test_account
        FOREIGN KEY (test_account_id) REFERENCES atp_test_account (test_account_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_test_account_audit_actor
        FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

DELIMITER $$
CREATE TRIGGER trg_atp_test_account_audit_no_update
BEFORE UPDATE ON atp_test_account_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'atp_test_account_audit is append-only';
END$$

CREATE TRIGGER trg_atp_test_account_audit_no_delete
BEFORE DELETE ON atp_test_account_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'atp_test_account_audit is append-only';
END$$
DELIMITER ;
