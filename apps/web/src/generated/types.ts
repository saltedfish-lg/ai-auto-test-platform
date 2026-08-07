/* Generated from PDBR-2026.08.07-R4.2 OpenAPI. DO NOT EDIT. */



export type LoginRequest = {
  username: string;
  password: string;
};

export type AuthCookieActionRequest = Record<string, unknown>;

export type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
};

export type CurrentUserResource = {
  user_id: string;
  username: string;
  display_name?: string | null;
  lifecycle_status: "ACTIVE";
  roles: Array<string>;
  permissions: Array<string>;
  force_password_change: boolean;
};

export type AuthenticationTokenResource = {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  current_user: CurrentUserResource;
};

export type AuthenticationResponse = {
  data: AuthenticationTokenResource;
  correlation_id: string;
};

export type CurrentUserResponse = {
  data: CurrentUserResource;
  correlation_id: string;
};

export type AuthenticationErrorCode = "AUTH_REQUIRED" | "AUTH_INVALID_CREDENTIALS" | "AUTH_TOKEN_INVALID" | "AUTH_TOKEN_EXPIRED" | "AUTH_SESSION_REVOKED" | "AUTH_IDENTITY_NOT_FOUND" | "AUTH_PERMISSION_DENIED" | "AUTH_ACCOUNT_LOCKED" | "AUTH_ACCOUNT_DISABLED" | "AUTH_ACCOUNT_ARCHIVED" | "AUTH_ACCOUNT_TEMPORARILY_LOCKED" | "AUTH_PASSWORD_CHANGE_REQUIRED" | "AUTH_OPERATION_FORBIDDEN_FOR_STATE";

export type AuthenticationProblemDetails = ProblemDetails & {
  code?: AuthenticationErrorCode;
};

export type ProblemDetails = {
  type: string;
  title: string;
  status: number;
  code: string;
  detail?: string | null;
  correlation_id: string;
  field_errors?: Array<{
  field: string;
  message: string;
}>;
};

export type PageMeta = {
  page: number;
  page_size: number;
  total: number;
  next_cursor?: string | null;
};

