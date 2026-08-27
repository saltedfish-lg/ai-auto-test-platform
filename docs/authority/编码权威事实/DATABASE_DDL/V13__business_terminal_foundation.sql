-- Business Terminal Foundation: terminal-owned immutable access revisions.

ALTER TABLE atp_environment
  DROP FOREIGN KEY fk_atp_environment_environment_terminal_access_revision_id,
  DROP COLUMN environment_terminal_access_revision_id;

ALTER TABLE atp_business_terminal
  DROP FOREIGN KEY fk_atp_business_terminal_environment_id,
  DROP FOREIGN KEY fk_atp_business_terminal_project_id,
  DROP INDEX uq_atp_business_terminal_business,
  MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
  MODIFY COLUMN terminal_code VARCHAR(191) NOT NULL,
  MODIFY COLUMN environment_id VARCHAR(26) NOT NULL,
  ADD COLUMN terminal_type VARCHAR(16) NOT NULL AFTER environment_id,
  ADD COLUMN current_published_revision_id VARCHAR(26) NULL AFTER terminal_type,
  ADD CONSTRAINT uq_atp_business_terminal_business UNIQUE (project_id, terminal_code),
  ADD CONSTRAINT uq_atp_business_terminal_scope
    UNIQUE (business_terminal_id, project_id, environment_id),
  ADD CONSTRAINT ck_atp_business_terminal_type
    CHECK (terminal_type IN ('MANAGEMENT', 'CLIENT', 'PDA')),
  ADD INDEX idx_atp_business_terminal_environment_status (environment_id, lifecycle_status),
  ADD INDEX idx_atp_business_terminal_project_type (project_id, terminal_type);

ALTER TABLE atp_login_strategy
  DROP FOREIGN KEY fk_atp_login_strategy_project_id,
  DROP FOREIGN KEY fk_atp_login_strategy_automation_asset_id,
  MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
  MODIFY COLUMN automation_asset_id VARCHAR(26) NOT NULL,
  ADD COLUMN local_storage_presets JSON NOT NULL AFTER automation_asset_id,
  ADD COLUMN refresh_after_local_storage BOOLEAN NOT NULL DEFAULT FALSE AFTER local_storage_presets,
  ADD COLUMN captcha_policy VARCHAR(24) NOT NULL DEFAULT 'NONE' AFTER refresh_after_local_storage,
  ADD COLUMN captcha_request_header_name VARCHAR(191) NULL AFTER captcha_policy,
  ADD COLUMN captcha_request_header_value VARCHAR(191) NULL AFTER captcha_request_header_name,
  ADD COLUMN captcha_response_header_name VARCHAR(191) NULL AFTER captcha_request_header_value,
  ADD COLUMN session_policy JSON NULL AFTER captcha_response_header_name,
  ADD CONSTRAINT ck_atp_login_strategy_captcha_policy
    CHECK (captcha_policy IN ('NONE', 'RESPONSE_HEADER')),
  ADD CONSTRAINT uq_atp_login_strategy_scope UNIQUE (login_strategy_id, project_id),
  ADD INDEX idx_atp_login_strategy_project_status (project_id, lifecycle_status);

ALTER TABLE atp_automation_asset
  MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
  ADD CONSTRAINT uq_atp_automation_asset_scope UNIQUE (automation_asset_id, project_id);

ALTER TABLE atp_environment
  ADD CONSTRAINT uq_atp_environment_scope UNIQUE (environment_id, project_id);

ALTER TABLE atp_environment_terminal_access_revision
  DROP FOREIGN KEY fk_atp_environment_terminal_access_revision_environment_id,
  DROP FOREIGN KEY fk_atp_environment_terminal_access_revision_project_id,
  MODIFY COLUMN project_id VARCHAR(26) NOT NULL,
  MODIFY COLUMN environment_id VARCHAR(26) NOT NULL,
  ADD COLUMN revision_no BIGINT UNSIGNED NOT NULL AFTER business_terminal_id,
  ADD COLUMN entry_url VARCHAR(2048) NOT NULL AFTER revision_no,
  ADD COLUMN login_url VARCHAR(2048) NULL AFTER entry_url,
  ADD COLUMN login_strategy_id VARCHAR(26) NULL AFTER login_url,
  ADD COLUMN login_prerequisites JSON NULL AFTER login_strategy_id,
  ADD COLUMN network_requirements JSON NULL AFTER login_prerequisites,
  ADD CONSTRAINT uq_atp_terminal_access_revision_business
    UNIQUE (business_terminal_id, revision_no),
  ADD CONSTRAINT uq_atp_terminal_access_revision_owner
    UNIQUE (environment_terminal_access_revision_id, business_terminal_id),
  ADD INDEX idx_atp_terminal_access_revision_status
    (business_terminal_id, lifecycle_status, revision_no);

