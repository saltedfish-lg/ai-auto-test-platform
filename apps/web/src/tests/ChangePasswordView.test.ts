import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { useSessionStore } from "../stores/session";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import { authenticationResponse, currentUser } from "./auth-fixtures";

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

  it("sends only the generated DTO plus a fresh idempotency header", async () => {
    vi.spyOn(apiClient, "change_current_user_password").mockResolvedValue(
      authenticationResponse(currentUser({ force_password_change: false })),
    );
    const router = await renderChangePassword();
    await fillPasswordForm();

    await fireEvent.click(screen.getByRole("button", { name: "保存新密码" }));

    await waitFor(() => expect(router.currentRoute.value.path).toBe("/"));
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
  });
});
