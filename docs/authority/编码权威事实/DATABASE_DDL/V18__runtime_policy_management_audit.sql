-- Project RuntimePolicy Revision formal management audit.
-- Existing V16/V17 policy revisions remain immutable; this migration adds only append-only audit.

CREATE TABLE atp_project_runtime_policy_audit (
    audit_id VARCHAR(26) NOT NULL,
    runtime_policy_revision_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NOT NULL,
    action VARCHAR(32) NOT NULL,
    actor_user_id VARCHAR(26) NOT NULL,
    required_permission VARCHAR(64) NOT NULL,
    previous_status VARCHAR(10),
    new_status VARCHAR(10) NOT NULL,
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000) NOT NULL,
    policy_snapshot_json JSON NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id),
    CONSTRAINT ck_atp_runtime_policy_audit_action CHECK (action = 'CREATE_AND_PUBLISH'),
    CONSTRAINT ck_atp_runtime_policy_audit_new_status CHECK (new_status = 'PUBLISHED'),
    CONSTRAINT fk_atp_runtime_policy_audit_revision FOREIGN KEY (runtime_policy_revision_id) REFERENCES atp_project_runtime_policy_revision (runtime_policy_revision_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runtime_policy_audit_project FOREIGN KEY (project_id) REFERENCES atp_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_atp_runtime_policy_audit_actor FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE atp_project_runtime_policy_audit
    ADD INDEX ix_atp_runtime_policy_audit_policy_time (runtime_policy_revision_id, occurred_at),
    ADD INDEX ix_atp_runtime_policy_audit_project_time (project_id, occurred_at);

DELIMITER $$
CREATE TRIGGER trg_atp_runtime_policy_audit_no_update
BEFORE UPDATE ON atp_project_runtime_policy_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'atp_project_runtime_policy_audit is append-only';
END$$

CREATE TRIGGER trg_atp_runtime_policy_audit_no_delete
BEFORE DELETE ON atp_project_runtime_policy_audit
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'atp_project_runtime_policy_audit is append-only';
END$$
DELIMITER ;