export type UserResource = {
  user_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  username?: string | null;
  role_binding_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "LOCKED" | "DISABLED" | "RECOVERING" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type AdminResource = {
  admin_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  username?: string | null;
  user_id?: string | null;
  lifecycle_status: "INITIALIZED" | "ACTIVE" | "LOCKED";
};

export type RoleResource = {
  role_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  role_code?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type EntitySuperAdminRoleResource = {
  entity_super_admin_role_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  role_code?: string | null;
  role_id?: string | null;
  lifecycle_status: "INITIALIZED" | "ACTIVE" | "LOCKED";
};

export type PermissionCodeResource = {
  permission_code_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  permission_code?: string | null;
  role_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ProjectResource = {
  project_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_code?: string | null;
  lifecycle_status: "CREATED" | "CONFIGURING" | "VALIDATING" | "ACTIVE" | "DISABLED" | "RECOVERING" | "ARCHIVED" | "CLEANUP_PENDING" | "LOGICALLY_DELETED";
};

export type ProjectMemberResource = {
  project_member_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  user_id?: string | null;
  role_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type EnvironmentResource = {
  environment_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  environment_code?: string | null;
  environment_terminal_access_revision_id?: string | null;
  lifecycle_status: "CREATED" | "CONFIGURING" | "VALIDATING" | "ACTIVE" | "UNREACHABLE" | "DISABLED" | "RECOVERING" | "ARCHIVED";
  enablement_state: "ENABLED" | "DISABLED";
  accessibility_state: "UNKNOWN" | "REACHABLE" | "UNREACHABLE";
};

export type BusinessModuleResource = {
  business_module_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  module_code?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type BusinessTerminalResource = {
  business_terminal_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  terminal_code?: string | null;
  environment_id?: string | null;
  lifecycle_status: "CREATED" | "CONFIGURING" | "VALIDATING" | "ACTIVE" | "UNREACHABLE" | "DISABLED" | "RECOVERING" | "ARCHIVED";
};

export type EnvironmentTerminalAccessRevisionResource = {
  environment_terminal_access_revision_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  environment_id?: string | null;
  business_terminal_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type TestAccountResource = {
  test_account_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  environment_id?: string | null;
  account_identifier?: string | null;
  sso_identity_id?: string | null;
  login_qualification_id?: string | null;
  lifecycle_status: "CREATED" | "CONFIGURING" | "VALIDATING" | "ACTIVE" | "CREDENTIAL_EXPIRED" | "DISABLED" | "RECOVERING" | "ARCHIVED";
  credential_state: "VALID" | "EXPIRING" | "EXPIRED" | "REVOKED";
};

export type CredentialRevisionResource = {
  credential_revision_id: string;
  test_account_id: string;
  project_id: string;
  revision_no: number;
  secret_ref?: string;
  published_at?: string | null;
  superseded_by_revision_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
};

export type AccountMappingRevisionResource = {
  account_mapping_revision_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  test_account_id?: string | null;
  environment_id?: string | null;
  business_terminal_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type SsoIdentityResource = {
  sso_identity_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  environment_id?: string | null;
  sso_identity_key?: string | null;
  test_account_id?: string | null;
  lease_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type LoginQualificationResource = {
  login_qualification_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  test_account_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type TestDataTypeResource = {
  test_data_type_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  data_type_code?: string | null;
  test_data_resource_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type TestDataResourceResource = {
  test_data_resource_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  environment_id?: string | null;
  resource_key?: string | null;
  test_data_type_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type DataOperationTaskResource = {
  data_operation_task_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  test_data_resource_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type NaturalLanguageCaseResource = {
  natural_language_case_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  page_exploration_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "CONVERSION_REQUESTED" | "EXPLORATION_REQUESTED" | "STRUCTURED_DRAFT_PRODUCED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type StandardCaseResource = {
  standard_case_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  case_code?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "VALIDATING" | "READY" | "DISABLED" | "RECOVERING" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type CaseVersionResource = {
  case_version_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  case_id?: string | null;
  version_no?: string | null;
  standard_case_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type CaseSuiteResource = {
  case_suite_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  suite_code?: string | null;
  case_version_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type BusinessFlowTemplateResource = {
  business_flow_template_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type CrossTerminalOrchestrationResource = {
  cross_terminal_orchestration_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  business_flow_template_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type PageExplorationResource = {
  page_exploration_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  runner_id?: string | null;
  ai_candidate_revision_id?: string | null;
  lifecycle_status: "CREATED" | "VALIDATING" | "WAITING_RUNNER" | "PREPARING" | "EXPLORING" | "WAITING_CONFIRMATION" | "SUCCEEDED" | "FAILED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "RECOVERING" | "ARCHIVED";
};

export type ManualRecordingTaskResource = {
  manual_recording_task_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  status: "ASSIGNED" | "CANCELLED" | "COMPLETED" | "CREATED" | "FAILED" | "PARTIAL" | "RECORDING";
  lifecycle_status: "CREATED" | "WAITING_RUNNER" | "PREPARING" | "WAITING_USER" | "RUNNING" | "PAUSED" | "DISCONNECTED" | "RECOVERABLE" | "RECOVERING" | "ENDED" | "PENDING_CONVERSION" | "PENDING_CONFIRMATION" | "COMPLETED" | "CANCELED" | "ABORTED" | "RECOVERY_FAILED" | "ARCHIVED";
};

export type ManualRecordingSessionResource = {
  manual_recording_session_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  manual_recording_task_id?: string | null;
  runner_id?: string | null;
  test_account_id?: string | null;
  manual_recording_control_lease_id?: string | null;
  recording_evidence_bundle_id?: string | null;
  status: "ABORTED" | "ACTIVE" | "COMPLETED" | "CREATED" | "PARTIAL" | "PAUSED";
  lifecycle_status: "CREATED" | "WAITING_RUNNER" | "PREPARING" | "WAITING_USER" | "RUNNING" | "PAUSED" | "DISCONNECTED" | "RECOVERABLE" | "RECOVERING" | "ENDED" | "PENDING_CONVERSION" | "PENDING_CONFIRMATION" | "COMPLETED" | "CANCELED" | "ABORTED" | "RECOVERY_FAILED" | "ARCHIVED";
};

export type ManualRecordingControlLeaseResource = {
  manual_recording_control_lease_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  manual_recording_task_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type RecordingEvidenceBundleResource = {
  recording_evidence_bundle_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  manual_recording_task_id?: string | null;
  ai_candidate_revision_id?: string | null;
  lifecycle_status: "COLLECTED" | "UPLOAD_PENDING" | "UPLOADING" | "STORED" | "UPLOAD_FAILED" | "RETRYING" | "RETAINED" | "EXTENDED_RETENTION" | "HELD" | "CLEANUP_PENDING" | "CLEANED" | "ARCHIVED";
};

export type RunTaskResource = {
  run_task_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  idempotency_key?: string | null;
  case_suite_id?: string | null;
  environment_id?: string | null;
  lifecycle_status: "CREATED" | "SNAPSHOTTED" | "VALIDATING" | "WAITING_RESOURCE" | "DISPATCHING" | "PREPARING" | "RUNNING" | "RETRYING" | "CANCELING" | "ABORTING" | "EXCEPTION" | "RECOVERING" | "COMPLETED" | "REPORTING" | "ARCHIVED";
  task_state: "CREATED" | "WAITING_RESOURCE" | "RUNNING" | "RETRYING" | "COMPLETED" | "CANCELED" | "ABORTED" | "EXCEPTION";
  final_result: "PASSED" | "FAILED" | "CANCELED" | "ABORTED" | "PARTIAL" | "UNKNOWN";
};

export type ExecutionAttemptResource = {
  execution_attempt_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  run_task_id?: string | null;
  attempt_no?: string | null;
  case_attempt_id?: string | null;
  runner_id?: string | null;
  configuration_snapshot_id?: string | null;
  execution_batch_id?: string | null;
  lease_id?: string | null;
  execution_lock_id?: string | null;
  execution_status: "ABORTED" | "BROKEN" | "CANCELLED" | "FAILED" | "PRESTART_BLOCKED" | "READY" | "RUNNING" | "SUCCEEDED";
  finalization_status: "COMPLETED" | "INITIAL" | "IN_PROGRESS" | "PENDING_RECOVERY";
  lifecycle_status: "CREATED" | "PREPARING" | "RUNNING" | "PASSED" | "FAILED" | "SKIPPED" | "NOT_EXECUTED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "EXCEPTION" | "COMPLETED";
};

export type CaseAttemptResource = {
  case_attempt_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  run_task_id?: string | null;
  execution_attempt_id?: string | null;
  result_status: "BROKEN" | "CANCELLED" | "FAILED" | "PASSED" | "SKIPPED";
  lifecycle_status: "CREATED" | "PREPARING" | "RUNNING" | "PASSED" | "FAILED" | "SKIPPED" | "NOT_EXECUTED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "EXCEPTION" | "COMPLETED";
};

export type ExecutionPlanResource = {
  execution_plan_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  plan_code?: string | null;
  run_task_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "VALIDATING" | "ACTIVE" | "TRIGGERED" | "PAUSED" | "DISABLED" | "RECOVERING" | "ARCHIVED";
};

export type ExecutionPlanRevisionResource = {
  execution_plan_revision_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  plan_id?: string | null;
  revision_no?: string | null;
  execution_plan_id?: string | null;
  case_suite_id?: string | null;
  environment_id?: string | null;
  trigger_rule_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type TriggerRuleResource = {
  trigger_rule_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  execution_plan_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ExecutionLockResource = {
  execution_lock_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  lease_id?: string | null;
  lifecycle_status: "REQUESTED" | "WAITING" | "ACQUIRED" | "HELD" | "RENEWING" | "RELEASED" | "EXPIRED" | "REVOKED" | "RECOVERING" | "ARCHIVED";
};

export type LeaseResource = {
  lease_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  execution_slot_id?: string | null;
  status: "ACTIVE" | "EXPIRED" | "FENCED" | "RELEASED";
  lifecycle_status: "REQUESTED" | "WAITING" | "ACQUIRED" | "HELD" | "RENEWING" | "RELEASED" | "EXPIRED" | "REVOKED" | "RECOVERING" | "ARCHIVED";
};

export type AutomationAssetResource = {
  automation_asset_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type LoginStrategyResource = {
  login_strategy_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  automation_asset_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type PageObjectResource = {
  page_object_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  automation_asset_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ActionAssetResource = {
  action_asset_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  automation_asset_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type AssertionAssetResource = {
  assertion_asset_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  automation_asset_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type RunnerResource = {
  runner_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  runner_code?: string | null;
  runner_project_binding_id?: string | null;
  project_id?: string | null;
  health_status: "DEGRADED" | "HEALTHY" | "OFFLINE" | "UNHEALTHY" | "UNKNOWN";
  scheduling_status: "DISABLED" | "DRAINING" | "ENABLED";
  registration_state: "UNREGISTERED" | "REGISTERED" | "DEREGISTERED";
  authentication_state: "UNAUTHENTICATED" | "AUTHENTICATED" | "REVOKED";
  connection_state: "ONLINE" | "OFFLINE" | "DISCONNECTED";
  health_state: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  enablement_state: "ENABLED" | "DISABLED" | "DRAINING";
  binding_state: "UNBOUND" | "BOUND";
  scheduling_state: "IDLE" | "RESERVED" | "RUNNING" | "DRAINING";
  resource_state: "AVAILABLE" | "PARTIALLY_ALLOCATED" | "FULLY_ALLOCATED" | "EXHAUSTED";
  lifecycle_status: "REGISTERING" | "REGISTERED" | "AUTHENTICATED" | "BOUND" | "ENABLED" | "ONLINE" | "DEGRADED" | "UNHEALTHY" | "OFFLINE" | "RECOVERING" | "DRAINING" | "DISABLED" | "UNBOUND" | "DEREGISTERED" | "ARCHIVED";
};

export type RunnerCapabilityResource = {
  runner_capability_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  runner_id?: string | null;
  capability_code?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type RunnerProjectBindingResource = {
  runner_project_binding_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  runner_id?: string | null;
  effective_at?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ExecutionSlotResource = {
  execution_slot_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  runner_id?: string | null;
  slot_no?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ContextVariableResource = {
  context_variable_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  execution_context_id?: string | null;
  namespace?: string | null;
  variable_name?: string | null;
  run_task_id?: string | null;
  test_data_resource_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ModelConfigResource = {
  model_config_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  config_code?: string | null;
  lifecycle_status: "CREATED" | "CONFIGURING" | "VALIDATING" | "ACTIVE" | "DEGRADED" | "UNAVAILABLE" | "DISABLED" | "RECOVERING" | "ARCHIVED";
};

export type PromptRevisionResource = {
  prompt_revision_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  prompt_code?: string | null;
  revision_no?: string | null;
  model_config_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type AiCallResource = {
  ai_call_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  ai_task_id?: string | null;
  prompt_revision_id?: string | null;
  lifecycle_status: "CREATED" | "QUEUED" | "PREPARING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "EXCEPTION" | "RECOVERING" | "COMPLETED" | "ARCHIVED";
};

export type AiTaskResource = {
  ai_task_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  ai_result_id?: string | null;
  ai_call_id?: string | null;
  model_config_id?: string | null;
  status: "CANCELLED" | "CREATED" | "FAILED" | "QUEUED" | "RUNNING" | "SUCCEEDED" | "WAITING_HUMAN";
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type AiResultResource = {
  ai_result_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  ai_task_id?: string | null;
  ai_candidate_revision_id?: string | null;
  status: "ACCEPTED" | "CANDIDATE" | "INVALIDATED" | "REJECTED" | "RESTORED" | "SUPERSEDED";
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type HumanDecisionResource = {
  human_decision_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  ai_task_id?: string | null;
  ai_result_id?: string | null;
  audit_log_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type TestReportGenerationRequestResource = {
  test_report_generation_request_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  test_report_id?: string | null;
  status: "CANCELLED" | "FAILED" | "INITIAL" | "QUEUED" | "RUNNING" | "SUCCEEDED";
  lifecycle_status: "CREATED" | "QUEUED" | "PREPARING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "EXCEPTION" | "RECOVERING" | "COMPLETED" | "ARCHIVED";
};

export type TestReportResource = {
  test_report_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  test_artifact_id?: string | null;
  status: "COMPLETED" | "FAILED" | "GENERATING" | "SUPERSEDED";
  report_state: "PENDING" | "GENERATING" | "GENERATED" | "PARTIAL" | "FAILED" | "ARCHIVED";
  lifecycle_status: "PENDING" | "GENERATING" | "GENERATED" | "PARTIAL" | "FAILED" | "REGENERATING" | "ARCHIVED" | "METADATA_RETAINED";
};

export type TestArtifactResource = {
  test_artifact_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  test_report_id?: string | null;
  retention_policy_id?: string | null;
  lifecycle_status: "COLLECTED" | "UPLOAD_PENDING" | "UPLOADING" | "STORED" | "UPLOAD_FAILED" | "RETRYING" | "RETAINED" | "EXTENDED_RETENTION" | "HELD" | "CLEANUP_PENDING" | "CLEANED" | "ARCHIVED";
  upload_state: "PENDING" | "UPLOADING" | "STORED" | "FAILED";
  retention_state: "NORMAL" | "EXTENDED" | "HELD" | "EXPIRED";
  cleanup_state: "NOT_DUE" | "PENDING" | "CLEANED" | "FAILED";
};

export type TechnicalAlertResource = {
  technical_alert_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  signature_config_ref?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type IntegrationComponentResource = {
  integration_component_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  component_code?: string | null;
  lifecycle_status: "CREATED" | "CONFIGURING" | "VALIDATING" | "ACTIVE" | "DEGRADED" | "UNAVAILABLE" | "DISABLED" | "RECOVERING" | "ARCHIVED";
};

export type SystemParameterResource = {
  system_parameter_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  scope?: string | null;
  parameter_key?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type DataDictionaryResource = {
  data_dictionary_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  dictionary_code?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ConfigurationSnapshotResource = {
  configuration_snapshot_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  run_task_id?: string | null;
  lifecycle_status: "CAPTURED" | "SEALED" | "RETAINED" | "ARCHIVED";
};

export type AuditLogResource = {
  audit_log_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  human_decision_id?: string | null;
  lifecycle_status: "CAPTURED" | "SEALED" | "RETAINED" | "ARCHIVED";
};

export type RetentionPolicyResource = {
  retention_policy_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  scope?: string | null;
  policy_code?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type LegalHoldResource = {
  legal_hold_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  retention_policy_id?: string | null;
  controlled_purge_request_id?: string | null;
  test_artifact_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ControlledPurgeRequestResource = {
  controlled_purge_request_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  retention_policy_id?: string | null;
  legal_hold_id?: string | null;
  audit_log_id?: string | null;
  lifecycle_status: "CREATED" | "VALIDATING" | "CLEANUP_EXECUTING" | "SUCCEEDED" | "FAILED" | "CANCELED" | "ARCHIVED";
};

export type TechnicalAlertEndpointResource = {
  technical_alert_endpoint_id: string;
  endpoint_code: string;
  signature_config_ref?: string | null;
  sequence_rule: "STRICTLY_INCREASING" | "MONOTONIC_PER_SOURCE";
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
};

export type PlatformDesignBaselineReleaseResource = {
  platform_design_baseline_release_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  release_id?: string | null;
  data_dictionary_id?: string | null;
  release_status: "DRAFT" | "FROZEN" | "SUPERSEDED";
  readiness_status: "CONDITIONAL_CODE_READY" | "FULL_CODE_READY" | "NOT_CODE_READY";
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type AiCandidateRevisionResource = {
  ai_candidate_revision_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  ai_task_id?: string | null;
  standard_case_id?: string | null;
  lifecycle_status: "DRAFT" | "VALIDATING" | "PUBLISHED" | "SUPERSEDED" | "RETIRED" | "ARCHIVED";
};

export type RoleBindingResource = {
  role_binding_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  subject_id?: string | null;
  role_id?: string | null;
  effective_at?: string | null;
  user_id?: string | null;
  audit_log_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type TechnicalAlertIngestionBatchResource = {
  technical_alert_ingestion_batch_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  batch_key?: string | null;
  signature_config_ref?: string | null;
  technical_alert_id?: string | null;
  lifecycle_status: "CREATED" | "QUEUED" | "PREPARING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "EXCEPTION" | "RECOVERING" | "COMPLETED" | "ARCHIVED";
  technical_alert_endpoint_id: string;
};

export type RunnerAgentResource = {
  runner_agent_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  runner_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ExecutionBatchResource = {
  execution_batch_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  run_task_id?: string | null;
  batch_no?: string | null;
  lifecycle_status: "CREATED" | "PREPARING" | "RUNNING" | "PASSED" | "FAILED" | "SKIPPED" | "NOT_EXECUTED" | "CANCELED" | "ABORTED" | "TIMED_OUT" | "EXCEPTION" | "COMPLETED";
};

export type CaseStepResource = {
  case_step_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  case_version_id?: string | null;
  sequence?: string | null;
  standard_case_id?: string | null;
  business_terminal_id?: string | null;
  action_asset_id?: string | null;
  assertion_asset_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type CaseSuiteItemResource = {
  case_suite_item_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  suite_id?: string | null;
  case_version_id?: string | null;
  case_suite_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ExecutionContextResource = {
  execution_context_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  run_task_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ProjectExecutionConfigurationResource = {
  project_execution_configuration_id: string;
  display_name?: string | null;
  row_version: number;
  created_at: string;
  updated_at: string;
  project_id?: string | null;
  lifecycle_status: "CREATED" | "DRAFT" | "ACTIVE" | "DISABLED" | "RECOVERED" | "ARCHIVED" | "LOGICALLY_DELETED";
};

export type ListUserResponse = {
  items: Array<UserResource>;
  page: PageMeta;
};

export type CreateUserRequest = {
  expected_version?: number;
  reason?: string | null;
  user_id?: string;
  display_name?: string | null;
  username?: string | null;
  role_binding_id?: string | null;
};

export type CreateUserResponse = {
  data: UserResource;
  correlation_id: string;
};

export type GetUserResponse = {
  data: UserResource;
  correlation_id: string;
};

export type UpdateUserRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  username?: string | null;
  role_binding_id?: string | null;
};

export type UpdateUserResponse = {
  data: UserResource;
  correlation_id: string;
};

export type ListRoleResponse = {
  items: Array<RoleResource>;
  page: PageMeta;
};

export type CreateRoleRequest = {
  expected_version?: number;
  reason?: string | null;
  role_id?: string;
  display_name?: string | null;
  role_code?: string | null;
};

export type CreateRoleResponse = {
  data: RoleResource;
  correlation_id: string;
};

export type GetRoleResponse = {
  data: RoleResource;
  correlation_id: string;
};

export type UpdateRoleRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  role_code?: string | null;
};

export type UpdateRoleResponse = {
  data: RoleResource;
  correlation_id: string;
};

export type ListProjectResponse = {
  items: Array<ProjectResource>;
  page: PageMeta;
};

export type CreateProjectRequest = {
  expected_version?: number;
  reason?: string | null;
  project_id?: string;
  display_name?: string | null;
  project_code?: string | null;
};

export type CreateProjectResponse = {
  data: ProjectResource;
  correlation_id: string;
};

export type GetProjectResponse = {
  data: ProjectResource;
  correlation_id: string;
};

export type UpdateProjectRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_code?: string | null;
};

export type UpdateProjectResponse = {
  data: ProjectResource;
  correlation_id: string;
};

export type ListEnvironmentResponse = {
  items: Array<EnvironmentResource>;
  page: PageMeta;
};

export type CreateEnvironmentRequest = {
  expected_version?: number;
  reason?: string | null;
  environment_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  environment_code?: string | null;
  environment_terminal_access_revision_id?: string | null;
  enablement_state?: "ENABLED" | "DISABLED";
  accessibility_state?: "UNKNOWN" | "REACHABLE" | "UNREACHABLE";
};

export type CreateEnvironmentResponse = {
  data: EnvironmentResource;
  correlation_id: string;
};

export type GetEnvironmentResponse = {
  data: EnvironmentResource;
  correlation_id: string;
};

export type UpdateEnvironmentRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  environment_code?: string | null;
  environment_terminal_access_revision_id?: string | null;
  enablement_state?: "ENABLED" | "DISABLED";
  accessibility_state?: "UNKNOWN" | "REACHABLE" | "UNREACHABLE";
};

export type UpdateEnvironmentResponse = {
  data: EnvironmentResource;
  correlation_id: string;
};

export type ListBusinessTerminalResponse = {
  items: Array<BusinessTerminalResource>;
  page: PageMeta;
};

export type CreateBusinessTerminalRequest = {
  expected_version?: number;
  reason?: string | null;
  business_terminal_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  terminal_code?: string | null;
  environment_id?: string | null;
};

export type CreateBusinessTerminalResponse = {
  data: BusinessTerminalResource;
  correlation_id: string;
};

export type GetBusinessTerminalResponse = {
  data: BusinessTerminalResource;
  correlation_id: string;
};

export type UpdateBusinessTerminalRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  terminal_code?: string | null;
  environment_id?: string | null;
};

export type UpdateBusinessTerminalResponse = {
  data: BusinessTerminalResource;
  correlation_id: string;
};

export type ListEnvironmentTerminalAccessRevisionResponse = {
  items: Array<EnvironmentTerminalAccessRevisionResource>;
  page: PageMeta;
};

export type CreateEnvironmentTerminalAccessRevisionRequest = {
  expected_version?: number;
  reason?: string | null;
  environment_terminal_access_revision_id?: string;
  display_name?: string | null;
  environment_id?: string | null;
  business_terminal_id?: string | null;
};

export type CreateEnvironmentTerminalAccessRevisionResponse = {
  data: EnvironmentTerminalAccessRevisionResource;
  correlation_id: string;
};

export type GetEnvironmentTerminalAccessRevisionResponse = {
  data: EnvironmentTerminalAccessRevisionResource;
  correlation_id: string;
};

export type UpdateEnvironmentTerminalAccessRevisionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  environment_id?: string | null;
  business_terminal_id?: string | null;
};

export type UpdateEnvironmentTerminalAccessRevisionResponse = {
  data: EnvironmentTerminalAccessRevisionResource;
  correlation_id: string;
};

export type ListTestAccountResponse = {
  items: Array<TestAccountResource>;
  page: PageMeta;
};

export type CreateTestAccountRequest = {
  expected_version?: number;
  reason?: string | null;
  test_account_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  environment_id?: string | null;
  account_identifier?: string | null;
  sso_identity_id?: string | null;
  login_qualification_id?: string | null;
  credential_state?: "VALID" | "EXPIRING" | "EXPIRED" | "REVOKED";
};

export type CreateTestAccountResponse = {
  data: TestAccountResource;
  correlation_id: string;
};

export type GetTestAccountResponse = {
  data: TestAccountResource;
  correlation_id: string;
};

export type UpdateTestAccountRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  environment_id?: string | null;
  account_identifier?: string | null;
  sso_identity_id?: string | null;
  login_qualification_id?: string | null;
  credential_state?: "VALID" | "EXPIRING" | "EXPIRED" | "REVOKED";
};

export type UpdateTestAccountResponse = {
  data: TestAccountResource;
  correlation_id: string;
};

export type ListCredentialRevisionResponse = {
  items: Array<CredentialRevisionResource>;
  page: PageMeta;
};

export type CreateCredentialRevisionRequest = {
  credential_revision_id: string;
  test_account_id: string;
  project_id: string;
  revision_no: number;
  secret_ref: string;
  display_name?: string | null;
  reason: string;
};

export type CreateCredentialRevisionResponse = {
  data: CredentialRevisionResource;
  correlation_id: string;
};

export type GetCredentialRevisionResponse = {
  data: CredentialRevisionResource;
  correlation_id: string;
};

export type UpdateCredentialRevisionRequest = {
  expected_version: number;
  reason: string;
  display_name?: string | null;
};

export type UpdateCredentialRevisionResponse = {
  data: CredentialRevisionResource;
  correlation_id: string;
};

export type ListAccountMappingRevisionResponse = {
  items: Array<AccountMappingRevisionResource>;
  page: PageMeta;
};

export type CreateAccountMappingRevisionRequest = {
  expected_version?: number;
  reason?: string | null;
  account_mapping_revision_id?: string;
  display_name?: string | null;
  test_account_id?: string | null;
  environment_id?: string | null;
  business_terminal_id?: string | null;
};

export type CreateAccountMappingRevisionResponse = {
  data: AccountMappingRevisionResource;
  correlation_id: string;
};

export type GetAccountMappingRevisionResponse = {
  data: AccountMappingRevisionResource;
  correlation_id: string;
};

export type UpdateAccountMappingRevisionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  test_account_id?: string | null;
  environment_id?: string | null;
  business_terminal_id?: string | null;
};

export type UpdateAccountMappingRevisionResponse = {
  data: AccountMappingRevisionResource;
  correlation_id: string;
};

export type ListTestDataTypeResponse = {
  items: Array<TestDataTypeResource>;
  page: PageMeta;
};

export type CreateTestDataTypeRequest = {
  expected_version?: number;
  reason?: string | null;
  test_data_type_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  data_type_code?: string | null;
  test_data_resource_id?: string | null;
};

export type CreateTestDataTypeResponse = {
  data: TestDataTypeResource;
  correlation_id: string;
};

export type GetTestDataTypeResponse = {
  data: TestDataTypeResource;
  correlation_id: string;
};

export type UpdateTestDataTypeRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  data_type_code?: string | null;
  test_data_resource_id?: string | null;
};

export type UpdateTestDataTypeResponse = {
  data: TestDataTypeResource;
  correlation_id: string;
};

export type ListTestDataResourceResponse = {
  items: Array<TestDataResourceResource>;
  page: PageMeta;
};

export type CreateTestDataResourceRequest = {
  expected_version?: number;
  reason?: string | null;
  test_data_resource_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  environment_id?: string | null;
  resource_key?: string | null;
  test_data_type_id?: string | null;
};

export type CreateTestDataResourceResponse = {
  data: TestDataResourceResource;
  correlation_id: string;
};

export type GetTestDataResourceResponse = {
  data: TestDataResourceResource;
  correlation_id: string;
};

export type UpdateTestDataResourceRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  environment_id?: string | null;
  resource_key?: string | null;
  test_data_type_id?: string | null;
};

export type UpdateTestDataResourceResponse = {
  data: TestDataResourceResource;
  correlation_id: string;
};

export type ListDataOperationTaskResponse = {
  items: Array<DataOperationTaskResource>;
  page: PageMeta;
};

export type CreateDataOperationTaskRequest = {
  expected_version?: number;
  reason?: string | null;
  data_operation_task_id?: string;
  display_name?: string | null;
  test_data_resource_id?: string | null;
};

export type CreateDataOperationTaskResponse = {
  data: DataOperationTaskResource;
  correlation_id: string;
};

export type GetDataOperationTaskResponse = {
  data: DataOperationTaskResource;
  correlation_id: string;
};

export type UpdateDataOperationTaskRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  test_data_resource_id?: string | null;
};

export type UpdateDataOperationTaskResponse = {
  data: DataOperationTaskResource;
  correlation_id: string;
};

export type ListNaturalLanguageCaseResponse = {
  items: Array<NaturalLanguageCaseResource>;
  page: PageMeta;
};

export type CreateNaturalLanguageCaseRequest = {
  expected_version?: number;
  reason?: string | null;
  natural_language_case_id?: string;
  display_name?: string | null;
  page_exploration_id?: string | null;
};

export type CreateNaturalLanguageCaseResponse = {
  data: NaturalLanguageCaseResource;
  correlation_id: string;
};

export type GetNaturalLanguageCaseResponse = {
  data: NaturalLanguageCaseResource;
  correlation_id: string;
};

export type UpdateNaturalLanguageCaseRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  page_exploration_id?: string | null;
};

export type UpdateNaturalLanguageCaseResponse = {
  data: NaturalLanguageCaseResource;
  correlation_id: string;
};

export type ListStandardCaseResponse = {
  items: Array<StandardCaseResource>;
  page: PageMeta;
};

export type CreateStandardCaseRequest = {
  expected_version?: number;
  reason?: string | null;
  standard_case_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  case_code?: string | null;
};

export type CreateStandardCaseResponse = {
  data: StandardCaseResource;
  correlation_id: string;
};

export type GetStandardCaseResponse = {
  data: StandardCaseResource;
  correlation_id: string;
};

export type UpdateStandardCaseRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  case_code?: string | null;
};

export type UpdateStandardCaseResponse = {
  data: StandardCaseResource;
  correlation_id: string;
};

export type ListCaseVersionResponse = {
  items: Array<CaseVersionResource>;
  page: PageMeta;
};

export type CreateCaseVersionRequest = {
  expected_version?: number;
  reason?: string | null;
  case_version_id?: string;
  display_name?: string | null;
  case_id?: string | null;
  version_no?: string | null;
  standard_case_id?: string | null;
};

export type CreateCaseVersionResponse = {
  data: CaseVersionResource;
  correlation_id: string;
};

export type GetCaseVersionResponse = {
  data: CaseVersionResource;
  correlation_id: string;
};

export type UpdateCaseVersionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  case_id?: string | null;
  version_no?: string | null;
  standard_case_id?: string | null;
};

export type UpdateCaseVersionResponse = {
  data: CaseVersionResource;
  correlation_id: string;
};

export type ListCaseSuiteResponse = {
  items: Array<CaseSuiteResource>;
  page: PageMeta;
};

export type CreateCaseSuiteRequest = {
  expected_version?: number;
  reason?: string | null;
  case_suite_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  suite_code?: string | null;
  case_version_id?: string | null;
};

export type CreateCaseSuiteResponse = {
  data: CaseSuiteResource;
  correlation_id: string;
};

export type GetCaseSuiteResponse = {
  data: CaseSuiteResource;
  correlation_id: string;
};

export type UpdateCaseSuiteRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  suite_code?: string | null;
  case_version_id?: string | null;
};

export type UpdateCaseSuiteResponse = {
  data: CaseSuiteResource;
  correlation_id: string;
};

export type ListBusinessFlowTemplateResponse = {
  items: Array<BusinessFlowTemplateResource>;
  page: PageMeta;
};

export type CreateBusinessFlowTemplateRequest = {
  expected_version?: number;
  reason?: string | null;
  business_flow_template_id?: string;
  display_name?: string | null;
};

export type CreateBusinessFlowTemplateResponse = {
  data: BusinessFlowTemplateResource;
  correlation_id: string;
};

export type GetBusinessFlowTemplateResponse = {
  data: BusinessFlowTemplateResource;
  correlation_id: string;
};

export type UpdateBusinessFlowTemplateRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
};

export type UpdateBusinessFlowTemplateResponse = {
  data: BusinessFlowTemplateResource;
  correlation_id: string;
};

export type ListPageExplorationResponse = {
  items: Array<PageExplorationResource>;
  page: PageMeta;
};

export type CreatePageExplorationRequest = {
  expected_version?: number;
  reason?: string | null;
  page_exploration_id?: string;
  display_name?: string | null;
  runner_id?: string | null;
  ai_candidate_revision_id?: string | null;
};

export type CreatePageExplorationResponse = {
  data: PageExplorationResource;
  correlation_id: string;
};

export type GetPageExplorationResponse = {
  data: PageExplorationResource;
  correlation_id: string;
};

export type UpdatePageExplorationRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  runner_id?: string | null;
  ai_candidate_revision_id?: string | null;
};

export type UpdatePageExplorationResponse = {
  data: PageExplorationResource;
  correlation_id: string;
};

export type ListManualRecordingTaskResponse = {
  items: Array<ManualRecordingTaskResource>;
  page: PageMeta;
};

export type CreateManualRecordingTaskRequest = {
  expected_version?: number;
  reason?: string | null;
  manual_recording_task_id?: string;
  display_name?: string | null;
};

export type CreateManualRecordingTaskResponse = {
  data: ManualRecordingTaskResource;
  correlation_id: string;
};

export type GetManualRecordingTaskResponse = {
  data: ManualRecordingTaskResource;
  correlation_id: string;
};

export type UpdateManualRecordingTaskRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
};

export type UpdateManualRecordingTaskResponse = {
  data: ManualRecordingTaskResource;
  correlation_id: string;
};

export type ListManualRecordingSessionResponse = {
  items: Array<ManualRecordingSessionResource>;
  page: PageMeta;
};

export type CreateManualRecordingSessionRequest = {
  expected_version?: number;
  reason?: string | null;
  manual_recording_session_id?: string;
  display_name?: string | null;
  manual_recording_task_id?: string | null;
  runner_id?: string | null;
  test_account_id?: string | null;
  manual_recording_control_lease_id?: string | null;
  recording_evidence_bundle_id?: string | null;
};

export type CreateManualRecordingSessionResponse = {
  data: ManualRecordingSessionResource;
  correlation_id: string;
};

export type GetManualRecordingSessionResponse = {
  data: ManualRecordingSessionResource;
  correlation_id: string;
};

export type UpdateManualRecordingSessionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  manual_recording_task_id?: string | null;
  runner_id?: string | null;
  test_account_id?: string | null;
  manual_recording_control_lease_id?: string | null;
  recording_evidence_bundle_id?: string | null;
};

export type UpdateManualRecordingSessionResponse = {
  data: ManualRecordingSessionResource;
  correlation_id: string;
};

export type ListRecordingEvidenceBundleResponse = {
  items: Array<RecordingEvidenceBundleResource>;
  page: PageMeta;
};

export type CreateRecordingEvidenceBundleRequest = {
  expected_version?: number;
  reason?: string | null;
  recording_evidence_bundle_id?: string;
  display_name?: string | null;
  manual_recording_task_id?: string | null;
  ai_candidate_revision_id?: string | null;
};

export type CreateRecordingEvidenceBundleResponse = {
  data: RecordingEvidenceBundleResource;
  correlation_id: string;
};

export type GetRecordingEvidenceBundleResponse = {
  data: RecordingEvidenceBundleResource;
  correlation_id: string;
};

export type UpdateRecordingEvidenceBundleRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  manual_recording_task_id?: string | null;
  ai_candidate_revision_id?: string | null;
};

export type UpdateRecordingEvidenceBundleResponse = {
  data: RecordingEvidenceBundleResource;
  correlation_id: string;
};

export type ListRunTaskResponse = {
  items: Array<RunTaskResource>;
  page: PageMeta;
};

export type CreateRunTaskRequest = {
  expected_version?: number;
  reason?: string | null;
  run_task_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  idempotency_key?: string | null;
  case_suite_id?: string | null;
  environment_id?: string | null;
  task_state?: "CREATED" | "WAITING_RESOURCE" | "RUNNING" | "RETRYING" | "COMPLETED" | "CANCELED" | "ABORTED" | "EXCEPTION";
  final_result?: "PASSED" | "FAILED" | "CANCELED" | "ABORTED" | "PARTIAL" | "UNKNOWN";
};

export type CreateRunTaskResponse = {
  data: RunTaskResource;
  correlation_id: string;
};

export type GetRunTaskResponse = {
  data: RunTaskResource;
  correlation_id: string;
};

export type UpdateRunTaskRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  idempotency_key?: string | null;
  case_suite_id?: string | null;
  environment_id?: string | null;
  task_state?: "CREATED" | "WAITING_RESOURCE" | "RUNNING" | "RETRYING" | "COMPLETED" | "CANCELED" | "ABORTED" | "EXCEPTION";
  final_result?: "PASSED" | "FAILED" | "CANCELED" | "ABORTED" | "PARTIAL" | "UNKNOWN";
};

export type UpdateRunTaskResponse = {
  data: RunTaskResource;
  correlation_id: string;
};

export type ListExecutionAttemptResponse = {
  items: Array<ExecutionAttemptResource>;
  page: PageMeta;
};

export type CreateExecutionAttemptRequest = {
  expected_version?: number;
  reason?: string | null;
  execution_attempt_id?: string;
  display_name?: string | null;
  run_task_id?: string | null;
  attempt_no?: string | null;
  case_attempt_id?: string | null;
  runner_id?: string | null;
  configuration_snapshot_id?: string | null;
  execution_batch_id?: string | null;
  lease_id?: string | null;
  execution_lock_id?: string | null;
};

export type CreateExecutionAttemptResponse = {
  data: ExecutionAttemptResource;
  correlation_id: string;
};

export type GetExecutionAttemptResponse = {
  data: ExecutionAttemptResource;
  correlation_id: string;
};

export type UpdateExecutionAttemptRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  run_task_id?: string | null;
  attempt_no?: string | null;
  case_attempt_id?: string | null;
  runner_id?: string | null;
  configuration_snapshot_id?: string | null;
  execution_batch_id?: string | null;
  lease_id?: string | null;
  execution_lock_id?: string | null;
};

export type UpdateExecutionAttemptResponse = {
  data: ExecutionAttemptResource;
  correlation_id: string;
};

export type ListCaseAttemptResponse = {
  items: Array<CaseAttemptResource>;
  page: PageMeta;
};

export type CreateCaseAttemptRequest = {
  expected_version?: number;
  reason?: string | null;
  case_attempt_id?: string;
  display_name?: string | null;
  run_task_id?: string | null;
  execution_attempt_id?: string | null;
};

export type CreateCaseAttemptResponse = {
  data: CaseAttemptResource;
  correlation_id: string;
};

export type GetCaseAttemptResponse = {
  data: CaseAttemptResource;
  correlation_id: string;
};

export type UpdateCaseAttemptRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  run_task_id?: string | null;
  execution_attempt_id?: string | null;
};

export type UpdateCaseAttemptResponse = {
  data: CaseAttemptResource;
  correlation_id: string;
};

export type ListExecutionPlanResponse = {
  items: Array<ExecutionPlanResource>;
  page: PageMeta;
};

export type CreateExecutionPlanRequest = {
  expected_version?: number;
  reason?: string | null;
  execution_plan_id?: string;
  display_name?: string | null;
  project_id?: string | null;
  plan_code?: string | null;
  run_task_id?: string | null;
};

export type CreateExecutionPlanResponse = {
  data: ExecutionPlanResource;
  correlation_id: string;
};

export type GetExecutionPlanResponse = {
  data: ExecutionPlanResource;
  correlation_id: string;
};

export type UpdateExecutionPlanRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
  plan_code?: string | null;
  run_task_id?: string | null;
};

export type UpdateExecutionPlanResponse = {
  data: ExecutionPlanResource;
  correlation_id: string;
};

export type ListExecutionPlanRevisionResponse = {
  items: Array<ExecutionPlanRevisionResource>;
  page: PageMeta;
};

export type CreateExecutionPlanRevisionRequest = {
  expected_version?: number;
  reason?: string | null;
  execution_plan_revision_id?: string;
  display_name?: string | null;
  plan_id?: string | null;
  revision_no?: string | null;
  execution_plan_id?: string | null;
  case_suite_id?: string | null;
  environment_id?: string | null;
  trigger_rule_id?: string | null;
};

export type CreateExecutionPlanRevisionResponse = {
  data: ExecutionPlanRevisionResource;
  correlation_id: string;
};

export type GetExecutionPlanRevisionResponse = {
  data: ExecutionPlanRevisionResource;
  correlation_id: string;
};

export type UpdateExecutionPlanRevisionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  plan_id?: string | null;
  revision_no?: string | null;
  execution_plan_id?: string | null;
  case_suite_id?: string | null;
  environment_id?: string | null;
  trigger_rule_id?: string | null;
};

export type UpdateExecutionPlanRevisionResponse = {
  data: ExecutionPlanRevisionResource;
  correlation_id: string;
};

export type ListTriggerRuleResponse = {
  items: Array<TriggerRuleResource>;
  page: PageMeta;
};

export type CreateTriggerRuleRequest = {
  expected_version?: number;
  reason?: string | null;
  trigger_rule_id?: string;
  display_name?: string | null;
  execution_plan_id?: string | null;
};

export type CreateTriggerRuleResponse = {
  data: TriggerRuleResource;
  correlation_id: string;
};

export type GetTriggerRuleResponse = {
  data: TriggerRuleResource;
  correlation_id: string;
};

export type UpdateTriggerRuleRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  execution_plan_id?: string | null;
};

export type UpdateTriggerRuleResponse = {
  data: TriggerRuleResource;
  correlation_id: string;
};

export type ListLeaseResponse = {
  items: Array<LeaseResource>;
  page: PageMeta;
};

export type CreateLeaseRequest = {
  expected_version?: number;
  reason?: string | null;
  lease_id?: string;
  display_name?: string | null;
  execution_slot_id?: string | null;
};

export type CreateLeaseResponse = {
  data: LeaseResource;
  correlation_id: string;
};

export type GetLeaseResponse = {
  data: LeaseResource;
  correlation_id: string;
};

export type UpdateLeaseRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  execution_slot_id?: string | null;
};

export type UpdateLeaseResponse = {
  data: LeaseResource;
  correlation_id: string;
};

export type ListAutomationAssetResponse = {
  items: Array<AutomationAssetResource>;
  page: PageMeta;
};

export type CreateAutomationAssetRequest = {
  expected_version?: number;
  reason?: string | null;
  automation_asset_id?: string;
  display_name?: string | null;
};

export type CreateAutomationAssetResponse = {
  data: AutomationAssetResource;
  correlation_id: string;
};

export type GetAutomationAssetResponse = {
  data: AutomationAssetResource;
  correlation_id: string;
};

export type UpdateAutomationAssetRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
};

export type UpdateAutomationAssetResponse = {
  data: AutomationAssetResource;
  correlation_id: string;
};

export type ListLoginStrategyResponse = {
  items: Array<LoginStrategyResource>;
  page: PageMeta;
};

export type CreateLoginStrategyRequest = {
  expected_version?: number;
  reason?: string | null;
  login_strategy_id?: string;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type CreateLoginStrategyResponse = {
  data: LoginStrategyResource;
  correlation_id: string;
};

export type GetLoginStrategyResponse = {
  data: LoginStrategyResource;
  correlation_id: string;
};

export type UpdateLoginStrategyRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type UpdateLoginStrategyResponse = {
  data: LoginStrategyResource;
  correlation_id: string;
};

export type ListPageObjectResponse = {
  items: Array<PageObjectResource>;
  page: PageMeta;
};

export type CreatePageObjectRequest = {
  expected_version?: number;
  reason?: string | null;
  page_object_id?: string;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type CreatePageObjectResponse = {
  data: PageObjectResource;
  correlation_id: string;
};

export type GetPageObjectResponse = {
  data: PageObjectResource;
  correlation_id: string;
};

export type UpdatePageObjectRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type UpdatePageObjectResponse = {
  data: PageObjectResource;
  correlation_id: string;
};

export type ListActionAssetResponse = {
  items: Array<ActionAssetResource>;
  page: PageMeta;
};

export type CreateActionAssetRequest = {
  expected_version?: number;
  reason?: string | null;
  action_asset_id?: string;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type CreateActionAssetResponse = {
  data: ActionAssetResource;
  correlation_id: string;
};

export type GetActionAssetResponse = {
  data: ActionAssetResource;
  correlation_id: string;
};

export type UpdateActionAssetRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type UpdateActionAssetResponse = {
  data: ActionAssetResource;
  correlation_id: string;
};

export type ListAssertionAssetResponse = {
  items: Array<AssertionAssetResource>;
  page: PageMeta;
};

export type CreateAssertionAssetRequest = {
  expected_version?: number;
  reason?: string | null;
  assertion_asset_id?: string;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type CreateAssertionAssetResponse = {
  data: AssertionAssetResource;
  correlation_id: string;
};

export type GetAssertionAssetResponse = {
  data: AssertionAssetResource;
  correlation_id: string;
};

export type UpdateAssertionAssetRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  automation_asset_id?: string | null;
};

export type UpdateAssertionAssetResponse = {
  data: AssertionAssetResource;
  correlation_id: string;
};

export type ListRunnerResponse = {
  items: Array<RunnerResource>;
  page: PageMeta;
};

export type CreateRunnerRequest = {
  expected_version?: number;
  reason?: string | null;
  runner_id?: string;
  display_name?: string | null;
  runner_code?: string | null;
  runner_project_binding_id?: string | null;
  project_id?: string | null;
  registration_state?: "UNREGISTERED" | "REGISTERED" | "DEREGISTERED";
  authentication_state?: "UNAUTHENTICATED" | "AUTHENTICATED" | "REVOKED";
  connection_state?: "ONLINE" | "OFFLINE" | "DISCONNECTED";
  health_state?: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  enablement_state?: "ENABLED" | "DISABLED" | "DRAINING";
  binding_state?: "UNBOUND" | "BOUND";
  scheduling_state?: "IDLE" | "RESERVED" | "RUNNING" | "DRAINING";
  resource_state?: "AVAILABLE" | "PARTIALLY_ALLOCATED" | "FULLY_ALLOCATED" | "EXHAUSTED";
};

export type CreateRunnerResponse = {
  data: RunnerResource;
  correlation_id: string;
};

export type GetRunnerResponse = {
  data: RunnerResource;
  correlation_id: string;
};

export type UpdateRunnerRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  runner_code?: string | null;
  runner_project_binding_id?: string | null;
  project_id?: string | null;
  registration_state?: "UNREGISTERED" | "REGISTERED" | "DEREGISTERED";
  authentication_state?: "UNAUTHENTICATED" | "AUTHENTICATED" | "REVOKED";
  connection_state?: "ONLINE" | "OFFLINE" | "DISCONNECTED";
  health_state?: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  enablement_state?: "ENABLED" | "DISABLED" | "DRAINING";
  binding_state?: "UNBOUND" | "BOUND";
  scheduling_state?: "IDLE" | "RESERVED" | "RUNNING" | "DRAINING";
  resource_state?: "AVAILABLE" | "PARTIALLY_ALLOCATED" | "FULLY_ALLOCATED" | "EXHAUSTED";
};

export type UpdateRunnerResponse = {
  data: RunnerResource;
  correlation_id: string;
};

export type ListRunnerCapabilityResponse = {
  items: Array<RunnerCapabilityResource>;
  page: PageMeta;
};

export type CreateRunnerCapabilityRequest = {
  expected_version?: number;
  reason?: string | null;
  runner_capability_id?: string;
  display_name?: string | null;
  runner_id?: string | null;
  capability_code?: string | null;
};

export type CreateRunnerCapabilityResponse = {
  data: RunnerCapabilityResource;
  correlation_id: string;
};

export type GetRunnerCapabilityResponse = {
  data: RunnerCapabilityResource;
  correlation_id: string;
};

export type UpdateRunnerCapabilityRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  runner_id?: string | null;
  capability_code?: string | null;
};

export type UpdateRunnerCapabilityResponse = {
  data: RunnerCapabilityResource;
  correlation_id: string;
};

export type ListExecutionSlotResponse = {
  items: Array<ExecutionSlotResource>;
  page: PageMeta;
};

export type CreateExecutionSlotRequest = {
  expected_version?: number;
  reason?: string | null;
  execution_slot_id?: string;
  display_name?: string | null;
  runner_id?: string | null;
  slot_no?: string | null;
};

export type CreateExecutionSlotResponse = {
  data: ExecutionSlotResource;
  correlation_id: string;
};

export type GetExecutionSlotResponse = {
  data: ExecutionSlotResource;
  correlation_id: string;
};

export type UpdateExecutionSlotRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  runner_id?: string | null;
  slot_no?: string | null;
};

export type UpdateExecutionSlotResponse = {
  data: ExecutionSlotResource;
  correlation_id: string;
};

export type ListModelConfigResponse = {
  items: Array<ModelConfigResource>;
  page: PageMeta;
};

export type CreateModelConfigRequest = {
  expected_version?: number;
  reason?: string | null;
  model_config_id?: string;
  display_name?: string | null;
  config_code?: string | null;
};

export type CreateModelConfigResponse = {
  data: ModelConfigResource;
  correlation_id: string;
};

export type GetModelConfigResponse = {
  data: ModelConfigResource;
  correlation_id: string;
};

export type UpdateModelConfigRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  config_code?: string | null;
};

export type UpdateModelConfigResponse = {
  data: ModelConfigResource;
  correlation_id: string;
};

export type ListPromptRevisionResponse = {
  items: Array<PromptRevisionResource>;
  page: PageMeta;
};

export type CreatePromptRevisionRequest = {
  expected_version?: number;
  reason?: string | null;
  prompt_revision_id?: string;
  display_name?: string | null;
  prompt_code?: string | null;
  revision_no?: string | null;
  model_config_id?: string | null;
};

export type CreatePromptRevisionResponse = {
  data: PromptRevisionResource;
  correlation_id: string;
};

export type GetPromptRevisionResponse = {
  data: PromptRevisionResource;
  correlation_id: string;
};

export type UpdatePromptRevisionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  prompt_code?: string | null;
  revision_no?: string | null;
  model_config_id?: string | null;
};

export type UpdatePromptRevisionResponse = {
  data: PromptRevisionResource;
  correlation_id: string;
};

export type ListAiCallResponse = {
  items: Array<AiCallResource>;
  page: PageMeta;
};

export type CreateAiCallRequest = {
  expected_version?: number;
  reason?: string | null;
  ai_call_id?: string;
  display_name?: string | null;
  ai_task_id?: string | null;
  prompt_revision_id?: string | null;
};

export type CreateAiCallResponse = {
  data: AiCallResource;
  correlation_id: string;
};

export type GetAiCallResponse = {
  data: AiCallResource;
  correlation_id: string;
};

export type UpdateAiCallRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  ai_task_id?: string | null;
  prompt_revision_id?: string | null;
};

export type UpdateAiCallResponse = {
  data: AiCallResource;
  correlation_id: string;
};

export type ListAiTaskResponse = {
  items: Array<AiTaskResource>;
  page: PageMeta;
};

export type CreateAiTaskRequest = {
  expected_version?: number;
  reason?: string | null;
  ai_task_id?: string;
  display_name?: string | null;
  ai_result_id?: string | null;
  ai_call_id?: string | null;
  model_config_id?: string | null;
};

export type CreateAiTaskResponse = {
  data: AiTaskResource;
  correlation_id: string;
};

export type GetAiTaskResponse = {
  data: AiTaskResource;
  correlation_id: string;
};

export type UpdateAiTaskRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  ai_result_id?: string | null;
  ai_call_id?: string | null;
  model_config_id?: string | null;
};

export type UpdateAiTaskResponse = {
  data: AiTaskResource;
  correlation_id: string;
};

export type ListTestReportGenerationRequestResponse = {
  items: Array<TestReportGenerationRequestResource>;
  page: PageMeta;
};

export type CreateTestReportGenerationRequestRequest = {
  expected_version?: number;
  reason?: string | null;
  test_report_generation_request_id?: string;
  display_name?: string | null;
  test_report_id?: string | null;
};

export type CreateTestReportGenerationRequestResponse = {
  data: TestReportGenerationRequestResource;
  correlation_id: string;
};

export type GetTestReportGenerationRequestResponse = {
  data: TestReportGenerationRequestResource;
  correlation_id: string;
};

export type UpdateTestReportGenerationRequestRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  test_report_id?: string | null;
};

export type UpdateTestReportGenerationRequestResponse = {
  data: TestReportGenerationRequestResource;
  correlation_id: string;
};

export type ListTestReportResponse = {
  items: Array<TestReportResource>;
  page: PageMeta;
};

export type CreateTestReportRequest = {
  expected_version?: number;
  reason?: string | null;
  test_report_id?: string;
  display_name?: string | null;
  test_artifact_id?: string | null;
  report_state?: "PENDING" | "GENERATING" | "GENERATED" | "PARTIAL" | "FAILED" | "ARCHIVED";
};

export type CreateTestReportResponse = {
  data: TestReportResource;
  correlation_id: string;
};

export type GetTestReportResponse = {
  data: TestReportResource;
  correlation_id: string;
};

export type UpdateTestReportRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  test_artifact_id?: string | null;
  report_state?: "PENDING" | "GENERATING" | "GENERATED" | "PARTIAL" | "FAILED" | "ARCHIVED";
};

export type UpdateTestReportResponse = {
  data: TestReportResource;
  correlation_id: string;
};

export type ListTestArtifactResponse = {
  items: Array<TestArtifactResource>;
  page: PageMeta;
};

export type CreateTestArtifactRequest = {
  expected_version?: number;
  reason?: string | null;
  test_artifact_id?: string;
  display_name?: string | null;
  test_report_id?: string | null;
  retention_policy_id?: string | null;
  upload_state?: "PENDING" | "UPLOADING" | "STORED" | "FAILED";
  retention_state?: "NORMAL" | "EXTENDED" | "HELD" | "EXPIRED";
  cleanup_state?: "NOT_DUE" | "PENDING" | "CLEANED" | "FAILED";
};

export type CreateTestArtifactResponse = {
  data: TestArtifactResource;
  correlation_id: string;
};

export type GetTestArtifactResponse = {
  data: TestArtifactResource;
  correlation_id: string;
};

export type UpdateTestArtifactRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  test_report_id?: string | null;
  retention_policy_id?: string | null;
  upload_state?: "PENDING" | "UPLOADING" | "STORED" | "FAILED";
  retention_state?: "NORMAL" | "EXTENDED" | "HELD" | "EXPIRED";
  cleanup_state?: "NOT_DUE" | "PENDING" | "CLEANED" | "FAILED";
};

export type UpdateTestArtifactResponse = {
  data: TestArtifactResource;
  correlation_id: string;
};

export type ListTechnicalAlertResponse = {
  items: Array<TechnicalAlertResource>;
  page: PageMeta;
};

export type CreateTechnicalAlertRequest = {
  expected_version?: number;
  reason?: string | null;
  technical_alert_id?: string;
  display_name?: string | null;
  signature_config_ref?: string | null;
};

export type CreateTechnicalAlertResponse = {
  data: TechnicalAlertResource;
  correlation_id: string;
};

export type GetTechnicalAlertResponse = {
  data: TechnicalAlertResource;
  correlation_id: string;
};

export type UpdateTechnicalAlertRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  signature_config_ref?: string | null;
};

export type UpdateTechnicalAlertResponse = {
  data: TechnicalAlertResource;
  correlation_id: string;
};

export type ListIntegrationComponentResponse = {
  items: Array<IntegrationComponentResource>;
  page: PageMeta;
};

export type CreateIntegrationComponentRequest = {
  expected_version?: number;
  reason?: string | null;
  integration_component_id?: string;
  display_name?: string | null;
  component_code?: string | null;
};

export type CreateIntegrationComponentResponse = {
  data: IntegrationComponentResource;
  correlation_id: string;
};

export type GetIntegrationComponentResponse = {
  data: IntegrationComponentResource;
  correlation_id: string;
};

export type UpdateIntegrationComponentRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  component_code?: string | null;
};

export type UpdateIntegrationComponentResponse = {
  data: IntegrationComponentResource;
  correlation_id: string;
};

export type ListSystemParameterResponse = {
  items: Array<SystemParameterResource>;
  page: PageMeta;
};

export type CreateSystemParameterRequest = {
  expected_version?: number;
  reason?: string | null;
  system_parameter_id?: string;
  display_name?: string | null;
  scope?: string | null;
  parameter_key?: string | null;
};

export type CreateSystemParameterResponse = {
  data: SystemParameterResource;
  correlation_id: string;
};

export type GetSystemParameterResponse = {
  data: SystemParameterResource;
  correlation_id: string;
};

export type UpdateSystemParameterRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  scope?: string | null;
  parameter_key?: string | null;
};

export type UpdateSystemParameterResponse = {
  data: SystemParameterResource;
  correlation_id: string;
};

export type ListDataDictionaryResponse = {
  items: Array<DataDictionaryResource>;
  page: PageMeta;
};

export type CreateDataDictionaryRequest = {
  expected_version?: number;
  reason?: string | null;
  data_dictionary_id?: string;
  display_name?: string | null;
  dictionary_code?: string | null;
};

export type CreateDataDictionaryResponse = {
  data: DataDictionaryResource;
  correlation_id: string;
};

export type GetDataDictionaryResponse = {
  data: DataDictionaryResource;
  correlation_id: string;
};

export type UpdateDataDictionaryRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  dictionary_code?: string | null;
};

export type UpdateDataDictionaryResponse = {
  data: DataDictionaryResource;
  correlation_id: string;
};

export type ListAuditLogResponse = {
  items: Array<AuditLogResource>;
  page: PageMeta;
};

export type CreateAuditLogRequest = {
  expected_version?: number;
  reason?: string | null;
  audit_log_id?: string;
  display_name?: string | null;
  human_decision_id?: string | null;
};

export type CreateAuditLogResponse = {
  data: AuditLogResource;
  correlation_id: string;
};

export type GetAuditLogResponse = {
  data: AuditLogResource;
  correlation_id: string;
};

export type UpdateAuditLogRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  human_decision_id?: string | null;
};

export type UpdateAuditLogResponse = {
  data: AuditLogResource;
  correlation_id: string;
};

export type ListRetentionPolicyResponse = {
  items: Array<RetentionPolicyResource>;
  page: PageMeta;
};

export type CreateRetentionPolicyRequest = {
  expected_version?: number;
  reason?: string | null;
  retention_policy_id?: string;
  display_name?: string | null;
  scope?: string | null;
  policy_code?: string | null;
};

export type CreateRetentionPolicyResponse = {
  data: RetentionPolicyResource;
  correlation_id: string;
};

export type GetRetentionPolicyResponse = {
  data: RetentionPolicyResource;
  correlation_id: string;
};

export type UpdateRetentionPolicyRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  scope?: string | null;
  policy_code?: string | null;
};

export type UpdateRetentionPolicyResponse = {
  data: RetentionPolicyResource;
  correlation_id: string;
};

export type ListControlledPurgeRequestResponse = {
  items: Array<ControlledPurgeRequestResource>;
  page: PageMeta;
};

export type CreateControlledPurgeRequestRequest = {
  expected_version?: number;
  reason?: string | null;
  controlled_purge_request_id?: string;
  display_name?: string | null;
  retention_policy_id?: string | null;
  legal_hold_id?: string | null;
  audit_log_id?: string | null;
};

export type CreateControlledPurgeRequestResponse = {
  data: ControlledPurgeRequestResource;
  correlation_id: string;
};

export type GetControlledPurgeRequestResponse = {
  data: ControlledPurgeRequestResource;
  correlation_id: string;
};

export type UpdateControlledPurgeRequestRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  retention_policy_id?: string | null;
  legal_hold_id?: string | null;
  audit_log_id?: string | null;
};

export type UpdateControlledPurgeRequestResponse = {
  data: ControlledPurgeRequestResource;
  correlation_id: string;
};

export type ListTechnicalAlertEndpointResponse = {
  items: Array<TechnicalAlertEndpointResource>;
  page: PageMeta;
};

export type CreateTechnicalAlertEndpointRequest = {
  technical_alert_endpoint_id: string;
  endpoint_code: string;
  signature_config_ref?: string | null;
  sequence_rule: "STRICTLY_INCREASING" | "MONOTONIC_PER_SOURCE";
  display_name?: string | null;
  reason: string;
};

export type CreateTechnicalAlertEndpointResponse = {
  data: TechnicalAlertEndpointResource;
  correlation_id: string;
};

export type GetTechnicalAlertEndpointResponse = {
  data: TechnicalAlertEndpointResource;
  correlation_id: string;
};

export type UpdateTechnicalAlertEndpointRequest = {
  expected_version: number;
  signature_config_ref?: string | null;
  sequence_rule?: "STRICTLY_INCREASING" | "MONOTONIC_PER_SOURCE";
  display_name?: string | null;
  reason: string;
};

export type UpdateTechnicalAlertEndpointResponse = {
  data: TechnicalAlertEndpointResource;
  correlation_id: string;
};

export type ListPlatformDesignBaselineReleaseResponse = {
  items: Array<PlatformDesignBaselineReleaseResource>;
  page: PageMeta;
};

export type CreatePlatformDesignBaselineReleaseRequest = {
  expected_version?: number;
  reason?: string | null;
  platform_design_baseline_release_id?: string;
  display_name?: string | null;
  release_id?: string | null;
  data_dictionary_id?: string | null;
};

export type CreatePlatformDesignBaselineReleaseResponse = {
  data: PlatformDesignBaselineReleaseResource;
  correlation_id: string;
};

export type GetPlatformDesignBaselineReleaseResponse = {
  data: PlatformDesignBaselineReleaseResource;
  correlation_id: string;
};

export type UpdatePlatformDesignBaselineReleaseRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  release_id?: string | null;
  data_dictionary_id?: string | null;
};

export type UpdatePlatformDesignBaselineReleaseResponse = {
  data: PlatformDesignBaselineReleaseResource;
  correlation_id: string;
};

export type ListAiCandidateRevisionResponse = {
  items: Array<AiCandidateRevisionResource>;
  page: PageMeta;
};

export type CreateAiCandidateRevisionRequest = {
  expected_version?: number;
  reason?: string | null;
  ai_candidate_revision_id?: string;
  display_name?: string | null;
  ai_task_id?: string | null;
  standard_case_id?: string | null;
};

export type CreateAiCandidateRevisionResponse = {
  data: AiCandidateRevisionResource;
  correlation_id: string;
};

export type GetAiCandidateRevisionResponse = {
  data: AiCandidateRevisionResource;
  correlation_id: string;
};

export type UpdateAiCandidateRevisionRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  ai_task_id?: string | null;
  standard_case_id?: string | null;
};

