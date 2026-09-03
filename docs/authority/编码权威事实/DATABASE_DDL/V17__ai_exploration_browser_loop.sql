-- AI Exploration Browser Loop: exactly-one execution ownership and ordered step evidence.
-- MySQL 8.4; no scheduler, dispatch queue, reschedule, resume, or Result->TestCase tables.

ALTER TABLE atp_project_runtime_policy_revision
    ADD COLUMN max_steps INT UNSIGNED NOT NULL DEFAULT 50 AFTER timeout_seconds,
    ADD COLUMN total_exploration_timeout_seconds INT UNSIGNED NOT NULL DEFAULT 1800 AFTER max_steps,
    ADD COLUMN model_transient_retry_per_step INT UNSIGNED NOT NULL DEFAULT 2 AFTER total_exploration_timeout_seconds,
    ADD COLUMN allowed_origins JSON NULL AFTER model_transient_retry_per_step,
    ADD COLUMN authentication_redirect_origins JSON NULL AFTER allowed_origins,
    ADD CONSTRAINT ck_atp_runtime_policy_max_steps CHECK (max_steps > 0),
    ADD CONSTRAINT ck_atp_runtime_policy_exploration_timeout CHECK (total_exploration_timeout_seconds > 0),
    ADD CONSTRAINT ck_atp_runtime_policy_model_retry CHECK (model_transient_retry_per_step <= 10);

UPDATE atp_project_runtime_policy_revision
SET allowed_origins = JSON_ARRAY(), authentication_redirect_origins = JSON_ARRAY()
WHERE allowed_origins IS NULL OR authentication_redirect_origins IS NULL;

ALTER TABLE atp_project_runtime_policy_revision
    MODIFY COLUMN allowed_origins JSON NOT NULL,
    MODIFY COLUMN authentication_redirect_origins JSON NOT NULL;

