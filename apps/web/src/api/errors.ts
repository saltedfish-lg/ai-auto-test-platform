import type { AuthenticationErrorCode, ProblemDetails } from "../generated/types";
import { fieldLabel } from "../presentation/labels";

const authenticationErrorMessages: Partial<Record<AuthenticationErrorCode, string>> = {
  AUTH_REQUIRED: "登录状态已失效，请重新登录。",
  AUTH_INVALID_CREDENTIALS: "用户名或密码不正确。",
  AUTH_CURRENT_PASSWORD_INVALID: "当前密码不正确。",
  AUTH_PASSWORD_POLICY_VIOLATION: "新密码不符合密码策略。",
  AUTH_PASSWORD_UNCHANGED: "新密码不能与当前密码相同。",
  AUTH_TOKEN_INVALID: "登录凭证无效，请重新登录。",
  AUTH_TOKEN_EXPIRED: "登录状态已过期，请重新登录。",
  AUTH_SESSION_REVOKED: "当前会话已撤销，请重新登录。",
  AUTH_IDENTITY_NOT_FOUND: "当前身份不存在，请联系管理员。",
  AUTH_PERMISSION_DENIED: "当前账号没有执行此操作的权限。",
  AUTH_ACCOUNT_LOCKED: "账号已被管理员锁定，请联系管理员。",
  AUTH_ACCOUNT_DISABLED: "账号已停用，请联系管理员。",
  AUTH_ACCOUNT_ARCHIVED: "账号已归档，无法登录。",
  AUTH_ACCOUNT_TEMPORARILY_LOCKED: "登录失败次数过多，账号已被临时锁定，请稍后再试。",
  AUTH_PASSWORD_CHANGE_REQUIRED: "首次登录必须先修改密码。",
  AUTH_OPERATION_FORBIDDEN_FOR_STATE: "当前账号状态不允许执行此操作。",
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly problem?: ProblemDetails;

  constructor(status: number, message: string, problem?: ProblemDetails) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.problem = problem;
  }
}

export function isProblemDetails(value: unknown): value is ProblemDetails {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.type === "string" &&
    typeof candidate.title === "string" &&
    typeof candidate.status === "number" &&
    typeof candidate.code === "string" &&
    typeof candidate.correlation_id === "string"
  );
}

export function getAuthenticationErrorMessage(error: unknown, fallback: string): string {
  // 正式错误码优先于服务端 detail，确保登录防枚举文案与改密业务文案不被后端英文细节覆盖。
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code as AuthenticationErrorCode | undefined;
  if (code && authenticationErrorMessages[code]) return authenticationErrorMessages[code];
  if (error.status === 422) return validationMessage(error.problem, fallback);
  return fallback;
}

export function getCorrelationId(error: unknown): string | undefined {
  return error instanceof ApiRequestError ? error.problem?.correlation_id : undefined;
}

export function getProblemCode(error: unknown): string | undefined {
  return error instanceof ApiRequestError ? error.problem?.code : undefined;
}

export function getProblemDetail(error: unknown): string | undefined {
  const detail = error instanceof ApiRequestError ? error.problem?.detail : undefined;
  return detail || undefined;
}

function validationMessage(problem: ProblemDetails | undefined, fallback: string): string {
  const fields = [...new Set((problem?.field_errors ?? []).map((item) => fieldLabel(item.field)))];
  return fields.length > 0
    ? `请检查以下字段：${fields.join("、")}。`
    : fallback;
}

const projectErrorMessages: Record<string, string> = {
  PROJECT_NOT_FOUND: "项目不存在或已不可访问。",
  PROJECT_OWNER_NOT_ELIGIBLE: "指定负责人不具备项目负责人资格。",
  PROJECT_CODE_CONFLICT: "项目编码已被使用，请更换后重试。",
  PROJECT_CONCURRENCY_CONFLICT: "项目已被其他操作更新，请刷新后重试。",
  PROJECT_OPERATION_FORBIDDEN_FOR_STATE: "当前项目状态不允许执行此操作。",
  PROJECT_UPDATE_EMPTY: "请至少修改一个可编辑字段。",
  PROJECT_CONFIGURATION_UNAVAILABLE: "项目初始化配置暂不可用，请稍后重试。",
  AUTH_PERMISSION_DENIED: "当前账号没有执行此操作的权限。",
};

const environmentErrorMessages: Record<string, string> = {
  ENVIRONMENT_NOT_FOUND: "环境不存在或已不可访问。",
  ENVIRONMENT_PROJECT_SCOPE_REQUIRED: "请选择明确的项目后再查询环境。",
  ENVIRONMENT_FILTER_INVALID: "环境筛选条件不正确。",
  ENVIRONMENT_CODE_CONFLICT: "该项目内的环境编码已被使用。",
  ENVIRONMENT_IDENTITY_IMMUTABLE: "项目归属和环境编码创建后不可修改。",
  ENVIRONMENT_CONCURRENCY_CONFLICT: "环境已被其他操作更新，请刷新后重试。",
  ENVIRONMENT_OPERATION_FORBIDDEN_FOR_STATE: "当前环境状态不允许执行此操作。",
  ENVIRONMENT_TERMINAL_ACCESS_REVISION_INVALID: "Terminal Access Revision 无效或不属于当前项目。",
  ENVIRONMENT_UPDATE_EMPTY: "请至少修改一个可编辑的环境字段。",
};

