import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { ApiRequestError } from "../api/errors";
import { useSessionStore } from "../stores/session";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import { authenticationResponse, currentUser, problemDetails } from "./auth-fixtures";

async function renderChangePassword(): Promise<Router> {
  const pinia = createPinia();
  setActivePinia(pinia);
  vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
    authenticationResponse(currentUser({ force_password_change: true })),
  );
  await useSessionStore().login({
    username: "admin",
    password: "input-only",
  });

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/change-password", component: ChangePasswordView },
      { path: "/", component: { template: "<div>home</div>" } },
      { path: "/login", component: { template: "<div>login</div>" } },
    ],
  });
  await router.push("/change-password");
  await router.isReady();
  render(ChangePasswordView, {
    global: { plugins: [pinia, ElementPlus, router] },
  });
  return router;
}

async function fillPasswordForm(confirmPassword = "NewSecurePassword123"): Promise<void> {
  await fireEvent.update(screen.getByLabelText("当前密码"), "TemporaryPassword123");
  await fireEvent.update(screen.getByLabelText("新密码"), "NewSecurePassword123");
  await fireEvent.update(screen.getByLabelText("确认新密码"), confirmPassword);
}

describe("改密页（组件测试，API 为 mock）", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("validates password confirmation before calling the formal operation", async () => {
    const change = vi.spyOn(apiClient, "change_current_user_password");
    await renderChangePassword();
    await fillPasswordForm("MismatchPassword123");

    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));

    expect(await screen.findByText("两次输入的新密码不一致")).toBeTruthy();
    expect(change).not.toHaveBeenCalled();
  });

  it("treats 204 as terminal success, clears memory, and replaces the route with login", async () => {
    vi.spyOn(apiClient, "change_current_user_password").mockResolvedValue(undefined);
    const refresh = vi.spyOn(apiClient, "refresh_platform_session");
    const router = await renderChangePassword();
    const session = useSessionStore();
    await fillPasswordForm();

    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));

    await waitFor(() => expect(router.currentRoute.value.path).toBe("/login"));
    expect(apiClient.change_current_user_password).toHaveBeenCalledWith(
      {
        current_password: "TemporaryPassword123",
        new_password: "NewSecurePassword123",
      },
      {
        headers: {
          "Idempotency-Key": expect.stringMatching(/^password-change-/),
        },
      },
    );
    expect(session.accessToken).toBeNull();
    expect(session.currentUser).toBeNull();
    expect(session.isAuthenticated).toBe(false);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("reuses the idempotency key when an uncertain network result is retried unchanged", async () => {
    const change = vi
      .spyOn(apiClient, "change_current_user_password")
      .mockRejectedValueOnce(new TypeError("network result unknown"))
      .mockResolvedValueOnce(undefined);
    const router = await renderChangePassword();
    await fillPasswordForm();

    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));
    expect(await screen.findByText("密码修改失败，请检查当前密码和新密码策略。")).toBeTruthy();
    expect(useSessionStore().isAuthenticated).toBe(true);

    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));
    await waitFor(() => expect(router.currentRoute.value.path).toBe("/login"));

    const firstKey = change.mock.calls[0]?.[1].headers["Idempotency-Key"];
    const retryKey = change.mock.calls[1]?.[1].headers["Idempotency-Key"];
    expect(retryKey).toBe(firstKey);
  });

  it("creates a new idempotency key after request content changes and preserves formal errors", async () => {
    const problem = problemDetails(400, "AUTH_CURRENT_PASSWORD_INVALID", "当前密码不正确");
    const change = vi
      .spyOn(apiClient, "change_current_user_password")
      .mockRejectedValue(new ApiRequestError(400, problem.title, problem));
    await renderChangePassword();
    await fillPasswordForm();

    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));
    expect(await screen.findByText("当前密码不正确。")).toBeTruthy();
    expect(screen.getByText("请求标识：test-correlation-id")).toBeTruthy();
    expect(useSessionStore().isAuthenticated).toBe(true);

    await fireEvent.update(screen.getByLabelText("新密码"), "AnotherSecurePassword123");
    await fireEvent.update(screen.getByLabelText("确认新密码"), "AnotherSecurePassword123");
    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));
    await waitFor(() => expect(change).toHaveBeenCalledTimes(2));

    const firstKey = change.mock.calls[0]?.[1].headers["Idempotency-Key"];
    const changedKey = change.mock.calls[1]?.[1].headers["Idempotency-Key"];
    expect(changedKey).not.toBe(firstKey);
    expect(useSessionStore().isAuthenticated).toBe(true);
  });
});
