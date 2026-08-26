-- Environment Management Foundation: resolve the optional terminal-access boundary,
-- enforce project-scoped identity, and persist non-sensitive command audit evidence.

ALTER TABLE atp_environment
  MODIFY COLUMN environment_terminal_access_revision_id VARCHAR(26) NULL;

ALTER TABLE atp_environment
  DROP INDEX uq_atp_environment_business,
  ADD CONSTRAINT uq_atp_environment_business UNIQUE (project_id, environment_code),
  ADD INDEX idx_atp_environment_project_status (project_id, lifecycle_status),
  ADD INDEX idx_atp_environment_project_enablement (project_id, enablement_state);

CREATE TABLE atp_environment_audit (
  audit_id VARCHAR(26) NOT NULL,
  environment_id VARCHAR(26) NULL,
  project_id VARCHAR(26) NOT NULL,
  environment_code VARCHAR(191) NOT NULL,
  action VARCHAR(64) NOT NULL,
  operation_id VARCHAR(128) NOT NULL,
  actor_user_id VARCHAR(26) NOT NULL,
  required_permission VARCHAR(128) NOT NULL,
  scope_decision VARCHAR(64) NOT NULL,
  previous_status VARCHAR(11),
  new_status VARCHAR(11) NULL,
  result_code VARCHAR(64) NOT NULL,
  reason VARCHAR(1000),
  before_json JSON,
  after_json JSON,
  correlation_id VARCHAR(128) NOT NULL,
  occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  source_context_hash BINARY(32) NOT NULL,
  PRIMARY KEY (audit_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_environment_audit
  ADD CONSTRAINT fk_atp_environment_audit_environment
  FOREIGN KEY (environment_id) REFERENCES atp_environment (environment_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_environment_audit
  ADD CONSTRAINT fk_atp_environment_audit_project
  FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_environment_audit
  ADD CONSTRAINT fk_atp_environment_audit_actor
  FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX idx_atp_environment_audit_resource
  ON atp_environment_audit (project_id, environment_id, occurred_at);

CREATE TRIGGER trg_atp_environment_audit_no_update
BEFORE UPDATE ON atp_environment_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_environment_audit is append-only';

CREATE TRIGGER trg_atp_environment_audit_no_delete
BEFORE DELETE ON atp_environment_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_environment_audit is append-only';
