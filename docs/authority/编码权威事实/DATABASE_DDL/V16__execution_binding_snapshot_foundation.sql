-- ExecutionBindingSnapshot / ResourceLease foundation.
-- MySQL 8.4; no scheduler, dispatch queue, capacity planner, or browser loop tables.

CREATE TABLE atp_project_runtime_policy_revision (
    runtime_policy_revision_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    revision_no BIGINT UNSIGNED NOT NULL,
    browser_runtime VARCHAR(32) NOT NULL,
    artifact_policy VARCHAR(32) NOT NULL,
    timeout_seconds INT UNSIGNED NOT NULL,
    retry_mode VARCHAR(32) NOT NULL,
    network_requirement VARCHAR(32) NOT NULL,
    serial_execution_policy VARCHAR(32) NOT NULL DEFAULT 'SINGLE_PROCESS_UNIFIED_RETRY',
    lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'PUBLISHED',
    row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    created_by VARCHAR(26),
    updated_by VARCHAR(26),
    PRIMARY KEY (runtime_policy_revision_id),
    CONSTRAINT uq_atp_runtime_policy_revision_business UNIQUE (project_id, revision_no),
    CONSTRAINT uq_atp_runtime_policy_revision_scope UNIQUE (runtime_policy_revision_id, project_id),
    CONSTRAINT ck_atp_runtime_policy_revision_status CHECK (lifecycle_status IN ('PUBLISHED', 'RETIRED')),
    CONSTRAINT ck_atp_runtime_policy_serial CHECK (serial_execution_policy = 'SINGLE_PROCESS_UNIFIED_RETRY'),
    CONSTRAINT fk_atp_runtime_policy_revision_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runtime_policy_revision_created_by FOREIGN KEY (created_by) REFERENCES atp_user (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runtime_policy_revision_updated_by FOREIGN KEY (updated_by) REFERENCES atp_user (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE atp_resource_lease_generation (
    resource_type VARCHAR(16) NOT NULL,
    resource_identity_hash BINARY(32) NOT NULL,
    current_generation BIGINT UNSIGNED NOT NULL DEFAULT 0,
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (resource_type, resource_identity_hash),
    CONSTRAINT ck_atp_resource_generation_type CHECK (resource_type IN ('IDENTITY', 'RUNNER'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE atp_resource_lease (
    resource_lease_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    resource_type VARCHAR(16) NOT NULL,
    resource_identity VARCHAR(512) NOT NULL,
    resource_identity_hash BINARY(32) NOT NULL,
    owner_type VARCHAR(32) NOT NULL,
    owner_id VARCHAR(26) NOT NULL,
    status VARCHAR(8) NOT NULL DEFAULT 'ACTIVE',
    acquired_at DATETIME(6) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    released_at DATETIME(6),
    fencing_generation BIGINT UNSIGNED NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    active_resource_identity_hash BINARY(32) GENERATED ALWAYS AS (CASE WHEN status = 'ACTIVE' THEN resource_identity_hash ELSE NULL END) STORED,
    PRIMARY KEY (resource_lease_id), KEY ix_atp_resource_lease_owner (owner_type, owner_id, status), KEY ix_atp_resource_lease_expiry (status, expires_at),
    CONSTRAINT uq_atp_resource_lease_active UNIQUE (resource_type, active_resource_identity_hash),
    CONSTRAINT ck_atp_resource_lease_type CHECK (resource_type IN ('IDENTITY', 'RUNNER')),
    CONSTRAINT ck_atp_resource_lease_status CHECK (status IN ('ACTIVE', 'EXPIRED', 'FENCED', 'RELEASED')),
    CONSTRAINT ck_atp_resource_lease_expiry CHECK (expires_at > acquired_at),
    CONSTRAINT fk_atp_resource_lease_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE atp_execution_binding_snapshot (
    execution_binding_snapshot_id VARCHAR(26) NOT NULL,
    execution_attempt_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    environment_id VARCHAR(26) NOT NULL,
    business_terminal_id VARCHAR(26) NOT NULL,
    terminal_access_revision_id VARCHAR(26) NOT NULL,
    login_strategy_id VARCHAR(26) NOT NULL,
    login_strategy_row_version BIGINT NOT NULL,
    test_account_id VARCHAR(26) NOT NULL,
    credential_revision_id VARCHAR(26) NOT NULL,
    account_mapping_revision_id VARCHAR(26) NOT NULL,
    runner_id VARCHAR(26) NOT NULL,
    runner_row_version BIGINT NOT NULL,
    runner_heartbeat_at DATETIME(6) NOT NULL,
    runner_capability_snapshot JSON NOT NULL,
    runtime_policy_revision_id VARCHAR(26) NOT NULL,
    identity_lease_id VARCHAR(26) NOT NULL,
    identity_lease_generation BIGINT UNSIGNED NOT NULL,
    runner_lease_id VARCHAR(26) NOT NULL,
    runner_lease_generation BIGINT UNSIGNED NOT NULL,
    owner_execution_identity VARCHAR(191) NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    status VARCHAR(8) NOT NULL DEFAULT 'READY',
    row_version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    released_at DATETIME(6),
    expired_at DATETIME(6),
    created_by VARCHAR(26) NOT NULL,
    PRIMARY KEY (execution_binding_snapshot_id),
    CONSTRAINT uq_atp_execution_binding_attempt UNIQUE (execution_attempt_id),
    CONSTRAINT ck_atp_execution_binding_status CHECK (status IN ('READY', 'IN_USE', 'RELEASED', 'EXPIRED')),
    CONSTRAINT fk_atp_execution_binding_attempt FOREIGN KEY (execution_attempt_id) REFERENCES atp_execution_attempt (execution_attempt_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_environment FOREIGN KEY (environment_id) REFERENCES atp_environment (environment_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_terminal FOREIGN KEY (business_terminal_id) REFERENCES atp_business_terminal (business_terminal_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_terminal_revision FOREIGN KEY (terminal_access_revision_id) REFERENCES atp_environment_terminal_access_revision (environment_terminal_access_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_login_strategy FOREIGN KEY (login_strategy_id) REFERENCES atp_login_strategy (login_strategy_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_account FOREIGN KEY (test_account_id) REFERENCES atp_test_account (test_account_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_credential FOREIGN KEY (credential_revision_id) REFERENCES atp_credential_revision (credential_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_mapping FOREIGN KEY (account_mapping_revision_id) REFERENCES atp_account_mapping_revision (account_mapping_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_runner FOREIGN KEY (runner_id) REFERENCES atp_runner (runner_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_policy FOREIGN KEY (runtime_policy_revision_id) REFERENCES atp_project_runtime_policy_revision (runtime_policy_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_identity_lease FOREIGN KEY (identity_lease_id) REFERENCES atp_resource_lease (resource_lease_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_runner_lease FOREIGN KEY (runner_lease_id) REFERENCES atp_resource_lease (resource_lease_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_created_by FOREIGN KEY (created_by) REFERENCES atp_user (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE atp_execution_attempt
    ADD COLUMN execution_binding_snapshot_id VARCHAR(26) NULL AFTER execution_attempt_id,
    ADD CONSTRAINT uq_atp_execution_attempt_binding UNIQUE (execution_binding_snapshot_id),
    ADD CONSTRAINT fk_atp_execution_attempt_binding
        FOREIGN KEY (execution_binding_snapshot_id)
        REFERENCES atp_execution_binding_snapshot (execution_binding_snapshot_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE atp_execution_binding_audit (
    audit_id VARCHAR(26) NOT NULL,
    execution_binding_snapshot_id VARCHAR(26),
    project_id VARCHAR(26) NOT NULL,
    execution_attempt_id VARCHAR(26) NOT NULL,
    action VARCHAR(32) NOT NULL,
    actor_type VARCHAR(8) NOT NULL,
    actor_id VARCHAR(26) NOT NULL,
    previous_status VARCHAR(8),
    new_status VARCHAR(8),
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000),
    lease_generations_json JSON,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id), KEY ix_atp_execution_binding_audit_binding_time (execution_binding_snapshot_id, occurred_at),
    CONSTRAINT ck_atp_execution_binding_audit_actor CHECK (actor_type IN ('HUMAN', 'SYSTEM')),
    CONSTRAINT fk_atp_execution_binding_audit_binding FOREIGN KEY (execution_binding_snapshot_id) REFERENCES atp_execution_binding_snapshot (execution_binding_snapshot_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_audit_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_execution_binding_audit_attempt FOREIGN KEY (execution_attempt_id) REFERENCES atp_execution_attempt (execution_attempt_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
