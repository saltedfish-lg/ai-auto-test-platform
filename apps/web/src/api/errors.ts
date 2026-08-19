import type { AuthenticationErrorCode, ProblemDetails } from "../generated/types";

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

export function getAuthenticationErrorMessage(
  error: unknown,
  fallback: string,
): string {
  // 正式错误码优先于服务端 detail，确保登录防枚举文案与改密业务文案不被后端英文细节覆盖。
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code as AuthenticationErrorCode | undefined;
  return (
    (code ? authenticationErrorMessages[code] : undefined) ?? error.problem?.detail ?? fallback
  );
}

export function getCorrelationId(error: unknown): string | undefined {
  return error instanceof ApiRequestError ? error.problem?.correlation_id : undefined;
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

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code;
  if (code && projectErrorMessages[code]) return projectErrorMessages[code];
  if (error.status === 401) return "登录状态已失效，请重新登录。";
  if (error.status === 403) return "当前账号没有执行此操作的权限。";
  if (error.status === 404) return "请求的项目不存在。";
  if (error.status === 409) return "项目状态或版本已变化，请刷新后重试。";
  if (error.status === 422) return "提交内容不符合接口要求，请检查表单。";
  return error.problem?.detail ?? fallback;
}
