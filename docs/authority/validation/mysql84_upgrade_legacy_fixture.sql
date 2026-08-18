-- Full-schema upgrade fixture: materialize a legitimate pre-boundary idempotency row.
-- The boundary migration must preserve this row with contract_version=1 even though the post-upgrade default becomes 2.
INSERT INTO atp_idempotency_record
  (idempotency_key, operation_id, request_hash, response_status, response_json, expires_at)
VALUES
  ('FULL_SCHEMA_GATE_LEGACY_V1', 'legacy_full_schema_gate', REPEAT('0', 64), 200, NULL, DATE_ADD(NOW(6), INTERVAL 1 DAY));
