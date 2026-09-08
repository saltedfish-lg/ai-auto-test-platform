import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type {
  BusinessTerminalResource,
  EnvironmentResource,
  TestAccountResource,
} from "../generated/types";
import { useSessionStore } from "../stores/session";
import TestAccountsView from "../views/TestAccountsView.vue";
import { authenticationResponse, currentUser } from "./auth-fixtures";

const projectId = "P".repeat(26);
const environment: EnvironmentResource = {
  environment_id: "E".repeat(26),
  project_id: projectId,
  environment_code: "TEST",
  display_name: "测试环境",
  lifecycle_status: "ACTIVE",
  enablement_state: "ENABLED",
  accessibility_state: "REACHABLE",
  row_version: 1,
  created_at: "2026-08-28T00:00:00Z",
  updated_at: "2026-08-28T00:00:00Z",
};
const terminal: BusinessTerminalResource = {
  business_terminal_id: "T".repeat(26),
  project_id: projectId,
  environment_id: environment.environment_id,
  terminal_code: "ADMIN",
  display_name: "管理端",
  terminal_type: "MANAGEMENT",
  current_published_revision_id: "R".repeat(26),
  lifecycle_status: "ACTIVE",
  row_version: 2,
  created_at: "2026-08-28T00:00:00Z",
  updated_at: "2026-08-28T00:00:00Z",
};
const account: TestAccountResource = {
  test_account_id: "A".repeat(26),
  project_id: projectId,
  environment_id: environment.environment_id,
  account_identifier: "qa-admin",
  display_name: "验收账号",
  lifecycle_status: "ACTIVE",
  credential_state: "VALID",
  credential_revision_no: 1,
  business_terminals: [
    {
      business_terminal_id: terminal.business_terminal_id,
      terminal_code: terminal.terminal_code,
      display_name: terminal.display_name,
      terminal_type: terminal.terminal_type,
    },
  ],
  row_version: 3,
  created_at: "2026-08-28T00:00:00Z",
  updated_at: "2026-08-28T00:00:00Z",
};

describe("Test Account management view", () => {
  beforeEach(() => vi.restoreAllMocks());

  async function setup(permissions = ["PROJECT_VIEW", "PROJECT_EDIT"]) {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(currentUser({ permissions })),
    );
    await useSessionStore().login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "list_environment").mockResolvedValue({
      items: [environment],
      page: { page: 1, page_size: 200, total: 1 },
    });
    vi.spyOn(apiClient, "list_business_terminal").mockResolvedValue({
      items: [terminal],
      page: { page: 1, page_size: 200, total: 1 },
    });
    vi.spyOn(apiClient, "list_test_account").mockResolvedValue({
      items: [account],
      page: { page: 1, page_size: 50, total: 1 },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects/:projectId/test-accounts", component: TestAccountsView },
        { path: "/projects/:id", name: "projects.detail", component: { template: "<div />" } },
      ],
    });
    await router.push(`/projects/${projectId}/test-accounts`);
    await router.isReady();
    render(TestAccountsView, { global: { plugins: [pinia, ElementPlus, router] } });
  }

  it("loads the project-scoped list and never renders credential material", async () => {
    await setup();
    expect(await screen.findByText("qa-admin")).toBeTruthy();
    expect(screen.getByText("有效 · v1")).toBeTruthy();
    expect(document.body.textContent).not.toContain("secret_value");
    expect(apiClient.list_test_account).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ filter: `project_id=${projectId}` }),
      }),
    );
  });

  it("clears a newly entered credential after a failed rotation", async () => {
    const submittedSecret = "must-not-survive-a-failed-request";
    const rotate = vi
      .spyOn(apiClient, "rotate_test_account_secret")
      .mockRejectedValue(new Error("network down"));
    await setup();
    await fireEvent.click(await screen.findByRole("button", { name: "更新密码" }));
    const dialog = await screen.findByRole("dialog", { name: "更新登录密码" });
    const input = dialog.querySelector('input[type="password"]') as HTMLInputElement;
    await fireEvent.update(input, submittedSecret);
    await fireEvent.update(screen.getByLabelText("轮换原因"), "定期轮换");
    await fireEvent.click(screen.getByRole("button", { name: "安全更新" }));
    await waitFor(() => expect(rotate).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(input.value).toBe(""));
    expect(document.body.textContent).not.toContain(submittedSecret);
  });

  it("hides all Test Account mutations from a view-only principal", async () => {
    await setup(["PROJECT_VIEW"]);
    expect(await screen.findByText("qa-admin")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "新建测试账号" })).toBeNull();
    expect(screen.queryByRole("button", { name: "编辑" })).toBeNull();
    expect(screen.queryByRole("button", { name: "更新密码" })).toBeNull();
  });
});
