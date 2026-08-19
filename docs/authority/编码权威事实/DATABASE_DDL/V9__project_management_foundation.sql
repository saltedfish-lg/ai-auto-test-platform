-- Project management foundation: project identity, owner membership integrity, and immutable business audit.

UPDATE atp_project
SET project_code = CONCAT('legacy-', project_id)
WHERE project_code IS NULL OR project_code = '';

ALTER TABLE atp_project
    MODIFY COLUMN project_code VARCHAR(191) NOT NULL;

-- Preserve the supporting index required by fk_atp_project_member_user_id before
-- replacing the legacy one-column business unique key.
ALTER TABLE atp_project_member
    ADD INDEX ix_atp_project_member_user_id (user_id);

ALTER TABLE atp_project_member
    DROP INDEX uq_atp_project_member_business,
    MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
    MODIFY COLUMN user_id VARCHAR(26) NOT NULL,
    ADD CONSTRAINT uq_atp_project_member_business UNIQUE (project_id, user_id);

CREATE TABLE atp_project_audit (
    audit_id VARCHAR(26) NOT NULL,
    project_id VARCHAR(26) NULL,
    project_code VARCHAR(191) NOT NULL,
    action VARCHAR(32) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    actor_user_id VARCHAR(26) NOT NULL,
    participant_user_id VARCHAR(26) NULL,
    required_permission VARCHAR(128) NOT NULL,
    scope_decision VARCHAR(64) NOT NULL,
    previous_status VARCHAR(17) NULL,
    new_status VARCHAR(17) NULL,
    result_code VARCHAR(64) NOT NULL,
    reason VARCHAR(1000) NULL,
    correlation_id VARCHAR(128) NOT NULL,
    source_context_hash BINARY(32) NOT NULL,
    occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (audit_id),
    CONSTRAINT ck_atp_project_audit_action
        CHECK (action IN (
            'PROJECT_CREATED',
            'PROJECT_UPDATED',
            'PROJECT_DISABLED',
            'PROJECT_RECOVERED',
            'PROJECT_ARCHIVED',
            'PROJECT_OPERATION_DENIED',
            'PROJECT_OPERATION_FAILED'
        )),
    CONSTRAINT ck_atp_project_audit_scope_decision
        CHECK (scope_decision IN ('ALLOWED', 'DENIED', 'NOT_APPLICABLE', 'DYNAMIC_PROJECT_OWNER_ALL'))
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_project_audit
    ADD CONSTRAINT fk_atp_project_audit_actor_user_id
    FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_project_audit
    ADD CONSTRAINT fk_atp_project_audit_participant_user_id
    FOREIGN KEY (participant_user_id) REFERENCES atp_user (user_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX ix_atp_project_audit_project_occurred
    ON atp_project_audit (project_id, occurred_at);

CREATE INDEX ix_atp_project_audit_actor_occurred
    ON atp_project_audit (actor_user_id, occurred_at);

CREATE INDEX ix_atp_project_audit_correlation
    ON atp_project_audit (correlation_id);
