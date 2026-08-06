-- R4 formal MySQL 8.4 baseline
-- release_id: PDBR-2026.08.06-R4.1
SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET FOREIGN_KEY_CHECKS = 0;


CREATE TABLE atp_account_mapping_revision (
	account_mapping_revision_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	test_account_id VARCHAR(26) NOT NULL, 
	environment_id VARCHAR(26) NOT NULL, 
	business_terminal_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (account_mapping_revision_id), 
	CONSTRAINT ck_atp_account_mapping_revision_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_action_asset (
	action_asset_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	automation_asset_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (action_asset_id), 
	CONSTRAINT ck_atp_action_asset_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_admin (
	admin_id VARCHAR(26) NOT NULL, 
	username VARCHAR(191), 
	user_id VARCHAR(26), 
	lifecycle_status VARCHAR(11) NOT NULL DEFAULT 'INITIALIZED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (admin_id), 
	CONSTRAINT uq_atp_admin_business UNIQUE (username), 
	CONSTRAINT ck_atp_admin_lifecycle_status CHECK (lifecycle_status IN ('INITIALIZED', 'ACTIVE', 'LOCKED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_ai_call (
	ai_call_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	ai_task_id VARCHAR(26) NOT NULL, 
	prompt_revision_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (ai_call_id), 
	CONSTRAINT ck_atp_ai_call_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'QUEUED', 'PREPARING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'EXCEPTION', 'RECOVERING', 'COMPLETED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_ai_candidate_revision (
	ai_candidate_revision_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	ai_task_id VARCHAR(26), 
	standard_case_id VARCHAR(26), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (ai_candidate_revision_id), 
	CONSTRAINT ck_atp_ai_candidate_revision_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_ai_result (
	ai_result_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	ai_task_id VARCHAR(26), 
	ai_candidate_revision_id VARCHAR(26), 
	status VARCHAR(11) NOT NULL DEFAULT 'ACCEPTED', 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (ai_result_id), 
	CONSTRAINT ck_atp_ai_result_status CHECK (status IN ('ACCEPTED', 'CANDIDATE', 'INVALIDATED', 'REJECTED', 'RESTORED', 'SUPERSEDED')), 
	CONSTRAINT ck_atp_ai_result_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_ai_task (
	ai_task_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	ai_result_id VARCHAR(26), 
	ai_call_id VARCHAR(26) NOT NULL, 
	model_config_id VARCHAR(26) NOT NULL, 
	status VARCHAR(13) NOT NULL DEFAULT 'CANCELLED', 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (ai_task_id), 
	CONSTRAINT ck_atp_ai_task_status CHECK (status IN ('CANCELLED', 'CREATED', 'FAILED', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'WAITING_HUMAN')), 
	CONSTRAINT ck_atp_ai_task_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_assertion_asset (
	assertion_asset_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	automation_asset_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (assertion_asset_id), 
	CONSTRAINT ck_atp_assertion_asset_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_audit_log (
	audit_log_id VARCHAR(26) NOT NULL, 
	human_decision_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(8) NOT NULL DEFAULT 'CAPTURED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (audit_log_id), 
	CONSTRAINT ck_atp_audit_log_lifecycle_status CHECK (lifecycle_status IN ('CAPTURED', 'SEALED', 'RETAINED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_automation_asset (
	automation_asset_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (automation_asset_id), 
	CONSTRAINT ck_atp_automation_asset_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_business_flow_template (
	business_flow_template_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (business_flow_template_id), 
	CONSTRAINT ck_atp_business_flow_template_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_business_module (
	business_module_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	module_code VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (business_module_id), 
	CONSTRAINT uq_atp_business_module_business UNIQUE (module_code), 
	CONSTRAINT ck_atp_business_module_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_business_terminal (
	business_terminal_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	terminal_code VARCHAR(191), 
	environment_id VARCHAR(26), 
	lifecycle_status VARCHAR(11) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (business_terminal_id), 
	CONSTRAINT uq_atp_business_terminal_business UNIQUE (terminal_code), 
	CONSTRAINT ck_atp_business_terminal_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'CONFIGURING', 'VALIDATING', 'ACTIVE', 'UNREACHABLE', 'DISABLED', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_case_attempt (
	case_attempt_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	run_task_id VARCHAR(26), 
	execution_attempt_id VARCHAR(26) NOT NULL, 
	result_status VARCHAR(9) NOT NULL DEFAULT 'BROKEN', 
	lifecycle_status VARCHAR(12) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (case_attempt_id), 
	CONSTRAINT ck_atp_case_attempt_result_status CHECK (result_status IN ('BROKEN', 'CANCELLED', 'FAILED', 'PASSED', 'SKIPPED')), 
	CONSTRAINT ck_atp_case_attempt_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'PREPARING', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'NOT_EXECUTED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'EXCEPTION', 'COMPLETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_case_step (
	case_step_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	case_version_id VARCHAR(26), 
	sequence VARCHAR(191), 
	standard_case_id VARCHAR(26), 
	business_terminal_id VARCHAR(26) NOT NULL, 
	action_asset_id VARCHAR(26) NOT NULL, 
	assertion_asset_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (case_step_id), 
	CONSTRAINT uq_atp_case_step_business UNIQUE (case_version_id, sequence), 
	CONSTRAINT ck_atp_case_step_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_case_suite (
	case_suite_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	suite_code VARCHAR(191), 
	case_version_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (case_suite_id), 
	CONSTRAINT uq_atp_case_suite_business UNIQUE (suite_code), 
	CONSTRAINT ck_atp_case_suite_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_case_suite_item (
	case_suite_item_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	suite_id VARCHAR(26), 
	case_version_id VARCHAR(26), 
	case_suite_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (case_suite_item_id), 
	CONSTRAINT uq_atp_case_suite_item_business UNIQUE (suite_id, case_version_id), 
	CONSTRAINT ck_atp_case_suite_item_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_case_version (
	case_version_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	case_id VARCHAR(26), 
	version_no VARCHAR(191), 
	standard_case_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (case_version_id), 
	CONSTRAINT uq_atp_case_version_business UNIQUE (case_id, version_no), 
	CONSTRAINT ck_atp_case_version_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_configuration_snapshot (
	configuration_snapshot_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	run_task_id VARCHAR(26), 
	lifecycle_status VARCHAR(8) NOT NULL DEFAULT 'CAPTURED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (configuration_snapshot_id), 
	CONSTRAINT ck_atp_configuration_snapshot_lifecycle_status CHECK (lifecycle_status IN ('CAPTURED', 'SEALED', 'RETAINED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_context_variable (
	context_variable_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	execution_context_id VARCHAR(26), 
	namespace VARCHAR(191), 
	variable_name VARCHAR(191), 
	run_task_id VARCHAR(26), 
	test_data_resource_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (context_variable_id), 
	CONSTRAINT uq_atp_context_variable_business UNIQUE (execution_context_id, namespace, variable_name), 
	CONSTRAINT ck_atp_context_variable_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_controlled_purge_request (
	controlled_purge_request_id VARCHAR(26) NOT NULL, 
	retention_policy_id VARCHAR(26), 
	legal_hold_id VARCHAR(26), 
	audit_log_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (controlled_purge_request_id), 
	CONSTRAINT ck_atp_controlled_purge_request_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'VALIDATING', 'CLEANUP_EXECUTING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_credential_revision (
	credential_revision_id VARCHAR(26) NOT NULL, 
	test_account_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26) NOT NULL, 
	revision_no BIGINT NOT NULL, 
	secret_ref VARCHAR(255) NOT NULL, 
	published_at DATETIME(6), 
	superseded_by_revision_id VARCHAR(26), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (credential_revision_id), 
	CONSTRAINT uq_atp_credential_revision_account_revision UNIQUE (test_account_id, revision_no), 
	CONSTRAINT ck_atp_credential_revision_revision_no CHECK (revision_no > 0), 
	CONSTRAINT ck_atp_credential_revision_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_cross_terminal_orchestration (
	cross_terminal_orchestration_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	business_flow_template_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (cross_terminal_orchestration_id), 
	CONSTRAINT ck_atp_cross_terminal_orchestration_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_data_dictionary (
	data_dictionary_id VARCHAR(26) NOT NULL, 
	dictionary_code VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (data_dictionary_id), 
	CONSTRAINT uq_atp_data_dictionary_business UNIQUE (dictionary_code), 
	CONSTRAINT ck_atp_data_dictionary_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_data_operation_task (
	data_operation_task_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	test_data_resource_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (data_operation_task_id), 
	CONSTRAINT ck_atp_data_operation_task_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_data_scope_grant (
	grant_id VARCHAR(26) NOT NULL, 
	binding_id VARCHAR(26) NOT NULL, 
	scope_type VARCHAR(32) NOT NULL, 
	scope_id VARCHAR(26), 
	permission_code VARCHAR(128), 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	PRIMARY KEY (grant_id), 
	CONSTRAINT uq_scope_grant UNIQUE (binding_id, scope_type, scope_id, permission_code)
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_entity_super_admin_role (
	entity_super_admin_role_id VARCHAR(26) NOT NULL, 
	role_code VARCHAR(191), 
	role_id VARCHAR(26), 
	lifecycle_status VARCHAR(11) NOT NULL DEFAULT 'INITIALIZED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (entity_super_admin_role_id), 
	CONSTRAINT uq_atp_entity_super_admin_role_business UNIQUE (role_code), 
	CONSTRAINT ck_atp_entity_super_admin_role_lifecycle_status CHECK (lifecycle_status IN ('INITIALIZED', 'ACTIVE', 'LOCKED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_environment (
	environment_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	environment_code VARCHAR(191), 
	environment_terminal_access_revision_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(11) NOT NULL DEFAULT 'CREATED', 
	enablement_state VARCHAR(8) NOT NULL DEFAULT 'ENABLED', 
	accessibility_state VARCHAR(11) NOT NULL DEFAULT 'UNKNOWN', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (environment_id), 
	CONSTRAINT uq_atp_environment_business UNIQUE (environment_code), 
	CONSTRAINT ck_atp_environment_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'CONFIGURING', 'VALIDATING', 'ACTIVE', 'UNREACHABLE', 'DISABLED', 'RECOVERING', 'ARCHIVED')), 
	CONSTRAINT ck_atp_environment_enablement_state CHECK (enablement_state IN ('ENABLED', 'DISABLED')), 
	CONSTRAINT ck_atp_environment_accessibility_state CHECK (accessibility_state IN ('UNKNOWN', 'REACHABLE', 'UNREACHABLE'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_environment_terminal_access_revision (
	environment_terminal_access_revision_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	environment_id VARCHAR(26), 
	business_terminal_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (environment_terminal_access_revision_id), 
	CONSTRAINT ck_atp_environment_terminal_access_revision_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_attempt (
	execution_attempt_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	run_task_id VARCHAR(26), 
	attempt_no VARCHAR(191), 
	case_attempt_id VARCHAR(26) NOT NULL, 
	runner_id VARCHAR(26) NOT NULL, 
	configuration_snapshot_id VARCHAR(26) NOT NULL, 
	execution_batch_id VARCHAR(26) NOT NULL, 
	lease_id VARCHAR(26), 
	execution_lock_id VARCHAR(26), 
	execution_status VARCHAR(16) NOT NULL DEFAULT 'ABORTED', 
	finalization_status VARCHAR(16) NOT NULL DEFAULT 'COMPLETED', 
	lifecycle_status VARCHAR(12) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_attempt_id), 
	CONSTRAINT uq_atp_execution_attempt_business UNIQUE (run_task_id, attempt_no), 
	CONSTRAINT ck_atp_execution_attempt_execution_status CHECK (execution_status IN ('ABORTED', 'BROKEN', 'CANCELLED', 'FAILED', 'PRESTART_BLOCKED', 'READY', 'RUNNING', 'SUCCEEDED')), 
	CONSTRAINT ck_atp_execution_attempt_finalization_status CHECK (finalization_status IN ('COMPLETED', 'INITIAL', 'IN_PROGRESS', 'PENDING_RECOVERY')), 
	CONSTRAINT ck_atp_execution_attempt_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'PREPARING', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'NOT_EXECUTED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'EXCEPTION', 'COMPLETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_batch (
	execution_batch_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	run_task_id VARCHAR(26), 
	batch_no VARCHAR(191), 
	lifecycle_status VARCHAR(12) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_batch_id), 
	CONSTRAINT uq_atp_execution_batch_business UNIQUE (run_task_id, batch_no), 
	CONSTRAINT ck_atp_execution_batch_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'PREPARING', 'RUNNING', 'PASSED', 'FAILED', 'SKIPPED', 'NOT_EXECUTED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'EXCEPTION', 'COMPLETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_context (
	execution_context_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	run_task_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_context_id), 
	CONSTRAINT ck_atp_execution_context_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_lock (
	execution_lock_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	lease_id VARCHAR(26), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'REQUESTED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_lock_id), 
	CONSTRAINT ck_atp_execution_lock_lifecycle_status CHECK (lifecycle_status IN ('REQUESTED', 'WAITING', 'ACQUIRED', 'HELD', 'RENEWING', 'RELEASED', 'EXPIRED', 'REVOKED', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_plan (
	execution_plan_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	plan_code VARCHAR(191), 
	run_task_id VARCHAR(26), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_plan_id), 
	CONSTRAINT uq_atp_execution_plan_business UNIQUE (plan_code), 
	CONSTRAINT ck_atp_execution_plan_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'VALIDATING', 'ACTIVE', 'TRIGGERED', 'PAUSED', 'DISABLED', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_plan_revision (
	execution_plan_revision_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	plan_id VARCHAR(26), 
	revision_no VARCHAR(191), 
	execution_plan_id VARCHAR(26) NOT NULL, 
	case_suite_id VARCHAR(26) NOT NULL, 
	environment_id VARCHAR(26) NOT NULL, 
	trigger_rule_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_plan_revision_id), 
	CONSTRAINT uq_atp_execution_plan_revision_business UNIQUE (plan_id, revision_no), 
	CONSTRAINT ck_atp_execution_plan_revision_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_execution_slot (
	execution_slot_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	runner_id VARCHAR(26), 
	slot_no VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (execution_slot_id), 
	CONSTRAINT uq_atp_execution_slot_business UNIQUE (runner_id, slot_no), 
	CONSTRAINT ck_atp_execution_slot_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_human_decision (
	human_decision_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	ai_task_id VARCHAR(26), 
	ai_result_id VARCHAR(26) NOT NULL, 
	audit_log_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (human_decision_id), 
	CONSTRAINT ck_atp_human_decision_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_idempotency_record (
	idempotency_key VARCHAR(191) NOT NULL, 
	operation_id VARCHAR(191) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	response_status INTEGER, 
	response_json JSON, 
	expires_at DATETIME(6) NOT NULL, 
	PRIMARY KEY (idempotency_key)
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_integration_component (
	integration_component_id VARCHAR(26) NOT NULL, 
	component_code VARCHAR(191), 
	lifecycle_status VARCHAR(11) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (integration_component_id), 
	CONSTRAINT uq_atp_integration_component_business UNIQUE (component_code), 
	CONSTRAINT ck_atp_integration_component_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'CONFIGURING', 'VALIDATING', 'ACTIVE', 'DEGRADED', 'UNAVAILABLE', 'DISABLED', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_lease (
	lease_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	execution_slot_id VARCHAR(26) NOT NULL, 
	status VARCHAR(8) NOT NULL DEFAULT 'ACTIVE', 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'REQUESTED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (lease_id), 
	CONSTRAINT ck_atp_lease_status CHECK (status IN ('ACTIVE', 'EXPIRED', 'FENCED', 'RELEASED')), 
	CONSTRAINT ck_atp_lease_lifecycle_status CHECK (lifecycle_status IN ('REQUESTED', 'WAITING', 'ACQUIRED', 'HELD', 'RENEWING', 'RELEASED', 'EXPIRED', 'REVOKED', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_legal_hold (
	legal_hold_id VARCHAR(26) NOT NULL, 
	retention_policy_id VARCHAR(26), 
	controlled_purge_request_id VARCHAR(26) NOT NULL, 
	test_artifact_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (legal_hold_id), 
	CONSTRAINT ck_atp_legal_hold_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_login_qualification (
	login_qualification_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	test_account_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (login_qualification_id), 
	CONSTRAINT ck_atp_login_qualification_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_login_strategy (
	login_strategy_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	automation_asset_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (login_strategy_id), 
	CONSTRAINT ck_atp_login_strategy_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_manual_recording_control_lease (
	manual_recording_control_lease_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	manual_recording_task_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (manual_recording_control_lease_id), 
	CONSTRAINT ck_atp_manual_recording_control_lease_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_manual_recording_session (
	manual_recording_session_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	manual_recording_task_id VARCHAR(26) NOT NULL, 
	runner_id VARCHAR(26) NOT NULL, 
	test_account_id VARCHAR(26), 
	manual_recording_control_lease_id VARCHAR(26) NOT NULL, 
	recording_evidence_bundle_id VARCHAR(26), 
	status VARCHAR(9) NOT NULL DEFAULT 'ABORTED', 
	lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (manual_recording_session_id), 
	CONSTRAINT ck_atp_manual_recording_session_status CHECK (status IN ('ABORTED', 'ACTIVE', 'COMPLETED', 'CREATED', 'PARTIAL', 'PAUSED')), 
	CONSTRAINT ck_atp_manual_recording_session_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'WAITING_RUNNER', 'PREPARING', 'WAITING_USER', 'RUNNING', 'PAUSED', 'DISCONNECTED', 'RECOVERABLE', 'RECOVERING', 'ENDED', 'PENDING_CONVERSION', 'PENDING_CONFIRMATION', 'COMPLETED', 'CANCELED', 'ABORTED', 'RECOVERY_FAILED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_manual_recording_task (
	manual_recording_task_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	status VARCHAR(9) NOT NULL DEFAULT 'ASSIGNED', 
	lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (manual_recording_task_id), 
	CONSTRAINT ck_atp_manual_recording_task_status CHECK (status IN ('ASSIGNED', 'CANCELLED', 'COMPLETED', 'CREATED', 'FAILED', 'PARTIAL', 'RECORDING')), 
	CONSTRAINT ck_atp_manual_recording_task_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'WAITING_RUNNER', 'PREPARING', 'WAITING_USER', 'RUNNING', 'PAUSED', 'DISCONNECTED', 'RECOVERABLE', 'RECOVERING', 'ENDED', 'PENDING_CONVERSION', 'PENDING_CONFIRMATION', 'COMPLETED', 'CANCELED', 'ABORTED', 'RECOVERY_FAILED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_model_config (
	model_config_id VARCHAR(26) NOT NULL, 
	config_code VARCHAR(191), 
	lifecycle_status VARCHAR(11) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (model_config_id), 
	CONSTRAINT uq_atp_model_config_business UNIQUE (config_code), 
	CONSTRAINT ck_atp_model_config_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'CONFIGURING', 'VALIDATING', 'ACTIVE', 'DEGRADED', 'UNAVAILABLE', 'DISABLED', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_natural_language_case (
	natural_language_case_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	page_exploration_id VARCHAR(26), 
	lifecycle_status VARCHAR(25) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (natural_language_case_id), 
	CONSTRAINT ck_atp_natural_language_case_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'CONVERSION_REQUESTED', 'EXPLORATION_REQUESTED', 'STRUCTURED_DRAFT_PRODUCED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_outbox_event (
	event_id VARCHAR(26) NOT NULL, 
	aggregate_id VARCHAR(26) NOT NULL, 
	sequence BIGINT NOT NULL, 
	event_type VARCHAR(191) NOT NULL, 
	payload_json JSON NOT NULL, 
	occurred_at DATETIME(6) NOT NULL, 
	published_at DATETIME(6), 
	attempt_count INTEGER NOT NULL DEFAULT '0', 
	PRIMARY KEY (event_id), 
	CONSTRAINT uq_outbox_aggregate_sequence UNIQUE (aggregate_id, sequence)
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_page_exploration (
	page_exploration_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	runner_id VARCHAR(26) NOT NULL, 
	ai_candidate_revision_id VARCHAR(26), 
	lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (page_exploration_id), 
	CONSTRAINT ck_atp_page_exploration_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'VALIDATING', 'WAITING_RUNNER', 'PREPARING', 'EXPLORING', 'WAITING_CONFIRMATION', 'SUCCEEDED', 'FAILED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'RECOVERING', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_page_object (
	page_object_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	automation_asset_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (page_object_id), 
	CONSTRAINT ck_atp_page_object_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_permission_code (
	permission_code_id VARCHAR(26) NOT NULL, 
	permission_code VARCHAR(191) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (permission_code_id), 
	CONSTRAINT uq_atp_permission_code_business UNIQUE (permission_code), 
	CONSTRAINT ck_atp_permission_code_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_platform_design_baseline_release (
	platform_design_baseline_release_id VARCHAR(26) NOT NULL, 
	release_id VARCHAR(26), 
	data_dictionary_id VARCHAR(26) NOT NULL, 
	release_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	readiness_status VARCHAR(22) NOT NULL DEFAULT 'CONDITIONAL_CODE_READY', 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (platform_design_baseline_release_id), 
	CONSTRAINT uq_atp_platform_design_baseline_release_business UNIQUE (release_id), 
	CONSTRAINT ck_atp_platform_design_baseline_release_release_status CHECK (release_status IN ('DRAFT', 'FROZEN', 'SUPERSEDED')), 
	CONSTRAINT ck_atp_platform_design_baseline_release_readiness_status CHECK (readiness_status IN ('CONDITIONAL_CODE_READY', 'FULL_CODE_READY', 'NOT_CODE_READY')), 
	CONSTRAINT ck_atp_platform_design_baseline_release_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_project (
	project_id VARCHAR(26) NOT NULL, 
	project_code VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (project_id), 
	CONSTRAINT uq_atp_project_business UNIQUE (project_code), 
	CONSTRAINT ck_atp_project_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'CONFIGURING', 'VALIDATING', 'ACTIVE', 'DISABLED', 'RECOVERING', 'ARCHIVED', 'CLEANUP_PENDING', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_project_execution_configuration (
	project_execution_configuration_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (project_execution_configuration_id), 
	CONSTRAINT ck_atp_project_execution_configuration_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_project_member (
	project_member_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	user_id VARCHAR(26), 
	role_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (project_member_id), 
	CONSTRAINT uq_atp_project_member_business UNIQUE (user_id), 
	CONSTRAINT ck_atp_project_member_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_prompt_revision (
	prompt_revision_id VARCHAR(26) NOT NULL, 
	prompt_code VARCHAR(191), 
	revision_no VARCHAR(191), 
	model_config_id VARCHAR(26), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (prompt_revision_id), 
	CONSTRAINT uq_atp_prompt_revision_business UNIQUE (prompt_code, revision_no), 
	CONSTRAINT ck_atp_prompt_revision_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_recording_evidence_bundle (
	recording_evidence_bundle_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	manual_recording_task_id VARCHAR(26), 
	ai_candidate_revision_id VARCHAR(26), 
	lifecycle_status VARCHAR(18) NOT NULL DEFAULT 'COLLECTED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (recording_evidence_bundle_id), 
	CONSTRAINT ck_atp_recording_evidence_bundle_lifecycle_status CHECK (lifecycle_status IN ('COLLECTED', 'UPLOAD_PENDING', 'UPLOADING', 'STORED', 'UPLOAD_FAILED', 'RETRYING', 'RETAINED', 'EXTENDED_RETENTION', 'HELD', 'CLEANUP_PENDING', 'CLEANED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_retention_policy (
	retention_policy_id VARCHAR(26) NOT NULL, 
	scope VARCHAR(191), 
	policy_code VARCHAR(191), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'DRAFT', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (retention_policy_id), 
	CONSTRAINT uq_atp_retention_policy_business UNIQUE (scope, policy_code), 
	CONSTRAINT ck_atp_retention_policy_lifecycle_status CHECK (lifecycle_status IN ('DRAFT', 'VALIDATING', 'PUBLISHED', 'SUPERSEDED', 'RETIRED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_role (
	role_id VARCHAR(26) NOT NULL, 
	role_code VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (role_id), 
	CONSTRAINT uq_atp_role_business UNIQUE (role_code), 
	CONSTRAINT ck_atp_role_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_role_binding (
	role_binding_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	subject_id VARCHAR(26), 
	role_id VARCHAR(26), 
	effective_at VARCHAR(191), 
	user_id VARCHAR(26), 
	audit_log_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (role_binding_id), 
	CONSTRAINT uq_atp_role_binding_business UNIQUE (subject_id, role_id, effective_at), 
	CONSTRAINT ck_atp_role_binding_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_role_permission (
	role_id VARCHAR(26) NOT NULL, 
	permission_id VARCHAR(26) NOT NULL, 
	decision VARCHAR(16) NOT NULL, 
	conditions VARCHAR(1000), 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	PRIMARY KEY (role_id, permission_id)
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_run_task (
	run_task_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	idempotency_key VARCHAR(191), 
	case_suite_id VARCHAR(26) NOT NULL, 
	environment_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(16) NOT NULL DEFAULT 'CREATED', 
	task_state VARCHAR(16) NOT NULL DEFAULT 'CREATED', 
	final_result VARCHAR(8) NOT NULL DEFAULT 'UNKNOWN', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (run_task_id), 
	CONSTRAINT uq_atp_run_task_business UNIQUE (idempotency_key), 
	CONSTRAINT ck_atp_run_task_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'SNAPSHOTTED', 'VALIDATING', 'WAITING_RESOURCE', 'DISPATCHING', 'PREPARING', 'RUNNING', 'RETRYING', 'CANCELING', 'ABORTING', 'EXCEPTION', 'RECOVERING', 'COMPLETED', 'REPORTING', 'ARCHIVED')), 
	CONSTRAINT ck_atp_run_task_task_state CHECK (task_state IN ('CREATED', 'WAITING_RESOURCE', 'RUNNING', 'RETRYING', 'COMPLETED', 'CANCELED', 'ABORTED', 'EXCEPTION')), 
	CONSTRAINT ck_atp_run_task_final_result CHECK (final_result IN ('PASSED', 'FAILED', 'CANCELED', 'ABORTED', 'PARTIAL', 'UNKNOWN'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_runner (
	runner_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	runner_code VARCHAR(191), 
	runner_project_binding_id VARCHAR(26) NOT NULL, 
	health_status VARCHAR(9) NOT NULL DEFAULT 'DEGRADED', 
	scheduling_status VARCHAR(8) NOT NULL DEFAULT 'DISABLED', 
	registration_state VARCHAR(12) NOT NULL DEFAULT 'UNREGISTERED', 
	authentication_state VARCHAR(15) NOT NULL DEFAULT 'UNAUTHENTICATED', 
	connection_state VARCHAR(12) NOT NULL DEFAULT 'ONLINE', 
	health_state VARCHAR(9) NOT NULL DEFAULT 'HEALTHY', 
	enablement_state VARCHAR(8) NOT NULL DEFAULT 'ENABLED', 
	binding_state VARCHAR(7) NOT NULL DEFAULT 'UNBOUND', 
	scheduling_state VARCHAR(8) NOT NULL DEFAULT 'IDLE', 
	resource_state VARCHAR(19) NOT NULL DEFAULT 'AVAILABLE', 
	lifecycle_status VARCHAR(13) NOT NULL DEFAULT 'REGISTERING', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (runner_id), 
	CONSTRAINT uq_atp_runner_business UNIQUE (runner_code), 
	CONSTRAINT ck_atp_runner_health_status CHECK (health_status IN ('DEGRADED', 'HEALTHY', 'OFFLINE', 'UNHEALTHY', 'UNKNOWN')), 
	CONSTRAINT ck_atp_runner_scheduling_status CHECK (scheduling_status IN ('DISABLED', 'DRAINING', 'ENABLED')), 
	CONSTRAINT ck_atp_runner_registration_state CHECK (registration_state IN ('UNREGISTERED', 'REGISTERED', 'DEREGISTERED')), 
	CONSTRAINT ck_atp_runner_authentication_state CHECK (authentication_state IN ('UNAUTHENTICATED', 'AUTHENTICATED', 'REVOKED')), 
	CONSTRAINT ck_atp_runner_connection_state CHECK (connection_state IN ('ONLINE', 'OFFLINE', 'DISCONNECTED')), 
	CONSTRAINT ck_atp_runner_health_state CHECK (health_state IN ('HEALTHY', 'DEGRADED', 'UNHEALTHY')), 
	CONSTRAINT ck_atp_runner_enablement_state CHECK (enablement_state IN ('ENABLED', 'DISABLED', 'DRAINING')), 
	CONSTRAINT ck_atp_runner_binding_state CHECK (binding_state IN ('UNBOUND', 'BOUND')), 
	CONSTRAINT ck_atp_runner_scheduling_state CHECK (scheduling_state IN ('IDLE', 'RESERVED', 'RUNNING', 'DRAINING')), 
	CONSTRAINT ck_atp_runner_resource_state CHECK (resource_state IN ('AVAILABLE', 'PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED', 'EXHAUSTED')), 
	CONSTRAINT ck_atp_runner_lifecycle_status CHECK (lifecycle_status IN ('REGISTERING', 'REGISTERED', 'AUTHENTICATED', 'BOUND', 'ENABLED', 'ONLINE', 'DEGRADED', 'UNHEALTHY', 'OFFLINE', 'RECOVERING', 'DRAINING', 'DISABLED', 'UNBOUND', 'DEREGISTERED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_runner_agent (
	runner_agent_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	runner_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (runner_agent_id), 
	CONSTRAINT ck_atp_runner_agent_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_runner_capability (
	runner_capability_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	runner_id VARCHAR(26), 
	capability_code VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (runner_capability_id), 
	CONSTRAINT uq_atp_runner_capability_business UNIQUE (runner_id, capability_code), 
	CONSTRAINT ck_atp_runner_capability_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_runner_project_binding (
	runner_project_binding_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	runner_id VARCHAR(26), 
	effective_at VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (runner_project_binding_id), 
	CONSTRAINT uq_atp_runner_project_binding_business UNIQUE (runner_id, effective_at), 
	CONSTRAINT ck_atp_runner_project_binding_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_sso_identity (
	sso_identity_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	environment_id VARCHAR(26), 
	sso_identity_key VARCHAR(191), 
	test_account_id VARCHAR(26), 
	lease_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (sso_identity_id), 
	CONSTRAINT uq_atp_sso_identity_business UNIQUE (environment_id, sso_identity_key), 
	CONSTRAINT ck_atp_sso_identity_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_standard_case (
	standard_case_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	case_code VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (standard_case_id), 
	CONSTRAINT uq_atp_standard_case_business UNIQUE (case_code), 
	CONSTRAINT ck_atp_standard_case_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'VALIDATING', 'READY', 'DISABLED', 'RECOVERING', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_system_parameter (
	system_parameter_id VARCHAR(26) NOT NULL, 
	scope VARCHAR(191), 
	parameter_key VARCHAR(191), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (system_parameter_id), 
	CONSTRAINT uq_atp_system_parameter_business UNIQUE (scope, parameter_key), 
	CONSTRAINT ck_atp_system_parameter_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_technical_alert (
	technical_alert_id VARCHAR(26) NOT NULL, 
	signature_config_ref VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (technical_alert_id), 
	CONSTRAINT ck_atp_technical_alert_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_technical_alert_endpoint (
	technical_alert_endpoint_id VARCHAR(26) NOT NULL, 
	endpoint_code VARCHAR(191) NOT NULL, 
	signature_config_ref VARCHAR(255), 
	sequence_rule VARCHAR(64) NOT NULL DEFAULT 'STRICTLY_INCREASING', 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (technical_alert_endpoint_id), 
	CONSTRAINT uq_atp_technical_alert_endpoint_business UNIQUE (endpoint_code), 
	CONSTRAINT ck_atp_technical_alert_endpoint_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_technical_alert_ingestion_batch (
	technical_alert_ingestion_batch_id VARCHAR(26) NOT NULL, 
	technical_alert_endpoint_id VARCHAR(26) NOT NULL, 
	batch_key VARCHAR(191), 
	signature_config_ref VARCHAR(255) NOT NULL, 
	technical_alert_id VARCHAR(26), 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (technical_alert_ingestion_batch_id), 
	CONSTRAINT uq_atp_technical_alert_ingestion_batch_business UNIQUE (technical_alert_endpoint_id, batch_key), 
	CONSTRAINT ck_atp_technical_alert_ingestion_batch_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'QUEUED', 'PREPARING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'EXCEPTION', 'RECOVERING', 'COMPLETED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_test_account (
	test_account_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	environment_id VARCHAR(26), 
	account_identifier VARCHAR(191), 
	sso_identity_id VARCHAR(26) NOT NULL, 
	login_qualification_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(18) NOT NULL DEFAULT 'CREATED', 
	credential_state VARCHAR(8) NOT NULL DEFAULT 'VALID', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (test_account_id), 
	CONSTRAINT uq_atp_test_account_business UNIQUE (environment_id, account_identifier), 
	CONSTRAINT ck_atp_test_account_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'CONFIGURING', 'VALIDATING', 'ACTIVE', 'CREDENTIAL_EXPIRED', 'DISABLED', 'RECOVERING', 'ARCHIVED')), 
	CONSTRAINT ck_atp_test_account_credential_state CHECK (credential_state IN ('VALID', 'EXPIRING', 'EXPIRED', 'REVOKED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_test_artifact (
	test_artifact_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	test_report_id VARCHAR(26), 
	retention_policy_id VARCHAR(26), 
	lifecycle_status VARCHAR(18) NOT NULL DEFAULT 'COLLECTED', 
	upload_state VARCHAR(9) NOT NULL DEFAULT 'PENDING', 
	retention_state VARCHAR(8) NOT NULL DEFAULT 'NORMAL', 
	cleanup_state VARCHAR(7) NOT NULL DEFAULT 'NOT_DUE', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (test_artifact_id), 
	CONSTRAINT ck_atp_test_artifact_lifecycle_status CHECK (lifecycle_status IN ('COLLECTED', 'UPLOAD_PENDING', 'UPLOADING', 'STORED', 'UPLOAD_FAILED', 'RETRYING', 'RETAINED', 'EXTENDED_RETENTION', 'HELD', 'CLEANUP_PENDING', 'CLEANED', 'ARCHIVED')), 
	CONSTRAINT ck_atp_test_artifact_upload_state CHECK (upload_state IN ('PENDING', 'UPLOADING', 'STORED', 'FAILED')), 
	CONSTRAINT ck_atp_test_artifact_retention_state CHECK (retention_state IN ('NORMAL', 'EXTENDED', 'HELD', 'EXPIRED')), 
	CONSTRAINT ck_atp_test_artifact_cleanup_state CHECK (cleanup_state IN ('NOT_DUE', 'PENDING', 'CLEANED', 'FAILED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_test_data_resource (
	test_data_resource_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	environment_id VARCHAR(26), 
	resource_key VARCHAR(191), 
	test_data_type_id VARCHAR(26) NOT NULL, 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (test_data_resource_id), 
	CONSTRAINT uq_atp_test_data_resource_business UNIQUE (environment_id, resource_key), 
	CONSTRAINT ck_atp_test_data_resource_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_test_data_type (
	test_data_type_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	data_type_code VARCHAR(191), 
	test_data_resource_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (test_data_type_id), 
	CONSTRAINT uq_atp_test_data_type_business UNIQUE (data_type_code), 
	CONSTRAINT ck_atp_test_data_type_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_test_report (
	test_report_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	test_artifact_id VARCHAR(26) NOT NULL, 
	status VARCHAR(10) NOT NULL DEFAULT 'COMPLETED', 
	report_state VARCHAR(10) NOT NULL DEFAULT 'PENDING', 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'PENDING', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (test_report_id), 
	CONSTRAINT ck_atp_test_report_status CHECK (status IN ('COMPLETED', 'FAILED', 'GENERATING', 'SUPERSEDED')), 
	CONSTRAINT ck_atp_test_report_report_state CHECK (report_state IN ('PENDING', 'GENERATING', 'GENERATED', 'PARTIAL', 'FAILED', 'ARCHIVED')), 
	CONSTRAINT ck_atp_test_report_lifecycle_status CHECK (lifecycle_status IN ('PENDING', 'GENERATING', 'GENERATED', 'PARTIAL', 'FAILED', 'REGENERATING', 'ARCHIVED', 'METADATA_RETAINED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_test_report_generation_request (
	test_report_generation_request_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	test_report_id VARCHAR(26), 
	status VARCHAR(9) NOT NULL DEFAULT 'CANCELLED', 
	lifecycle_status VARCHAR(10) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (test_report_generation_request_id), 
	CONSTRAINT ck_atp_test_report_generation_request_status CHECK (status IN ('CANCELLED', 'FAILED', 'INITIAL', 'QUEUED', 'RUNNING', 'SUCCEEDED')), 
	CONSTRAINT ck_atp_test_report_generation_request_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'QUEUED', 'PREPARING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'ABORTED', 'TIMED_OUT', 'EXCEPTION', 'RECOVERING', 'COMPLETED', 'ARCHIVED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_trigger_rule (
	trigger_rule_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	execution_plan_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (trigger_rule_id), 
	CONSTRAINT ck_atp_trigger_rule_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'DISABLED', 'RECOVERED', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_user (
	user_id VARCHAR(26) NOT NULL, 
	username VARCHAR(191), 
	role_binding_id VARCHAR(26), 
	lifecycle_status VARCHAR(17) NOT NULL DEFAULT 'CREATED', 
	display_name VARCHAR(255), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), 
	updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6), 
	created_by VARCHAR(26), 
	updated_by VARCHAR(26), 
	extension_json JSON, 
	PRIMARY KEY (user_id), 
	CONSTRAINT uq_atp_user_business UNIQUE (username), 
	CONSTRAINT ck_atp_user_lifecycle_status CHECK (lifecycle_status IN ('CREATED', 'DRAFT', 'ACTIVE', 'LOCKED', 'DISABLED', 'RECOVERING', 'ARCHIVED', 'LOGICALLY_DELETED'))
)ENGINE=InnoDB CHARSET=utf8mb4;


CREATE TABLE atp_user_role_binding (
	binding_id VARCHAR(26) NOT NULL, 
	user_id VARCHAR(26) NOT NULL, 
	role_id VARCHAR(26) NOT NULL, 
	project_id VARCHAR(26), 
	valid_from DATETIME(6) NOT NULL, 
	valid_to DATETIME(6), 
	row_version BIGINT NOT NULL DEFAULT '0', 
	PRIMARY KEY (binding_id), 
	CONSTRAINT uq_user_role_scope UNIQUE (user_id, role_id, project_id, valid_from)
)ENGINE=InnoDB CHARSET=utf8mb4;

ALTER TABLE `atp_admin` ADD CONSTRAINT `fk_atp_admin_user_id` FOREIGN KEY (`user_id`) REFERENCES `atp_user` (`user_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_role_binding` ADD CONSTRAINT `fk_atp_role_binding_user_id` FOREIGN KEY (`user_id`) REFERENCES `atp_user` (`user_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_role_binding` ADD CONSTRAINT `fk_atp_role_binding_role_id` FOREIGN KEY (`role_id`) REFERENCES `atp_role` (`role_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_role_binding` ADD CONSTRAINT `fk_atp_role_binding_audit_log_id` FOREIGN KEY (`audit_log_id`) REFERENCES `atp_audit_log` (`audit_log_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_entity_super_admin_role` ADD CONSTRAINT `fk_atp_entity_super_admin_role_role_id` FOREIGN KEY (`role_id`) REFERENCES `atp_role` (`role_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_project_member` ADD CONSTRAINT `fk_atp_project_member_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_project_member` ADD CONSTRAINT `fk_atp_project_member_user_id` FOREIGN KEY (`user_id`) REFERENCES `atp_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_project_member` ADD CONSTRAINT `fk_atp_project_member_role_id` FOREIGN KEY (`role_id`) REFERENCES `atp_role` (`role_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_business_module` ADD CONSTRAINT `fk_atp_business_module_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_project_execution_configuration` ADD CONSTRAINT `fk_atp_project_execution_configuration_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_business_terminal` ADD CONSTRAINT `fk_atp_business_terminal_environment_id` FOREIGN KEY (`environment_id`) REFERENCES `atp_environment` (`environment_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_business_terminal` ADD CONSTRAINT `fk_atp_business_terminal_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_environment_terminal_access_revision` ADD CONSTRAINT `fk_atp_environment_terminal_access_revision_environment_id` FOREIGN KEY (`environment_id`) REFERENCES `atp_environment` (`environment_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_environment_terminal_access_revision` ADD CONSTRAINT `fk_atp_environment_terminal_access_revision_business_termina` FOREIGN KEY (`business_terminal_id`) REFERENCES `atp_business_terminal` (`business_terminal_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_credential_revision` ADD CONSTRAINT `fk_atp_credential_revision_test_account_id` FOREIGN KEY (`test_account_id`) REFERENCES `atp_test_account` (`test_account_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_credential_revision` ADD CONSTRAINT `fk_atp_credential_revision_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_credential_revision` ADD CONSTRAINT `fk_atp_credential_revision_superseded_by` FOREIGN KEY (`superseded_by_revision_id`) REFERENCES `atp_credential_revision` (`credential_revision_id`) ON DELETE SET NULL ON UPDATE RESTRICT;
ALTER TABLE `atp_account_mapping_revision` ADD CONSTRAINT `fk_atp_account_mapping_revision_test_account_id` FOREIGN KEY (`test_account_id`) REFERENCES `atp_test_account` (`test_account_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_account_mapping_revision` ADD CONSTRAINT `fk_atp_account_mapping_revision_environment_id` FOREIGN KEY (`environment_id`) REFERENCES `atp_environment` (`environment_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_account_mapping_revision` ADD CONSTRAINT `fk_atp_account_mapping_revision_business_terminal_id` FOREIGN KEY (`business_terminal_id`) REFERENCES `atp_business_terminal` (`business_terminal_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_sso_identity` ADD CONSTRAINT `fk_atp_sso_identity_test_account_id` FOREIGN KEY (`test_account_id`) REFERENCES `atp_test_account` (`test_account_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_sso_identity` ADD CONSTRAINT `fk_atp_sso_identity_lease_id` FOREIGN KEY (`lease_id`) REFERENCES `atp_lease` (`lease_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_login_qualification` ADD CONSTRAINT `fk_atp_login_qualification_test_account_id` FOREIGN KEY (`test_account_id`) REFERENCES `atp_test_account` (`test_account_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_test_data_type` ADD CONSTRAINT `fk_atp_test_data_type_test_data_resource_id` FOREIGN KEY (`test_data_resource_id`) REFERENCES `atp_test_data_resource` (`test_data_resource_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_case_version` ADD CONSTRAINT `fk_atp_case_version_standard_case_id` FOREIGN KEY (`standard_case_id`) REFERENCES `atp_standard_case` (`standard_case_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_step` ADD CONSTRAINT `fk_atp_case_step_standard_case_id` FOREIGN KEY (`standard_case_id`) REFERENCES `atp_standard_case` (`standard_case_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_case_step` ADD CONSTRAINT `fk_atp_case_step_case_version_id` FOREIGN KEY (`case_version_id`) REFERENCES `atp_case_version` (`case_version_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_step` ADD CONSTRAINT `fk_atp_case_step_business_terminal_id` FOREIGN KEY (`business_terminal_id`) REFERENCES `atp_business_terminal` (`business_terminal_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_step` ADD CONSTRAINT `fk_atp_case_step_action_asset_id` FOREIGN KEY (`action_asset_id`) REFERENCES `atp_action_asset` (`action_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_step` ADD CONSTRAINT `fk_atp_case_step_assertion_asset_id` FOREIGN KEY (`assertion_asset_id`) REFERENCES `atp_assertion_asset` (`assertion_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_suite_item` ADD CONSTRAINT `fk_atp_case_suite_item_case_suite_id` FOREIGN KEY (`case_suite_id`) REFERENCES `atp_case_suite` (`case_suite_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_suite_item` ADD CONSTRAINT `fk_atp_case_suite_item_case_version_id` FOREIGN KEY (`case_version_id`) REFERENCES `atp_case_version` (`case_version_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_cross_terminal_orchestration` ADD CONSTRAINT `fk_atp_cross_terminal_orchestration_business_flow_template_i` FOREIGN KEY (`business_flow_template_id`) REFERENCES `atp_business_flow_template` (`business_flow_template_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_session` ADD CONSTRAINT `fk_atp_manual_recording_session_manual_recording_task_id` FOREIGN KEY (`manual_recording_task_id`) REFERENCES `atp_manual_recording_task` (`manual_recording_task_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_session` ADD CONSTRAINT `fk_atp_manual_recording_session_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_session` ADD CONSTRAINT `fk_atp_manual_recording_session_test_account_id` FOREIGN KEY (`test_account_id`) REFERENCES `atp_test_account` (`test_account_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_session` ADD CONSTRAINT `fk_atp_manual_recording_session_manual_recording_control_lea` FOREIGN KEY (`manual_recording_control_lease_id`) REFERENCES `atp_manual_recording_control_lease` (`manual_recording_control_lease_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_session` ADD CONSTRAINT `fk_atp_manual_recording_session_recording_evidence_bundle_id` FOREIGN KEY (`recording_evidence_bundle_id`) REFERENCES `atp_recording_evidence_bundle` (`recording_evidence_bundle_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_control_lease` ADD CONSTRAINT `fk_atp_manual_recording_control_lease_manual_recording_task_` FOREIGN KEY (`manual_recording_task_id`) REFERENCES `atp_manual_recording_task` (`manual_recording_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_recording_evidence_bundle` ADD CONSTRAINT `fk_atp_recording_evidence_bundle_manual_recording_task_id` FOREIGN KEY (`manual_recording_task_id`) REFERENCES `atp_manual_recording_task` (`manual_recording_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_recording_evidence_bundle` ADD CONSTRAINT `fk_atp_recording_evidence_bundle_ai_candidate_revision_id` FOREIGN KEY (`ai_candidate_revision_id`) REFERENCES `atp_ai_candidate_revision` (`ai_candidate_revision_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_batch` ADD CONSTRAINT `fk_atp_execution_batch_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_case_attempt_id` FOREIGN KEY (`case_attempt_id`) REFERENCES `atp_case_attempt` (`case_attempt_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_configuration_snapshot_id` FOREIGN KEY (`configuration_snapshot_id`) REFERENCES `atp_configuration_snapshot` (`configuration_snapshot_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_execution_batch_id` FOREIGN KEY (`execution_batch_id`) REFERENCES `atp_execution_batch` (`execution_batch_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_lease_id` FOREIGN KEY (`lease_id`) REFERENCES `atp_lease` (`lease_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_execution_lock_id` FOREIGN KEY (`execution_lock_id`) REFERENCES `atp_execution_lock` (`execution_lock_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_attempt` ADD CONSTRAINT `fk_atp_case_attempt_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_case_attempt` ADD CONSTRAINT `fk_atp_case_attempt_execution_attempt_id` FOREIGN KEY (`execution_attempt_id`) REFERENCES `atp_execution_attempt` (`execution_attempt_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_configuration_snapshot` ADD CONSTRAINT `fk_atp_configuration_snapshot_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_context` ADD CONSTRAINT `fk_atp_execution_context_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_context_variable` ADD CONSTRAINT `fk_atp_context_variable_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_context_variable` ADD CONSTRAINT `fk_atp_context_variable_test_data_resource_id` FOREIGN KEY (`test_data_resource_id`) REFERENCES `atp_test_data_resource` (`test_data_resource_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_context_variable` ADD CONSTRAINT `fk_atp_context_variable_execution_context_id` FOREIGN KEY (`execution_context_id`) REFERENCES `atp_execution_context` (`execution_context_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan_revision` ADD CONSTRAINT `fk_atp_execution_plan_revision_execution_plan_id` FOREIGN KEY (`execution_plan_id`) REFERENCES `atp_execution_plan` (`execution_plan_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan_revision` ADD CONSTRAINT `fk_atp_execution_plan_revision_case_suite_id` FOREIGN KEY (`case_suite_id`) REFERENCES `atp_case_suite` (`case_suite_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan_revision` ADD CONSTRAINT `fk_atp_execution_plan_revision_environment_id` FOREIGN KEY (`environment_id`) REFERENCES `atp_environment` (`environment_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan_revision` ADD CONSTRAINT `fk_atp_execution_plan_revision_trigger_rule_id` FOREIGN KEY (`trigger_rule_id`) REFERENCES `atp_trigger_rule` (`trigger_rule_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_trigger_rule` ADD CONSTRAINT `fk_atp_trigger_rule_execution_plan_id` FOREIGN KEY (`execution_plan_id`) REFERENCES `atp_execution_plan` (`execution_plan_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_lock` ADD CONSTRAINT `fk_atp_execution_lock_lease_id` FOREIGN KEY (`lease_id`) REFERENCES `atp_lease` (`lease_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_login_strategy` ADD CONSTRAINT `fk_atp_login_strategy_automation_asset_id` FOREIGN KEY (`automation_asset_id`) REFERENCES `atp_automation_asset` (`automation_asset_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_page_object` ADD CONSTRAINT `fk_atp_page_object_automation_asset_id` FOREIGN KEY (`automation_asset_id`) REFERENCES `atp_automation_asset` (`automation_asset_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_action_asset` ADD CONSTRAINT `fk_atp_action_asset_automation_asset_id` FOREIGN KEY (`automation_asset_id`) REFERENCES `atp_automation_asset` (`automation_asset_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_assertion_asset` ADD CONSTRAINT `fk_atp_assertion_asset_automation_asset_id` FOREIGN KEY (`automation_asset_id`) REFERENCES `atp_automation_asset` (`automation_asset_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_runner_agent` ADD CONSTRAINT `fk_atp_runner_agent_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner_capability` ADD CONSTRAINT `fk_atp_runner_capability_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner_project_binding` ADD CONSTRAINT `fk_atp_runner_project_binding_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_slot` ADD CONSTRAINT `fk_atp_execution_slot_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_prompt_revision` ADD CONSTRAINT `fk_atp_prompt_revision_model_config_id` FOREIGN KEY (`model_config_id`) REFERENCES `atp_model_config` (`model_config_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_call` ADD CONSTRAINT `fk_atp_ai_call_ai_task_id` FOREIGN KEY (`ai_task_id`) REFERENCES `atp_ai_task` (`ai_task_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_call` ADD CONSTRAINT `fk_atp_ai_call_prompt_revision_id` FOREIGN KEY (`prompt_revision_id`) REFERENCES `atp_prompt_revision` (`prompt_revision_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_result` ADD CONSTRAINT `fk_atp_ai_result_ai_task_id` FOREIGN KEY (`ai_task_id`) REFERENCES `atp_ai_task` (`ai_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_result` ADD CONSTRAINT `fk_atp_ai_result_ai_candidate_revision_id` FOREIGN KEY (`ai_candidate_revision_id`) REFERENCES `atp_ai_candidate_revision` (`ai_candidate_revision_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_human_decision` ADD CONSTRAINT `fk_atp_human_decision_ai_task_id` FOREIGN KEY (`ai_task_id`) REFERENCES `atp_ai_task` (`ai_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_human_decision` ADD CONSTRAINT `fk_atp_human_decision_ai_result_id` FOREIGN KEY (`ai_result_id`) REFERENCES `atp_ai_result` (`ai_result_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_human_decision` ADD CONSTRAINT `fk_atp_human_decision_audit_log_id` FOREIGN KEY (`audit_log_id`) REFERENCES `atp_audit_log` (`audit_log_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_candidate_revision` ADD CONSTRAINT `fk_atp_ai_candidate_revision_ai_task_id` FOREIGN KEY (`ai_task_id`) REFERENCES `atp_ai_task` (`ai_task_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_candidate_revision` ADD CONSTRAINT `fk_atp_ai_candidate_revision_standard_case_id` FOREIGN KEY (`standard_case_id`) REFERENCES `atp_standard_case` (`standard_case_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_report_generation_request` ADD CONSTRAINT `fk_atp_test_report_generation_request_test_report_id` FOREIGN KEY (`test_report_id`) REFERENCES `atp_test_report` (`test_report_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_test_artifact` ADD CONSTRAINT `fk_atp_test_artifact_test_report_id` FOREIGN KEY (`test_report_id`) REFERENCES `atp_test_report` (`test_report_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_test_artifact` ADD CONSTRAINT `fk_atp_test_artifact_retention_policy_id` FOREIGN KEY (`retention_policy_id`) REFERENCES `atp_retention_policy` (`retention_policy_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_legal_hold` ADD CONSTRAINT `fk_atp_legal_hold_retention_policy_id` FOREIGN KEY (`retention_policy_id`) REFERENCES `atp_retention_policy` (`retention_policy_id`) ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE `atp_legal_hold` ADD CONSTRAINT `fk_atp_legal_hold_controlled_purge_request_id` FOREIGN KEY (`controlled_purge_request_id`) REFERENCES `atp_controlled_purge_request` (`controlled_purge_request_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_legal_hold` ADD CONSTRAINT `fk_atp_legal_hold_test_artifact_id` FOREIGN KEY (`test_artifact_id`) REFERENCES `atp_test_artifact` (`test_artifact_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_technical_alert_ingestion_batch` ADD CONSTRAINT `fk_atp_technical_alert_ingestion_batch_technical_alert_id` FOREIGN KEY (`technical_alert_id`) REFERENCES `atp_technical_alert` (`technical_alert_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_suite` ADD CONSTRAINT `fk_atp_case_suite_case_version_id` FOREIGN KEY (`case_version_id`) REFERENCES `atp_case_version` (`case_version_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner` ADD CONSTRAINT `fk_atp_runner_runner_project_binding_id` FOREIGN KEY (`runner_project_binding_id`) REFERENCES `atp_runner_project_binding` (`runner_project_binding_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner` ADD CONSTRAINT `fk_atp_runner_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_page_exploration` ADD CONSTRAINT `fk_atp_page_exploration_runner_id` FOREIGN KEY (`runner_id`) REFERENCES `atp_runner` (`runner_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_page_exploration` ADD CONSTRAINT `fk_atp_page_exploration_ai_candidate_revision_id` FOREIGN KEY (`ai_candidate_revision_id`) REFERENCES `atp_ai_candidate_revision` (`ai_candidate_revision_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_task` ADD CONSTRAINT `fk_atp_ai_task_ai_result_id` FOREIGN KEY (`ai_result_id`) REFERENCES `atp_ai_result` (`ai_result_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_task` ADD CONSTRAINT `fk_atp_ai_task_ai_call_id` FOREIGN KEY (`ai_call_id`) REFERENCES `atp_ai_call` (`ai_call_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_task` ADD CONSTRAINT `fk_atp_ai_task_model_config_id` FOREIGN KEY (`model_config_id`) REFERENCES `atp_model_config` (`model_config_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_report` ADD CONSTRAINT `fk_atp_test_report_test_artifact_id` FOREIGN KEY (`test_artifact_id`) REFERENCES `atp_test_artifact` (`test_artifact_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_technical_alert` ADD CONSTRAINT `fk_atp_technical_alert_signature_config_ref` FOREIGN KEY (`signature_config_ref`) REFERENCES `atp_technical_alert_endpoint` (`technical_alert_endpoint_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_audit_log` ADD CONSTRAINT `fk_atp_audit_log_human_decision_id` FOREIGN KEY (`human_decision_id`) REFERENCES `atp_human_decision` (`human_decision_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_user` ADD CONSTRAINT `fk_atp_user_role_binding_id` FOREIGN KEY (`role_binding_id`) REFERENCES `atp_role_binding` (`role_binding_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_environment` ADD CONSTRAINT `fk_atp_environment_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_environment` ADD CONSTRAINT `fk_atp_environment_environment_terminal_access_revision_id` FOREIGN KEY (`environment_terminal_access_revision_id`) REFERENCES `atp_environment_terminal_access_revision` (`environment_terminal_access_revision_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_account` ADD CONSTRAINT `fk_atp_test_account_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_account` ADD CONSTRAINT `fk_atp_test_account_sso_identity_id` FOREIGN KEY (`sso_identity_id`) REFERENCES `atp_sso_identity` (`sso_identity_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_account` ADD CONSTRAINT `fk_atp_test_account_login_qualification_id` FOREIGN KEY (`login_qualification_id`) REFERENCES `atp_login_qualification` (`login_qualification_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_data_resource` ADD CONSTRAINT `fk_atp_test_data_resource_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_data_resource` ADD CONSTRAINT `fk_atp_test_data_resource_test_data_type_id` FOREIGN KEY (`test_data_type_id`) REFERENCES `atp_test_data_type` (`test_data_type_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_data_operation_task` ADD CONSTRAINT `fk_atp_data_operation_task_test_data_resource_id` FOREIGN KEY (`test_data_resource_id`) REFERENCES `atp_test_data_resource` (`test_data_resource_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_natural_language_case` ADD CONSTRAINT `fk_atp_natural_language_case_page_exploration_id` FOREIGN KEY (`page_exploration_id`) REFERENCES `atp_page_exploration` (`page_exploration_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan` ADD CONSTRAINT `fk_atp_execution_plan_run_task_id` FOREIGN KEY (`run_task_id`) REFERENCES `atp_run_task` (`run_task_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_run_task` ADD CONSTRAINT `fk_atp_run_task_case_suite_id` FOREIGN KEY (`case_suite_id`) REFERENCES `atp_case_suite` (`case_suite_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_run_task` ADD CONSTRAINT `fk_atp_run_task_environment_id` FOREIGN KEY (`environment_id`) REFERENCES `atp_environment` (`environment_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_lease` ADD CONSTRAINT `fk_atp_lease_execution_slot_id` FOREIGN KEY (`execution_slot_id`) REFERENCES `atp_execution_slot` (`execution_slot_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_controlled_purge_request` ADD CONSTRAINT `fk_atp_controlled_purge_request_retention_policy_id` FOREIGN KEY (`retention_policy_id`) REFERENCES `atp_retention_policy` (`retention_policy_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_controlled_purge_request` ADD CONSTRAINT `fk_atp_controlled_purge_request_legal_hold_id` FOREIGN KEY (`legal_hold_id`) REFERENCES `atp_legal_hold` (`legal_hold_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_controlled_purge_request` ADD CONSTRAINT `fk_atp_controlled_purge_request_audit_log_id` FOREIGN KEY (`audit_log_id`) REFERENCES `atp_audit_log` (`audit_log_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_platform_design_baseline_release` ADD CONSTRAINT `fk_atp_platform_design_baseline_release_data_dictionary_id` FOREIGN KEY (`data_dictionary_id`) REFERENCES `atp_data_dictionary` (`data_dictionary_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_environment_terminal_access_revision` ADD CONSTRAINT `fk_atp_environment_terminal_access_revision_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_account_mapping_revision` ADD CONSTRAINT `fk_atp_account_mapping_revision_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_sso_identity` ADD CONSTRAINT `fk_atp_sso_identity_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_login_qualification` ADD CONSTRAINT `fk_atp_login_qualification_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_data_type` ADD CONSTRAINT `fk_atp_test_data_type_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_data_operation_task` ADD CONSTRAINT `fk_atp_data_operation_task_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_natural_language_case` ADD CONSTRAINT `fk_atp_natural_language_case_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_standard_case` ADD CONSTRAINT `fk_atp_standard_case_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_version` ADD CONSTRAINT `fk_atp_case_version_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_suite` ADD CONSTRAINT `fk_atp_case_suite_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_business_flow_template` ADD CONSTRAINT `fk_atp_business_flow_template_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_cross_terminal_orchestration` ADD CONSTRAINT `fk_atp_cross_terminal_orchestration_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_page_exploration` ADD CONSTRAINT `fk_atp_page_exploration_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_task` ADD CONSTRAINT `fk_atp_manual_recording_task_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_session` ADD CONSTRAINT `fk_atp_manual_recording_session_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_manual_recording_control_lease` ADD CONSTRAINT `fk_atp_manual_recording_control_lease_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_recording_evidence_bundle` ADD CONSTRAINT `fk_atp_recording_evidence_bundle_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_run_task` ADD CONSTRAINT `fk_atp_run_task_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_attempt` ADD CONSTRAINT `fk_atp_execution_attempt_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_attempt` ADD CONSTRAINT `fk_atp_case_attempt_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan` ADD CONSTRAINT `fk_atp_execution_plan_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_plan_revision` ADD CONSTRAINT `fk_atp_execution_plan_revision_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_trigger_rule` ADD CONSTRAINT `fk_atp_trigger_rule_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_lock` ADD CONSTRAINT `fk_atp_execution_lock_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_lease` ADD CONSTRAINT `fk_atp_lease_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_automation_asset` ADD CONSTRAINT `fk_atp_automation_asset_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_login_strategy` ADD CONSTRAINT `fk_atp_login_strategy_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_page_object` ADD CONSTRAINT `fk_atp_page_object_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_action_asset` ADD CONSTRAINT `fk_atp_action_asset_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_assertion_asset` ADD CONSTRAINT `fk_atp_assertion_asset_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner_capability` ADD CONSTRAINT `fk_atp_runner_capability_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner_project_binding` ADD CONSTRAINT `fk_atp_runner_project_binding_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_slot` ADD CONSTRAINT `fk_atp_execution_slot_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_context_variable` ADD CONSTRAINT `fk_atp_context_variable_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_call` ADD CONSTRAINT `fk_atp_ai_call_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_task` ADD CONSTRAINT `fk_atp_ai_task_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_result` ADD CONSTRAINT `fk_atp_ai_result_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_human_decision` ADD CONSTRAINT `fk_atp_human_decision_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_report_generation_request` ADD CONSTRAINT `fk_atp_test_report_generation_request_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_report` ADD CONSTRAINT `fk_atp_test_report_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_test_artifact` ADD CONSTRAINT `fk_atp_test_artifact_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_configuration_snapshot` ADD CONSTRAINT `fk_atp_configuration_snapshot_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_ai_candidate_revision` ADD CONSTRAINT `fk_atp_ai_candidate_revision_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_role_binding` ADD CONSTRAINT `fk_atp_role_binding_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_runner_agent` ADD CONSTRAINT `fk_atp_runner_agent_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_batch` ADD CONSTRAINT `fk_atp_execution_batch_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_step` ADD CONSTRAINT `fk_atp_case_step_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_case_suite_item` ADD CONSTRAINT `fk_atp_case_suite_item_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_execution_context` ADD CONSTRAINT `fk_atp_execution_context_project_id` FOREIGN KEY (`project_id`) REFERENCES `atp_project` (`project_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE `atp_role_permission` ADD CONSTRAINT `fk_role_permission_role` FOREIGN KEY (`role_id`) REFERENCES `atp_role` (`role_id`) ON DELETE CASCADE;
ALTER TABLE `atp_role_permission` ADD CONSTRAINT `fk_role_permission_permission` FOREIGN KEY (`permission_id`) REFERENCES `atp_permission_code` (`permission_code_id`) ON DELETE CASCADE;
ALTER TABLE `atp_user_role_binding` ADD CONSTRAINT `fk_user_role_user` FOREIGN KEY (`user_id`) REFERENCES `atp_user` (`user_id`) ON DELETE CASCADE;
ALTER TABLE `atp_user_role_binding` ADD CONSTRAINT `fk_user_role_role` FOREIGN KEY (`role_id`) REFERENCES `atp_role` (`role_id`) ON DELETE RESTRICT;
ALTER TABLE `atp_data_scope_grant` ADD CONSTRAINT `fk_scope_binding` FOREIGN KEY (`binding_id`) REFERENCES `atp_user_role_binding` (`binding_id`) ON DELETE CASCADE;
ALTER TABLE `atp_technical_alert_ingestion_batch` ADD CONSTRAINT `fk_atp_technical_alert_ingestion_batch_endpoint` FOREIGN KEY (`technical_alert_endpoint_id`) REFERENCES `atp_technical_alert_endpoint` (`technical_alert_endpoint_id`) ON DELETE RESTRICT ON UPDATE RESTRICT;
SET FOREIGN_KEY_CHECKS = 1;
