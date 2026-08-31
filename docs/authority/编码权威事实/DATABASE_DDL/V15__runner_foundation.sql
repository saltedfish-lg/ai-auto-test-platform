-- Runner Foundation: project-scoped enrollment, opaque machine credentials,
-- independent lifecycle/runtime state, governed capabilities, audit, and outbox.

-- A legacy Runner is migratable only when its existing binding already resolves to one
-- Project. V15 never invents ownership for an UNBOUND row. The temporary CHECK makes
-- an ambiguous legacy row fail before any destructive column or constraint changes.
CREATE TEMPORARY TABLE atp_v15_runner_scope_violation (
    violation TINYINT NOT NULL,
    CONSTRAINT ck_atp_v15_runner_scope_violation CHECK (violation = 0)
);

INSERT INTO atp_v15_runner_scope_violation (violation)
SELECT 1
FROM atp_runner AS runner
LEFT JOIN atp_runner_project_binding AS binding
  ON binding.runner_project_binding_id = runner.runner_project_binding_id
WHERE runner.binding_state <> 'BOUND'
   OR binding.runner_project_binding_id IS NULL
   OR binding.runner_id <> runner.runner_id
   OR binding.project_id IS NULL
   OR (runner.project_id IS NOT NULL AND runner.project_id <> binding.project_id)
LIMIT 1;

DROP TEMPORARY TABLE atp_v15_runner_scope_violation;

UPDATE atp_runner AS runner
JOIN atp_runner_project_binding AS binding
  ON binding.runner_project_binding_id = runner.runner_project_binding_id
SET runner.project_id = binding.project_id
WHERE runner.project_id IS NULL
  AND binding.project_id IS NOT NULL;

ALTER TABLE atp_runner
    ADD CONSTRAINT ck_atp_runner_v15_project_scope_ready
        CHECK (project_id IS NOT NULL AND runner_code IS NOT NULL);

ALTER TABLE atp_runner
    DROP FOREIGN KEY fk_atp_runner_runner_project_binding_id,
    DROP FOREIGN KEY fk_atp_runner_project_id,
    DROP INDEX uq_atp_runner_business,
    DROP CHECK ck_atp_runner_health_status,
    DROP CHECK ck_atp_runner_scheduling_status,
    DROP CHECK ck_atp_runner_registration_state,
    DROP CHECK ck_atp_runner_authentication_state,
    DROP CHECK ck_atp_runner_connection_state,
    DROP CHECK ck_atp_runner_health_state,
    DROP CHECK ck_atp_runner_enablement_state,
    DROP CHECK ck_atp_runner_binding_state,
    DROP CHECK ck_atp_runner_scheduling_state,
    DROP CHECK ck_atp_runner_resource_state,
    DROP CHECK ck_atp_runner_lifecycle_status;

ALTER TABLE atp_runner
    ADD COLUMN registration_status VARCHAR(12) NULL AFTER runner_code,
    ADD COLUMN connection_status VARCHAR(12) NULL AFTER registration_status,
    ADD COLUMN enable_status VARCHAR(8) NULL AFTER connection_status,
    ADD COLUMN project_binding_status VARCHAR(7) NULL AFTER enable_status,
    MODIFY COLUMN health_status VARCHAR(9) NULL,
    MODIFY COLUMN scheduling_status VARCHAR(20) NULL,
    MODIFY COLUMN lifecycle_status VARCHAR(13) NULL,
    ADD COLUMN resource_status VARCHAR(20) NULL AFTER scheduling_status,
    ADD COLUMN version_compatibility VARCHAR(20) NULL AFTER resource_status,
    ADD COLUMN last_heartbeat_at DATETIME(6) NULL AFTER version_compatibility,
    ADD COLUMN registered_at DATETIME(6) NULL AFTER last_heartbeat_at,
    ADD COLUMN runtime_metadata_json JSON NULL AFTER registered_at;

