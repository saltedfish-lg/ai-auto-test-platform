import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import PlatformShell from "../components/PlatformShell.vue";
import { useSessionStore } from "../stores/session";
import WorkspaceHomeView from "../views/WorkspaceHomeView.vue";
import { authenticationResponse, currentUser, currentUserResponse } from "./auth-fixtures";

async function renderShell(permissions = ["PROJECT_VIEW", "PROJECT_CREATE"]): Promise<Router> {
  const pinia = createPinia();
  setActivePinia(pinia);
  vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
    authenticationResponse(currentUser({ permissions })),
  );
  await useSessionStore().login({
    username: "admin",
    password: "input-only",
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/",
        component: PlatformShell,
        children: [
          { path: "", name: "platform-home", component: WorkspaceHomeView },
          {
            path: "projects",
            name: "projects.list",
            component: { template: "<div>projects</div>" },
          },
        ],
      },
      {
        path: "/login",
        component: { template: "<div>login route</div>" },
      },
      {
        path: "/change-password",
        component: { template: "<div>change</div>" },
      },
    ],
  });
  await router.push("/");
  await router.isReady();
  render(
    { template: "<RouterView />" },
    { global: { plugins: [pinia, ElementPlus, router] } },
  );
  return router;
}

describe("身份工作台（组件测试，API 为 mock）", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders current user, roles, permissions and permission-gated UX", async () => {
    await renderShell();

    expect(screen.getByText("欢迎回来，平台管理员")).toBeTruthy();
    expect(screen.getByText("ROLE-SUPER-ADMIN")).toBeTruthy();
    expect(screen.getByText("PROJECT_VIEW")).toBeTruthy();
    expect(
      screen.getByText("当前身份可创建项目；所有写操作仍由服务端执行实时权限与范围校验。"),
    ).toBeTruthy();
  });

  it("shows the fallback UX when the realtime permission is absent", async () => {
    await renderShell(["PROJECT_VIEW"]);
    expect(
      screen.getByText("当前身份不能创建新项目；可见项目仍由服务端实时权限与范围决定。"),
    ).toBeTruthy();
  });

  it("reloads current-user data and clears local state on logout", async () => {
    const router = await renderShell();
    vi.spyOn(apiClient, "get_current_user").mockResolvedValue(
      currentUserResponse(currentUser({ display_name: "最新名称" })),
    );
    vi.spyOn(apiClient, "logout_platform_user").mockResolvedValue(undefined);

    await fireEvent.click(screen.getByRole("button", { name: "刷新身份" }));
    expect(await screen.findByText("欢迎回来，最新名称")).toBeTruthy();

    await fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
    await waitFor(() => expect(router.currentRoute.value.path).toBe("/login"));
    expect(useSessionStore().isAuthenticated).toBe(false);
  });

  it("leaves the protected view even when the logout request fails", async () => {
    const router = await renderShell();
    vi.spyOn(apiClient, "logout_platform_user").mockRejectedValue(new Error("synthetic failure"));

    await fireEvent.click(screen.getByRole("button", { name: "退出登录" }));

    await waitFor(() => expect(router.currentRoute.value.path).toBe("/login"));
    expect(useSessionStore().isAuthenticated).toBe(false);
  });
});