export type UpdateAiCandidateRevisionResponse = {
  data: AiCandidateRevisionResource;
  correlation_id: string;
};

export type ListTechnicalAlertIngestionBatchResponse = {
  items: Array<TechnicalAlertIngestionBatchResource>;
  page: PageMeta;
};

export type CreateTechnicalAlertIngestionBatchRequest = {
  expected_version?: number;
  reason?: string | null;
  technical_alert_ingestion_batch_id?: string;
  display_name?: string | null;
  endpoint_id?: string | null;
  batch_key?: string | null;
  signature_config_ref?: string | null;
  technical_alert_id?: string | null;
};

export type CreateTechnicalAlertIngestionBatchResponse = {
  data: TechnicalAlertIngestionBatchResource;
  correlation_id: string;
};

export type GetTechnicalAlertIngestionBatchResponse = {
  data: TechnicalAlertIngestionBatchResource;
  correlation_id: string;
};

export type UpdateTechnicalAlertIngestionBatchRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  endpoint_id?: string | null;
  batch_key?: string | null;
  signature_config_ref?: string | null;
  technical_alert_id?: string | null;
};

export type UpdateTechnicalAlertIngestionBatchResponse = {
  data: TechnicalAlertIngestionBatchResource;
  correlation_id: string;
};

export type ListExecutionBatchResponse = {
  items: Array<ExecutionBatchResource>;
  page: PageMeta;
};