ALTER TABLE atp_ai_exploration_session
    ADD COLUMN execution_attempt_id VARCHAR(26) NULL AFTER ai_call_id,
    ADD COLUMN execution_binding_snapshot_id VARCHAR(26) NULL AFTER execution_attempt_id,
    ADD COLUMN browser_session_id VARCHAR(191) NULL AFTER execution_binding_snapshot_id,
    ADD COLUMN current_observation_id VARCHAR(26) NULL AFTER browser_session_id,
    ADD COLUMN current_step_sequence BIGINT UNSIGNED NOT NULL DEFAULT 0 AFTER current_observation_id,
    ADD COLUMN max_steps INT UNSIGNED NULL AFTER current_step_sequence,
    ADD COLUMN total_timeout_seconds INT UNSIGNED NULL AFTER max_steps,
    ADD COLUMN model_transient_retry_per_step INT UNSIGNED NULL AFTER total_timeout_seconds,
    ADD COLUMN row_version BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER model_transient_retry_per_step,
    ADD COLUMN total_deadline_at DATETIME(6) NULL AFTER planning_deadline_at,
    ADD COLUMN started_at DATETIME(6) NULL AFTER total_deadline_at,
    ADD COLUMN terminal_at DATETIME(6) NULL AFTER started_at,
    ADD COLUMN cancel_requested_at DATETIME(6) NULL AFTER terminal_at,
    ADD CONSTRAINT uq_atp_ai_exploration_session_attempt UNIQUE (execution_attempt_id),
    ADD CONSTRAINT uq_atp_ai_exploration_session_binding UNIQUE (execution_binding_snapshot_id),
    ADD CONSTRAINT fk_atp_ai_exploration_session_attempt
        FOREIGN KEY (execution_attempt_id) REFERENCES atp_execution_attempt (execution_attempt_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_ai_exploration_session_binding
        FOREIGN KEY (execution_binding_snapshot_id)
        REFERENCES atp_execution_binding_snapshot (execution_binding_snapshot_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT ck_atp_ai_exploration_session_runtime_limits
        CHECK (
            (max_steps IS NULL AND total_timeout_seconds IS NULL AND model_transient_retry_per_step IS NULL)
            OR (max_steps > 0 AND total_timeout_seconds > 0 AND model_transient_retry_per_step BETWEEN 0 AND 10)
        );

UPDATE atp_ai_exploration_session
SET terminal_at = updated_at
WHERE lifecycle_status = 'FAILED' AND terminal_at IS NULL;

ALTER TABLE atp_ai_exploration_session
    DROP CHECK ck_atp_ai_exploration_session_status,
    DROP CHECK ck_atp_ai_exploration_session_failed,
    ADD CONSTRAINT ck_atp_ai_exploration_session_status
        CHECK (lifecycle_status IN (
            'CREATED', 'PLANNING', 'READY', 'FAILED', 'RUNNING', 'SUCCEEDED', 'CANCELLED'
        )),
    ADD CONSTRAINT ck_atp_ai_exploration_session_failed
        CHECK (
            lifecycle_status <> 'FAILED'
            OR (failure_code IS NOT NULL AND failure_message IS NOT NULL AND terminal_at IS NOT NULL)
        ),
    ADD CONSTRAINT ck_atp_ai_exploration_session_execution_owner
        CHECK (
            lifecycle_status NOT IN ('RUNNING', 'SUCCEEDED', 'CANCELLED')
            OR (
                execution_attempt_id IS NOT NULL
                AND execution_binding_snapshot_id IS NOT NULL
                AND max_steps IS NOT NULL
                AND total_timeout_seconds IS NOT NULL
                AND model_transient_retry_per_step IS NOT NULL
                AND started_at IS NOT NULL
            )
        );

CREATE INDEX ix_atp_ai_exploration_session_attempt_status
    ON atp_ai_exploration_session (execution_attempt_id, lifecycle_status);

CREATE INDEX ix_atp_ai_exploration_session_runtime_deadline
    ON atp_ai_exploration_session (lifecycle_status, total_deadline_at);

CREATE TABLE atp_ai_exploration_step (
    ai_exploration_step_id VARCHAR(26) NOT NULL,
    session_id VARCHAR(26) NOT NULL,
    execution_attempt_id VARCHAR(26) NOT NULL,
    ai_call_id VARCHAR(26) NOT NULL,
    sequence BIGINT UNSIGNED NOT NULL,
    model_call_identity VARCHAR(191) NOT NULL,
    observation_identity VARCHAR(26) NOT NULL,
    action_identity VARCHAR(26) NOT NULL,
    status VARCHAR(24) NOT NULL,
    observation_json JSON NOT NULL,
    action_json JSON NULL,
    action_result_json JSON NULL,
    sanitized_reason VARCHAR(1000) NULL,
    failure_code VARCHAR(64) NULL,
    state_version BIGINT UNSIGNED NOT NULL,
    identity_lease_generation BIGINT UNSIGNED NOT NULL,
    runner_lease_generation BIGINT UNSIGNED NOT NULL,
    started_at DATETIME(6) NOT NULL,
    completed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (ai_exploration_step_id),
    CONSTRAINT uq_atp_ai_exploration_step_sequence UNIQUE (session_id, sequence),
    CONSTRAINT uq_atp_ai_exploration_step_observation UNIQUE (observation_identity),
    CONSTRAINT uq_atp_ai_exploration_step_action UNIQUE (action_identity),
    CONSTRAINT ck_atp_ai_exploration_step_status
        CHECK (status IN ('DECIDING', 'EXECUTING', 'SUCCEEDED', 'FAILED', 'COMPLETION_PROPOSED', 'DISCARDED')),
    CONSTRAINT ck_atp_ai_exploration_step_sequence CHECK (sequence > 0),
    CONSTRAINT ck_atp_ai_exploration_step_terminal CHECK (status IN ('DECIDING', 'EXECUTING') OR completed_at IS NOT NULL),
    CONSTRAINT fk_atp_ai_exploration_step_session
        FOREIGN KEY (session_id) REFERENCES atp_ai_exploration_session (session_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_ai_exploration_step_attempt
        FOREIGN KEY (execution_attempt_id) REFERENCES atp_execution_attempt (execution_attempt_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_ai_exploration_step_ai_call
        FOREIGN KEY (ai_call_id) REFERENCES atp_ai_call (ai_call_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_atp_ai_exploration_step_session_status
    ON atp_ai_exploration_step (session_id, status, sequence);

CREATE INDEX ix_atp_ai_exploration_step_attempt_created
    ON atp_ai_exploration_step (execution_attempt_id, created_at);

ALTER TABLE atp_ai_exploration_audit
    DROP CHECK ck_atp_ai_exploration_audit_action,
    ADD CONSTRAINT ck_atp_ai_exploration_audit_action
        CHECK (action IN (
            'SESSION_CREATED', 'PLANNING_STARTED', 'PLANNING_SUCCEEDED',
            'PLANNING_FAILED', 'PLANNING_INTERRUPTED', 'BROWSER_STARTED',
            'STEP_RECORDED', 'BROWSER_SUCCEEDED', 'BROWSER_FAILED',
            'CANCEL_REQUESTED', 'BROWSER_CANCELLED', 'LEASE_LOST', 'RUNTIME_RECOVERED'
        ));
