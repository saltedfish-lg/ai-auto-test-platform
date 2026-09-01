import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus, { ElMessageBox } from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type { EnvironmentResource } from "../generated/types";
import { useSessionStore } from "../stores/session";
import EnvironmentsView from "../views/EnvironmentsView.vue";
import { authenticationResponse, currentUser } from "./auth-fixtures";

const environment: EnvironmentResource = {
  environment_id: "E".repeat(26),
  project_id: "P".repeat(26),
  environment_code: "TEST",
  display_name: "测试环境",
  lifecycle_status: "CONFIGURING",
  enablement_state: "ENABLED",
  accessibility_state: "UNKNOWN",
  row_version: 1,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

describe("Environment management view", () => {
  beforeEach(() => vi.restoreAllMocks());

  async function setup(
    permissions = ["PROJECT_VIEW", "PROJECT_EDIT"],
    listedEnvironment = environment,
  ) {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(currentUser({ permissions })),
    );
    await useSessionStore().login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "list_environment").mockResolvedValue({
      items: [listedEnvironment],
      page: { page: 1, page_size: 50, total: 1 },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects/:projectId/environments", component: EnvironmentsView },
        { path: "/projects/:id", name: "projects.detail", component: { template: "<div />" } },
      ],
    });
    await router.push(`/projects/${environment.project_id}/environments`);
    await router.isReady();
    render(EnvironmentsView, { global: { plugins: [pinia, ElementPlus, router] } });
    return router;
  }

  it("loads only the route project and renders the Authority lifecycle", async () => {
    await setup();
    expect(await screen.findByText("TEST")).toBeTruthy();
    expect(screen.getAllByText("CONFIGURING").length).toBeGreaterThan(0);
    expect(apiClient.list_environment).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ filter: `project_id=${environment.project_id}` }),
      }),
    );
  });

  it("creates without terminal, base URL, or future module fields", async () => {
    await setup();
    const create = vi.spyOn(apiClient, "create_environment").mockResolvedValue({
      data: environment,
      correlation_id: "corr-env",
    });
    await fireEvent.click(screen.getByRole("button", { name: "创建环境" }));
    const dialog = screen.getByRole("dialog", { name: "创建环境" });
    await fireEvent.update(screen.getByLabelText("环境编码"), "TEST-2");
    await fireEvent.update(screen.getByLabelText("环境名称"), "集成测试环境");
    await fireEvent.click(dialog.querySelector("button.el-button--primary")!);
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const body = create.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(body).toMatchObject({ project_id: environment.project_id, environment_code: "TEST-2" });
    expect(body).not.toHaveProperty("base_url");
    expect(body).not.toHaveProperty("environment_terminal_access_revision_id");
  });

  it("submits CONFIGURING for validation through the generated lifecycle client", async () => {
    await setup();
    vi.spyOn(ElMessageBox, "prompt").mockResolvedValue({ value: "配置完成" } as never);
    const validate = vi.spyOn(apiClient, "validate_environment").mockResolvedValue({
      data: { ...environment, lifecycle_status: "VALIDATING", row_version: 2 },
      correlation_id: "corr-validate",
    });

    await fireEvent.click(await screen.findByRole("button", { name: "提交校验" }));
    await waitFor(() =>
      expect(validate).toHaveBeenCalledWith(
        environment.environment_id,
        { expected_version: 1, reason: "配置完成" },
        expect.objectContaining({
          headers: expect.objectContaining({ "Idempotency-Key": expect.any(String) }),
        }),
      ),
    );
    await waitFor(() => expect(screen.getAllByText("VALIDATING").length).toBeGreaterThan(0));
  });

  it("exposes only the Authority commands available from VALIDATING", async () => {
    await setup(undefined, { ...environment, lifecycle_status: "VALIDATING", row_version: 2 });
    expect(await screen.findByRole("button", { name: "退回配置" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "激活" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "提交校验" })).toBeNull();
  });

  it("labels RECOVERING activation as completing recovery", async () => {
    await setup(undefined, { ...environment, lifecycle_status: "RECOVERING", row_version: 4 });
    expect(await screen.findByRole("button", { name: "完成恢复" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "激活" })).toBeNull();
  });
});