const modelConfigurationErrorMessages: Record<string, string> = {
  MODEL_CONFIG_NOT_FOUND: "模型配置不存在或已不可访问。",
  MODEL_CONFIG_CODE_CONFLICT: "模型配置编码已被使用，请更换后重试。",
  MODEL_CONFIG_CONCURRENCY_CONFLICT: "模型配置已被其他操作更新，请刷新后重试。",
  MODEL_CONFIG_OPERATION_FORBIDDEN_FOR_STATE: "当前模型配置状态不允许执行此操作。",
  MODEL_CONFIG_UPDATE_EMPTY: "请至少修改一个可编辑的模型配置字段。",
  MODEL_CONFIG_SELF_REVIEW_FORBIDDEN: "提交人不能审核并激活自己的模型配置。",
  MODEL_CONFIG_DEFAULT_DISABLE_CONFLICT: "当前默认模型必须先解除或切换后才能禁用。",
  MODEL_CONFIG_CONNECTION_TEST_ATTEMPT_STALE: "连接测试已被更新的请求接管，请重新执行。",
  MODEL_CONFIG_IDEMPOTENCY_REQUEST_INCOMPLETE: "相同模型操作仍在处理中，请稍后重试。",
  MODEL_CONFIG_IDEMPOTENCY_KEY_CONFLICT: "幂等键已用于不同的模型操作请求。",
  MODEL_CAPABILITY_DEFAULT_MODEL_NOT_ACTIVE: "只有 ACTIVE 模型配置才能设为能力默认模型。",
  MODEL_CAPABILITY_DEFAULT_NOT_FOUND: "当前 AI 能力尚未绑定默认模型。",
  MODEL_CAPABILITY_DEFAULT_UNAVAILABLE: "当前 AI 能力默认模型不可用。",
  MODEL_CAPABILITY_DEFAULT_CONCURRENCY_CONFLICT: "默认模型绑定已变化，请刷新后重试。",
  MODEL_CAPABILITY_NOT_FOUND: "请求的 AI 能力不存在。",
  MODEL_SECRET_STORE_UNAVAILABLE: "模型凭据安全存储当前不可用，请稍后重试。",
  AUTH_PERMISSION_DENIED: "当前账号没有执行此操作的权限。",
};


const executionErrorMessages: Record<string, string> = {
  EXECUTION_SLOT_NOT_FOUND: "当前范围内未找到可用的正式执行槽位。",
  EXECUTION_SLOT_SYSTEM_MANAGED: "正式执行槽位由系统根据 Runner 状态自动维护，不能手工创建或修改。",
  EXECUTION_BINDING_PREFLIGHT_FAILED: "执行预检查未通过，请根据检查项修正配置后重试。",
  EXECUTION_BINDING_STATE_CONFLICT: "执行绑定状态已变化，请刷新后重试。",
  EXECUTION_OWNER_STATE_CONFLICT: "当前 Runner 或执行实例状态不满足新执行准入条件。",
};

const aiExplorationErrorMessages: Record<string, string> = {
  AI_EXPLORATION_MODEL_NOT_CONFIGURED: "尚未配置可用的 AI_EXPLORATION 默认模型。",
  AI_EXPLORATION_MODEL_UNAVAILABLE: "AI 探索默认模型当前不可用，请稍后重试。",
  AI_EXPLORATION_MODEL_RESPONSE_INVALID: "模型未返回有效的结构化探索计划。",
  AI_EXPLORATION_PLANNING_FAILED: "初始探索计划生成失败，请稍后重试。",
  AI_EXPLORATION_PLANNING_INTERRUPTED: "上次探索规划已中断，请重新发起规划。",
  AI_EXPLORATION_PROJECT_UNAVAILABLE: "只有 ACTIVE 项目可以创建 AI 探索会话。",
  AUTH_PERMISSION_DENIED: "当前账号没有执行此操作的权限。",
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code;
  if (code && environmentErrorMessages[code]) return environmentErrorMessages[code];
  if (code && projectErrorMessages[code]) return projectErrorMessages[code];
  if (code && executionErrorMessages[code]) return executionErrorMessages[code];
  if (error.status === 401) return "登录状态已失效，请重新登录。";
  if (error.status === 403) return "当前账号没有执行此操作的权限。";
  if (error.status === 404) return "请求的项目不存在。";
  if (error.status === 409) return "项目状态或版本已变化，请刷新后重试。";
  if (error.status === 422) return validationMessage(error.problem, "提交内容不符合接口要求，请检查表单。");
  return fallback;
}

export function getModelConfigurationErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code;
  if (code && modelConfigurationErrorMessages[code]) {
    return modelConfigurationErrorMessages[code];
  }
  if (error.status === 401) return "登录状态已失效，请重新登录。";
  if (error.status === 403) return "当前账号没有执行此操作的权限。";
  if (error.status === 404) return "请求的模型配置不存在。";
  if (error.status === 409) return "模型配置状态或版本已变化，请刷新后重试。";
  if (error.status === 422) return validationMessage(error.problem, "提交内容不符合接口要求，请检查表单。");
  return fallback;
}

export function getAIExplorationErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code;
  if (code && aiExplorationErrorMessages[code]) return aiExplorationErrorMessages[code];
  if (error.status === 401) return "登录状态已失效，请重新登录。";
  if (error.status === 403) return "当前账号没有执行此操作的权限。";
  if (error.status === 404) return "请求的项目不存在。";
  if (error.status === 409) return "项目状态已变化，请刷新后重试。";
  if (error.status === 422) return validationMessage(error.problem, "提交内容不符合接口要求，请检查表单。");
  return fallback;
}
