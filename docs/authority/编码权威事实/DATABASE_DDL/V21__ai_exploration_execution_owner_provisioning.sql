-- Align the physical execution-owner model with the existing RunTask/ExecutionAttempt
-- contracts for AI exploration. Case-specific execution objects are not fabricated for
-- PAGE_EXPLORATION; the immutable runtime facts are frozen by ExecutionBindingSnapshot.

ALTER TABLE atp_run_task
    MODIFY COLUMN case_suite_id VARCHAR(26) NULL,
    ADD COLUMN task_type VARCHAR(32) NULL AFTER environment_id,
    ADD CONSTRAINT ck_atp_run_task_task_type
        CHECK (task_type IN ('FORMAL_EXECUTION', 'AI_EXPLORATION', 'AI_VALIDATION'));

ALTER TABLE atp_execution_attempt
    MODIFY COLUMN case_attempt_id VARCHAR(26) NULL,
    MODIFY COLUMN configuration_snapshot_id VARCHAR(26) NULL,
    MODIFY COLUMN execution_batch_id VARCHAR(26) NULL;

CREATE TABLE atp_execution_owner_audit (
    audit_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    aggregate_type VARCHAR(32) NOT NULL,
    aggregate_id VARCHAR(26) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    action VARCHAR(64) NOT NULL,
    actor_user_id VARCHAR(26) NOT NULL,
    previous_status VARCHAR(32) NULL,
    new_status VARCHAR(32) NULL,
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000) NULL,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id),
    CONSTRAINT ck_atp_execution_owner_audit_type
        CHECK (aggregate_type IN ('RUN_TASK', 'EXECUTION_ATTEMPT'))
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_execution_owner_audit
    ADD INDEX idx_atp_execution_owner_audit_aggregate (aggregate_type, aggregate_id, occurred_at);

ALTER TABLE atp_execution_owner_audit
    ADD CONSTRAINT fk_atp_execution_owner_audit_project
        FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    ADD CONSTRAINT fk_atp_execution_owner_audit_actor
        FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

DELIMITER $$
CREATE TRIGGER trg_atp_execution_owner_audit_no_update
BEFORE UPDATE ON atp_execution_owner_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_execution_owner_audit is append-only';
END$$

CREATE TRIGGER trg_atp_execution_owner_audit_no_delete
BEFORE DELETE ON atp_execution_owner_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_execution_owner_audit is append-only';
END$$
DELIMITER ;
