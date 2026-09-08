/* Generated from current docs/authority OpenAPI. DO NOT EDIT. */
import type { LoginRequest, AuthCookieActionRequest, ChangePasswordRequest, CurrentUserResource, AuthenticationTokenResource, AuthenticationResponse, CurrentUserResponse, AuthenticationErrorCode, AuthenticationProblemDetails, ProblemDetails, PageMeta, UserResource, AdminResource, RoleResource, EntitySuperAdminRoleResource, PermissionCodeResource, ProjectResource, ProjectOwnerResource, ProjectMemberResource, EnvironmentResource, BusinessModuleResource, BusinessTerminalResource, EnvironmentTerminalAccessRevisionResource, TestAccountTerminalResource, TestAccountResource, CredentialRevisionResource, AccountMappingRevisionResource, SsoIdentityResource, LoginQualificationResource, TestDataTypeResource, TestDataResourceResource, DataOperationTaskResource, NaturalLanguageCaseResource, StandardCaseResource, CaseVersionResource, CaseSuiteResource, BusinessFlowTemplateResource, CrossTerminalOrchestrationResource, PageExplorationResource, ManualRecordingTaskResource, ManualRecordingSessionResource, ManualRecordingControlLeaseResource, RecordingEvidenceBundleResource, RunTaskResource, ExecutionAttemptResource, CaseAttemptResource, ExecutionPlanResource, ExecutionPlanRevisionResource, TriggerRuleResource, ExecutionLockResource, LeaseResource, AutomationAssetResource, LocalStoragePreset, LoginStrategyResource, PageObjectResource, ActionAssetResource, AssertionAssetResource, RunnerCapabilityResource, ValidateRunnerCapabilityRequest, RunnerResource, ExecutionSlotResource, ContextVariableResource, ModelConfigResource, ModelProviderCode, PromptRevisionResource, AiCallResource, AiTaskResource, AiResultResource, HumanDecisionResource, TestReportGenerationRequestResource, TestReportResource, TestArtifactResource, TechnicalAlertResource, IntegrationComponentResource, SystemParameterResource, DataDictionaryResource, ConfigurationSnapshotResource, AuditLogResource, RetentionPolicyResource, LegalHoldResource, ControlledPurgeRequestResource, TechnicalAlertEndpointResource, AiCandidateRevisionResource, RoleBindingResource, TechnicalAlertIngestionBatchResource, RunnerAgentResource, ExecutionBatchResource, CaseStepResource, CaseSuiteItemResource, ExecutionContextResource, ProjectExecutionConfigurationResource, ListUserResponse, CreateUserRequest, CreateUserResponse, GetUserResponse, UpdateUserRequest, UpdateUserResponse, DataScopeGrantInput, UserRoleBindingAssignmentInput, OneTimeCredentialDeliveryResource, OneTimeCredentialDeliveryResponse, ResetUserCredentialRequest, UserStateCommandRequest, CreateUserRoleBindingRequest, RevokeUserRoleBindingRequest, UserRoleBindingResource, UserRoleBindingResponse, ListRoleResponse, CreateRoleRequest, CreateRoleResponse, GetRoleResponse, UpdateRoleRequest, UpdateRoleResponse, ListProjectResponse, CreateProjectRequest, CreateProjectResponse, GetProjectResponse, UpdateProjectRequest, ProjectLifecycleRequest, UpdateProjectResponse, ListEnvironmentResponse, CreateEnvironmentRequest, CreateEnvironmentResponse, GetEnvironmentResponse, UpdateEnvironmentRequest, UpdateEnvironmentResponse, ListBusinessTerminalResponse, LifecycleCommandRequest, PublishTerminalAccessRevisionRequest, CreateBusinessTerminalRequest, CreateBusinessTerminalResponse, GetBusinessTerminalResponse, UpdateBusinessTerminalRequest, UpdateBusinessTerminalResponse, ListEnvironmentTerminalAccessRevisionResponse, CreateEnvironmentTerminalAccessRevisionRequest, CreateEnvironmentTerminalAccessRevisionResponse, UpdateEnvironmentTerminalAccessRevisionRequest, GetEnvironmentTerminalAccessRevisionResponse, UpdateEnvironmentTerminalAccessRevisionResponse, ListTestAccountResponse, CreateTestAccountRequest, CreateTestAccountResponse, GetTestAccountResponse, UpdateTestAccountRequest, RotateTestAccountSecretRequest, TestAccountLifecycleRequest, UpdateTestAccountResponse, ListCredentialRevisionResponse, CreateCredentialRevisionRequest, CreateCredentialRevisionResponse, GetCredentialRevisionResponse, UpdateCredentialRevisionRequest, UpdateCredentialRevisionResponse, ListAccountMappingRevisionResponse, CreateAccountMappingRevisionRequest, CreateAccountMappingRevisionResponse, GetAccountMappingRevisionResponse, UpdateAccountMappingRevisionRequest, UpdateAccountMappingRevisionResponse, ListTestDataTypeResponse, CreateTestDataTypeRequest, CreateTestDataTypeResponse, GetTestDataTypeResponse, UpdateTestDataTypeRequest, UpdateTestDataTypeResponse, ListTestDataResourceResponse, CreateTestDataResourceRequest, CreateTestDataResourceResponse, GetTestDataResourceResponse, UpdateTestDataResourceRequest, UpdateTestDataResourceResponse, ListDataOperationTaskResponse, CreateDataOperationTaskRequest, CreateDataOperationTaskResponse, GetDataOperationTaskResponse, UpdateDataOperationTaskRequest, UpdateDataOperationTaskResponse, ListNaturalLanguageCaseResponse, CreateNaturalLanguageCaseRequest, CreateNaturalLanguageCaseResponse, GetNaturalLanguageCaseResponse, UpdateNaturalLanguageCaseRequest, UpdateNaturalLanguageCaseResponse, ListStandardCaseResponse, CreateStandardCaseRequest, CreateStandardCaseResponse, GetStandardCaseResponse, UpdateStandardCaseRequest, UpdateStandardCaseResponse, ListCaseVersionResponse, CreateCaseVersionRequest, CreateCaseVersionResponse, GetCaseVersionResponse, UpdateCaseVersionRequest, UpdateCaseVersionResponse, ListCaseSuiteResponse, CreateCaseSuiteRequest, CreateCaseSuiteResponse, GetCaseSuiteResponse, UpdateCaseSuiteRequest, UpdateCaseSuiteResponse, ListBusinessFlowTemplateResponse, CreateBusinessFlowTemplateRequest, CreateBusinessFlowTemplateResponse, GetBusinessFlowTemplateResponse, UpdateBusinessFlowTemplateRequest, UpdateBusinessFlowTemplateResponse, ListPageExplorationResponse, CreatePageExplorationRequest, CreatePageExplorationResponse, GetPageExplorationResponse, UpdatePageExplorationRequest, UpdatePageExplorationResponse, ListManualRecordingTaskResponse, CreateManualRecordingTaskRequest, CreateManualRecordingTaskResponse, GetManualRecordingTaskResponse, UpdateManualRecordingTaskRequest, UpdateManualRecordingTaskResponse, ListManualRecordingSessionResponse, CreateManualRecordingSessionRequest, CreateManualRecordingSessionResponse, GetManualRecordingSessionResponse, UpdateManualRecordingSessionRequest, UpdateManualRecordingSessionResponse, ListRecordingEvidenceBundleResponse, CreateRecordingEvidenceBundleRequest, CreateRecordingEvidenceBundleResponse, GetRecordingEvidenceBundleResponse, UpdateRecordingEvidenceBundleRequest, UpdateRecordingEvidenceBundleResponse, ListRunTaskResponse, CreateRunTaskRequest, CreateRunTaskResponse, GetRunTaskResponse, UpdateRunTaskRequest, UpdateRunTaskResponse, ListExecutionAttemptResponse, CreateExecutionAttemptRequest, CreateExecutionAttemptResponse, GetExecutionAttemptResponse, UpdateExecutionAttemptRequest, UpdateExecutionAttemptResponse, ListCaseAttemptResponse, CreateCaseAttemptRequest, CreateCaseAttemptResponse, GetCaseAttemptResponse, UpdateCaseAttemptRequest, UpdateCaseAttemptResponse, ListExecutionPlanResponse, CreateExecutionPlanRequest, CreateExecutionPlanResponse, GetExecutionPlanResponse, UpdateExecutionPlanRequest, UpdateExecutionPlanResponse, ListExecutionPlanRevisionResponse, CreateExecutionPlanRevisionRequest, CreateExecutionPlanRevisionResponse, GetExecutionPlanRevisionResponse, UpdateExecutionPlanRevisionRequest, UpdateExecutionPlanRevisionResponse, ListTriggerRuleResponse, CreateTriggerRuleRequest, CreateTriggerRuleResponse, GetTriggerRuleResponse, UpdateTriggerRuleRequest, UpdateTriggerRuleResponse, ListLeaseResponse, CreateLeaseRequest, CreateLeaseResponse, GetLeaseResponse, UpdateLeaseRequest, UpdateLeaseResponse, ListAutomationAssetResponse, CreateAutomationAssetRequest, CreateAutomationAssetResponse, GetAutomationAssetResponse, UpdateAutomationAssetRequest, UpdateAutomationAssetResponse, ListLoginStrategyResponse, CreateLoginStrategyRequest, CreateLoginStrategyResponse, GetLoginStrategyResponse, UpdateLoginStrategyRequest, UpdateLoginStrategyResponse, ListPageObjectResponse, CreatePageObjectRequest, CreatePageObjectResponse, GetPageObjectResponse, UpdatePageObjectRequest, UpdatePageObjectResponse, ListActionAssetResponse, CreateActionAssetRequest, CreateActionAssetResponse, GetActionAssetResponse, UpdateActionAssetRequest, UpdateActionAssetResponse, ListAssertionAssetResponse, CreateAssertionAssetRequest, CreateAssertionAssetResponse, GetAssertionAssetResponse, UpdateAssertionAssetRequest, UpdateAssertionAssetResponse, ListRunnerResponse, CreateRunnerEnrollmentRequest, RunnerEnrollmentIssuedResource, CreateRunnerEnrollmentResponse, GetRunnerResponse, UpdateRunnerRequest, RunnerLifecycleRequest, RotateRunnerAgentTokenData, RotateRunnerAgentTokenResponse, ListExecutionSlotResponse, CreateExecutionSlotRequest, CreateExecutionSlotResponse, GetExecutionSlotResponse, UpdateExecutionSlotRequest, UpdateExecutionSlotResponse, ListModelConfigResponse, CreateModelConfigRequest, CreateModelConfigResponse, GetModelConfigResponse, UpdateModelConfigRequest, UpdateModelConfigResponse, ModelConfigLifecycleRequest, TestModelConfigConnectionRequest, ModelConnectionTestResult, TestModelConfigConnectionResponse, CapabilityDefaultResource, SetCapabilityDefaultModelRequest, SetCapabilityDefaultModelResponse, ClearCapabilityDefaultModelRequest, ClearCapabilityDefaultResult, ClearCapabilityDefaultModelResponse, ListPromptRevisionResponse, CreatePromptRevisionRequest, CreatePromptRevisionResponse, GetPromptRevisionResponse, UpdatePromptRevisionRequest, UpdatePromptRevisionResponse, ListAiCallResponse, CreateAiCallRequest, CreateAiCallResponse, GetAiCallResponse, UpdateAiCallRequest, UpdateAiCallResponse, ListAiTaskResponse, CreateAiTaskRequest, CreateAiTaskResponse, GetAiTaskResponse, UpdateAiTaskRequest, UpdateAiTaskResponse, ListTestReportGenerationRequestResponse, CreateTestReportGenerationRequestRequest, CreateTestReportGenerationRequestResponse, GetTestReportGenerationRequestResponse, UpdateTestReportGenerationRequestRequest, UpdateTestReportGenerationRequestResponse, ListTestReportResponse, CreateTestReportRequest, CreateTestReportResponse, GetTestReportResponse, UpdateTestReportRequest, UpdateTestReportResponse, ListTestArtifactResponse, CreateTestArtifactRequest, CreateTestArtifactResponse, GetTestArtifactResponse, UpdateTestArtifactRequest, UpdateTestArtifactResponse, ListTechnicalAlertResponse, CreateTechnicalAlertRequest, CreateTechnicalAlertResponse, GetTechnicalAlertResponse, UpdateTechnicalAlertRequest, UpdateTechnicalAlertResponse, ListIntegrationComponentResponse, CreateIntegrationComponentRequest, CreateIntegrationComponentResponse, GetIntegrationComponentResponse, UpdateIntegrationComponentRequest, UpdateIntegrationComponentResponse, ListSystemParameterResponse, CreateSystemParameterRequest, CreateSystemParameterResponse, GetSystemParameterResponse, UpdateSystemParameterRequest, UpdateSystemParameterResponse, ListDataDictionaryResponse, CreateDataDictionaryRequest, CreateDataDictionaryResponse, GetDataDictionaryResponse, UpdateDataDictionaryRequest, UpdateDataDictionaryResponse, ListAuditLogResponse, CreateAuditLogRequest, CreateAuditLogResponse, GetAuditLogResponse, UpdateAuditLogRequest, UpdateAuditLogResponse, ListRetentionPolicyResponse, CreateRetentionPolicyRequest, CreateRetentionPolicyResponse, GetRetentionPolicyResponse, UpdateRetentionPolicyRequest, UpdateRetentionPolicyResponse, ListControlledPurgeRequestResponse, CreateControlledPurgeRequestRequest, CreateControlledPurgeRequestResponse, GetControlledPurgeRequestResponse, UpdateControlledPurgeRequestRequest, UpdateControlledPurgeRequestResponse, ListTechnicalAlertEndpointResponse, CreateTechnicalAlertEndpointRequest, CreateTechnicalAlertEndpointResponse, GetTechnicalAlertEndpointResponse, UpdateTechnicalAlertEndpointRequest, UpdateTechnicalAlertEndpointResponse, ListAiCandidateRevisionResponse, CreateAiCandidateRevisionRequest, CreateAiCandidateRevisionResponse, GetAiCandidateRevisionResponse, UpdateAiCandidateRevisionRequest, UpdateAiCandidateRevisionResponse, ListTechnicalAlertIngestionBatchResponse, CreateTechnicalAlertIngestionBatchRequest, CreateTechnicalAlertIngestionBatchResponse, GetTechnicalAlertIngestionBatchResponse, UpdateTechnicalAlertIngestionBatchRequest, UpdateTechnicalAlertIngestionBatchResponse, ListExecutionBatchResponse, CreateExecutionBatchRequest, CreateExecutionBatchResponse, GetExecutionBatchResponse, UpdateExecutionBatchRequest, UpdateExecutionBatchResponse, ListProjectExecutionConfigurationResponse, CreateProjectExecutionConfigurationRequest, CreateProjectExecutionConfigurationResponse, GetProjectExecutionConfigurationResponse, UpdateProjectExecutionConfigurationRequest, UpdateProjectExecutionConfigurationResponse, GenericOperationResource, CreateExecutionRequest, CreateExecutionResponse, CancelExecutionRequest, CancelExecutionResponse, TerminateExecutionRequest, TerminateExecutionResponse, RunnerCapabilityReportItem, RegisterRunnerRequest, RegisterRunnerData, RegisterRunnerResponse, HeartbeatRunnerRequest, ReportRunnerCapabilitiesRequest, HeartbeatRunnerResponse, ClaimRunnerTaskRequest, ClaimRunnerTaskResponse, RenewRunnerLeaseRequest, RenewRunnerLeaseResponse, ReportRunnerProgressRequest, ReportRunnerProgressResponse, ReportRunnerResultRequest, ReportRunnerResultResponse, ConvertNaturalLanguageCaseRequest, ConvertNaturalLanguageCaseResponse, CreateAiExplorationRequest, CreateAiExplorationResponse, AIExplorationPlanStep, AIExplorationPlan, AIExplorationSessionResource, StartAIExplorationSessionRequest, CancelAIExplorationSessionRequest, AIExplorationBrowserAction, AIExplorationStepResource, AIExplorationSessionResponse, AIExplorationStepListResponse, CreateAiExplorationSessionRequest, CreateAiExplorationSessionResponse, CreateManualRecordingRequest, CreateManualRecordingResponse, SaveRecordingDraftAndStopRequest, SaveRecordingDraftAndStopResponse, GetReportResponse, ExportReportRequest, ExportReportResponse, CreateReportShareRequest, CreateReportShareResponse, DownloadArtifactResponse, CreateArtifactUploadSessionRequest, CreateArtifactUploadSessionResponse, CompleteArtifactUploadRequest, CompleteArtifactUploadResponse, ListRecoveryItemsResponse, CreateExternalTriggerRequest, CreateExternalTriggerResponse, ExecutionBindingInput, ExecutionBindingPreflightCheck, ExecutionBindingPreflightResult, ExecutionBindingPreflightResponse, ExecutionBindingCommandRequest, ExecutionBindingRecoverRequest, ResourceLeaseResource, RuntimePolicySnapshot, ExecutionBindingSnapshotResource, ExecutionBindingSnapshotResponse, ExecutionBindingSnapshotListResponse, RuntimePolicyRevisionResource, CreateRuntimePolicyRevisionRequest, RuntimePolicyRevisionResponse, RuntimePolicyRevisionListResponse } from './types.js';
export type RequestOptions = { headers?: Record<string,string>; signal?: AbortSignal };
export type QueryRequestOptions<Q extends Record<string, unknown>> = RequestOptions & { query?: Q };
export type RequiredHeaderOptions<K extends string> = Omit<RequestOptions, 'headers'> & { headers: Record<string,string> & Record<K,string> };
export type RequiredHeaderQueryOptions<K extends string, Q extends Record<string, unknown>> = RequiredHeaderOptions<K> & { query?: Q };
export class ApiClient {
  constructor(private readonly baseUrl: string, private readonly fetcher: typeof fetch = fetch) {}
  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, init);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }
  async login_platform_user(body: LoginRequest, options: RequestOptions = {}): Promise<AuthenticationResponse> {
    let path = "/api/v1/auth/login";
    return this.request<AuthenticationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async refresh_platform_session(body?: AuthCookieActionRequest, options: RequestOptions = {}): Promise<AuthenticationResponse> {
    let path = "/api/v1/auth/refresh";
    return this.request<AuthenticationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  }
  async logout_platform_user(body?: AuthCookieActionRequest, options: RequestOptions = {}): Promise<void> {
    let path = "/api/v1/auth/logout";
    return this.request<void>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  }
  async get_current_user(options: RequestOptions = {}): Promise<CurrentUserResponse> {
    let path = "/api/v1/auth/me";
    return this.request<CurrentUserResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async change_current_user_password(body: ChangePasswordRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<void> {
    let path = "/api/v1/auth/change-password";
    return this.request<void>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_user(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListUserResponse> {
    let path = "/api/v1/user";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListUserResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_user(body: CreateUserRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateUserResponse> {
    let path = "/api/v1/user";
    return this.request<CreateUserResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_user(id: string, options: RequestOptions = {}): Promise<GetUserResponse> {
    let path = "/api/v1/user/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetUserResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_user(id: string, body: UpdateUserRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateUserResponse> {
    let path = "/api/v1/user/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateUserResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async reset_user_credential(id: string, body: ResetUserCredentialRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<OneTimeCredentialDeliveryResponse> {
    let path = "/api/v1/user/{id}/credential-reset".replace('{id}', encodeURIComponent(id));
    return this.request<OneTimeCredentialDeliveryResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async enable_user(id: string, body: UserStateCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateUserResponse> {
    let path = "/api/v1/user/{id}/enable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateUserResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async disable_user(id: string, body: UserStateCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateUserResponse> {
    let path = "/api/v1/user/{id}/disable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateUserResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_user_role_binding(body: CreateUserRoleBindingRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UserRoleBindingResponse> {
    let path = "/api/v1/user-role-binding";
    return this.request<UserRoleBindingResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async revoke_user_role_binding(id: string, body: RevokeUserRoleBindingRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UserRoleBindingResponse> {
    let path = "/api/v1/user-role-binding/{id}/revoke".replace('{id}', encodeURIComponent(id));
    return this.request<UserRoleBindingResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_role(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListRoleResponse> {
    let path = "/api/v1/role";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListRoleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_role(body: CreateRoleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateRoleResponse> {
    let path = "/api/v1/role";
    return this.request<CreateRoleResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_role(id: string, options: RequestOptions = {}): Promise<GetRoleResponse> {
    let path = "/api/v1/role/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRoleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_role(id: string, body: UpdateRoleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateRoleResponse> {
    let path = "/api/v1/role/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRoleResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_project(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListProjectResponse> {
    let path = "/api/v1/project";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListProjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_project(body: CreateProjectRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateProjectResponse> {
    let path = "/api/v1/project";
    return this.request<CreateProjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_project(id: string, options: RequestOptions = {}): Promise<GetProjectResponse> {
    let path = "/api/v1/project/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetProjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_project(id: string, body: UpdateProjectRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateProjectResponse> {
    let path = "/api/v1/project/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async disable_project(id: string, body: ProjectLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateProjectResponse> {
    let path = "/api/v1/project/{id}/disable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async recover_project(id: string, body: ProjectLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateProjectResponse> {
    let path = "/api/v1/project/{id}/recover".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async archive_project(id: string, body: ProjectLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateProjectResponse> {
    let path = "/api/v1/project/{id}/archive".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_environment(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListEnvironmentResponse> {
    let path = "/api/v1/environment";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListEnvironmentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_environment(body: CreateEnvironmentRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateEnvironmentResponse> {
    let path = "/api/v1/environment";
    return this.request<CreateEnvironmentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_environment(id: string, options: RequestOptions = {}): Promise<GetEnvironmentResponse> {
    let path = "/api/v1/environment/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetEnvironmentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_environment(id: string, body: UpdateEnvironmentRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentResponse> {
    let path = "/api/v1/environment/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async validate_environment(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentResponse> {
    let path = "/api/v1/environment/{id}/validate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async reconfigure_environment(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentResponse> {
    let path = "/api/v1/environment/{id}/reconfigure".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async activate_environment(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentResponse> {
    let path = "/api/v1/environment/{id}/activate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_business_terminal(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListBusinessTerminalResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_business_terminal(body: CreateBusinessTerminalRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal";
    return this.request<CreateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_business_terminal(id: string, options: RequestOptions = {}): Promise<GetBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetBusinessTerminalResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_business_terminal(id: string, body: UpdateBusinessTerminalRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async validate_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/validate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async reconfigure_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/reconfigure".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async activate_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/activate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async mark_unreachable_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/mark-unreachable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async recover_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/recover".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async disable_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/disable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async archive_business_terminal(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessTerminalResponse> {
    let path = "/api/v1/business-terminal/{id}/archive".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessTerminalResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async activate_login_strategy(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateLoginStrategyResponse> {
    let path = "/api/v1/login-strategy/{id}/activate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateLoginStrategyResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async validate_environment_terminal_access_revision(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision/{id}/validate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async return_to_draft_environment_terminal_access_revision(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision/{id}/return-to-draft".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async abandon_environment_terminal_access_revision(id: string, body: LifecycleCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision/{id}/abandon".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async publish_environment_terminal_access_revision(id: string, body: PublishTerminalAccessRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision/{id}/publish".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_environment_terminal_access_revision(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListEnvironmentTerminalAccessRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_environment_terminal_access_revision(body: CreateEnvironmentTerminalAccessRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision";
    return this.request<CreateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_environment_terminal_access_revision(id: string, options: RequestOptions = {}): Promise<GetEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetEnvironmentTerminalAccessRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_environment_terminal_access_revision(id: string, body: UpdateEnvironmentTerminalAccessRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateEnvironmentTerminalAccessRevisionResponse> {
    let path = "/api/v1/environment-terminal-access-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateEnvironmentTerminalAccessRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_account(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTestAccountResponse> {
    let path = "/api/v1/test-account";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTestAccountResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_account(body: CreateTestAccountRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTestAccountResponse> {
    let path = "/api/v1/test-account";
    return this.request<CreateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_account(id: string, options: RequestOptions = {}): Promise<GetTestAccountResponse> {
    let path = "/api/v1/test-account/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestAccountResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_account(id: string, body: UpdateTestAccountRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async rotate_test_account_secret(id: string, body: RotateTestAccountSecretRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/credential-rotate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async validate_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/validate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async reconfigure_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/reconfigure".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async activate_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/activate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async mark_credential_expired_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/mark-credential-expired".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async recover_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/recover".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async disable_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/disable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async archive_test_account(id: string, body: TestAccountLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestAccountResponse> {
    let path = "/api/v1/test-account/{id}/archive".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestAccountResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_credential_revision(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListCredentialRevisionResponse> {
    let path = "/api/v1/credential-revision";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListCredentialRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_credential_revision(body: CreateCredentialRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateCredentialRevisionResponse> {
    let path = "/api/v1/credential-revision";
    return this.request<CreateCredentialRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_credential_revision(id: string, options: RequestOptions = {}): Promise<GetCredentialRevisionResponse> {
    let path = "/api/v1/credential-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCredentialRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_credential_revision(id: string, body: UpdateCredentialRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateCredentialRevisionResponse> {
    let path = "/api/v1/credential-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCredentialRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_account_mapping_revision(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAccountMappingRevisionResponse> {
    let path = "/api/v1/account-mapping-revision";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAccountMappingRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_account_mapping_revision(body: CreateAccountMappingRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAccountMappingRevisionResponse> {
    let path = "/api/v1/account-mapping-revision";
    return this.request<CreateAccountMappingRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_account_mapping_revision(id: string, options: RequestOptions = {}): Promise<GetAccountMappingRevisionResponse> {
    let path = "/api/v1/account-mapping-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAccountMappingRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_account_mapping_revision(id: string, body: UpdateAccountMappingRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAccountMappingRevisionResponse> {
    let path = "/api/v1/account-mapping-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAccountMappingRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_data_type(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTestDataTypeResponse> {
    let path = "/api/v1/test-data-type";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTestDataTypeResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_data_type(body: CreateTestDataTypeRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTestDataTypeResponse> {
    let path = "/api/v1/test-data-type";
    return this.request<CreateTestDataTypeResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_data_type(id: string, options: RequestOptions = {}): Promise<GetTestDataTypeResponse> {
    let path = "/api/v1/test-data-type/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestDataTypeResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_data_type(id: string, body: UpdateTestDataTypeRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestDataTypeResponse> {
    let path = "/api/v1/test-data-type/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestDataTypeResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_data_resource(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTestDataResourceResponse> {
    let path = "/api/v1/test-data-resource";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTestDataResourceResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_data_resource(body: CreateTestDataResourceRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTestDataResourceResponse> {
    let path = "/api/v1/test-data-resource";
    return this.request<CreateTestDataResourceResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_data_resource(id: string, options: RequestOptions = {}): Promise<GetTestDataResourceResponse> {
    let path = "/api/v1/test-data-resource/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestDataResourceResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_data_resource(id: string, body: UpdateTestDataResourceRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestDataResourceResponse> {
    let path = "/api/v1/test-data-resource/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestDataResourceResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_data_operation_task(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListDataOperationTaskResponse> {
    let path = "/api/v1/data-operation-task";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListDataOperationTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_data_operation_task(body: CreateDataOperationTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateDataOperationTaskResponse> {
    let path = "/api/v1/data-operation-task";
    return this.request<CreateDataOperationTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_data_operation_task(id: string, options: RequestOptions = {}): Promise<GetDataOperationTaskResponse> {
    let path = "/api/v1/data-operation-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetDataOperationTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_data_operation_task(id: string, body: UpdateDataOperationTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateDataOperationTaskResponse> {
    let path = "/api/v1/data-operation-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateDataOperationTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_natural_language_case(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListNaturalLanguageCaseResponse> {
    let path = "/api/v1/natural-language-case";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListNaturalLanguageCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_natural_language_case(body: CreateNaturalLanguageCaseRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateNaturalLanguageCaseResponse> {
    let path = "/api/v1/natural-language-case";
    return this.request<CreateNaturalLanguageCaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_natural_language_case(id: string, options: RequestOptions = {}): Promise<GetNaturalLanguageCaseResponse> {
    let path = "/api/v1/natural-language-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetNaturalLanguageCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_natural_language_case(id: string, body: UpdateNaturalLanguageCaseRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateNaturalLanguageCaseResponse> {
    let path = "/api/v1/natural-language-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateNaturalLanguageCaseResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_standard_case(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListStandardCaseResponse> {
    let path = "/api/v1/standard-case";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListStandardCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_standard_case(body: CreateStandardCaseRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateStandardCaseResponse> {
    let path = "/api/v1/standard-case";
    return this.request<CreateStandardCaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_standard_case(id: string, options: RequestOptions = {}): Promise<GetStandardCaseResponse> {
    let path = "/api/v1/standard-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetStandardCaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_standard_case(id: string, body: UpdateStandardCaseRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateStandardCaseResponse> {
    let path = "/api/v1/standard-case/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateStandardCaseResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_case_version(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListCaseVersionResponse> {
    let path = "/api/v1/case-version";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListCaseVersionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_case_version(body: CreateCaseVersionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateCaseVersionResponse> {
    let path = "/api/v1/case-version";
    return this.request<CreateCaseVersionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_case_version(id: string, options: RequestOptions = {}): Promise<GetCaseVersionResponse> {
    let path = "/api/v1/case-version/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCaseVersionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_case_version(id: string, body: UpdateCaseVersionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateCaseVersionResponse> {
    let path = "/api/v1/case-version/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCaseVersionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_case_suite(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListCaseSuiteResponse> {
    let path = "/api/v1/case-suite";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListCaseSuiteResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_case_suite(body: CreateCaseSuiteRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateCaseSuiteResponse> {
    let path = "/api/v1/case-suite";
    return this.request<CreateCaseSuiteResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_case_suite(id: string, options: RequestOptions = {}): Promise<GetCaseSuiteResponse> {
    let path = "/api/v1/case-suite/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCaseSuiteResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_case_suite(id: string, body: UpdateCaseSuiteRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateCaseSuiteResponse> {
    let path = "/api/v1/case-suite/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCaseSuiteResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_business_flow_template(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListBusinessFlowTemplateResponse> {
    let path = "/api/v1/business-flow-template";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListBusinessFlowTemplateResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_business_flow_template(body: CreateBusinessFlowTemplateRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateBusinessFlowTemplateResponse> {
    let path = "/api/v1/business-flow-template";
    return this.request<CreateBusinessFlowTemplateResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_business_flow_template(id: string, options: RequestOptions = {}): Promise<GetBusinessFlowTemplateResponse> {
    let path = "/api/v1/business-flow-template/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetBusinessFlowTemplateResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_business_flow_template(id: string, body: UpdateBusinessFlowTemplateRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateBusinessFlowTemplateResponse> {
    let path = "/api/v1/business-flow-template/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateBusinessFlowTemplateResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_page_exploration(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListPageExplorationResponse> {
    let path = "/api/v1/page-exploration";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListPageExplorationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_page_exploration(body: CreatePageExplorationRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreatePageExplorationResponse> {
    let path = "/api/v1/page-exploration";
    return this.request<CreatePageExplorationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_page_exploration(id: string, options: RequestOptions = {}): Promise<GetPageExplorationResponse> {
    let path = "/api/v1/page-exploration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPageExplorationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_page_exploration(id: string, body: UpdatePageExplorationRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdatePageExplorationResponse> {
    let path = "/api/v1/page-exploration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePageExplorationResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_manual_recording_task(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListManualRecordingTaskResponse> {
    let path = "/api/v1/manual-recording-task";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListManualRecordingTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_manual_recording_task(body: CreateManualRecordingTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateManualRecordingTaskResponse> {
    let path = "/api/v1/manual-recording-task";
    return this.request<CreateManualRecordingTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_manual_recording_task(id: string, options: RequestOptions = {}): Promise<GetManualRecordingTaskResponse> {
    let path = "/api/v1/manual-recording-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetManualRecordingTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_manual_recording_task(id: string, body: UpdateManualRecordingTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateManualRecordingTaskResponse> {
    let path = "/api/v1/manual-recording-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateManualRecordingTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_manual_recording_session(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListManualRecordingSessionResponse> {
    let path = "/api/v1/manual-recording-session";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListManualRecordingSessionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_manual_recording_session(body: CreateManualRecordingSessionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateManualRecordingSessionResponse> {
    let path = "/api/v1/manual-recording-session";
    return this.request<CreateManualRecordingSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_manual_recording_session(id: string, options: RequestOptions = {}): Promise<GetManualRecordingSessionResponse> {
    let path = "/api/v1/manual-recording-session/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetManualRecordingSessionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_manual_recording_session(id: string, body: UpdateManualRecordingSessionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateManualRecordingSessionResponse> {
    let path = "/api/v1/manual-recording-session/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateManualRecordingSessionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_recording_evidence_bundle(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListRecordingEvidenceBundleResponse> {
    let path = "/api/v1/recording-evidence-bundle";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListRecordingEvidenceBundleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_recording_evidence_bundle(body: CreateRecordingEvidenceBundleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateRecordingEvidenceBundleResponse> {
    let path = "/api/v1/recording-evidence-bundle";
    return this.request<CreateRecordingEvidenceBundleResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_recording_evidence_bundle(id: string, options: RequestOptions = {}): Promise<GetRecordingEvidenceBundleResponse> {
    let path = "/api/v1/recording-evidence-bundle/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRecordingEvidenceBundleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_recording_evidence_bundle(id: string, body: UpdateRecordingEvidenceBundleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateRecordingEvidenceBundleResponse> {
    let path = "/api/v1/recording-evidence-bundle/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRecordingEvidenceBundleResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_run_task(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListRunTaskResponse> {
    let path = "/api/v1/run-task";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListRunTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_run_task(body: CreateRunTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateRunTaskResponse> {
    let path = "/api/v1/run-task";
    return this.request<CreateRunTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_run_task(id: string, options: RequestOptions = {}): Promise<GetRunTaskResponse> {
    let path = "/api/v1/run-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_run_task(id: string, body: UpdateRunTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateRunTaskResponse> {
    let path = "/api/v1/run-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRunTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_attempt(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListExecutionAttemptResponse> {
    let path = "/api/v1/execution-attempt";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListExecutionAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_attempt(body: CreateExecutionAttemptRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExecutionAttemptResponse> {
    let path = "/api/v1/execution-attempt";
    return this.request<CreateExecutionAttemptResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_attempt(id: string, options: RequestOptions = {}): Promise<GetExecutionAttemptResponse> {
    let path = "/api/v1/execution-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_attempt(id: string, body: UpdateExecutionAttemptRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateExecutionAttemptResponse> {
    let path = "/api/v1/execution-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionAttemptResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_case_attempt(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListCaseAttemptResponse> {
    let path = "/api/v1/case-attempt";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListCaseAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_case_attempt(body: CreateCaseAttemptRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateCaseAttemptResponse> {
    let path = "/api/v1/case-attempt";
    return this.request<CreateCaseAttemptResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_case_attempt(id: string, options: RequestOptions = {}): Promise<GetCaseAttemptResponse> {
    let path = "/api/v1/case-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetCaseAttemptResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_case_attempt(id: string, body: UpdateCaseAttemptRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateCaseAttemptResponse> {
    let path = "/api/v1/case-attempt/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateCaseAttemptResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_plan(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListExecutionPlanResponse> {
    let path = "/api/v1/execution-plan";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListExecutionPlanResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_plan(body: CreateExecutionPlanRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExecutionPlanResponse> {
    let path = "/api/v1/execution-plan";
    return this.request<CreateExecutionPlanResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_plan(id: string, options: RequestOptions = {}): Promise<GetExecutionPlanResponse> {
    let path = "/api/v1/execution-plan/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionPlanResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_plan(id: string, body: UpdateExecutionPlanRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateExecutionPlanResponse> {
    let path = "/api/v1/execution-plan/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionPlanResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_plan_revision(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListExecutionPlanRevisionResponse> {
    let path = "/api/v1/execution-plan-revision";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListExecutionPlanRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_plan_revision(body: CreateExecutionPlanRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExecutionPlanRevisionResponse> {
    let path = "/api/v1/execution-plan-revision";
    return this.request<CreateExecutionPlanRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_plan_revision(id: string, options: RequestOptions = {}): Promise<GetExecutionPlanRevisionResponse> {
    let path = "/api/v1/execution-plan-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionPlanRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_plan_revision(id: string, body: UpdateExecutionPlanRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateExecutionPlanRevisionResponse> {
    let path = "/api/v1/execution-plan-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionPlanRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_trigger_rule(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTriggerRuleResponse> {
    let path = "/api/v1/trigger-rule";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTriggerRuleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_trigger_rule(body: CreateTriggerRuleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTriggerRuleResponse> {
    let path = "/api/v1/trigger-rule";
    return this.request<CreateTriggerRuleResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_trigger_rule(id: string, options: RequestOptions = {}): Promise<GetTriggerRuleResponse> {
    let path = "/api/v1/trigger-rule/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTriggerRuleResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_trigger_rule(id: string, body: UpdateTriggerRuleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTriggerRuleResponse> {
    let path = "/api/v1/trigger-rule/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTriggerRuleResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_lease(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListLeaseResponse> {
    let path = "/api/v1/lease";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListLeaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async get_lease(id: string, options: RequestOptions = {}): Promise<GetLeaseResponse> {
    let path = "/api/v1/lease/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetLeaseResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async list_automation_asset(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAutomationAssetResponse> {
    let path = "/api/v1/automation-asset";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAutomationAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_automation_asset(body: CreateAutomationAssetRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAutomationAssetResponse> {
    let path = "/api/v1/automation-asset";
    return this.request<CreateAutomationAssetResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_automation_asset(id: string, options: RequestOptions = {}): Promise<GetAutomationAssetResponse> {
    let path = "/api/v1/automation-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAutomationAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_automation_asset(id: string, body: UpdateAutomationAssetRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAutomationAssetResponse> {
    let path = "/api/v1/automation-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAutomationAssetResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_login_strategy(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListLoginStrategyResponse> {
    let path = "/api/v1/login-strategy";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListLoginStrategyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_login_strategy(body: CreateLoginStrategyRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateLoginStrategyResponse> {
    let path = "/api/v1/login-strategy";
    return this.request<CreateLoginStrategyResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_login_strategy(id: string, options: RequestOptions = {}): Promise<GetLoginStrategyResponse> {
    let path = "/api/v1/login-strategy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetLoginStrategyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_login_strategy(id: string, body: UpdateLoginStrategyRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateLoginStrategyResponse> {
    let path = "/api/v1/login-strategy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateLoginStrategyResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_page_object(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListPageObjectResponse> {
    let path = "/api/v1/page-object";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListPageObjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_page_object(body: CreatePageObjectRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreatePageObjectResponse> {
    let path = "/api/v1/page-object";
    return this.request<CreatePageObjectResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_page_object(id: string, options: RequestOptions = {}): Promise<GetPageObjectResponse> {
    let path = "/api/v1/page-object/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPageObjectResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_page_object(id: string, body: UpdatePageObjectRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdatePageObjectResponse> {
    let path = "/api/v1/page-object/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePageObjectResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_action_asset(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListActionAssetResponse> {
    let path = "/api/v1/action-asset";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListActionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_action_asset(body: CreateActionAssetRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateActionAssetResponse> {
    let path = "/api/v1/action-asset";
    return this.request<CreateActionAssetResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_action_asset(id: string, options: RequestOptions = {}): Promise<GetActionAssetResponse> {
    let path = "/api/v1/action-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetActionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_action_asset(id: string, body: UpdateActionAssetRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateActionAssetResponse> {
    let path = "/api/v1/action-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateActionAssetResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_assertion_asset(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAssertionAssetResponse> {
    let path = "/api/v1/assertion-asset";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAssertionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_assertion_asset(body: CreateAssertionAssetRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAssertionAssetResponse> {
    let path = "/api/v1/assertion-asset";
    return this.request<CreateAssertionAssetResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_assertion_asset(id: string, options: RequestOptions = {}): Promise<GetAssertionAssetResponse> {
    let path = "/api/v1/assertion-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAssertionAssetResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_assertion_asset(id: string, body: UpdateAssertionAssetRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAssertionAssetResponse> {
    let path = "/api/v1/assertion-asset/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAssertionAssetResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_runner(options: QueryRequestOptions<{ project_id: string; lifecycle_status?: "REGISTERED" | "ACTIVE" | "DISABLED" | "ARCHIVED"; health_status?: "UNKNOWN" | "HEALTHY" | "DEGRADED" | "UNHEALTHY"; capability_code?: string; page?: number; page_size?: number }> = {}): Promise<ListRunnerResponse> {
    let path = "/api/v1/runner";
    const query = new URLSearchParams();
    if (options.query?.project_id !== undefined) query.set("project_id", String(options.query?.project_id));
    if (options.query?.lifecycle_status !== undefined) query.set("lifecycle_status", String(options.query?.lifecycle_status));
    if (options.query?.health_status !== undefined) query.set("health_status", String(options.query?.health_status));
    if (options.query?.capability_code !== undefined) query.set("capability_code", String(options.query?.capability_code));
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListRunnerResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_runner_enrollment(body: CreateRunnerEnrollmentRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateRunnerEnrollmentResponse> {
    let path = "/api/v1/runner-enrollments";
    return this.request<CreateRunnerEnrollmentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_runner(id: string, options: RequestOptions = {}): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_runner(id: string, body: UpdateRunnerRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async enable_runner(id: string, body: RunnerLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}/enable".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async disable_runner(id: string, body: RunnerLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}/disable".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async archive_runner(id: string, body: RunnerLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}/archive".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async rotate_runner_agent_token(id: string, body: RunnerLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<RotateRunnerAgentTokenResponse> {
    let path = "/api/v1/runner/{id}/agent-token/rotate".replace('{id}', encodeURIComponent(id));
    return this.request<RotateRunnerAgentTokenResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async revoke_runner_agent_token(id: string, body: RunnerLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}/agent-token/revoke".replace('{id}', encodeURIComponent(id));
    return this.request<GetRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async validate_runner_capability(id: string, capability_code: string, body: ValidateRunnerCapabilityRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<GetRunnerResponse> {
    let path = "/api/v1/runner/{id}/capabilities/{capability_code}/validate".replace('{id}', encodeURIComponent(id)).replace('{capability_code}', encodeURIComponent(capability_code));
    return this.request<GetRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_slot(options: QueryRequestOptions<{ page?: number; page_size?: number; project_id: string; runner_id?: string; lifecycle_status?: "ACTIVE" | "DISABLED" | "ARCHIVED"; available_only?: boolean; sort?: string; filter?: string }> = {}): Promise<ListExecutionSlotResponse> {
    let path = "/api/v1/execution-slot";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.project_id !== undefined) query.set("project_id", String(options.query?.project_id));
    if (options.query?.runner_id !== undefined) query.set("runner_id", String(options.query?.runner_id));
    if (options.query?.lifecycle_status !== undefined) query.set("lifecycle_status", String(options.query?.lifecycle_status));
    if (options.query?.available_only !== undefined) query.set("available_only", String(options.query?.available_only));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListExecutionSlotResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_slot(body: CreateExecutionSlotRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExecutionSlotResponse> {
    let path = "/api/v1/execution-slot";
    return this.request<CreateExecutionSlotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_slot(id: string, options: RequestOptions = {}): Promise<GetExecutionSlotResponse> {
    let path = "/api/v1/execution-slot/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionSlotResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_slot(id: string, body: UpdateExecutionSlotRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateExecutionSlotResponse> {
    let path = "/api/v1/execution-slot/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionSlotResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_model_config(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListModelConfigResponse> {
    let path = "/api/v1/model-config";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListModelConfigResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_model_config(body: CreateModelConfigRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateModelConfigResponse> {
    let path = "/api/v1/model-config";
    return this.request<CreateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_model_config(id: string, options: RequestOptions = {}): Promise<GetModelConfigResponse> {
    let path = "/api/v1/model-config/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetModelConfigResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_model_config(id: string, body: UpdateModelConfigRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async submit_model_config_review(id: string, body: ModelConfigLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}/submit-review".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async activate_model_config(id: string, body: ModelConfigLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}/activate".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async return_model_config_to_configuring(id: string, body: ModelConfigLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}/return-to-configuring".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async disable_model_config(id: string, body: ModelConfigLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}/disable".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async recover_model_config(id: string, body: ModelConfigLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}/recover".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async archive_model_config(id: string, body: ModelConfigLifecycleRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateModelConfigResponse> {
    let path = "/api/v1/model-config/{id}/archive".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateModelConfigResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async test_model_config_connection(id: string, body: TestModelConfigConnectionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<TestModelConfigConnectionResponse> {
    let path = "/api/v1/model-config/{id}/connection-test".replace('{id}', encodeURIComponent(id));
    return this.request<TestModelConfigConnectionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_model_config_reviews(options: QueryRequestOptions<{ page?: number; page_size?: number }> = {}): Promise<ListModelConfigResponse> {
    let path = "/api/v1/model-config-review";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListModelConfigResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async get_model_config_review(id: string, options: RequestOptions = {}): Promise<GetModelConfigResponse> {
    let path = "/api/v1/model-config-review/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetModelConfigResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async set_capability_default_model(capability_code: string, body: SetCapabilityDefaultModelRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<SetCapabilityDefaultModelResponse> {
    let path = "/api/v1/model-capability-default/{capability_code}".replace('{capability_code}', encodeURIComponent(capability_code));
    return this.request<SetCapabilityDefaultModelResponse>(path, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async clear_capability_default_model(capability_code: string, body: ClearCapabilityDefaultModelRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ClearCapabilityDefaultModelResponse> {
    let path = "/api/v1/model-capability-default/{capability_code}/clear".replace('{capability_code}', encodeURIComponent(capability_code));
    return this.request<ClearCapabilityDefaultModelResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_prompt_revision(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListPromptRevisionResponse> {
    let path = "/api/v1/prompt-revision";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListPromptRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_prompt_revision(body: CreatePromptRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreatePromptRevisionResponse> {
    let path = "/api/v1/prompt-revision";
    return this.request<CreatePromptRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_prompt_revision(id: string, options: RequestOptions = {}): Promise<GetPromptRevisionResponse> {
    let path = "/api/v1/prompt-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetPromptRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_prompt_revision(id: string, body: UpdatePromptRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdatePromptRevisionResponse> {
    let path = "/api/v1/prompt-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdatePromptRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_call(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAiCallResponse> {
    let path = "/api/v1/ai-call";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAiCallResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_ai_call(body: CreateAiCallRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAiCallResponse> {
    let path = "/api/v1/ai-call";
    return this.request<CreateAiCallResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_call(id: string, options: RequestOptions = {}): Promise<GetAiCallResponse> {
    let path = "/api/v1/ai-call/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAiCallResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_ai_call(id: string, body: UpdateAiCallRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAiCallResponse> {
    let path = "/api/v1/ai-call/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAiCallResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_task(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAiTaskResponse> {
    let path = "/api/v1/ai-task";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAiTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_ai_task(body: CreateAiTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAiTaskResponse> {
    let path = "/api/v1/ai-task";
    return this.request<CreateAiTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_task(id: string, options: RequestOptions = {}): Promise<GetAiTaskResponse> {
    let path = "/api/v1/ai-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAiTaskResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_ai_task(id: string, body: UpdateAiTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAiTaskResponse> {
    let path = "/api/v1/ai-task/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAiTaskResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_report_generation_request(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTestReportGenerationRequestResponse> {
    let path = "/api/v1/test-report-generation-request";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTestReportGenerationRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_report_generation_request(body: CreateTestReportGenerationRequestRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTestReportGenerationRequestResponse> {
    let path = "/api/v1/test-report-generation-request";
    return this.request<CreateTestReportGenerationRequestResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_report_generation_request(id: string, options: RequestOptions = {}): Promise<GetTestReportGenerationRequestResponse> {
    let path = "/api/v1/test-report-generation-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestReportGenerationRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_report_generation_request(id: string, body: UpdateTestReportGenerationRequestRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestReportGenerationRequestResponse> {
    let path = "/api/v1/test-report-generation-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestReportGenerationRequestResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_report(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTestReportResponse> {
    let path = "/api/v1/test-report";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTestReportResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_report(body: CreateTestReportRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTestReportResponse> {
    let path = "/api/v1/test-report";
    return this.request<CreateTestReportResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_report(id: string, options: RequestOptions = {}): Promise<GetTestReportResponse> {
    let path = "/api/v1/test-report/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestReportResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_report(id: string, body: UpdateTestReportRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestReportResponse> {
    let path = "/api/v1/test-report/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestReportResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_test_artifact(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTestArtifactResponse> {
    let path = "/api/v1/test-artifact";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTestArtifactResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_test_artifact(body: CreateTestArtifactRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTestArtifactResponse> {
    let path = "/api/v1/test-artifact";
    return this.request<CreateTestArtifactResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_test_artifact(id: string, options: RequestOptions = {}): Promise<GetTestArtifactResponse> {
    let path = "/api/v1/test-artifact/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTestArtifactResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_test_artifact(id: string, body: UpdateTestArtifactRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTestArtifactResponse> {
    let path = "/api/v1/test-artifact/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTestArtifactResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_technical_alert(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTechnicalAlertResponse> {
    let path = "/api/v1/technical-alert";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTechnicalAlertResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_technical_alert(body: CreateTechnicalAlertRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTechnicalAlertResponse> {
    let path = "/api/v1/technical-alert";
    return this.request<CreateTechnicalAlertResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_technical_alert(id: string, options: RequestOptions = {}): Promise<GetTechnicalAlertResponse> {
    let path = "/api/v1/technical-alert/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTechnicalAlertResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_technical_alert(id: string, body: UpdateTechnicalAlertRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTechnicalAlertResponse> {
    let path = "/api/v1/technical-alert/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTechnicalAlertResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_integration_component(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListIntegrationComponentResponse> {
    let path = "/api/v1/integration-component";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListIntegrationComponentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_integration_component(body: CreateIntegrationComponentRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateIntegrationComponentResponse> {
    let path = "/api/v1/integration-component";
    return this.request<CreateIntegrationComponentResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_integration_component(id: string, options: RequestOptions = {}): Promise<GetIntegrationComponentResponse> {
    let path = "/api/v1/integration-component/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetIntegrationComponentResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_integration_component(id: string, body: UpdateIntegrationComponentRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateIntegrationComponentResponse> {
    let path = "/api/v1/integration-component/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateIntegrationComponentResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_system_parameter(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListSystemParameterResponse> {
    let path = "/api/v1/system-parameter";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListSystemParameterResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_system_parameter(body: CreateSystemParameterRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateSystemParameterResponse> {
    let path = "/api/v1/system-parameter";
    return this.request<CreateSystemParameterResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_system_parameter(id: string, options: RequestOptions = {}): Promise<GetSystemParameterResponse> {
    let path = "/api/v1/system-parameter/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetSystemParameterResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_system_parameter(id: string, body: UpdateSystemParameterRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateSystemParameterResponse> {
    let path = "/api/v1/system-parameter/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateSystemParameterResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_data_dictionary(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListDataDictionaryResponse> {
    let path = "/api/v1/data-dictionary";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListDataDictionaryResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_data_dictionary(body: CreateDataDictionaryRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateDataDictionaryResponse> {
    let path = "/api/v1/data-dictionary";
    return this.request<CreateDataDictionaryResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_data_dictionary(id: string, options: RequestOptions = {}): Promise<GetDataDictionaryResponse> {
    let path = "/api/v1/data-dictionary/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetDataDictionaryResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_data_dictionary(id: string, body: UpdateDataDictionaryRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateDataDictionaryResponse> {
    let path = "/api/v1/data-dictionary/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateDataDictionaryResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_audit_log(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAuditLogResponse> {
    let path = "/api/v1/audit-log";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAuditLogResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_audit_log(body: CreateAuditLogRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAuditLogResponse> {
    let path = "/api/v1/audit-log";
    return this.request<CreateAuditLogResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_audit_log(id: string, options: RequestOptions = {}): Promise<GetAuditLogResponse> {
    let path = "/api/v1/audit-log/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAuditLogResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_audit_log(id: string, body: UpdateAuditLogRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAuditLogResponse> {
    let path = "/api/v1/audit-log/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAuditLogResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_retention_policy(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListRetentionPolicyResponse> {
    let path = "/api/v1/retention-policy";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListRetentionPolicyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_retention_policy(body: CreateRetentionPolicyRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateRetentionPolicyResponse> {
    let path = "/api/v1/retention-policy";
    return this.request<CreateRetentionPolicyResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_retention_policy(id: string, options: RequestOptions = {}): Promise<GetRetentionPolicyResponse> {
    let path = "/api/v1/retention-policy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetRetentionPolicyResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_retention_policy(id: string, body: UpdateRetentionPolicyRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateRetentionPolicyResponse> {
    let path = "/api/v1/retention-policy/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateRetentionPolicyResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_controlled_purge_request(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListControlledPurgeRequestResponse> {
    let path = "/api/v1/controlled-purge-request";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListControlledPurgeRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_controlled_purge_request(body: CreateControlledPurgeRequestRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateControlledPurgeRequestResponse> {
    let path = "/api/v1/controlled-purge-request";
    return this.request<CreateControlledPurgeRequestResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_controlled_purge_request(id: string, options: RequestOptions = {}): Promise<GetControlledPurgeRequestResponse> {
    let path = "/api/v1/controlled-purge-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetControlledPurgeRequestResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_controlled_purge_request(id: string, body: UpdateControlledPurgeRequestRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateControlledPurgeRequestResponse> {
    let path = "/api/v1/controlled-purge-request/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateControlledPurgeRequestResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_technical_alert_endpoint(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTechnicalAlertEndpointResponse> {
    let path = "/api/v1/technical-alert-endpoint";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTechnicalAlertEndpointResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_technical_alert_endpoint(body: CreateTechnicalAlertEndpointRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTechnicalAlertEndpointResponse> {
    let path = "/api/v1/technical-alert-endpoint";
    return this.request<CreateTechnicalAlertEndpointResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_technical_alert_endpoint(id: string, options: RequestOptions = {}): Promise<GetTechnicalAlertEndpointResponse> {
    let path = "/api/v1/technical-alert-endpoint/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTechnicalAlertEndpointResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_technical_alert_endpoint(id: string, body: UpdateTechnicalAlertEndpointRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTechnicalAlertEndpointResponse> {
    let path = "/api/v1/technical-alert-endpoint/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTechnicalAlertEndpointResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_candidate_revision(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListAiCandidateRevisionResponse> {
    let path = "/api/v1/ai-candidate-revision";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListAiCandidateRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_ai_candidate_revision(body: CreateAiCandidateRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAiCandidateRevisionResponse> {
    let path = "/api/v1/ai-candidate-revision";
    return this.request<CreateAiCandidateRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_candidate_revision(id: string, options: RequestOptions = {}): Promise<GetAiCandidateRevisionResponse> {
    let path = "/api/v1/ai-candidate-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetAiCandidateRevisionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_ai_candidate_revision(id: string, body: UpdateAiCandidateRevisionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateAiCandidateRevisionResponse> {
    let path = "/api/v1/ai-candidate-revision/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateAiCandidateRevisionResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_technical_alert_ingestion_batch(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListTechnicalAlertIngestionBatchResponse> {
    let path = "/api/v1/technical-alert-ingestion-batch";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListTechnicalAlertIngestionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_technical_alert_ingestion_batch(body: CreateTechnicalAlertIngestionBatchRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateTechnicalAlertIngestionBatchResponse> {
    let path = "/api/v1/technical-alert-ingestion-batch";
    return this.request<CreateTechnicalAlertIngestionBatchResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_technical_alert_ingestion_batch(id: string, options: RequestOptions = {}): Promise<GetTechnicalAlertIngestionBatchResponse> {
    let path = "/api/v1/technical-alert-ingestion-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetTechnicalAlertIngestionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_technical_alert_ingestion_batch(id: string, body: UpdateTechnicalAlertIngestionBatchRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateTechnicalAlertIngestionBatchResponse> {
    let path = "/api/v1/technical-alert-ingestion-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateTechnicalAlertIngestionBatchResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_batch(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListExecutionBatchResponse> {
    let path = "/api/v1/execution-batch";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListExecutionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_execution_batch(body: CreateExecutionBatchRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExecutionBatchResponse> {
    let path = "/api/v1/execution-batch";
    return this.request<CreateExecutionBatchResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_execution_batch(id: string, options: RequestOptions = {}): Promise<GetExecutionBatchResponse> {
    let path = "/api/v1/execution-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetExecutionBatchResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_execution_batch(id: string, body: UpdateExecutionBatchRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateExecutionBatchResponse> {
    let path = "/api/v1/execution-batch/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateExecutionBatchResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_project_execution_configuration(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListProjectExecutionConfigurationResponse> {
    let path = "/api/v1/project-execution-configuration";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListProjectExecutionConfigurationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_project_execution_configuration(body: CreateProjectExecutionConfigurationRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateProjectExecutionConfigurationResponse> {
    let path = "/api/v1/project-execution-configuration";
    return this.request<CreateProjectExecutionConfigurationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_project_execution_configuration(id: string, options: RequestOptions = {}): Promise<GetProjectExecutionConfigurationResponse> {
    let path = "/api/v1/project-execution-configuration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetProjectExecutionConfigurationResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async update_project_execution_configuration(id: string, body: UpdateProjectExecutionConfigurationRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<UpdateProjectExecutionConfigurationResponse> {
    let path = "/api/v1/project-execution-configuration/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<UpdateProjectExecutionConfigurationResponse>(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_execution(body: CreateExecutionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExecutionResponse> {
    let path = "/api/v1/executions";
    return this.request<CreateExecutionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async cancel_execution(id: string, body: CancelExecutionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CancelExecutionResponse> {
    let path = "/api/v1/executions/{id}/cancel".replace('{id}', encodeURIComponent(id));
    return this.request<CancelExecutionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async terminate_execution(id: string, body: TerminateExecutionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<TerminateExecutionResponse> {
    let path = "/api/v1/executions/{id}/terminate".replace('{id}', encodeURIComponent(id));
    return this.request<TerminateExecutionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async register_runner(body: RegisterRunnerRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<RegisterRunnerResponse> {
    let path = "/api/v1/runners/register";
    return this.request<RegisterRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async heartbeat_runner(id: string, body: HeartbeatRunnerRequest, options: RequiredHeaderOptions<"X-Runner-Agent-Token">): Promise<HeartbeatRunnerResponse> {
    let path = "/api/v1/runners/{id}/heartbeat".replace('{id}', encodeURIComponent(id));
    return this.request<HeartbeatRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async report_runner_capabilities(id: string, body: ReportRunnerCapabilitiesRequest, options: RequiredHeaderOptions<"X-Runner-Agent-Token">): Promise<HeartbeatRunnerResponse> {
    let path = "/api/v1/runners/{id}/capabilities".replace('{id}', encodeURIComponent(id));
    return this.request<HeartbeatRunnerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async claim_runner_task(id: string, body: ClaimRunnerTaskRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ClaimRunnerTaskResponse> {
    let path = "/api/v1/runners/{id}/claim".replace('{id}', encodeURIComponent(id));
    return this.request<ClaimRunnerTaskResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async renew_runner_lease(id: string, body: RenewRunnerLeaseRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<RenewRunnerLeaseResponse> {
    let path = "/api/v1/runners/{id}/renew".replace('{id}', encodeURIComponent(id));
    return this.request<RenewRunnerLeaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async report_runner_progress(id: string, body: ReportRunnerProgressRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ReportRunnerProgressResponse> {
    let path = "/api/v1/runners/{id}/progress".replace('{id}', encodeURIComponent(id));
    return this.request<ReportRunnerProgressResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async report_runner_result(id: string, body: ReportRunnerResultRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ReportRunnerResultResponse> {
    let path = "/api/v1/runners/{id}/result".replace('{id}', encodeURIComponent(id));
    return this.request<ReportRunnerResultResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async convert_natural_language_case(id: string, body: ConvertNaturalLanguageCaseRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ConvertNaturalLanguageCaseResponse> {
    let path = "/api/v1/natural-language-cases/{id}/convert".replace('{id}', encodeURIComponent(id));
    return this.request<ConvertNaturalLanguageCaseResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_ai_exploration(body: CreateAiExplorationRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAiExplorationResponse> {
    let path = "/api/v1/ai-explorations";
    return this.request<CreateAiExplorationResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_ai_exploration_session(body: CreateAiExplorationSessionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateAiExplorationSessionResponse> {
    let path = "/api/v1/ai-exploration-sessions";
    return this.request<CreateAiExplorationSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_ai_exploration_session(session_id: string, options: RequestOptions = {}): Promise<AIExplorationSessionResponse> {
    let path = "/api/v1/ai-exploration-sessions/{session_id}".replace('{session_id}', encodeURIComponent(session_id));
    return this.request<AIExplorationSessionResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async start_ai_exploration_session(session_id: string, body: StartAIExplorationSessionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<AIExplorationSessionResponse> {
    let path = "/api/v1/ai-exploration-sessions/{session_id}/start".replace('{session_id}', encodeURIComponent(session_id));
    return this.request<AIExplorationSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_ai_exploration_steps(session_id: string, options: RequestOptions = {}): Promise<AIExplorationStepListResponse> {
    let path = "/api/v1/ai-exploration-sessions/{session_id}/steps".replace('{session_id}', encodeURIComponent(session_id));
    return this.request<AIExplorationStepListResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async cancel_ai_exploration_session(session_id: string, body: CancelAIExplorationSessionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<AIExplorationSessionResponse> {
    let path = "/api/v1/ai-exploration-sessions/{session_id}/cancel".replace('{session_id}', encodeURIComponent(session_id));
    return this.request<AIExplorationSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_manual_recording(body: CreateManualRecordingRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateManualRecordingResponse> {
    let path = "/api/v1/manual-recordings";
    return this.request<CreateManualRecordingResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async save_recording_draft_and_stop(id: string, body: SaveRecordingDraftAndStopRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<SaveRecordingDraftAndStopResponse> {
    let path = "/api/v1/manual-recordings/{id}/save-draft-and-stop".replace('{id}', encodeURIComponent(id));
    return this.request<SaveRecordingDraftAndStopResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async get_report(id: string, options: RequestOptions = {}): Promise<GetReportResponse> {
    let path = "/api/v1/reports/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<GetReportResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async export_report(id: string, body: ExportReportRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExportReportResponse> {
    let path = "/api/v1/reports/{id}/export".replace('{id}', encodeURIComponent(id));
    return this.request<ExportReportResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_report_share(id: string, body: CreateReportShareRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateReportShareResponse> {
    let path = "/api/v1/reports/{id}/shares".replace('{id}', encodeURIComponent(id));
    return this.request<CreateReportShareResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async download_artifact(id: string, options: RequestOptions = {}): Promise<DownloadArtifactResponse> {
    let path = "/api/v1/artifacts/{id}/download".replace('{id}', encodeURIComponent(id));
    return this.request<DownloadArtifactResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_artifact_upload_session(body: CreateArtifactUploadSessionRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateArtifactUploadSessionResponse> {
    let path = "/api/v1/artifact-upload-sessions";
    return this.request<CreateArtifactUploadSessionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async complete_artifact_upload(id: string, body: CompleteArtifactUploadRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CompleteArtifactUploadResponse> {
    let path = "/api/v1/artifact-upload-sessions/{id}/complete".replace('{id}', encodeURIComponent(id));
    return this.request<CompleteArtifactUploadResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_recovery_items(options: QueryRequestOptions<{ page?: number; page_size?: number; sort?: string; filter?: string }> = {}): Promise<ListRecoveryItemsResponse> {
    let path = "/api/v1/recovery-center";
    const query = new URLSearchParams();
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    if (options.query?.sort !== undefined) query.set("sort", String(options.query?.sort));
    if (options.query?.filter !== undefined) query.set("filter", String(options.query?.filter));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ListRecoveryItemsResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async create_external_trigger(body: CreateExternalTriggerRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<CreateExternalTriggerResponse> {
    let path = "/api/v1/external-triggers";
    return this.request<CreateExternalTriggerResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async preflight_execution_binding_snapshot(body: ExecutionBindingInput, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExecutionBindingPreflightResponse> {
    let path = "/api/v1/execution-binding-snapshots/preflight";
    return this.request<ExecutionBindingPreflightResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_execution_binding_snapshot(body: ExecutionBindingInput, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExecutionBindingSnapshotResponse> {
    let path = "/api/v1/execution-binding-snapshots";
    return this.request<ExecutionBindingSnapshotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_execution_binding_snapshots(options: QueryRequestOptions<{ project_id: string; status?: "READY" | "IN_USE" | "RELEASED" | "EXPIRED"; page?: number; page_size?: number }> = {}): Promise<ExecutionBindingSnapshotListResponse> {
    let path = "/api/v1/execution-binding-snapshots";
    const query = new URLSearchParams();
    if (options.query?.project_id !== undefined) query.set("project_id", String(options.query?.project_id));
    if (options.query?.status !== undefined) query.set("status", String(options.query?.status));
    if (options.query?.page !== undefined) query.set("page", String(options.query?.page));
    if (options.query?.page_size !== undefined) query.set("page_size", String(options.query?.page_size));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<ExecutionBindingSnapshotListResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async get_execution_binding_snapshot(id: string, options: RequestOptions = {}): Promise<ExecutionBindingSnapshotResponse> {
    let path = "/api/v1/execution-binding-snapshots/{id}".replace('{id}', encodeURIComponent(id));
    return this.request<ExecutionBindingSnapshotResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
  async consume_execution_binding_snapshot(id: string, body: ExecutionBindingCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExecutionBindingSnapshotResponse> {
    let path = "/api/v1/execution-binding-snapshots/{id}/consume".replace('{id}', encodeURIComponent(id));
    return this.request<ExecutionBindingSnapshotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async renew_execution_binding_snapshot_leases(id: string, body: ExecutionBindingCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExecutionBindingSnapshotResponse> {
    let path = "/api/v1/execution-binding-snapshots/{id}/leases/renew".replace('{id}', encodeURIComponent(id));
    return this.request<ExecutionBindingSnapshotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async release_execution_binding_snapshot(id: string, body: ExecutionBindingCommandRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExecutionBindingSnapshotResponse> {
    let path = "/api/v1/execution-binding-snapshots/{id}/release".replace('{id}', encodeURIComponent(id));
    return this.request<ExecutionBindingSnapshotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async recover_execution_binding_snapshot(id: string, body: ExecutionBindingRecoverRequest, options: RequiredHeaderOptions<"Idempotency-Key">): Promise<ExecutionBindingSnapshotResponse> {
    let path = "/api/v1/execution-binding-snapshots/{id}/recover".replace('{id}', encodeURIComponent(id));
    return this.request<ExecutionBindingSnapshotResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async create_project_runtime_policy_revision(body: CreateRuntimePolicyRevisionRequest, options: RequestOptions = {}): Promise<RuntimePolicyRevisionResponse> {
    let path = "/api/v1/project-runtime-policy-revisions";
    return this.request<RuntimePolicyRevisionResponse>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal, body: JSON.stringify(body) });
  }
  async list_project_runtime_policy_revisions(options: QueryRequestOptions<{ project_id: string }> = {}): Promise<RuntimePolicyRevisionListResponse> {
    let path = "/api/v1/project-runtime-policy-revisions";
    const query = new URLSearchParams();
    if (options.query?.project_id !== undefined) query.set("project_id", String(options.query?.project_id));
    const encodedQuery = query.toString();
    if (encodedQuery) path += `?${encodedQuery}`;
    return this.request<RuntimePolicyRevisionListResponse>(path, { method: 'GET', headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }, signal: options.signal });
  }
}
