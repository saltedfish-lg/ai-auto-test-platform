import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { ApiRequestError } from "../api/errors";
import { createPlatformRouter } from "../router";
import { authenticationResponse, currentUser, problemDetails } from "./auth-fixtures";

describe("认证路由守卫（组件/路由层测试）", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("restores the HttpOnly-cookie session before entering a protected route", async () => {
    vi.spyOn(apiClient, "refresh_platform_session").mockResolvedValue(authenticationResponse());
    const router = createPlatformRouter(createMemoryHistory());

    await router.push("/");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("platform-home");
  });

  it("sends an unauthenticated visitor to login and retains a local redirect", async () => {
    const problem = problemDetails(401, "AUTH_REQUIRED");
    vi.spyOn(apiClient, "refresh_platform_session").mockRejectedValue(
      new ApiRequestError(401, problem.title, problem),
    );
    const router = createPlatformRouter(createMemoryHistory());

    await router.push("/");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/");
  });

  it("forces bootstrap users onto the password-change route", async () => {
    vi.spyOn(apiClient, "refresh_platform_session").mockResolvedValue(
      authenticationResponse(currentUser({ force_password_change: true })),
    );
    const router = createPlatformRouter(createMemoryHistory());

    await router.push("/");
    await router.isReady();

    expect(router.currentRoute.value.name).toBe("change-password");
  });
});