UPDATE atp_runner
SET registration_status = 'REGISTERED',
    connection_status = CASE
        WHEN connection_state = 'ONLINE' THEN 'ONLINE'
        WHEN connection_state = 'DISCONNECTED' THEN 'LOST'
        ELSE 'OFFLINE'
    END,
    enable_status = CASE
        WHEN enablement_state = 'ENABLED' THEN 'ENABLED'
        ELSE 'DISABLED'
    END,
    project_binding_status = 'BOUND',
    scheduling_status = 'UNSCHEDULABLE',
    resource_status = 'AVAILABLE',
    version_compatibility = 'UNKNOWN',
    lifecycle_status = CASE
        WHEN lifecycle_status = 'ARCHIVED' THEN 'ARCHIVED'
        WHEN lifecycle_status = 'DISABLED' THEN 'DISABLED'
        ELSE 'REGISTERED'
    END,
    registered_at = COALESCE(created_at, CURRENT_TIMESTAMP(6));

ALTER TABLE atp_runner
    DROP CHECK ck_atp_runner_v15_project_scope_ready,
    DROP COLUMN registration_state,
    DROP COLUMN runner_project_binding_id,
    DROP COLUMN connection_state,
    DROP COLUMN enablement_state,
    DROP COLUMN binding_state,
    DROP COLUMN authentication_state,
    DROP COLUMN health_state,
    DROP COLUMN scheduling_state,
    DROP COLUMN resource_state,
    MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN runner_code VARCHAR(191) NOT NULL,
    MODIFY COLUMN registration_status VARCHAR(12) NOT NULL DEFAULT 'REGISTERED',
    MODIFY COLUMN connection_status VARCHAR(12) NOT NULL DEFAULT 'OFFLINE',
    MODIFY COLUMN enable_status VARCHAR(8) NOT NULL DEFAULT 'DISABLED',
    MODIFY COLUMN project_binding_status VARCHAR(7) NOT NULL DEFAULT 'BOUND',
    MODIFY COLUMN health_status VARCHAR(9) NOT NULL DEFAULT 'UNKNOWN',
    MODIFY COLUMN scheduling_status VARCHAR(20) NOT NULL,
    MODIFY COLUMN lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'REGISTERED',
    MODIFY COLUMN resource_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    MODIFY COLUMN version_compatibility VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    MODIFY COLUMN registered_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    ADD CONSTRAINT uq_atp_runner_business UNIQUE (project_id, runner_code),
    ADD CONSTRAINT uq_atp_runner_project_scope UNIQUE (runner_id, project_id),
    ADD INDEX ix_atp_runner_project_lifecycle (project_id, lifecycle_status),
    ADD INDEX ix_atp_runner_project_health (project_id, health_status, connection_status),
    ADD INDEX ix_atp_runner_last_heartbeat (last_heartbeat_at),
    ADD CONSTRAINT ck_atp_runner_registration_status CHECK (registration_status = 'REGISTERED'),
    ADD CONSTRAINT ck_atp_runner_connection_status
        CHECK (connection_status IN ('OFFLINE', 'CONNECTING', 'ONLINE', 'LOST')),
    ADD CONSTRAINT ck_atp_runner_health_status
        CHECK (health_status IN ('UNKNOWN', 'HEALTHY', 'DEGRADED', 'UNHEALTHY')),
    ADD CONSTRAINT ck_atp_runner_enable_status CHECK (enable_status IN ('ENABLED', 'DISABLED')),
    ADD CONSTRAINT ck_atp_runner_project_binding_status CHECK (project_binding_status = 'BOUND'),
    ADD CONSTRAINT ck_atp_runner_scheduling_status
        CHECK (scheduling_status IN ('UNSCHEDULABLE', 'IDLE', 'PARTIALLY_OCCUPIED', 'BUSY', 'DRAINING')),
    ADD CONSTRAINT ck_atp_runner_resource_status
        CHECK (resource_status IN ('AVAILABLE', 'PARTIALLY_OCCUPIED', 'EXHAUSTED', 'RECLAIMING')),
    ADD CONSTRAINT ck_atp_runner_version_compatibility
        CHECK (version_compatibility IN ('UNKNOWN', 'COMPATIBLE', 'INCOMPATIBLE', 'UPGRADE_REQUIRED')),
    ADD CONSTRAINT ck_atp_runner_lifecycle_status
        CHECK (lifecycle_status IN ('REGISTERED', 'ACTIVE', 'DISABLED', 'ARCHIVED')),
    ADD CONSTRAINT fk_atp_runner_project_id
        FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE atp_runner_enrollment (
    enrollment_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    runner_code VARCHAR(191) NOT NULL,
    display_name VARCHAR(255) NULL,
    credential_hash BINARY(32) NOT NULL,
    enrollment_status VARCHAR(8) NOT NULL DEFAULT 'PENDING',
    consumed_runner_id VARCHAR(26) NULL,
    consumed_at DATETIME(6) NULL,
    revoked_at DATETIME(6) NULL,
    row_version BIGINT NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by VARCHAR(26) NOT NULL,
    updated_by VARCHAR(26) NOT NULL,
    reason VARCHAR(1000) NOT NULL,
    PRIMARY KEY (enrollment_id),
    CONSTRAINT uq_atp_runner_enrollment_credential UNIQUE (credential_hash),
    CONSTRAINT ck_atp_runner_enrollment_status
        CHECK (enrollment_status IN ('PENDING', 'CONSUMED', 'REVOKED')),
    CONSTRAINT fk_atp_runner_enrollment_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runner_enrollment_runner FOREIGN KEY (consumed_runner_id) REFERENCES atp_runner (runner_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runner_enrollment_created_by FOREIGN KEY (created_by) REFERENCES atp_user (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runner_enrollment_updated_by FOREIGN KEY (updated_by) REFERENCES atp_user (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_runner_enrollment
    ADD INDEX ix_atp_runner_enrollment_project_status (project_id, enrollment_status),
    ADD INDEX ix_atp_runner_enrollment_project_code (project_id, runner_code);

ALTER TABLE atp_runner_agent
    DROP FOREIGN KEY fk_atp_runner_agent_runner_id,
    DROP FOREIGN KEY fk_atp_runner_agent_project_id,
    DROP CHECK ck_atp_runner_agent_lifecycle_status;

ALTER TABLE atp_runner_agent
    ADD COLUMN token_hash BINARY(32) NULL AFTER runner_id,
    ADD COLUMN token_status VARCHAR(7) NULL AFTER token_hash,
    ADD COLUMN token_version BIGINT NULL AFTER token_status,
    ADD COLUMN machine_fingerprint_hash BINARY(32) NULL AFTER token_version,
    ADD COLUMN agent_version VARCHAR(64) NULL AFTER machine_fingerprint_hash,
    ADD COLUMN last_authenticated_at DATETIME(6) NULL AFTER agent_version,
    ADD COLUMN credential_rotated_at DATETIME(6) NULL AFTER last_authenticated_at,
    ADD COLUMN revoked_at DATETIME(6) NULL AFTER credential_rotated_at;

-- Pre-V15 Agent rows have no recoverable machine credential. Preserve their audit
-- identity but revoke them; unique deterministic hashes prevent a fake active token.
UPDATE atp_runner_agent AS agent
JOIN atp_runner AS runner ON runner.runner_id = agent.runner_id
SET agent.project_id = runner.project_id,
    agent.token_hash = UNHEX(SHA2(CONCAT('legacy-revoked-token:', agent.runner_agent_id), 256)),
    agent.token_status = 'REVOKED',
    agent.token_version = 1,
    agent.machine_fingerprint_hash = UNHEX(SHA2(CONCAT('legacy-machine:', agent.runner_agent_id), 256)),
    agent.agent_version = 'legacy-pre-v15',
    agent.lifecycle_status = 'REVOKED',
    agent.revoked_at = COALESCE(agent.updated_at, CURRENT_TIMESTAMP(6));

ALTER TABLE atp_runner_agent
    MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN lifecycle_status VARCHAR(8) NOT NULL DEFAULT 'ACTIVE',
    MODIFY COLUMN token_hash BINARY(32) NOT NULL,
    MODIFY COLUMN token_status VARCHAR(7) NOT NULL DEFAULT 'ACTIVE',
    MODIFY COLUMN token_version BIGINT NOT NULL DEFAULT 1,
    MODIFY COLUMN machine_fingerprint_hash BINARY(32) NOT NULL,
    MODIFY COLUMN agent_version VARCHAR(64) NOT NULL,
    ADD CONSTRAINT uq_atp_runner_agent_runner UNIQUE (runner_id),
    ADD CONSTRAINT uq_atp_runner_agent_token_hash UNIQUE (token_hash),
    ADD CONSTRAINT ck_atp_runner_agent_lifecycle_status
        CHECK (lifecycle_status IN ('ACTIVE', 'REVOKED')),
    ADD CONSTRAINT ck_atp_runner_agent_token_status
        CHECK (token_status IN ('ACTIVE', 'REVOKED')),
    ADD CONSTRAINT fk_atp_runner_agent_runner_scope
        FOREIGN KEY (runner_id, project_id)
        REFERENCES atp_runner (runner_id, project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_runner_agent_project_id
        FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD INDEX ix_atp_runner_agent_status (runner_id, token_status);

ALTER TABLE atp_runner_capability
    DROP FOREIGN KEY fk_atp_runner_capability_runner_id,
    DROP FOREIGN KEY fk_atp_runner_capability_project_id,
    DROP CHECK ck_atp_runner_capability_lifecycle_status;

ALTER TABLE atp_runner_capability
    ADD COLUMN capability_type VARCHAR(16) NULL AFTER capability_code,
    ADD COLUMN availability_status VARCHAR(14) NULL AFTER capability_type,
    ADD COLUMN validation_status VARCHAR(16) NULL AFTER availability_status,
    ADD COLUMN observed_version VARCHAR(64) NULL AFTER validation_status,
    ADD COLUMN observed_metadata_json JSON NULL AFTER observed_version,
    ADD COLUMN reported_at DATETIME(6) NULL AFTER observed_metadata_json;

UPDATE atp_runner_capability AS capability
JOIN atp_runner AS runner ON runner.runner_id = capability.runner_id
SET capability.project_id = runner.project_id,
    capability.capability_type = CASE
        WHEN capability.capability_code IN ('BROWSER_CHROMIUM', 'BROWSER_CHROME', 'BROWSER_EDGE') THEN 'BROWSER'
        WHEN capability.capability_code IN ('MODE_HEADED', 'MODE_HEADLESS') THEN 'SESSION'
        WHEN capability.capability_code IN ('TERMINAL_ADMIN_WEB', 'TERMINAL_CLIENT_WEB', 'TERMINAL_PDA_WEB') THEN 'TERMINAL'
        WHEN capability.capability_code IN ('SINGLE_TERMINAL', 'CROSS_TERMINAL', 'MANUAL_RECORDING', 'AI_EXPLORATION', 'FORMAL_EXECUTION') THEN 'FLOW'
        WHEN capability.capability_code IN ('CAPTURE_SCREENSHOT', 'CAPTURE_VIDEO', 'CAPTURE_TRACE') THEN 'ARTIFACT'
        WHEN capability.capability_code IN ('NETWORK_RESPONSE_LISTEN', 'INTRANET_ACCESS', 'PROXY_ACCESS') THEN 'NETWORK'
        WHEN capability.capability_code = 'FILE_TRANSFER' THEN 'IO'
        WHEN capability.capability_code = 'LOCAL_ARTIFACT_CACHE' THEN 'STORAGE'
        WHEN capability.capability_code IN ('PLAYWRIGHT_VERSION', 'AGENT_VERSION') THEN 'VERSION'
        WHEN capability.capability_code = 'CONTEXT_ISOLATION' THEN 'SECURITY'
        ELSE NULL
    END,
    capability.availability_status = 'CONFIGURED',
    capability.validation_status = 'PENDING',
    capability.lifecycle_status = 'ACTIVE',
    capability.reported_at = COALESCE(capability.updated_at, CURRENT_TIMESTAMP(6));

ALTER TABLE atp_runner_capability
    MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN runner_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN capability_code VARCHAR(64) NOT NULL,
    MODIFY COLUMN lifecycle_status VARCHAR(8) NOT NULL DEFAULT 'ACTIVE',
    MODIFY COLUMN capability_type VARCHAR(16) NOT NULL,
    MODIFY COLUMN availability_status VARCHAR(14) NOT NULL DEFAULT 'CONFIGURED',
    MODIFY COLUMN validation_status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    MODIFY COLUMN reported_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    ADD CONSTRAINT ck_atp_runner_capability_code CHECK (capability_code IN (
        'BROWSER_CHROMIUM', 'BROWSER_CHROME', 'BROWSER_EDGE', 'MODE_HEADED', 'MODE_HEADLESS',
        'TERMINAL_ADMIN_WEB', 'TERMINAL_CLIENT_WEB', 'TERMINAL_PDA_WEB', 'SINGLE_TERMINAL',
        'CROSS_TERMINAL', 'CAPTURE_SCREENSHOT', 'CAPTURE_VIDEO', 'CAPTURE_TRACE',
        'NETWORK_RESPONSE_LISTEN', 'INTRANET_ACCESS', 'PROXY_ACCESS', 'FILE_TRANSFER',
        'MANUAL_RECORDING', 'AI_EXPLORATION', 'FORMAL_EXECUTION', 'LOCAL_ARTIFACT_CACHE',
        'PLAYWRIGHT_VERSION', 'AGENT_VERSION', 'CONTEXT_ISOLATION'
    )),
    ADD CONSTRAINT ck_atp_runner_capability_type CHECK (capability_type IN (
        'BROWSER', 'SESSION', 'TERMINAL', 'FLOW', 'ARTIFACT', 'NETWORK', 'IO', 'STORAGE', 'VERSION', 'SECURITY'
    )),
    ADD CONSTRAINT ck_atp_runner_capability_availability
        CHECK (availability_status IN ('CONFIGURED', 'NOT_CONFIGURED')),
    ADD CONSTRAINT ck_atp_runner_capability_validation
        CHECK (validation_status IN ('PENDING', 'VALID', 'INVALID')),
    ADD CONSTRAINT ck_atp_runner_capability_lifecycle_status
        CHECK (lifecycle_status IN ('ACTIVE', 'DISABLED')),
    ADD CONSTRAINT fk_atp_runner_capability_runner_scope
        FOREIGN KEY (runner_id, project_id)
        REFERENCES atp_runner (runner_id, project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_runner_capability_project_id
        FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD INDEX ix_atp_runner_capability_project_code
        (project_id, capability_code, availability_status),
    ADD INDEX ix_atp_runner_capability_runner_reported
        (runner_id, reported_at);

CREATE TABLE atp_runner_audit (
    audit_id VARCHAR(26) NOT NULL,
    runner_id VARCHAR(26) NULL,
    enrollment_id VARCHAR(26) NULL,
    project_id VARCHAR(26) NOT NULL,
    action VARCHAR(64) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    actor_type VARCHAR(8) NOT NULL,
    actor_id VARCHAR(26) NOT NULL,
    required_permission VARCHAR(128) NULL,
    previous_status VARCHAR(16) NULL,
    new_status VARCHAR(16) NULL,
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000) NULL,
    before_json JSON NULL,
    after_json JSON NULL,
    credential_changed BOOLEAN NOT NULL DEFAULT FALSE,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id),
    CONSTRAINT ck_atp_runner_audit_actor_type CHECK (actor_type IN ('HUMAN', 'AGENT')),
    CONSTRAINT fk_atp_runner_audit_runner FOREIGN KEY (runner_id) REFERENCES atp_runner (runner_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runner_audit_enrollment FOREIGN KEY (enrollment_id) REFERENCES atp_runner_enrollment (enrollment_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runner_audit_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_runner_audit
    ADD INDEX ix_atp_runner_audit_runner_time (runner_id, occurred_at),
    ADD INDEX ix_atp_runner_audit_enrollment_time (enrollment_id, occurred_at);

DELIMITER $$
CREATE TRIGGER trg_atp_runner_audit_no_update
BEFORE UPDATE ON atp_runner_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'atp_runner_audit is append-only';
END$$

CREATE TRIGGER trg_atp_runner_audit_no_delete
BEFORE DELETE ON atp_runner_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'atp_runner_audit is append-only';
END$$
DELIMITER ;