ALTER TABLE atp_environment_terminal_access_revision
  ADD CONSTRAINT fk_atp_terminal_access_revision_terminal_scope
    FOREIGN KEY (business_terminal_id, project_id, environment_id)
    REFERENCES atp_business_terminal (business_terminal_id, project_id, environment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT fk_atp_terminal_access_revision_environment_v13
    FOREIGN KEY (environment_id) REFERENCES atp_environment (environment_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_environment_terminal_access_revision
  ADD CONSTRAINT fk_atp_terminal_access_revision_project_v13
    FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_environment_terminal_access_revision
  ADD CONSTRAINT fk_atp_terminal_access_revision_login_strategy_scope
    FOREIGN KEY (login_strategy_id, project_id)
    REFERENCES atp_login_strategy (login_strategy_id, project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_business_terminal
  ADD CONSTRAINT fk_atp_business_terminal_environment_scope
    FOREIGN KEY (environment_id, project_id)
    REFERENCES atp_environment (environment_id, project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_business_terminal
  ADD CONSTRAINT fk_atp_business_terminal_project_v13
    FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_login_strategy
  ADD CONSTRAINT fk_atp_login_strategy_project_v13
    FOREIGN KEY (project_id) REFERENCES atp_project (project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_login_strategy
  ADD CONSTRAINT fk_atp_login_strategy_automation_asset_scope
    FOREIGN KEY (automation_asset_id, project_id)
    REFERENCES atp_automation_asset (automation_asset_id, project_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_business_terminal
  ADD CONSTRAINT fk_atp_business_terminal_current_revision
    FOREIGN KEY (current_published_revision_id, business_terminal_id)
    REFERENCES atp_environment_terminal_access_revision
      (environment_terminal_access_revision_id, business_terminal_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE atp_business_terminal_audit (
  audit_id VARCHAR(26) NOT NULL,
  business_terminal_id VARCHAR(26) NOT NULL,
  environment_id VARCHAR(26) NOT NULL,
  project_id VARCHAR(26) NOT NULL,
  action VARCHAR(64) NOT NULL,
  operation_id VARCHAR(128) NOT NULL,
  actor_user_id VARCHAR(26) NOT NULL,
  required_permission VARCHAR(128) NOT NULL,
  previous_status VARCHAR(11) NULL,
  new_status VARCHAR(11) NULL,
  result_code VARCHAR(64) NOT NULL,
  reason VARCHAR(1000) NULL,
  before_json JSON NULL,
  after_json JSON NULL,
  correlation_id VARCHAR(128) NOT NULL,
  occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  source_context_hash BINARY(32) NOT NULL,
  PRIMARY KEY (audit_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_business_terminal_audit
  ADD CONSTRAINT fk_atp_business_terminal_audit_terminal
  FOREIGN KEY (business_terminal_id) REFERENCES atp_business_terminal (business_terminal_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_business_terminal_audit
  ADD CONSTRAINT fk_atp_business_terminal_audit_actor
  FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX idx_atp_business_terminal_audit_resource
  ON atp_business_terminal_audit (project_id, business_terminal_id, occurred_at);

CREATE TRIGGER trg_atp_business_terminal_audit_no_update
BEFORE UPDATE ON atp_business_terminal_audit FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_business_terminal_audit is append-only';

CREATE TRIGGER trg_atp_business_terminal_audit_no_delete
BEFORE DELETE ON atp_business_terminal_audit FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_business_terminal_audit is append-only';

CREATE TABLE atp_login_strategy_audit (
  audit_id VARCHAR(26) NOT NULL,
  login_strategy_id VARCHAR(26) NOT NULL,
  automation_asset_id VARCHAR(26) NOT NULL,
  project_id VARCHAR(26) NOT NULL,
  action VARCHAR(64) NOT NULL,
  operation_id VARCHAR(128) NOT NULL,
  actor_user_id VARCHAR(26) NOT NULL,
  required_permission VARCHAR(128) NOT NULL,
  previous_status VARCHAR(17) NULL,
  new_status VARCHAR(17) NULL,
  result_code VARCHAR(64) NOT NULL,
  reason VARCHAR(1000) NULL,
  before_json JSON NULL,
  after_json JSON NULL,
  correlation_id VARCHAR(128) NOT NULL,
  occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  source_context_hash BINARY(32) NOT NULL,
  PRIMARY KEY (audit_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE atp_login_strategy_audit
  ADD CONSTRAINT fk_atp_login_strategy_audit_strategy
  FOREIGN KEY (login_strategy_id) REFERENCES atp_login_strategy (login_strategy_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE atp_login_strategy_audit
  ADD CONSTRAINT fk_atp_login_strategy_audit_actor
  FOREIGN KEY (actor_user_id) REFERENCES atp_user (user_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX idx_atp_login_strategy_audit_resource
  ON atp_login_strategy_audit (project_id, login_strategy_id, occurred_at);

CREATE TRIGGER trg_atp_login_strategy_audit_no_update
BEFORE UPDATE ON atp_login_strategy_audit FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_login_strategy_audit is append-only';

CREATE TRIGGER trg_atp_login_strategy_audit_no_delete
BEFORE DELETE ON atp_login_strategy_audit FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_login_strategy_audit is append-only';
