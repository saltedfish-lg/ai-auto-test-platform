-- Repair publication evidence introduced by the prior business-terminal configuration migration.
-- Historical non-current revisions may have updated_at values from supersede/retire/archive
-- transitions, so those timestamps cannot truthfully prove the original publication time.
-- Keep current PUBLISHED rows intact; unknown historical publication timestamps remain NULL.

UPDATE atp_environment_terminal_access_revision
SET published_at = NULL
WHERE lifecycle_status IN ('SUPERSEDED', 'RETIRED', 'ARCHIVED');
