-- AI model configuration foundation: governed provider/model data, encrypted Secret,
-- platform capability default binding, and immutable non-sensitive audit.

UPDATE atp_model_config
SET config_code = CONCAT('legacy-', model_config_id)
WHERE config_code IS NULL OR config_code = '';

ALTER TABLE atp_model_config
    ADD COLUMN provider_code VARCHAR(32) NULL AFTER config_code,
    ADD COLUMN model_name VARCHAR(191) NULL AFTER provider_code,
    ADD COLUMN request_timeout_seconds INT NOT NULL DEFAULT 30 AFTER model_name;

-- Pre-foundation rows were not consumable model configurations. Quarantine them in
-- CONFIGURING while supplying explicit placeholders that must be reviewed before ACTIVE.
UPDATE atp_model_config
SET provider_code = 'OPENAI',
    model_name = CONCAT('legacy-unconfigured-', model_config_id),
    lifecycle_status = 'CONFIGURING'
WHERE provider_code IS NULL OR model_name IS NULL;

ALTER TABLE atp_model_config
    MODIFY COLUMN config_code VARCHAR(191) NOT NULL,
    MODIFY COLUMN provider_code VARCHAR(32) NOT NULL,
    MODIFY COLUMN model_name VARCHAR(191) NOT NULL,
    ADD CONSTRAINT ck_atp_model_config_provider_code
        CHECK (provider_code IN ('OPENAI', 'ANTHROPIC', 'DEEPSEEK', 'QWEN', 'DOUBAO')),
    ADD CONSTRAINT ck_atp_model_config_timeout
        CHECK (request_timeout_seconds BETWEEN 1 AND 300),
    ADD INDEX ix_atp_model_config_provider_status (provider_code, lifecycle_status);

CREATE TABLE atp_model_config_secret (
    model_config_id VARCHAR(26) NOT NULL,
    -- 4096 UTF-8 characters require up to 16384 bytes; AES-GCM adds a
    -- 12-byte nonce and 16-byte authentication tag.
    encrypted_secret VARBINARY(16412) NOT NULL,
    key_id VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (model_config_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_model_config_secret
    ADD CONSTRAINT fk_atp_model_config_secret_model_config_id
    FOREIGN KEY (model_config_id) REFERENCES atp_model_config (model_config_id)
    ON DELETE CASCADE ON UPDATE RESTRICT;

CREATE TABLE atp_model_capability_default (
    capability_code VARCHAR(64) NOT NULL,
    model_config_id VARCHAR(26) NOT NULL,
    row_version BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    created_by VARCHAR(26) NULL,
    updated_by VARCHAR(26) NULL,
    PRIMARY KEY (capability_code),
    CONSTRAINT uq_atp_model_capability_default_model_config UNIQUE (model_config_id),
    CONSTRAINT ck_atp_model_capability_default_capability
        CHECK (capability_code IN ('AI_EXPLORATION'))
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_model_capability_default
    ADD CONSTRAINT fk_atp_model_capability_default_model_config_id
    FOREIGN KEY (model_config_id) REFERENCES atp_model_config (model_config_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE atp_model_config_audit (
    audit_id VARCHAR(26) NOT NULL,
    model_config_id VARCHAR(26) NULL,
    config_code VARCHAR(191) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,
    actor_user_id VARCHAR(26) NOT NULL,
    required_permission VARCHAR(128) NOT NULL,
    previous_status VARCHAR(11) NULL,
    new_status VARCHAR(11) NULL,
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000) NULL,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    details_json JSON NULL,
    PRIMARY KEY (audit_id),
    CONSTRAINT ck_atp_model_config_audit_action
        CHECK (action IN (
            'MODEL_CONFIG_CREATED',
            'MODEL_CONFIG_UPDATED',
            'MODEL_CONFIG_SECRET_UPDATED',
            'MODEL_CONFIG_REVIEW_SUBMITTED',
            'MODEL_CONFIG_RETURNED_TO_CONFIGURING',
            'MODEL_CONFIG_ACTIVATED',
            'MODEL_CONFIG_DISABLED',
            'MODEL_CONFIG_RECOVERY_STARTED',
            'MODEL_CONFIG_ARCHIVED',
            'CAPABILITY_DEFAULT_SET',
            'CAPABILITY_DEFAULT_CLEARED',
            'MODEL_CONFIG_CONNECTION_TESTED',
            'MODEL_CONFIG_OPERATION_DENIED',
            'MODEL_CONFIG_OPERATION_FAILED'
        ))
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_model_config_audit
    ADD CONSTRAINT fk_atp_model_config_audit_actor_user_id
    FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX ix_atp_model_config_audit_model_occurred
    ON atp_model_config_audit (model_config_id, occurred_at);

CREATE INDEX ix_atp_model_config_audit_actor_occurred
    ON atp_model_config_audit (actor_user_id, occurred_at);

CREATE INDEX ix_atp_model_config_audit_correlation
    ON atp_model_config_audit (correlation_id);

CREATE TRIGGER trg_atp_model_config_audit_no_update
BEFORE UPDATE ON atp_model_config_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_model_config_audit is append-only';

CREATE TRIGGER trg_atp_model_config_audit_no_delete
BEFORE DELETE ON atp_model_config_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_model_config_audit is append-only';
