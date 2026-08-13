import { runtimeConfig } from "../config";
import { ApiClient } from "../generated/client";
import { ApiRequestError, isProblemDetails } from "./errors";

type AuthTransportBindings = {
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<void>;
  onAuthenticationLost: () => void;
};

const emptyBindings: AuthTransportBindings = {
  getAccessToken: () => null,
  refreshAccessToken: async () => undefined,
  onAuthenticationLost: () => undefined,
};

let authBindings = emptyBindings;

const refreshableCodes = new Set([
  "AUTH_REQUIRED",
  "AUTH_TOKEN_INVALID",
  "AUTH_TOKEN_EXPIRED",
  "AUTH_SESSION_REVOKED",
]);
const cookieOnlyPaths = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
]);

export function bindAuthTransport(bindings: AuthTransportBindings): () => void {
  authBindings = bindings;
  return () => {
    if (authBindings === bindings) authBindings = emptyBindings;
  };
}

function requestPath(input: RequestInfo | URL): string {
  const rawUrl =
    typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  return new URL(rawUrl, globalThis.location?.origin ?? "http://localhost").pathname;
}

function isRefreshCandidate(path: string, status: number, code?: string): boolean {
  if (status !== 401 || !code || !refreshableCodes.has(code)) return false;
  return !cookieOnlyPaths.has(path);
}

async function requestError(response: Response): Promise<ApiRequestError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return new ApiRequestError(response.status, `请求失败（HTTP ${response.status}）`);
  }

  if (isProblemDetails(payload)) {
    return new ApiRequestError(response.status, payload.detail ?? payload.title, payload);
  }
  return new ApiRequestError(response.status, `请求失败（HTTP ${response.status}）`);
}

export function createPlatformFetcher(fetchImplementation: typeof fetch): typeof fetch {
  const execute = async (
    input: RequestInfo | URL,
    init: RequestInit | undefined,
    allowRefresh: boolean,
  ): Promise<Response> => {
    const path = requestPath(input);
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));

    const accessToken = authBindings.getAccessToken();
    if (accessToken && !cookieOnlyPaths.has(path) && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }

    const response = await fetchImplementation(input, {
      ...init,
      credentials: "same-origin",
      headers,
    });
    if (response.ok) return response;

    const error = await requestError(response);
    if (
      allowRefresh &&
      accessToken &&
      isRefreshCandidate(path, response.status, error.problem?.code)
    ) {
      try {
        await authBindings.refreshAccessToken();
      } catch (refreshError) {
        authBindings.onAuthenticationLost();
        throw refreshError;
      }
      return execute(input, init, false);
    }
    if (response.status === 401 && accessToken) {
      authBindings.onAuthenticationLost();
    }
    throw error;
  };

  return (input, init) => execute(input, init, true);
}

const browserFetch: typeof fetch = (input, init) => globalThis.fetch(input, init);

export function createApiClient(fetchImplementation: typeof fetch = browserFetch): ApiClient {
  return new ApiClient(runtimeConfig.VITE_API_BASE_URL, createPlatformFetcher(fetchImplementation));
}

export const apiClient = createApiClient();
