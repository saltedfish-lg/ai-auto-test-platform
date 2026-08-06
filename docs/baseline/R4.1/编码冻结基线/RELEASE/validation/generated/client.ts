/* Generated from PDBR-2026.08.06-R4.1 OpenAPI. DO NOT EDIT. */
import type { ProblemDetails, PageMeta, UserResource, AdminResource, RoleResource, EntitySuperAdminRoleResource, PermissionCodeResource, ProjectResource, ProjectMemberResource, EnvironmentResource, BusinessModuleResource, BusinessTerminalResource, EnvironmentTerminalAccessRevisionResource, TestAccountResource, CredentialRevisionResource, AccountMappingRevisionResource, SsoIdentityResource, LoginQualificationResource, TestDataTypeResource, TestDataResourceResource, DataOperationTaskResource, NaturalLanguageCaseResource, StandardCaseResource, CaseVersionResource, CaseSuiteResource, BusinessFlowTemplateResource, CrossTerminalOrchestrationResource, PageExplorationResource, ManualRecordingTaskResource, ManualRecordingSessionResource, ManualRecordingControlLeaseResource, RecordingEvidenceBundleResource, RunTaskResource, ExecutionAttemptResource, CaseAttemptResource, ExecutionPlanResource, ExecutionPlanRevisionResource, TriggerRuleResource, ExecutionLockResource, LeaseResource, AutomationAssetResource, LoginStrategyResource, PageObjectResource, ActionAssetResource, AssertionAssetResource, RunnerResource, RunnerCapabilityResource, RunnerProjectBindingResource, ExecutionSlotResource, ContextVariableResource, ModelConfigResource, PromptRevisionResource, AiCallResource, AiTaskResource, AiResultResource, HumanDecisionResource, TestReportGenerationRequestResource, TestReportResource, TestArtifactResource, TechnicalAlertResource, IntegrationComponentResource, SystemParameterResource, DataDictionaryResource, ConfigurationSnapshotResource, AuditLogResource, RetentionPolicyResource, LegalHoldResource, ControlledPurgeRequestResource, TechnicalAlertEndpointResource, PlatformDesignBaselineReleaseResource, AiCandidateRevisionResource, RoleBindingResource, TechnicalAlertIngestionBatchResource, RunnerAgentResource, ExecutionBatchResource, CaseStepResource, CaseSuiteItemResource, ExecutionContextResource, ProjectExecutionConfigurationResource, ListUserResponse, CreateUserRequest, CreateUserResponse, GetUserResponse, UpdateUserRequest, UpdateUserResponse, ListRoleResponse, CreateRoleRequest, CreateRoleResponse, GetRoleResponse, UpdateRoleRequest, UpdateRoleResponse, ListProjectResponse, CreateProjectRequest, CreateProjectResponse, GetProjectResponse, UpdateProjectRequest, UpdateProjectResponse, ListEnvironmentResponse, CreateEnvironmentRequest, CreateEnvironmentResponse, GetEnvironmentResponse, UpdateEnvironmentRequest, UpdateEnvironmentResponse, ListBusinessTerminalResponse, CreateBusinessTerminalRequest, CreateBusinessTerminalResponse, GetBusinessTerminalResponse, UpdateBusinessTerminalRequest, UpdateBusinessTerminalResponse, ListEnvironmentTerminalAccessRevisionResponse, CreateEnvironmentTerminalAccessRevisionRequest, CreateEnvironmentTerminalAccessRevisionResponse, GetEnvironmentTerminalAccessRevisionResponse, UpdateEnvironmentTerminalAccessRevisionRequest, UpdateEnvironmentTerminalAccessRevisionResponse, ListTestAccountResponse, CreateTestAccountRequest, CreateTestAccountResponse, GetTestAccountResponse, UpdateTestAccountRequest, UpdateTestAccountResponse, ListCredentialRevisionResponse, CreateCredentialRevisionRequest, CreateCredentialRevisionResponse, GetCredentialRevisionResponse, UpdateCredentialRevisionRequest, UpdateCredentialRevisionResponse, ListAccountMappingRevisionResponse, CreateAccountMappingRevisionRequest, CreateAccountMappingRevisionResponse, GetAccountMappingRevisionResponse, UpdateAccountMappingRevisionRequest, UpdateAccountMappingRevisionResponse, ListTestDataTypeResponse, CreateTestDataTypeRequest, CreateTestDataTypeResponse, GetTestDataTypeResponse, UpdateTestDataTypeRequest, UpdateTestDataTypeResponse, ListTestDataResourceResponse, CreateTestDataResourceRequest, CreateTestDataResourceResponse, GetTestDataResourceResponse, UpdateTestDataResourceRequest, UpdateTestDataResourceResponse, ListDataOperationTaskResponse, CreateDataOperationTaskRequest, CreateDataOperationTaskResponse, GetDataOperationTaskResponse, UpdateDataOperationTaskRequest, UpdateDataOperationTaskResponse, ListNaturalLanguageCaseResponse, CreateNaturalLanguageCaseRequest, CreateNaturalLanguageCaseResponse, GetNaturalLanguageCaseResponse, UpdateNaturalLanguageCaseRequest, UpdateNaturalLanguageCaseResponse, ListStandardCaseResponse, CreateStandardCaseRequest, CreateStandardCaseResponse, GetStandardCaseResponse, UpdateStandardCaseRequest, UpdateStandardCaseResponse, ListCaseVersionResponse, CreateCaseVersionRequest, CreateCaseVersionResponse, GetCaseVersionResponse, UpdateCaseVersionRequest, UpdateCaseVersionResponse, ListCaseSuiteResponse, CreateCaseSuiteRequest, CreateCaseSuiteResponse, GetCaseSuiteResponse, UpdateCaseSuiteRequest, UpdateCaseSuiteResponse, ListBusinessFlowTemplateResponse, CreateBusinessFlowTemplateRequest, CreateBusinessFlowTemplateResponse, GetBusinessFlowTemplateResponse, UpdateBusinessFlowTemplateRequest, UpdateBusinessFlowTemplateResponse, ListPageExplorationResponse, CreatePageExplorationRequest, CreatePageExplorationResponse, GetPageExplorationResponse, UpdatePageExplorationRequest, UpdatePageExplorationResponse, ListManualRecordingTaskResponse, CreateManualRecordingTaskRequest, CreateManualRecordingTaskResponse, GetManualRecordingTaskResponse, UpdateManualRecordingTaskRequest, UpdateManualRecordingTaskResponse, ListManualRecordingSessionResponse, CreateManualRecordingSessionRequest, CreateManualRecordingSessionResponse, GetManualRecordingSessionResponse, UpdateManualRecordingSessionRequest, UpdateManualRecordingSessionResponse, ListRecordingEvidenceBundleResponse, CreateRecordingEvidenceBundleRequest, CreateRecordingEvidenceBundleResponse, GetRecordingEvidenceBundleResponse, UpdateRecordingEvidenceBundleRequest, UpdateRecordingEvidenceBundleResponse, ListRunTaskResponse, CreateRunTaskRequest, CreateRunTaskResponse, GetRunTaskResponse, UpdateRunTaskRequest, UpdateRunTaskResponse, ListExecutionAttemptResponse, CreateExecutionAttemptRequest, CreateExecutionAttemptResponse, GetExecutionAttemptResponse, UpdateExecutionAttemptRequest, UpdateExecutionAttemptResponse, ListCaseAttemptResponse, CreateCaseAttemptRequest, CreateCaseAttemptResponse, GetCaseAttemptResponse, UpdateCaseAttemptRequest, UpdateCaseAttemptResponse, ListExecutionPlanResponse, CreateExecutionPlanRequest, CreateExecutionPlanResponse, GetExecutionPlanResponse, UpdateExecutionPlanRequest, UpdateExecutionPlanResponse, ListExecutionPlanRevisionResponse, CreateExecutionPlanRevisionRequest, CreateExecutionPlanRevisionResponse, GetExecutionPlanRevisionResponse, UpdateExecutionPlanRevisionRequest, UpdateExecutionPlanRevisionResponse, ListTriggerRuleResponse, CreateTriggerRuleRequest, CreateTriggerRuleResponse, GetTriggerRuleResponse, UpdateTriggerRuleRequest, UpdateTriggerRuleResponse, ListLeaseResponse, CreateLeaseRequest, CreateLeaseResponse, GetLeaseResponse, UpdateLeaseRequest, UpdateLeaseResponse, ListAutomationAssetResponse, CreateAutomationAssetRequest, CreateAutomationAssetResponse, GetAutomationAssetResponse, UpdateAutomationAssetRequest, UpdateAutomationAssetResponse, ListLoginStrategyResponse, CreateLoginStrategyRequest, CreateLoginStrategyResponse, GetLoginStrategyResponse, UpdateLoginStrategyRequest, UpdateLoginStrategyResponse, ListPageObjectResponse, CreatePageObjectRequest, CreatePageObjectResponse, GetPageObjectResponse, UpdatePageObjectRequest, UpdatePageObjectResponse, ListActionAssetResponse, CreateActionAssetRequest, CreateActionAssetResponse, GetActionAssetResponse, UpdateActionAssetRequest, UpdateActionAssetResponse, ListAssertionAssetResponse, CreateAssertionAssetRequest, CreateAssertionAssetResponse, GetAssertionAssetResponse, UpdateAssertionAssetRequest, UpdateAssertionAssetResponse, ListRunnerResponse, CreateRunnerRequest, CreateRunnerResponse, GetRunnerResponse, UpdateRunnerRequest, UpdateRunnerResponse, ListRunnerCapabilityResponse, CreateRunnerCapabilityRequest, CreateRunnerCapabilityResponse, GetRunnerCapabilityResponse, UpdateRunnerCapabilityRequest, UpdateRunnerCapabilityResponse, ListExecutionSlotResponse, CreateExecutionSlotRequest, CreateExecutionSlotResponse, GetExecutionSlotResponse, UpdateExecutionSlotRequest, UpdateExecutionSlotResponse, ListModelConfigResponse, CreateModelConfigRequest, CreateModelConfigResponse, GetModelConfigResponse, UpdateModelConfigRequest, UpdateModelConfigResponse, ListPromptRevisionResponse, CreatePromptRevisionRequest, CreatePromptRevisionResponse, GetPromptRevisionResponse, UpdatePromptRevisionRequest, UpdatePromptRevisionResponse, ListAiCallResponse, CreateAiCallRequest, CreateAiCallResponse, GetAiCallResponse, UpdateAiCallRequest, UpdateAiCallResponse, ListAiTaskResponse, CreateAiTaskRequest, CreateAiTaskResponse, GetAiTaskResponse, UpdateAiTaskRequest, UpdateAiTaskResponse, ListTestReportGenerationRequestResponse, CreateTestReportGenerationRequestRequest, CreateTestReportGenerationRequestResponse, GetTestReportGenerationRequestResponse, UpdateTestReportGenerationRequestRequest, UpdateTestReportGenerationRequestResponse, ListTestReportResponse, CreateTestReportRequest, CreateTestReportResponse, GetTestReportResponse, UpdateTestReportRequest, UpdateTestReportResponse, ListTestArtifactResponse, CreateTestArtifactRequest, CreateTestArtifactResponse, GetTestArtifactResponse, UpdateTestArtifactRequest, UpdateTestArtifactResponse, ListTechnicalAlertResponse, CreateTechnicalAlertRequest, CreateTechnicalAlertResponse, GetTechnicalAlertResponse, UpdateTechnicalAlertRequest, UpdateTechnicalAlertResponse, ListIntegrationComponentResponse, CreateIntegrationComponentRequest, CreateIntegrationComponentResponse, GetIntegrationComponentResponse, UpdateIntegrationComponentRequest, UpdateIntegrationComponentResponse, ListSystemParameterResponse, CreateSystemParameterRequest, CreateSystemParameterResponse, GetSystemParameterResponse, UpdateSystemParameterRequest, UpdateSystemParameterResponse, ListDataDictionaryResponse, CreateDataDictionaryRequest, CreateDataDictionaryResponse, GetDataDictionaryResponse, UpdateDataDictionaryRequest, UpdateDataDictionaryResponse, ListAuditLogResponse, CreateAuditLogRequest, CreateAuditLogResponse, GetAuditLogResponse, UpdateAuditLogRequest, UpdateAuditLogResponse, ListRetentionPolicyResponse, CreateRetentionPolicyRequest, CreateRetentionPolicyResponse, GetRetentionPolicyResponse, UpdateRetentionPolicyRequest, UpdateRetentionPolicyResponse, ListControlledPurgeRequestResponse, CreateControlledPurgeRequestRequest, CreateControlledPurgeRequestResponse, GetControlledPurgeRequestResponse, UpdateControlledPurgeRequestRequest, UpdateControlledPurgeRequestResponse, ListTechnicalAlertEndpointResponse, CreateTechnicalAlertEndpointRequest, CreateTechnicalAlertEndpointResponse, GetTechnicalAlertEndpointResponse, UpdateTechnicalAlertEndpointRequest, UpdateTechnicalAlertEndpointResponse, ListPlatformDesignBaselineReleaseResponse, CreatePlatformDesignBaselineReleaseRequest, CreatePlatformDesignBaselineReleaseResponse, GetPlatformDesignBaselineReleaseResponse, UpdatePlatformDesignBaselineReleaseRequest, UpdatePlatformDesignBaselineReleaseResponse, ListAiCandidateRevisionResponse, CreateAiCandidateRevisionRequest, CreateAiCandidateRevisionResponse, GetAiCandidateRevisionResponse, UpdateAiCandidateRevisionRequest, UpdateAiCandidateRevisionResponse, ListTechnicalAlertIngestionBatchResponse, CreateTechnicalAlertIngestionBatchRequest, CreateTechnicalAlertIngestionBatchResponse, GetTechnicalAlertIngestionBatchResponse, UpdateTechnicalAlertIngestionBatchRequest, UpdateTechnicalAlertIngestionBatchResponse, ListExecutionBatchResponse, CreateExecutionBatchRequest, CreateExecutionBatchResponse, GetExecutionBatchResponse, UpdateExecutionBatchRequest, UpdateExecutionBatchResponse, ListProjectExecutionConfigurationResponse, CreateProjectExecutionConfigurationRequest, CreateProjectExecutionConfigurationResponse, GetProjectExecutionConfigurationResponse, UpdateProjectExecutionConfigurationRequest, UpdateProjectExecutionConfigurationResponse, GenericOperationResource, CreateExecutionRequest, CreateExecutionResponse, CancelExecutionRequest, CancelExecutionResponse, TerminateExecutionRequest, TerminateExecutionResponse, RegisterRunnerRequest, RegisterRunnerResponse, HeartbeatRunnerRequest, HeartbeatRunnerResponse, ClaimRunnerTaskRequest, ClaimRunnerTaskResponse, RenewRunnerLeaseRequest, RenewRunnerLeaseResponse, ReportRunnerProgressRequest, ReportRunnerProgressResponse, ReportRunnerResultRequest, ReportRunnerResultResponse, ConvertNaturalLanguageCaseRequest, ConvertNaturalLanguageCaseResponse, CreateAiExplorationRequest, CreateAiExplorationResponse, CreateManualRecordingRequest, CreateManualRecordingResponse, SaveRecordingDraftAndStopRequest, SaveRecordingDraftAndStopResponse, GetReportResponse, ExportReportRequest, ExportReportResponse, CreateReportShareRequest, CreateReportShareResponse, DownloadArtifactResponse, CreateArtifactUploadSessionRequest, CreateArtifactUploadSessionResponse, CompleteArtifactUploadRequest, CompleteArtifactUploadResponse, ListRecoveryItemsResponse, CreateExternalTriggerRequest, CreateExternalTriggerResponse } from './types.js';
export type RequestOptions = { headers?: Record<string,string>; signal?: AbortSignal };
export class ApiClient {
  constructor(private readonly baseUrl: string, private readonly fetcher: typeof fetch = fetch) {}
  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, init);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return (await response.json()) as T;
  }
  async list_user(options: RequestOptions = {}): Promise<ListUserResponse> {
    const path = "/api/v1/user";
    return this.request<ListUserResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_user(body: CreateUserRequest, options: RequestOptions = {}): Promise<CreateUserResponse> {
    const path = "/api/v1/user";
    return this.request<CreateUserResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_user(id: string, options: RequestOptions = {}): Promise<GetUserResponse> {
    const path = "/api/v1/user/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetUserResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_user(id: string, body: UpdateUserRequest, options: RequestOptions = {}): Promise<UpdateUserResponse> {
    const path = "/api/v1/user/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateUserResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_role(options: RequestOptions = {}): Promise<ListRoleResponse> {
    const path = "/api/v1/role";
    return this.request<ListRoleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_role(body: CreateRoleRequest, options: RequestOptions = {}): Promise<CreateRoleResponse> {
    const path = "/api/v1/role";
    return this.request<CreateRoleResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_role(id: string, options: RequestOptions = {}): Promise<GetRoleResponse> {
    const path = "/api/v1/role/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRoleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_role(id: string, body: UpdateRoleRequest, options: RequestOptions = {}): Promise<UpdateRoleResponse> {
    const path = "/api/v1/role/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRoleResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_project(options: RequestOptions = {}): Promise<ListProjectResponse> {
    const path = "/api/v1/project";
    return this.request<ListProjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_project(body: CreateProjectRequest, options: RequestOptions = {}): Promise<CreateProjectResponse> {
    const path = "/api/v1/project";
    return this.request<CreateProjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_project(id: string, options: RequestOptions = {}): Promise<GetProjectResponse> {
    const path = "/api/v1/project/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetProjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_project(id: string, body: UpdateProjectRequest, options: RequestOptions = {}): Promise<UpdateProjectResponse> {
    const path = "/api/v1/project/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_environment(options: RequestOptions = {}): Promise<ListEnvironmentResponse> {
    const path = "/api/v1/environment";
    return this.request<ListEnvironmentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_environment(body: CreateEnvironmentRequest, options: RequestOptions = {}): Promise<CreateEnvironmentResponse> {
    const path = "/api/v1/environment";
    return this.request<CreateEnvironmentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_environment(id: string, options: RequestOptions = {}): Promise<GetEnvironmentResponse> {
    const path = "/api/v1/environment/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetEnvironmentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_environment(id: string, body: UpdateEnvironmentRequest, options: RequestOptions = {}): Promise<UpdateEnvironmentResponse> {
    const path = "/api/v1/environment/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_business_terminal(options: RequestOptions = {}): Promise<ListBusinessTerminalResponse> {
    const path = "/api/v1/business-terminal";
    return this.request<ListBusinessTerminalResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_business_terminal(body: CreateBusinessTerminalRequest, options: RequestOptions = {}): Promise<CreateBusinessTerminalResponse> {
    const path = "/api/v1/business-terminal";
    return this.request<CreateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_business_terminal(id: string, options: RequestOptions = {}): Promise<GetBusinessTerminalResponse> {
    const path = "/api/v1/business-terminal/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetBusinessTerminalResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_business_terminal(id: string, body: UpdateBusinessTerminalRequest, options: RequestOptions = {}): Promise<UpdateBusinessTerminalResponse> {
    const path = "/api/v1/business-terminal/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_environment_terminal_access_revision(options: RequestOptions = {}): Promise<ListEnvironmentTerminalAccessRevisionResponse> {
    const path = "/api/v1/environment-terminal-access-revision";
    return this.request<ListEnvironmentTerminalAccessRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_environment_terminal_access_revision(body: CreateEnvironmentTerminalAccessRevisionRequest, options: RequestOptions = {}): Promise<CreateEnvironmentTerminalAccessRevisionResponse> {
    const path = "/api/v1/environment-terminal-access-revision";
    return this.request<CreateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_environment_terminal_access_revision(id: string, options: RequestOptions = {}): Promise<GetEnvironmentTerminalAccessRevisionResponse> {
    const path = "/api/v1/environment-terminal-access-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetEnvironmentTerminalAccessRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_environment_terminal_access_revision(id: string, body: UpdateEnvironmentTerminalAccessRevisionRequest, options: RequestOptions = {}): Promise<UpdateEnvironmentTerminalAccessRevisionResponse> {
    const path = "/api/v1/environment-terminal-access-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_account(options: RequestOptions = {}): Promise<ListTestAccountResponse> {
    const path = "/api/v1/test-account";
    return this.request<ListTestAccountResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_account(body: CreateTestAccountRequest, options: RequestOptions = {}): Promise<CreateTestAccountResponse> {
    const path = "/api/v1/test-account";
    return this.request<CreateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_account(id: string, options: RequestOptions = {}): Promise<GetTestAccountResponse> {
    const path = "/api/v1/test-account/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestAccountResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_account(id: string, body: UpdateTestAccountRequest, options: RequestOptions = {}): Promise<UpdateTestAccountResponse> {
    const path = "/api/v1/test-account/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_credential_revision(options: RequestOptions = {}): Promise<ListCredentialRevisionResponse> {
    const path = "/api/v1/credential-revision";
    return this.request<ListCredentialRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_credential_revision(body: CreateCredentialRevisionRequest, options: RequestOptions = {}): Promise<CreateCredentialRevisionResponse> {
    const path = "/api/v1/credential-revision";
    return this.request<CreateCredentialRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_credential_revision(id: string, options: RequestOptions = {}): Promise<GetCredentialRevisionResponse> {
    const path = "/api/v1/credential-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCredentialRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_credential_revision(id: string, body: UpdateCredentialRevisionRequest, options: RequestOptions = {}): Promise<UpdateCredentialRevisionResponse> {
    const path = "/api/v1/credential-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCredentialRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_account_mapping_revision(options: RequestOptions = {}): Promise<ListAccountMappingRevisionResponse> {
    const path = "/api/v1/account-mapping-revision";
    return this.request<ListAccountMappingRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_account_mapping_revision(body: CreateAccountMappingRevisionRequest, options: RequestOptions = {}): Promise<CreateAccountMappingRevisionResponse> {
    const path = "/api/v1/account-mapping-revision";
    return this.request<CreateAccountMappingRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_account_mapping_revision(id: string, options: RequestOptions = {}): Promise<GetAccountMappingRevisionResponse> {
    const path = "/api/v1/account-mapping-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAccountMappingRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_account_mapping_revision(id: string, body: UpdateAccountMappingRevisionRequest, options: RequestOptions = {}): Promise<UpdateAccountMappingRevisionResponse> {
    const path = "/api/v1/account-mapping-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAccountMappingRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_data_type(options: RequestOptions = {}): Promise<ListTestDataTypeResponse> {
    const path = "/api/v1/test-data-type";
    return this.request<ListTestDataTypeResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_data_type(body: CreateTestDataTypeRequest, options: RequestOptions = {}): Promise<CreateTestDataTypeResponse> {
    const path = "/api/v1/test-data-type";
    return this.request<CreateTestDataTypeResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_data_type(id: string, options: RequestOptions = {}): Promise<GetTestDataTypeResponse> {
    const path = "/api/v1/test-data-type/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestDataTypeResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_data_type(id: string, body: UpdateTestDataTypeRequest, options: RequestOptions = {}): Promise<UpdateTestDataTypeResponse> {
    const path = "/api/v1/test-data-type/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestDataTypeResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_data_resource(options: RequestOptions = {}): Promise<ListTestDataResourceResponse> {
    const path = "/api/v1/test-data-resource";
    return this.request<ListTestDataResourceResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_data_resource(body: CreateTestDataResourceRequest, options: RequestOptions = {}): Promise<CreateTestDataResourceResponse> {
    const path = "/api/v1/test-data-resource";
    return this.request<CreateTestDataResourceResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_data_resource(id: string, options: RequestOptions = {}): Promise<GetTestDataResourceResponse> {
    const path = "/api/v1/test-data-resource/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestDataResourceResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_data_resource(id: string, body: UpdateTestDataResourceRequest, options: RequestOptions = {}): Promise<UpdateTestDataResourceResponse> {
    const path = "/api/v1/test-data-resource/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestDataResourceResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_data_operation_task(options: RequestOptions = {}): Promise<ListDataOperationTaskResponse> {
    const path = "/api/v1/data-operation-task";
    return this.request<ListDataOperationTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_data_operation_task(body: CreateDataOperationTaskRequest, options: RequestOptions = {}): Promise<CreateDataOperationTaskResponse> {
    const path = "/api/v1/data-operation-task";
    return this.request<CreateDataOperationTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_data_operation_task(id: string, options: RequestOptions = {}): Promise<GetDataOperationTaskResponse> {
    const path = "/api/v1/data-operation-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetDataOperationTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_data_operation_task(id: string, body: UpdateDataOperationTaskRequest, options: RequestOptions = {}): Promise<UpdateDataOperationTaskResponse> {
    const path = "/api/v1/data-operation-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateDataOperationTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_natural_language_case(options: RequestOptions = {}): Promise<ListNaturalLanguageCaseResponse> {
    const path = "/api/v1/natural-language-case";
    return this.request<ListNaturalLanguageCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_natural_language_case(body: CreateNaturalLanguageCaseRequest, options: RequestOptions = {}): Promise<CreateNaturalLanguageCaseResponse> {
    const path = "/api/v1/natural-language-case";
    return this.request<CreateNaturalLanguageCaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_natural_language_case(id: string, options: RequestOptions = {}): Promise<GetNaturalLanguageCaseResponse> {
    const path = "/api/v1/natural-language-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetNaturalLanguageCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_natural_language_case(id: string, body: UpdateNaturalLanguageCaseRequest, options: RequestOptions = {}): Promise<UpdateNaturalLanguageCaseResponse> {
    const path = "/api/v1/natural-language-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateNaturalLanguageCaseResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_standard_case(options: RequestOptions = {}): Promise<ListStandardCaseResponse> {
    const path = "/api/v1/standard-case";
    return this.request<ListStandardCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_standard_case(body: CreateStandardCaseRequest, options: RequestOptions = {}): Promise<CreateStandardCaseResponse> {
    const path = "/api/v1/standard-case";
    return this.request<CreateStandardCaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_standard_case(id: string, options: RequestOptions = {}): Promise<GetStandardCaseResponse> {
    const path = "/api/v1/standard-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetStandardCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_standard_case(id: string, body: UpdateStandardCaseRequest, options: RequestOptions = {}): Promise<UpdateStandardCaseResponse> {
    const path = "/api/v1/standard-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateStandardCaseResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_case_version(options: RequestOptions = {}): Promise<ListCaseVersionResponse> {
    const path = "/api/v1/case-version";
    return this.request<ListCaseVersionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_case_version(body: CreateCaseVersionRequest, options: RequestOptions = {}): Promise<CreateCaseVersionResponse> {
    const path = "/api/v1/case-version";
    return this.request<CreateCaseVersionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_case_version(id: string, options: RequestOptions = {}): Promise<GetCaseVersionResponse> {
    const path = "/api/v1/case-version/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCaseVersionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_case_version(id: string, body: UpdateCaseVersionRequest, options: RequestOptions = {}): Promise<UpdateCaseVersionResponse> {
    const path = "/api/v1/case-version/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCaseVersionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_case_suite(options: RequestOptions = {}): Promise<ListCaseSuiteResponse> {
    const path = "/api/v1/case-suite";
    return this.request<ListCaseSuiteResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_case_suite(body: CreateCaseSuiteRequest, options: RequestOptions = {}): Promise<CreateCaseSuiteResponse> {
    const path = "/api/v1/case-suite";
    return this.request<CreateCaseSuiteResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_case_suite(id: string, options: RequestOptions = {}): Promise<GetCaseSuiteResponse> {
    const path = "/api/v1/case-suite/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCaseSuiteResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_case_suite(id: string, body: UpdateCaseSuiteRequest, options: RequestOptions = {}): Promise<UpdateCaseSuiteResponse> {
    const path = "/api/v1/case-suite/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCaseSuiteResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_business_flow_template(options: RequestOptions = {}): Promise<ListBusinessFlowTemplateResponse> {
    const path = "/api/v1/business-flow-template";
    return this.request<ListBusinessFlowTemplateResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_business_flow_template(body: CreateBusinessFlowTemplateRequest, options: RequestOptions = {}): Promise<CreateBusinessFlowTemplateResponse> {
    const path = "/api/v1/business-flow-template";
    return this.request<CreateBusinessFlowTemplateResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_business_flow_template(id: string, options: RequestOptions = {}): Promise<GetBusinessFlowTemplateResponse> {
    const path = "/api/v1/business-flow-template/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetBusinessFlowTemplateResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_business_flow_template(id: string, body: UpdateBusinessFlowTemplateRequest, options: RequestOptions = {}): Promise<UpdateBusinessFlowTemplateResponse> {
    const path = "/api/v1/business-flow-template/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessFlowTemplateResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_page_exploration(options: RequestOptions = {}): Promise<ListPageExplorationResponse> {
    const path = "/api/v1/page-exploration";
    return this.request<ListPageExplorationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_page_exploration(body: CreatePageExplorationRequest, options: RequestOptions = {}): Promise<CreatePageExplorationResponse> {
    const path = "/api/v1/page-exploration";
    return this.request<CreatePageExplorationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_page_exploration(id: string, options: RequestOptions = {}): Promise<GetPageExplorationResponse> {
    const path = "/api/v1/page-exploration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPageExplorationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_page_exploration(id: string, body: UpdatePageExplorationRequest, options: RequestOptions = {}): Promise<UpdatePageExplorationResponse> {
    const path = "/api/v1/page-exploration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePageExplorationResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_manual_recording_task(options: RequestOptions = {}): Promise<ListManualRecordingTaskResponse> {
    const path = "/api/v1/manual-recording-task";
    return this.request<ListManualRecordingTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_manual_recording_task(body: CreateManualRecordingTaskRequest, options: RequestOptions = {}): Promise<CreateManualRecordingTaskResponse> {
    const path = "/api/v1/manual-recording-task";
    return this.request<CreateManualRecordingTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_manual_recording_task(id: string, options: RequestOptions = {}): Promise<GetManualRecordingTaskResponse> {
    const path = "/api/v1/manual-recording-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetManualRecordingTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_manual_recording_task(id: string, body: UpdateManualRecordingTaskRequest, options: RequestOptions = {}): Promise<UpdateManualRecordingTaskResponse> {
    const path = "/api/v1/manual-recording-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateManualRecordingTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_manual_recording_session(options: RequestOptions = {}): Promise<ListManualRecordingSessionResponse> {
    const path = "/api/v1/manual-recording-session";
    return this.request<ListManualRecordingSessionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_manual_recording_session(body: CreateManualRecordingSessionRequest, options: RequestOptions = {}): Promise<CreateManualRecordingSessionResponse> {
    const path = "/api/v1/manual-recording-session";
    return this.request<CreateManualRecordingSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_manual_recording_session(id: string, options: RequestOptions = {}): Promise<GetManualRecordingSessionResponse> {
    const path = "/api/v1/manual-recording-session/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetManualRecordingSessionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_manual_recording_session(id: string, body: UpdateManualRecordingSessionRequest, options: RequestOptions = {}): Promise<UpdateManualRecordingSessionResponse> {
    const path = "/api/v1/manual-recording-session/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateManualRecordingSessionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_recording_evidence_bundle(options: RequestOptions = {}): Promise<ListRecordingEvidenceBundleResponse> {
    const path = "/api/v1/recording-evidence-bundle";
    return this.request<ListRecordingEvidenceBundleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_recording_evidence_bundle(body: CreateRecordingEvidenceBundleRequest, options: RequestOptions = {}): Promise<CreateRecordingEvidenceBundleResponse> {
    const path = "/api/v1/recording-evidence-bundle";
    return this.request<CreateRecordingEvidenceBundleResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_recording_evidence_bundle(id: string, options: RequestOptions = {}): Promise<GetRecordingEvidenceBundleResponse> {
    const path = "/api/v1/recording-evidence-bundle/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRecordingEvidenceBundleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_recording_evidence_bundle(id: string, body: UpdateRecordingEvidenceBundleRequest, options: RequestOptions = {}): Promise<UpdateRecordingEvidenceBundleResponse> {
    const path = "/api/v1/recording-evidence-bundle/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRecordingEvidenceBundleResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_run_task(options: RequestOptions = {}): Promise<ListRunTaskResponse> {
    const path = "/api/v1/run-task";
    return this.request<ListRunTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_run_task(body: CreateRunTaskRequest, options: RequestOptions = {}): Promise<CreateRunTaskResponse> {
    const path = "/api/v1/run-task";
    return this.request<CreateRunTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_run_task(id: string, options: RequestOptions = {}): Promise<GetRunTaskResponse> {
    const path = "/api/v1/run-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_run_task(id: string, body: UpdateRunTaskRequest, options: RequestOptions = {}): Promise<UpdateRunTaskResponse> {
    const path = "/api/v1/run-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRunTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_attempt(options: RequestOptions = {}): Promise<ListExecutionAttemptResponse> {
    const path = "/api/v1/execution-attempt";
    return this.request<ListExecutionAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_attempt(body: CreateExecutionAttemptRequest, options: RequestOptions = {}): Promise<CreateExecutionAttemptResponse> {
    const path = "/api/v1/execution-attempt";
    return this.request<CreateExecutionAttemptResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_attempt(id: string, options: RequestOptions = {}): Promise<GetExecutionAttemptResponse> {
    const path = "/api/v1/execution-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_attempt(id: string, body: UpdateExecutionAttemptRequest, options: RequestOptions = {}): Promise<UpdateExecutionAttemptResponse> {
    const path = "/api/v1/execution-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionAttemptResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_case_attempt(options: RequestOptions = {}): Promise<ListCaseAttemptResponse> {
    const path = "/api/v1/case-attempt";
    return this.request<ListCaseAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_case_attempt(body: CreateCaseAttemptRequest, options: RequestOptions = {}): Promise<CreateCaseAttemptResponse> {
    const path = "/api/v1/case-attempt";
    return this.request<CreateCaseAttemptResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_case_attempt(id: string, options: RequestOptions = {}): Promise<GetCaseAttemptResponse> {
    const path = "/api/v1/case-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCaseAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_case_attempt(id: string, body: UpdateCaseAttemptRequest, options: RequestOptions = {}): Promise<UpdateCaseAttemptResponse> {
    const path = "/api/v1/case-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCaseAttemptResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_plan(options: RequestOptions = {}): Promise<ListExecutionPlanResponse> {
    const path = "/api/v1/execution-plan";
    return this.request<ListExecutionPlanResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_plan(body: CreateExecutionPlanRequest, options: RequestOptions = {}): Promise<CreateExecutionPlanResponse> {
    const path = "/api/v1/execution-plan";
    return this.request<CreateExecutionPlanResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_plan(id: string, options: RequestOptions = {}): Promise<GetExecutionPlanResponse> {
    const path = "/api/v1/execution-plan/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionPlanResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_plan(id: string, body: UpdateExecutionPlanRequest, options: RequestOptions = {}): Promise<UpdateExecutionPlanResponse> {
    const path = "/api/v1/execution-plan/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionPlanResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_plan_revision(options: RequestOptions = {}): Promise<ListExecutionPlanRevisionResponse> {
    const path = "/api/v1/execution-plan-revision";
    return this.request<ListExecutionPlanRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_plan_revision(body: CreateExecutionPlanRevisionRequest, options: RequestOptions = {}): Promise<CreateExecutionPlanRevisionResponse> {
    const path = "/api/v1/execution-plan-revision";
    return this.request<CreateExecutionPlanRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_plan_revision(id: string, options: RequestOptions = {}): Promise<GetExecutionPlanRevisionResponse> {
    const path = "/api/v1/execution-plan-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionPlanRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_plan_revision(id: string, body: UpdateExecutionPlanRevisionRequest, options: RequestOptions = {}): Promise<UpdateExecutionPlanRevisionResponse> {
    const path = "/api/v1/execution-plan-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionPlanRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_trigger_rule(options: RequestOptions = {}): Promise<ListTriggerRuleResponse> {
    const path = "/api/v1/trigger-rule";
    return this.request<ListTriggerRuleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_trigger_rule(body: CreateTriggerRuleRequest, options: RequestOptions = {}): Promise<CreateTriggerRuleResponse> {
    const path = "/api/v1/trigger-rule";
    return this.request<CreateTriggerRuleResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_trigger_rule(id: string, options: RequestOptions = {}): Promise<GetTriggerRuleResponse> {
    const path = "/api/v1/trigger-rule/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTriggerRuleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_trigger_rule(id: string, body: UpdateTriggerRuleRequest, options: RequestOptions = {}): Promise<UpdateTriggerRuleResponse> {
    const path = "/api/v1/trigger-rule/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTriggerRuleResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_lease(options: RequestOptions = {}): Promise<ListLeaseResponse> {
    const path = "/api/v1/lease";
    return this.request<ListLeaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_lease(body: CreateLeaseRequest, options: RequestOptions = {}): Promise<CreateLeaseResponse> {
    const path = "/api/v1/lease";
    return this.request<CreateLeaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_lease(id: string, options: RequestOptions = {}): Promise<GetLeaseResponse> {
    const path = "/api/v1/lease/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetLeaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_lease(id: string, body: UpdateLeaseRequest, options: RequestOptions = {}): Promise<UpdateLeaseResponse> {
    const path = "/api/v1/lease/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateLeaseResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_automation_asset(options: RequestOptions = {}): Promise<ListAutomationAssetResponse> {
    const path = "/api/v1/automation-asset";
    return this.request<ListAutomationAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_automation_asset(body: CreateAutomationAssetRequest, options: RequestOptions = {}): Promise<CreateAutomationAssetResponse> {
    const path = "/api/v1/automation-asset";
    return this.request<CreateAutomationAssetResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_automation_asset(id: string, options: RequestOptions = {}): Promise<GetAutomationAssetResponse> {
    const path = "/api/v1/automation-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAutomationAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_automation_asset(id: string, body: UpdateAutomationAssetRequest, options: RequestOptions = {}): Promise<UpdateAutomationAssetResponse> {
    const path = "/api/v1/automation-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAutomationAssetResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_login_strategy(options: RequestOptions = {}): Promise<ListLoginStrategyResponse> {
    const path = "/api/v1/login-strategy";
    return this.request<ListLoginStrategyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_login_strategy(body: CreateLoginStrategyRequest, options: RequestOptions = {}): Promise<CreateLoginStrategyResponse> {
    const path = "/api/v1/login-strategy";
    return this.request<CreateLoginStrategyResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_login_strategy(id: string, options: RequestOptions = {}): Promise<GetLoginStrategyResponse> {
    const path = "/api/v1/login-strategy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetLoginStrategyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_login_strategy(id: string, body: UpdateLoginStrategyRequest, options: RequestOptions = {}): Promise<UpdateLoginStrategyResponse> {
    const path = "/api/v1/login-strategy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateLoginStrategyResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_page_object(options: RequestOptions = {}): Promise<ListPageObjectResponse> {
    const path = "/api/v1/page-object";
    return this.request<ListPageObjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_page_object(body: CreatePageObjectRequest, options: RequestOptions = {}): Promise<CreatePageObjectResponse> {
    const path = "/api/v1/page-object";
    return this.request<CreatePageObjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_page_object(id: string, options: RequestOptions = {}): Promise<GetPageObjectResponse> {
    const path = "/api/v1/page-object/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPageObjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_page_object(id: string, body: UpdatePageObjectRequest, options: RequestOptions = {}): Promise<UpdatePageObjectResponse> {
    const path = "/api/v1/page-object/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePageObjectResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_action_asset(options: RequestOptions = {}): Promise<ListActionAssetResponse> {
    const path = "/api/v1/action-asset";
    return this.request<ListActionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_action_asset(body: CreateActionAssetRequest, options: RequestOptions = {}): Promise<CreateActionAssetResponse> {
    const path = "/api/v1/action-asset";
    return this.request<CreateActionAssetResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_action_asset(id: string, options: RequestOptions = {}): Promise<GetActionAssetResponse> {
    const path = "/api/v1/action-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetActionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_action_asset(id: string, body: UpdateActionAssetRequest, options: RequestOptions = {}): Promise<UpdateActionAssetResponse> {
    const path = "/api/v1/action-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateActionAssetResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_assertion_asset(options: RequestOptions = {}): Promise<ListAssertionAssetResponse> {
    const path = "/api/v1/assertion-asset";
    return this.request<ListAssertionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_assertion_asset(body: CreateAssertionAssetRequest, options: RequestOptions = {}): Promise<CreateAssertionAssetResponse> {
    const path = "/api/v1/assertion-asset";
    return this.request<CreateAssertionAssetResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_assertion_asset(id: string, options: RequestOptions = {}): Promise<GetAssertionAssetResponse> {
    const path = "/api/v1/assertion-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAssertionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_assertion_asset(id: string, body: UpdateAssertionAssetRequest, options: RequestOptions = {}): Promise<UpdateAssertionAssetResponse> {
    const path = "/api/v1/assertion-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAssertionAssetResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_runner(options: RequestOptions = {}): Promise<ListRunnerResponse> {
    const path = "/api/v1/runner";
    return this.request<ListRunnerResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_runner(body: CreateRunnerRequest, options: RequestOptions = {}): Promise<CreateRunnerResponse> {
    const path = "/api/v1/runner";
    return this.request<CreateRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_runner(id: string, options: RequestOptions = {}): Promise<GetRunnerResponse> {
    const path = "/api/v1/runner/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_runner(id: string, body: UpdateRunnerRequest, options: RequestOptions = {}): Promise<UpdateRunnerResponse> {
    const path = "/api/v1/runner/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRunnerResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_runner_capability(options: RequestOptions = {}): Promise<ListRunnerCapabilityResponse> {
    const path = "/api/v1/runner-capability";
    return this.request<ListRunnerCapabilityResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_runner_capability(body: CreateRunnerCapabilityRequest, options: RequestOptions = {}): Promise<CreateRunnerCapabilityResponse> {
    const path = "/api/v1/runner-capability";
    return this.request<CreateRunnerCapabilityResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_runner_capability(id: string, options: RequestOptions = {}): Promise<GetRunnerCapabilityResponse> {
    const path = "/api/v1/runner-capability/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerCapabilityResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_runner_capability(id: string, body: UpdateRunnerCapabilityRequest, options: RequestOptions = {}): Promise<UpdateRunnerCapabilityResponse> {
    const path = "/api/v1/runner-capability/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRunnerCapabilityResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_slot(options: RequestOptions = {}): Promise<ListExecutionSlotResponse> {
    const path = "/api/v1/execution-slot";
    return this.request<ListExecutionSlotResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_slot(body: CreateExecutionSlotRequest, options: RequestOptions = {}): Promise<CreateExecutionSlotResponse> {
    const path = "/api/v1/execution-slot";
    return this.request<CreateExecutionSlotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_slot(id: string, options: RequestOptions = {}): Promise<GetExecutionSlotResponse> {
    const path = "/api/v1/execution-slot/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionSlotResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_slot(id: string, body: UpdateExecutionSlotRequest, options: RequestOptions = {}): Promise<UpdateExecutionSlotResponse> {
    const path = "/api/v1/execution-slot/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionSlotResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_model_config(options: RequestOptions = {}): Promise<ListModelConfigResponse> {
    const path = "/api/v1/model-config";
    return this.request<ListModelConfigResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_model_config(body: CreateModelConfigRequest, options: RequestOptions = {}): Promise<CreateModelConfigResponse> {
    const path = "/api/v1/model-config";
    return this.request<CreateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_model_config(id: string, options: RequestOptions = {}): Promise<GetModelConfigResponse> {
    const path = "/api/v1/model-config/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetModelConfigResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_model_config(id: string, body: UpdateModelConfigRequest, options: RequestOptions = {}): Promise<UpdateModelConfigResponse> {
    const path = "/api/v1/model-config/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_prompt_revision(options: RequestOptions = {}): Promise<ListPromptRevisionResponse> {
    const path = "/api/v1/prompt-revision";
    return this.request<ListPromptRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_prompt_revision(body: CreatePromptRevisionRequest, options: RequestOptions = {}): Promise<CreatePromptRevisionResponse> {
    const path = "/api/v1/prompt-revision";
    return this.request<CreatePromptRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_prompt_revision(id: string, options: RequestOptions = {}): Promise<GetPromptRevisionResponse> {
    const path = "/api/v1/prompt-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPromptRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_prompt_revision(id: string, body: UpdatePromptRevisionRequest, options: RequestOptions = {}): Promise<UpdatePromptRevisionResponse> {
    const path = "/api/v1/prompt-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePromptRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_call(options: RequestOptions = {}): Promise<ListAiCallResponse> {
    const path = "/api/v1/ai-call";
    return this.request<ListAiCallResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_ai_call(body: CreateAiCallRequest, options: RequestOptions = {}): Promise<CreateAiCallResponse> {
    const path = "/api/v1/ai-call";
    return this.request<CreateAiCallResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_call(id: string, options: RequestOptions = {}): Promise<GetAiCallResponse> {
    const path = "/api/v1/ai-call/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAiCallResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_ai_call(id: string, body: UpdateAiCallRequest, options: RequestOptions = {}): Promise<UpdateAiCallResponse> {
    const path = "/api/v1/ai-call/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAiCallResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_task(options: RequestOptions = {}): Promise<ListAiTaskResponse> {
    const path = "/api/v1/ai-task";
    return this.request<ListAiTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_ai_task(body: CreateAiTaskRequest, options: RequestOptions = {}): Promise<CreateAiTaskResponse> {
    const path = "/api/v1/ai-task";
    return this.request<CreateAiTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_task(id: string, options: RequestOptions = {}): Promise<GetAiTaskResponse> {
    const path = "/api/v1/ai-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAiTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_ai_task(id: string, body: UpdateAiTaskRequest, options: RequestOptions = {}): Promise<UpdateAiTaskResponse> {
    const path = "/api/v1/ai-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAiTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_report_generation_request(options: RequestOptions = {}): Promise<ListTestReportGenerationRequestResponse> {
    const path = "/api/v1/test-report-generation-request";
    return this.request<ListTestReportGenerationRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_report_generation_request(body: CreateTestReportGenerationRequestRequest, options: RequestOptions = {}): Promise<CreateTestReportGenerationRequestResponse> {
    const path = "/api/v1/test-report-generation-request";
    return this.request<CreateTestReportGenerationRequestResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_report_generation_request(id: string, options: RequestOptions = {}): Promise<GetTestReportGenerationRequestResponse> {
    const path = "/api/v1/test-report-generation-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestReportGenerationRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_report_generation_request(id: string, body: UpdateTestReportGenerationRequestRequest, options: RequestOptions = {}): Promise<UpdateTestReportGenerationRequestResponse> {
    const path = "/api/v1/test-report-generation-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestReportGenerationRequestResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_report(options: RequestOptions = {}): Promise<ListTestReportResponse> {
    const path = "/api/v1/test-report";
    return this.request<ListTestReportResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_report(body: CreateTestReportRequest, options: RequestOptions = {}): Promise<CreateTestReportResponse> {
    const path = "/api/v1/test-report";
    return this.request<CreateTestReportResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_report(id: string, options: RequestOptions = {}): Promise<GetTestReportResponse> {
    const path = "/api/v1/test-report/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestReportResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_report(id: string, body: UpdateTestReportRequest, options: RequestOptions = {}): Promise<UpdateTestReportResponse> {
    const path = "/api/v1/test-report/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestReportResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_artifact(options: RequestOptions = {}): Promise<ListTestArtifactResponse> {
    const path = "/api/v1/test-artifact";
    return this.request<ListTestArtifactResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_artifact(body: CreateTestArtifactRequest, options: RequestOptions = {}): Promise<CreateTestArtifactResponse> {
    const path = "/api/v1/test-artifact";
    return this.request<CreateTestArtifactResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_artifact(id: string, options: RequestOptions = {}): Promise<GetTestArtifactResponse> {
    const path = "/api/v1/test-artifact/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestArtifactResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_artifact(id: string, body: UpdateTestArtifactRequest, options: RequestOptions = {}): Promise<UpdateTestArtifactResponse> {
    const path = "/api/v1/test-artifact/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestArtifactResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_technical_alert(options: RequestOptions = {}): Promise<ListTechnicalAlertResponse> {
    const path = "/api/v1/technical-alert";
    return this.request<ListTechnicalAlertResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_technical_alert(body: CreateTechnicalAlertRequest, options: RequestOptions = {}): Promise<CreateTechnicalAlertResponse> {
    const path = "/api/v1/technical-alert";
    return this.request<CreateTechnicalAlertResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_technical_alert(id: string, options: RequestOptions = {}): Promise<GetTechnicalAlertResponse> {
    const path = "/api/v1/technical-alert/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTechnicalAlertResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_technical_alert(id: string, body: UpdateTechnicalAlertRequest, options: RequestOptions = {}): Promise<UpdateTechnicalAlertResponse> {
    const path = "/api/v1/technical-alert/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTechnicalAlertResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_integration_component(options: RequestOptions = {}): Promise<ListIntegrationComponentResponse> {
    const path = "/api/v1/integration-component";
    return this.request<ListIntegrationComponentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_integration_component(body: CreateIntegrationComponentRequest, options: RequestOptions = {}): Promise<CreateIntegrationComponentResponse> {
    const path = "/api/v1/integration-component";
    return this.request<CreateIntegrationComponentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_integration_component(id: string, options: RequestOptions = {}): Promise<GetIntegrationComponentResponse> {
    const path = "/api/v1/integration-component/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetIntegrationComponentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_integration_component(id: string, body: UpdateIntegrationComponentRequest, options: RequestOptions = {}): Promise<UpdateIntegrationComponentResponse> {
    const path = "/api/v1/integration-component/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateIntegrationComponentResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_system_parameter(options: RequestOptions = {}): Promise<ListSystemParameterResponse> {
    const path = "/api/v1/system-parameter";
    return this.request<ListSystemParameterResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_system_parameter(body: CreateSystemParameterRequest, options: RequestOptions = {}): Promise<CreateSystemParameterResponse> {
    const path = "/api/v1/system-parameter";
    return this.request<CreateSystemParameterResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_system_parameter(id: string, options: RequestOptions = {}): Promise<GetSystemParameterResponse> {
    const path = "/api/v1/system-parameter/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetSystemParameterResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_system_parameter(id: string, body: UpdateSystemParameterRequest, options: RequestOptions = {}): Promise<UpdateSystemParameterResponse> {
    const path = "/api/v1/system-parameter/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateSystemParameterResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_data_dictionary(options: RequestOptions = {}): Promise<ListDataDictionaryResponse> {
    const path = "/api/v1/data-dictionary";
    return this.request<ListDataDictionaryResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_data_dictionary(body: CreateDataDictionaryRequest, options: RequestOptions = {}): Promise<CreateDataDictionaryResponse> {
    const path = "/api/v1/data-dictionary";
    return this.request<CreateDataDictionaryResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_data_dictionary(id: string, options: RequestOptions = {}): Promise<GetDataDictionaryResponse> {
    const path = "/api/v1/data-dictionary/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetDataDictionaryResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_data_dictionary(id: string, body: UpdateDataDictionaryRequest, options: RequestOptions = {}): Promise<UpdateDataDictionaryResponse> {
    const path = "/api/v1/data-dictionary/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateDataDictionaryResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_audit_log(options: RequestOptions = {}): Promise<ListAuditLogResponse> {
    const path = "/api/v1/audit-log";
    return this.request<ListAuditLogResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_audit_log(body: CreateAuditLogRequest, options: RequestOptions = {}): Promise<CreateAuditLogResponse> {
    const path = "/api/v1/audit-log";
    return this.request<CreateAuditLogResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_audit_log(id: string, options: RequestOptions = {}): Promise<GetAuditLogResponse> {
    const path = "/api/v1/audit-log/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAuditLogResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_audit_log(id: string, body: UpdateAuditLogRequest, options: RequestOptions = {}): Promise<UpdateAuditLogResponse> {
    const path = "/api/v1/audit-log/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAuditLogResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_retention_policy(options: RequestOptions = {}): Promise<ListRetentionPolicyResponse> {
    const path = "/api/v1/retention-policy";
    return this.request<ListRetentionPolicyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_retention_policy(body: CreateRetentionPolicyRequest, options: RequestOptions = {}): Promise<CreateRetentionPolicyResponse> {
    const path = "/api/v1/retention-policy";
    return this.request<CreateRetentionPolicyResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_retention_policy(id: string, options: RequestOptions = {}): Promise<GetRetentionPolicyResponse> {
    const path = "/api/v1/retention-policy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRetentionPolicyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_retention_policy(id: string, body: UpdateRetentionPolicyRequest, options: RequestOptions = {}): Promise<UpdateRetentionPolicyResponse> {
    const path = "/api/v1/retention-policy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRetentionPolicyResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_controlled_purge_request(options: RequestOptions = {}): Promise<ListControlledPurgeRequestResponse> {
    const path = "/api/v1/controlled-purge-request";
    return this.request<ListControlledPurgeRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_controlled_purge_request(body: CreateControlledPurgeRequestRequest, options: RequestOptions = {}): Promise<CreateControlledPurgeRequestResponse> {
    const path = "/api/v1/controlled-purge-request";
    return this.request<CreateControlledPurgeRequestResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_controlled_purge_request(id: string, options: RequestOptions = {}): Promise<GetControlledPurgeRequestResponse> {
    const path = "/api/v1/controlled-purge-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetControlledPurgeRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_controlled_purge_request(id: string, body: UpdateControlledPurgeRequestRequest, options: RequestOptions = {}): Promise<UpdateControlledPurgeRequestResponse> {
    const path = "/api/v1/controlled-purge-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateControlledPurgeRequestResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_technical_alert_endpoint(options: RequestOptions = {}): Promise<ListTechnicalAlertEndpointResponse> {
    const path = "/api/v1/technical-alert-endpoint";
    return this.request<ListTechnicalAlertEndpointResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_technical_alert_endpoint(body: CreateTechnicalAlertEndpointRequest, options: RequestOptions = {}): Promise<CreateTechnicalAlertEndpointResponse> {
    const path = "/api/v1/technical-alert-endpoint";
    return this.request<CreateTechnicalAlertEndpointResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_technical_alert_endpoint(id: string, options: RequestOptions = {}): Promise<GetTechnicalAlertEndpointResponse> {
    const path = "/api/v1/technical-alert-endpoint/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTechnicalAlertEndpointResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_technical_alert_endpoint(id: string, body: UpdateTechnicalAlertEndpointRequest, options: RequestOptions = {}): Promise<UpdateTechnicalAlertEndpointResponse> {
    const path = "/api/v1/technical-alert-endpoint/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTechnicalAlertEndpointResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_platform_design_baseline_release(options: RequestOptions = {}): Promise<ListPlatformDesignBaselineReleaseResponse> {
    const path = "/api/v1/platform-design-baseline-release";
    return this.request<ListPlatformDesignBaselineReleaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_platform_design_baseline_release(body: CreatePlatformDesignBaselineReleaseRequest, options: RequestOptions = {}): Promise<CreatePlatformDesignBaselineReleaseResponse> {
    const path = "/api/v1/platform-design-baseline-release";
    return this.request<CreatePlatformDesignBaselineReleaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_platform_design_baseline_release(id: string, options: RequestOptions = {}): Promise<GetPlatformDesignBaselineReleaseResponse> {
    const path = "/api/v1/platform-design-baseline-release/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPlatformDesignBaselineReleaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_platform_design_baseline_release(id: string, body: UpdatePlatformDesignBaselineReleaseRequest, options: RequestOptions = {}): Promise<UpdatePlatformDesignBaselineReleaseResponse> {
    const path = "/api/v1/platform-design-baseline-release/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePlatformDesignBaselineReleaseResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_candidate_revision(options: RequestOptions = {}): Promise<ListAiCandidateRevisionResponse> {
    const path = "/api/v1/ai-candidate-revision";
    return this.request<ListAiCandidateRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_ai_candidate_revision(body: CreateAiCandidateRevisionRequest, options: RequestOptions = {}): Promise<CreateAiCandidateRevisionResponse> {
    const path = "/api/v1/ai-candidate-revision";
    return this.request<CreateAiCandidateRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_candidate_revision(id: string, options: RequestOptions = {}): Promise<GetAiCandidateRevisionResponse> {
    const path = "/api/v1/ai-candidate-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAiCandidateRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_ai_candidate_revision(id: string, body: UpdateAiCandidateRevisionRequest, options: RequestOptions = {}): Promise<UpdateAiCandidateRevisionResponse> {
    const path = "/api/v1/ai-candidate-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAiCandidateRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_technical_alert_ingestion_batch(options: RequestOptions = {}): Promise<ListTechnicalAlertIngestionBatchResponse> {
    const path = "/api/v1/technical-alert-ingestion-batch";
    return this.request<ListTechnicalAlertIngestionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_technical_alert_ingestion_batch(body: CreateTechnicalAlertIngestionBatchRequest, options: RequestOptions = {}): Promise<CreateTechnicalAlertIngestionBatchResponse> {
    const path = "/api/v1/technical-alert-ingestion-batch";
    return this.request<CreateTechnicalAlertIngestionBatchResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_technical_alert_ingestion_batch(id: string, options: RequestOptions = {}): Promise<GetTechnicalAlertIngestionBatchResponse> {
    const path = "/api/v1/technical-alert-ingestion-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTechnicalAlertIngestionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_technical_alert_ingestion_batch(id: string, body: UpdateTechnicalAlertIngestionBatchRequest, options: RequestOptions = {}): Promise<UpdateTechnicalAlertIngestionBatchResponse> {
    const path = "/api/v1/technical-alert-ingestion-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTechnicalAlertIngestionBatchResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_batch(options: RequestOptions = {}): Promise<ListExecutionBatchResponse> {
    const path = "/api/v1/execution-batch";
    return this.request<ListExecutionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_batch(body: CreateExecutionBatchRequest, options: RequestOptions = {}): Promise<CreateExecutionBatchResponse> {
    const path = "/api/v1/execution-batch";
    return this.request<CreateExecutionBatchResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_batch(id: string, options: RequestOptions = {}): Promise<GetExecutionBatchResponse> {
    const path = "/api/v1/execution-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_batch(id: string, body: UpdateExecutionBatchRequest, options: RequestOptions = {}): Promise<UpdateExecutionBatchResponse> {
    const path = "/api/v1/execution-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionBatchResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_project_execution_configuration(options: RequestOptions = {}): Promise<ListProjectExecutionConfigurationResponse> {
    const path = "/api/v1/project-execution-configuration";
    return this.request<ListProjectExecutionConfigurationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_project_execution_configuration(body: CreateProjectExecutionConfigurationRequest, options: RequestOptions = {}): Promise<CreateProjectExecutionConfigurationResponse> {
    const path = "/api/v1/project-execution-configuration";
    return this.request<CreateProjectExecutionConfigurationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_project_execution_configuration(id: string, options: RequestOptions = {}): Promise<GetProjectExecutionConfigurationResponse> {
    const path = "/api/v1/project-execution-configuration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetProjectExecutionConfigurationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_project_execution_configuration(id: string, body: UpdateProjectExecutionConfigurationRequest, options: RequestOptions = {}): Promise<UpdateProjectExecutionConfigurationResponse> {
    const path = "/api/v1/project-execution-configuration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectExecutionConfigurationResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_execution(body: CreateExecutionRequest, options: RequestOptions = {}): Promise<CreateExecutionResponse> {
    const path = "/api/v1/executions";
    return this.request<CreateExecutionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async cancel_execution(id: string, body: CancelExecutionRequest, options: RequestOptions = {}): Promise<CancelExecutionResponse> {
    const path = "/api/v1/executions/{id}/cancel".replace('{id}', encodeURIComponent(id));
    return this.request<CancelExecutionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async terminate_execution(id: string, body: TerminateExecutionRequest, options: RequestOptions = {}): Promise<TerminateExecutionResponse> {
    const path = "/api/v1/executions/{id}/terminate".replace('{id}', encodeURIComponent(id));
    return this.request<TerminateExecutionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async register_runner(body: RegisterRunnerRequest, options: RequestOptions = {}): Promise<RegisterRunnerResponse> {
    const path = "/api/v1/runners/register";
    return this.request<RegisterRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async heartbeat_runner(id: string, body: HeartbeatRunnerRequest, options: RequestOptions = {}): Promise<HeartbeatRunnerResponse> {
    const path = "/api/v1/runners/{id}/heartbeat".replace('{id}', encodeURIComponent(id));
    return this.request<HeartbeatRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async claim_runner_task(id: string, body: ClaimRunnerTaskRequest, options: RequestOptions = {}): Promise<ClaimRunnerTaskResponse> {
    const path = "/api/v1/runners/{id}/claim".replace('{id}', encodeURIComponent(id));
    return this.request<ClaimRunnerTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async renew_runner_lease(id: string, body: RenewRunnerLeaseRequest, options: RequestOptions = {}): Promise<RenewRunnerLeaseResponse> {
    const path = "/api/v1/runners/{id}/renew".replace('{id}', encodeURIComponent(id));
    return this.request<RenewRunnerLeaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async report_runner_progress(id: string, body: ReportRunnerProgressRequest, options: RequestOptions = {}): Promise<ReportRunnerProgressResponse> {
    const path = "/api/v1/runners/{id}/progress".replace('{id}', encodeURIComponent(id));
    return this.request<ReportRunnerProgressResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async report_runner_result(id: string, body: ReportRunnerResultRequest, options: RequestOptions = {}): Promise<ReportRunnerResultResponse> {
    const path = "/api/v1/runners/{id}/result".replace('{id}', encodeURIComponent(id));
    return this.request<ReportRunnerResultResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async convert_natural_language_case(id: string, body: ConvertNaturalLanguageCaseRequest, options: RequestOptions = {}): Promise<ConvertNaturalLanguageCaseResponse> {
    const path = "/api/v1/natural-language-cases/{id}/convert".replace('{id}', encodeURIComponent(id));
    return this.request<ConvertNaturalLanguageCaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_ai_exploration(body: CreateAiExplorationRequest, options: RequestOptions = {}): Promise<CreateAiExplorationResponse> {
    const path = "/api/v1/ai-explorations";
    return this.request<CreateAiExplorationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_manual_recording(body: CreateManualRecordingRequest, options: RequestOptions = {}): Promise<CreateManualRecordingResponse> {
    const path = "/api/v1/manual-recordings";
    return this.request<CreateManualRecordingResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async save_recording_draft_and_stop(id: string, body: SaveRecordingDraftAndStopRequest, options: RequestOptions = {}): Promise<SaveRecordingDraftAndStopResponse> {
    const path = "/api/v1/manual-recordings/{id}/save-draft-and-stop".replace('{id}', encodeURIComponent(id));
    return this.request<SaveRecordingDraftAndStopResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_report(id: string, options: RequestOptions = {}): Promise<GetReportResponse> {
    const path = "/api/v1/reports/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetReportResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async export_report(id: string, body: ExportReportRequest, options: RequestOptions = {}): Promise<ExportReportResponse> {
    const path = "/api/v1/reports/{id}/export".replace('{id}', encodeURIComponent(id));
    return this.request<ExportReportResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_report_share(id: string, body: CreateReportShareRequest, options: RequestOptions = {}): Promise<CreateReportShareResponse> {
    const path = "/api/v1/reports/{id}/shares".replace('{id}', encodeURIComponent(id));
    return this.request<CreateReportShareResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async download_artifact(id: string, options: RequestOptions = {}): Promise<DownloadArtifactResponse> {
    const path = "/api/v1/artifacts/{id}/download".replace('{id}', encodeURIComponent(id));
    return this.request<DownloadArtifactResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_artifact_upload_session(body: CreateArtifactUploadSessionRequest, options: RequestOptions = {}): Promise<CreateArtifactUploadSessionResponse> {
    const path = "/api/v1/artifact-upload-sessions";
    return this.request<CreateArtifactUploadSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async complete_artifact_upload(id: string, body: CompleteArtifactUploadRequest, options: RequestOptions = {}): Promise<CompleteArtifactUploadResponse> {
    const path = "/api/v1/artifact-upload-sessions/{id}/complete".replace('{id}', encodeURIComponent(id));
    return this.request<CompleteArtifactUploadResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_recovery_items(options: RequestOptions = {}): Promise<ListRecoveryItemsResponse> {
    const path = "/api/v1/recovery-center";
    return this.request<ListRecoveryItemsResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_external_trigger(body: CreateExternalTriggerRequest, options: RequestOptions = {}): Promise<CreateExternalTriggerResponse> {
    const path = "/api/v1/external-triggers";
    return this.request<CreateExternalTriggerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
}