export type CreateExecutionBatchRequest = {
  expected_version?: number;
  reason?: string | null;
  execution_batch_id?: string;
  display_name?: string | null;
  run_task_id?: string | null;
  batch_no?: string | null;
};

export type CreateExecutionBatchResponse = {
  data: ExecutionBatchResource;
  correlation_id: string;
};

export type GetExecutionBatchResponse = {
  data: ExecutionBatchResource;
  correlation_id: string;
};

export type UpdateExecutionBatchRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  run_task_id?: string | null;
  batch_no?: string | null;
};

export type UpdateExecutionBatchResponse = {
  data: ExecutionBatchResource;
  correlation_id: string;
};

export type ListProjectExecutionConfigurationResponse = {
  items: Array<ProjectExecutionConfigurationResource>;
  page: PageMeta;
};

export type CreateProjectExecutionConfigurationRequest = {
  expected_version?: number;
  reason?: string | null;
  project_execution_configuration_id?: string;
  display_name?: string | null;
  project_id?: string | null;
};

export type CreateProjectExecutionConfigurationResponse = {
  data: ProjectExecutionConfigurationResource;
  correlation_id: string;
};

export type GetProjectExecutionConfigurationResponse = {
  data: ProjectExecutionConfigurationResource;
  correlation_id: string;
};

