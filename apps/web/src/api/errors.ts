import type { AuthenticationErrorCode, ProblemDetails } from "../generated/types";

const authenticationErrorMessages: Record<AuthenticationErrorCode, string> = {
  AUTH_REQUIRED: "登录状态已失效，请重新登录。",
  AUTH_INVALID_CREDENTIALS: "用户名或密码不正确。",
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
  if (!(error instanceof ApiRequestError)) return fallback;
  const code = error.problem?.code as AuthenticationErrorCode | undefined;
  return code && code in authenticationErrorMessages
    ? authenticationErrorMessages[code]
    : (error.problem?.detail ?? fallback);
}

export function getCorrelationId(error: unknown): string | undefined {
  return error instanceof ApiRequestError ? error.problem?.correlation_id : undefined;
}
