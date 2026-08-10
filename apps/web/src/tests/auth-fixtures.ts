import type {
  AuthenticationResponse,
  CurrentUserResource,
  CurrentUserResponse,
  ProblemDetails,
} from "../generated/types";

export function currentUser(overrides: Partial<CurrentUserResource> = {}): CurrentUserResource {
  return {
    user_id: "01J00000000000000000000000",
    username: "admin",
    display_name: "平台管理员",
    lifecycle_status: "ACTIVE",
    roles: ["ROLE-SUPER-ADMIN"],
    permissions: ["PROJECT_VIEW", "USER_CREATE"],
    force_password_change: false,
    ...overrides,
  };
}

export function authenticationResponse(
  user: CurrentUserResource = currentUser(),
): AuthenticationResponse {
  return {
    data: {
      access_token: "x".repeat(32),
      token_type: "Bearer",
      expires_in: 900,
      current_user: user,
    },
    correlation_id: "test-correlation-id",
  };
}

export function currentUserResponse(
  user: CurrentUserResource = currentUser(),
): CurrentUserResponse {
  return { data: user, correlation_id: "test-correlation-id" };
}

export function problemDetails(status: number, code: string, detail?: string): ProblemDetails {
  return {
    type: `urn:problem:${code.toLocaleLowerCase()}`,
    title: "认证请求失败",
    status,
    code,
    detail,
    correlation_id: "test-correlation-id",
  };
}