export type UpdateProjectExecutionConfigurationRequest = {
  expected_version: number;
  reason?: string | null;
  display_name?: string | null;
  project_id?: string | null;
};

export type UpdateProjectExecutionConfigurationResponse = {
  data: ProjectExecutionConfigurationResource;
  correlation_id: string;
};

export type GenericOperationResource = {
  operation_id: string;
  status: string;
  row_version?: number;
};

export type CreateExecutionRequest = {
  expected_version?: number;
  reason?: string | null;
  operation_id?: string;
};

export type CreateExecutionResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type CancelExecutionRequest = {
  expected_version: number;
  reason?: string | null;
};

export type CancelExecutionResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type TerminateExecutionRequest = {
  expected_version: number;
  reason?: string | null;
};

export type TerminateExecutionResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type RegisterRunnerRequest = {
  expected_version?: number;
  reason?: string | null;
  operation_id?: string;
};

export type RegisterRunnerResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type HeartbeatRunnerRequest = {
  expected_version: number;
  reason?: string | null;
};

export type HeartbeatRunnerResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type ClaimRunnerTaskRequest = {
  expected_version: number;
  reason?: string | null;
};

export type ClaimRunnerTaskResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type RenewRunnerLeaseRequest = {
  expected_version: number;
  reason?: string | null;
};

