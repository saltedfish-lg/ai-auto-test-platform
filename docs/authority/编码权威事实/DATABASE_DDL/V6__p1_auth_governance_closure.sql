-- Current living-authority P1 authentication governance closure.
-- Additive migration after V3/V4/V5. GOV-P1-001 only: immutable authentication security audit.

CREATE TABLE atp_auth_security_audit (
    audit_id VARCHAR(26) NOT NULL,
    action VARCHAR(32) NOT NULL,
    operation_id VARCHAR(128) NOT NULL,
    actor_id VARCHAR(26),
    target_user_id VARCHAR(26),
    session_id VARCHAR(26),
    result_code VARCHAR(64) NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL,
    source_context_hash BINARY(32) NOT NULL,
    PRIMARY KEY (audit_id)
) ENGINE=InnoDB CHARSET=utf8mb4;

CREATE INDEX ix_atp_auth_security_audit_correlation
    ON atp_auth_security_audit (correlation_id);

CREATE INDEX ix_atp_auth_security_audit_occurred_at
    ON atp_auth_security_audit (occurred_at);

CREATE TRIGGER trg_atp_auth_security_audit_no_update
BEFORE UPDATE ON atp_auth_security_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_auth_security_audit is append-only';

CREATE TRIGGER trg_atp_auth_security_audit_no_delete
BEFORE DELETE ON atp_auth_security_audit
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'atp_auth_security_audit is append-only';
