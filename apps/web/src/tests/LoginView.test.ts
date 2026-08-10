import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { ApiRequestError } from "../api/errors";
import LoginView from "../views/LoginView.vue";
import { authenticationResponse, currentUser, problemDetails } from "./auth-fixtures";

async function renderLogin(): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/login", component: LoginView },
      { path: "/", component: { template: "<div>home</div>" } },
      {
        path: "/change-password",
        component: { template: "<div>change</div>" },
      },
    ],
  });
  await router.push("/login");
  await router.isReady();
  const pinia = createPinia();
  setActivePinia(pinia);
  render(LoginView, { global: { plugins: [pinia, ElementPlus, router] } });
  return router;
}

async function fillCredentials(): Promise<void> {
  await fireEvent.update(screen.getByLabelText("用户名"), "admin");
  await fireEvent.update(screen.getByLabelText("密码"), "input-only");
}

describe("登录页（组件测试，API 为 mock）", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders the formal login form and validates required fields", async () => {
    const login = vi.spyOn(apiClient, "login_platform_user");
    await renderLogin();

    expect(screen.getByRole("heading", { name: "登录平台" })).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(await screen.findByText("请输入用户名和密码。")).toBeTruthy();
    expect(login).not.toHaveBeenCalled();
  });

  it("shows loading, submits the generated DTO, and enters the protected route", async () => {
    let resolveLogin: ((value: ReturnType<typeof authenticationResponse>) => void) | undefined;
    const pending = new Promise<ReturnType<typeof authenticationResponse>>((resolve) => {
      resolveLogin = resolve;
    });
    const login = vi.spyOn(apiClient, "login_platform_user").mockReturnValue(pending);
    const router = await renderLogin();
    await fillCredentials();

    await fireEvent.click(screen.getByRole("button", { name: "登录" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "登录" })).toHaveProperty("disabled", true),
    );
    expect(login).toHaveBeenCalledWith({
      username: "admin",
      password: "input-only",
    });

    resolveLogin?.(authenticationResponse());
    await waitFor(() => expect(router.currentRoute.value.path).toBe("/"));
  });

  it("maps formal temporary-lock errors without exposing secrets", async () => {
    const problem = problemDetails(403, "AUTH_ACCOUNT_TEMPORARILY_LOCKED");
    vi.spyOn(apiClient, "login_platform_user").mockRejectedValue(
      new ApiRequestError(403, problem.title, problem),
    );
    await renderLogin();
    await fillCredentials();

    await fireEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(
      await screen.findByText("登录失败次数过多，账号已被临时锁定，请稍后再试。"),
    ).toBeTruthy();
    expect(screen.getByText("请求标识：test-correlation-id")).toBeTruthy();
  });

  it("routes a force-password-change identity to the required page", async () => {
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(currentUser({ force_password_change: true })),
    );
    const router = await renderLogin();
    await fillCredentials();

    await fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(router.currentRoute.value.path).toBe("/change-password"));
  });
});