export type RenewRunnerLeaseResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type ReportRunnerProgressRequest = {
  expected_version: number;
  reason?: string | null;
};

export type ReportRunnerProgressResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type ReportRunnerResultRequest = {
  expected_version: number;
  reason?: string | null;
};

export type ReportRunnerResultResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type ConvertNaturalLanguageCaseRequest = {
  expected_version: number;
  reason?: string | null;
};

export type ConvertNaturalLanguageCaseResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type CreateAiExplorationRequest = {
  expected_version?: number;
  reason?: string | null;
  operation_id?: string;
};

export type CreateAiExplorationResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type CreateManualRecordingRequest = {
  expected_version?: number;
  reason?: string | null;
  operation_id?: string;
};

export type CreateManualRecordingResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type SaveRecordingDraftAndStopRequest = {
  expected_version: number;
  reason?: string | null;
};

export type SaveRecordingDraftAndStopResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type GetReportResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type ExportReportRequest = {
  expected_version: number;
  reason?: string | null;
};

export type ExportReportResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type CreateReportShareRequest = {
  expected_version: number;
  reason?: string | null;
};

export type CreateReportShareResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type DownloadArtifactResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type CreateArtifactUploadSessionRequest = {
  file_name: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  expected_version?: number;
};

export type CreateArtifactUploadSessionResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type CompleteArtifactUploadRequest = {
  upload_id: string;
  checksum_sha256: string;
  size_bytes: number;
  expected_version: number;
};

export type CompleteArtifactUploadResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};

export type ListRecoveryItemsResponse = {
  items: Array<GenericOperationResource>;
  page: PageMeta;
};

export type CreateExternalTriggerRequest = {
  trigger_type: "CI" | "MANUAL" | "SCHEDULED";
  source_ref: string;
  payload_ref?: string | null;
  requested_at: string;
};

export type CreateExternalTriggerResponse = {
  data: GenericOperationResource;
  correlation_id: string;
};
