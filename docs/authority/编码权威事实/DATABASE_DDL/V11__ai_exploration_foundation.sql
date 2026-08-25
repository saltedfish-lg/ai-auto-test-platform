-- AI exploration foundation: model-snapshot planning sessions and append-only lifecycle audit.

CREATE TABLE atp_ai_exploration_session (
    session_id VARCHAR(26) NOT NULL,
    ai_task_id VARCHAR(26) NOT NULL,
    ai_call_id VARCHAR(26) NOT NULL,
    idempotency_key VARCHAR(191) NOT NULL,
    required_permission VARCHAR(128) NOT NULL,
    permission_decision VARCHAR(64) NOT NULL,
    data_scope_decision VARCHAR(128) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    source_case_id VARCHAR(26) NULL,
    objective VARCHAR(4000) NOT NULL,
    target_url VARCHAR(2048) NOT NULL,
    lifecycle_status VARCHAR(16) NOT NULL,
    resolved_model_config_id VARCHAR(26) NOT NULL,
    resolved_model_display_name VARCHAR(255) NULL,
    resolved_provider_code VARCHAR(32) NOT NULL,
    resolved_model_name VARCHAR(191) NOT NULL,
    plan JSON NULL,
    failure_code VARCHAR(64) NULL,
    failure_message VARCHAR(1000) NULL,
    planning_started_at DATETIME(6) NOT NULL,
    planning_deadline_at DATETIME(6) NOT NULL,
    created_by VARCHAR(26) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (session_id),
    CONSTRAINT uq_atp_ai_exploration_session_ai_task UNIQUE (ai_task_id),
    CONSTRAINT uq_atp_ai_exploration_session_ai_call UNIQUE (ai_call_id),
    CONSTRAINT uq_atp_ai_exploration_session_idempotency UNIQUE (idempotency_key),
    CONSTRAINT ck_atp_ai_exploration_session_status
        CHECK (lifecycle_status IN (
            'CREATED', 'PLANNING', 'READY', 'FAILED', 'RUNNING', 'SUCCEEDED'
        )),
    CONSTRAINT ck_atp_ai_exploration_session_ready
        CHECK (
            lifecycle_status <> 'READY'
            OR (plan IS NOT NULL AND failure_code IS NULL AND failure_message IS NULL)
        ),
    CONSTRAINT ck_atp_ai_exploration_session_failed
        CHECK (
            lifecycle_status <> 'FAILED'
            OR (plan IS NULL AND failure_code IS NOT NULL AND failure_message IS NOT NULL)
        )
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_ai_exploration_session
    ADD CONSTRAINT fk_atp_ai_exploration_session_ai_task_id
    FOREIGN KEY (ai_task_id) REFERENCES atp_ai_task (ai_task_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_session
    ADD CONSTRAINT fk_atp_ai_exploration_session_ai_call_id
    FOREIGN KEY (ai_call_id) REFERENCES atp_ai_call (ai_call_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_session
    ADD CONSTRAINT fk_atp_ai_exploration_session_idempotency_key
    FOREIGN KEY (idempotency_key) REFERENCES atp_idempotency_record (idempotency_key)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_session
    ADD CONSTRAINT fk_atp_ai_exploration_session_project_id
    FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_session
    ADD CONSTRAINT fk_atp_ai_exploration_session_model_config_id
    FOREIGN KEY (resolved_model_config_id) REFERENCES atp_model_config (model_config_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_session
    ADD CONSTRAINT fk_atp_ai_exploration_session_created_by
    FOREIGN KEY (created_by) REFERENCES atp_user (user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX ix_atp_ai_exploration_session_project_created
    ON atp_ai_exploration_session (project_id, created_at);

CREATE INDEX ix_atp_ai_exploration_session_source_case
    ON atp_ai_exploration_session (source_case_id);

CREATE INDEX ix_atp_ai_exploration_session_status_updated
    ON atp_ai_exploration_session (lifecycle_status, updated_at);

CREATE INDEX ix_atp_ai_exploration_session_planning_deadline
    ON atp_ai_exploration_session (lifecycle_status, planning_deadline_at);

CREATE TABLE atp_ai_exploration_audit (
    audit_id VARCHAR(26) NOT NULL,
    session_id VARCHAR(26) NOT NULL,
    ai_task_id VARCHAR(26) NOT NULL,
    ai_call_id VARCHAR(26) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,
    actor_user_id VARCHAR(26) NOT NULL,
    required_permission VARCHAR(128) NOT NULL,
    permission_decision VARCHAR(64) NOT NULL,
    data_scope_decision VARCHAR(128) NOT NULL,
    participant_subjects JSON NOT NULL,
    model_config_id VARCHAR(26) NOT NULL,
    provider_code VARCHAR(32) NOT NULL,
    model_name VARCHAR(191) NOT NULL,
    previous_status VARCHAR(16) NULL,
    new_status VARCHAR(16) NOT NULL,
    result_code VARCHAR(64) NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    provider_request_id VARCHAR(191) NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id),
    CONSTRAINT ck_atp_ai_exploration_audit_action
        CHECK (action IN (
            'SESSION_CREATED', 'PLANNING_STARTED', 'PLANNING_SUCCEEDED',
            'PLANNING_FAILED', 'PLANNING_INTERRUPTED'
        ))
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_ai_exploration_audit
    ADD CONSTRAINT fk_atp_ai_exploration_audit_session_id
    FOREIGN KEY (session_id) REFERENCES atp_ai_exploration_session (session_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_audit
    ADD CONSTRAINT fk_atp_ai_exploration_audit_ai_task_id
    FOREIGN KEY (ai_task_id) REFERENCES atp_ai_task (ai_task_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_audit
    ADD CONSTRAINT fk_atp_ai_exploration_audit_ai_call_id
    FOREIGN KEY (ai_call_id) REFERENCES atp_ai_call (ai_call_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_ai_exploration_audit
    ADD CONSTRAINT fk_atp_ai_exploration_audit_actor_user_id
    FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX ix_atp_ai_exploration_audit_session_occurred
    ON atp_ai_exploration_audit (session_id, occurred_at);

CREATE INDEX ix_atp_ai_exploration_audit_correlation
    ON atp_ai_exploration_audit (correlation_id);

CREATE TRIGGER trg_atp_ai_exploration_audit_no_update
BEFORE UPDATE ON atp_ai_exploration_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_ai_exploration_audit is append-only';

CREATE TRIGGER trg_atp_ai_exploration_audit_no_delete
BEFORE DELETE ON atp_ai_exploration_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_ai_exploration_audit is append-only';

-- Foundation sessions are planning-stage members of the existing AI Task aggregate.
-- These nullable edges support this bounded planning member without changing the
-- full Runner exploration contract.
ALTER TABLE atp_ai_task
    MODIFY COLUMN ai_call_id VARCHAR(26) NULL;

ALTER TABLE atp_ai_call
    MODIFY COLUMN prompt_revision_id VARCHAR(26) NULL;
