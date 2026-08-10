import { afterEach, describe, expect, it, vi } from "vitest";

import { bindAuthTransport, createApiClient, createPlatformFetcher } from "../api/client";
import { ApiRequestError } from "../api/errors";
import { problemDetails } from "./auth-fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("认证 API 传输适配器（组件/传输层测试）", () => {
  it("uses same-origin credentials and adds the in-memory Bearer token only to protected calls", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const unbind = bindAuthTransport({
      getAccessToken: () => "memory-only-token",
      refreshAccessToken: vi.fn(),
      onAuthenticationLost: vi.fn(),
    });
    const platformFetch = createPlatformFetcher(fetchMock as typeof fetch);

    await platformFetch("/api/v1/auth/me", { method: "GET" });
    await platformFetch("/api/v1/auth/refresh", { method: "POST" });

    const protectedInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const refreshInit = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(protectedInit.credentials).toBe("same-origin");
    expect(new Headers(protectedInit.headers).get("Authorization")).toBe(
      "Bearer memory-only-token",
    );
    expect(new Headers(refreshInit.headers).has("Authorization")).toBe(false);
    unbind();
  });

  it("refreshes and retries a protected request at most once", async () => {
    let token = "expired-token";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(problemDetails(401, "AUTH_TOKEN_EXPIRED")), {
          status: 401,
          headers: { "Content-Type": "application/problem+json" },
        }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: "ok" }), { status: 200 }));
    const refreshAccessToken = vi.fn(async () => {
      token = "rotated-token";
    });
    const unbind = bindAuthTransport({
      getAccessToken: () => token,
      refreshAccessToken,
      onAuthenticationLost: vi.fn(),
    });

    const response = await createPlatformFetcher(fetchMock as typeof fetch)("/api/v1/auth/me", {
      method: "GET",
    });

    expect(response.ok).toBe(true);
    expect(refreshAccessToken).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(
      new Headers((fetchMock.mock.calls[1]?.[1] as RequestInit).headers).get("Authorization"),
    ).toBe("Bearer rotated-token");
    unbind();
  });

  it("does not enter an infinite refresh loop when the single retry is rejected", async () => {
    const failure = () =>
      new Response(JSON.stringify(problemDetails(401, "AUTH_TOKEN_EXPIRED")), {
        status: 401,
        headers: { "Content-Type": "application/problem+json" },
      });
    const fetchMock = vi.fn().mockResolvedValueOnce(failure()).mockResolvedValueOnce(failure());
    const refreshAccessToken = vi.fn().mockResolvedValue(undefined);
    const onAuthenticationLost = vi.fn();
    const unbind = bindAuthTransport({
      getAccessToken: () => "memory-only-token",
      refreshAccessToken,
      onAuthenticationLost,
    });

    await expect(
      createPlatformFetcher(fetchMock as typeof fetch)("/api/v1/auth/me"),
    ).rejects.toBeInstanceOf(ApiRequestError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(refreshAccessToken).toHaveBeenCalledTimes(1);
    expect(onAuthenticationLost).toHaveBeenCalledTimes(1);
    unbind();
  });

  it("clears authentication for a final non-refreshable 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(problemDetails(401, "AUTH_IDENTITY_NOT_FOUND")), {
        status: 401,
        headers: { "Content-Type": "application/problem+json" },
      }),
    );
    const refreshAccessToken = vi.fn();
    const onAuthenticationLost = vi.fn();
    const unbind = bindAuthTransport({
      getAccessToken: () => "memory-only-token",
      refreshAccessToken,
      onAuthenticationLost,
    });

    await expect(
      createPlatformFetcher(fetchMock as typeof fetch)("/api/v1/auth/me"),
    ).rejects.toBeInstanceOf(ApiRequestError);
    expect(refreshAccessToken).not.toHaveBeenCalled();
    expect(onAuthenticationLost).toHaveBeenCalledTimes(1);
    unbind();
  });

  it("preserves formal ProblemDetails and normalizes the logout 204 for the generated client", async () => {
    const problem = problemDetails(403, "AUTH_ACCOUNT_DISABLED", "账号不可用");
    const failedClient = createApiClient(
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(problem), {
          status: 403,
          headers: { "Content-Type": "application/problem+json" },
        }),
      ) as typeof fetch,
    );
    await expect(
      failedClient.login_platform_user({ username: "u", password: "p" }),
    ).rejects.toMatchObject({ status: 403, problem });

    const logoutClient = createApiClient(
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })) as typeof fetch,
    );
    await expect(logoutClient.logout_platform_user({})).resolves.toBeNull();
  });
});
