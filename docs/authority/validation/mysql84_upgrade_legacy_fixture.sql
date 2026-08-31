-- Full-schema upgrade fixture: materialize a legitimate pre-boundary idempotency row.
-- The boundary migration must preserve this row with contract_version=1 even though the post-upgrade default becomes 2.
INSERT INTO atp_idempotency_record
  (idempotency_key, operation_id, request_hash, response_status, response_json, expires_at)
VALUES
  ('FULL_SCHEMA_GATE_LEGACY_V1', 'legacy_full_schema_gate', REPEAT('0', 64), 200, NULL, DATE_ADD(NOW(6), INTERVAL 1 DAY));

-- Materialize a legitimate pre-V15 Runner aggregate whose Project is carried by
-- the legacy binding relation. V15 must backfill ownership before removing that
-- relation, preserve the Runner, and safely revoke the non-recoverable old Agent.
INSERT INTO atp_project
  (project_id, project_code, lifecycle_status, display_name, row_version)
VALUES
  (CONCAT('P', REPEAT('0', 25)), 'LEGACY-RUNNER-PROJECT', 'ACTIVE', 'Legacy Runner Project', 1);

SET FOREIGN_KEY_CHECKS = 0;
INSERT INTO atp_runner
  (runner_id, project_id, runner_code, runner_project_binding_id, health_status,
   scheduling_status, registration_state, authentication_state, connection_state,
   health_state, enablement_state, binding_state, scheduling_state, resource_state,
   lifecycle_status, display_name, row_version)
VALUES
  (CONCAT('R', REPEAT('0', 25)), NULL, 'LEGACY-RUNNER-01', CONCAT('B', REPEAT('0', 25)),
   'HEALTHY', 'ENABLED', 'REGISTERED', 'AUTHENTICATED', 'ONLINE', 'HEALTHY',
   'ENABLED', 'BOUND', 'IDLE', 'AVAILABLE', 'AUTHENTICATED', 'Legacy Runner', 3);

INSERT INTO atp_runner_project_binding
  (runner_project_binding_id, project_id, runner_id, effective_at, lifecycle_status,
   display_name, row_version)
VALUES
  (CONCAT('B', REPEAT('0', 25)), CONCAT('P', REPEAT('0', 25)), CONCAT('R', REPEAT('0', 25)),
   'legacy-effective', 'ACTIVE', 'Legacy Binding', 1);
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO atp_runner_agent
  (runner_agent_id, project_id, runner_id, lifecycle_status, display_name, row_version)
VALUES
  (CONCAT('A', REPEAT('0', 25)), NULL, CONCAT('R', REPEAT('0', 25)), 'CREATED',
   'Legacy Agent', 1);

INSERT INTO atp_runner_capability
  (runner_capability_id, project_id, runner_id, capability_code, lifecycle_status,
   display_name, row_version)
VALUES
  (CONCAT('C', REPEAT('0', 25)), NULL, CONCAT('R', REPEAT('0', 25)), 'AGENT_VERSION',
   'CREATED', 'Legacy Agent Version', 1);
