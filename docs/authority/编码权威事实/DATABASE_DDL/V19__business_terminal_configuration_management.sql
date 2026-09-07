-- Business Terminal configuration management: preserve the original publication timestamp.

ALTER TABLE atp_environment_terminal_access_revision
  ADD COLUMN published_at DATETIME(6) NULL AFTER lifecycle_status;

UPDATE atp_environment_terminal_access_revision
SET published_at = updated_at
WHERE lifecycle_status IN ('PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED');
