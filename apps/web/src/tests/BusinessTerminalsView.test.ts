import { fireEvent, render, screen, waitFor, within } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type {
  BusinessTerminalResource,
  EnvironmentResource,
  EnvironmentTerminalAccessRevisionResource,
} from "../generated/types";
import { useBusinessTerminalsStore } from "../stores/businessTerminals";
import { useSessionStore } from "../stores/session";
import BusinessTerminalsView from "../views/BusinessTerminalsView.vue";
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
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const terminal: BusinessTerminalResource = {
  business_terminal_id: "T".repeat(26),
  project_id: projectId,
  environment_id: environment.environment_id,
  terminal_code: "ADMIN",
  display_name: "管理端",
  terminal_type: "MANAGEMENT",
  current_published_revision_id: null,
  lifecycle_status: "CONFIGURING",
  row_version: 1,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

const draftRevision: EnvironmentTerminalAccessRevisionResource = {
  environment_terminal_access_revision_id: "R".repeat(26),
  project_id: projectId,
  environment_id: environment.environment_id,
  business_terminal_id: terminal.business_terminal_id,
  revision_no: 1,
  entry_url: "https://example.test/app",
  login_url: null,
  login_strategy_id: null,
  login_prerequisites: null,
  network_requirements: null,
  display_name: "访问修订",
  lifecycle_status: "DRAFT",
  row_version: 1,
  created_at: "2026-08-26T00:00:00Z",
  updated_at: "2026-08-26T00:00:00Z",
};

describe("Business Terminal management view", () => {
  beforeEach(() => vi.restoreAllMocks());

  async function setup(
    permissions = [
      "PROJECT_VIEW",
      "BUSINESS_TERMINAL_VIEW",
      "BUSINESS_TERMINAL_CREATE",
      "BUSINESS_TERMINAL_EDIT",
    ],
    revisions: EnvironmentTerminalAccessRevisionResource[] = [],
  ) {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(
        currentUser({
          permissions,
        }),
      ),
    );
    await useSessionStore().login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "list_environment").mockResolvedValue({
      items: [environment],
      page: { page: 1, page_size: 200, total: 1 },
    });
    vi.spyOn(apiClient, "list_business_terminal").mockResolvedValue({
      items: [terminal],
      page: { page: 1, page_size: 50, total: 1 },
    });
    vi.spyOn(apiClient, "list_login_strategy").mockResolvedValue({
      items: [],
      page: { page: 1, page_size: 200, total: 0 },
    });
    vi.spyOn(apiClient, "list_environment_terminal_access_revision").mockResolvedValue({
      items: revisions,
      page: { page: 1, page_size: 200, total: revisions.length },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: "/projects/:projectId/business-terminals",
          component: BusinessTerminalsView,
        },
        { path: "/projects/:id", name: "projects.detail", component: { template: "<div />" } },
      ],
    });
    await router.push(`/projects/${projectId}/business-terminals`);
    await router.isReady();
    render(BusinessTerminalsView, { global: { plugins: [pinia, ElementPlus, router] } });
  }

  it("loads terminals within the route project", async () => {
    await setup();
    expect(await screen.findByText("ADMIN")).toBeTruthy();
    expect(apiClient.list_business_terminal).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ filter: `project_id=${projectId}` }),
      }),
    );
  });

  it("creates a terminal without implicitly creating a revision", async () => {
    await setup();
    const create = vi.spyOn(apiClient, "create_business_terminal").mockResolvedValue({
      data: terminal,
      correlation_id: "corr-terminal",
    });
    await fireEvent.click(screen.getByRole("button", { name: "创建业务终端" }));
    await fireEvent.click(screen.getByLabelText("Environment"));
    const environmentOptions = await screen.findAllByText("测试环境");
    await fireEvent.click(environmentOptions.at(-1)!);
    await fireEvent.update(screen.getByLabelText("终端编码"), "ADMIN-2");
    const dialog = screen.getByRole("dialog", { name: "创建业务终端" });
    await fireEvent.click(dialog.querySelector("button.el-button--primary")!);
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const body = create.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(body).toMatchObject({
      environment_id: environment.environment_id,
      terminal_code: "ADMIN-2",
      terminal_type: "MANAGEMENT",
    });
    expect(body).not.toHaveProperty("project_id");
    expect(body).not.toHaveProperty("current_published_revision_id");
    expect(body).not.toHaveProperty("revision");
  });

  it("hides revision mutation actions from a view-only principal", async () => {
    await setup(["PROJECT_VIEW", "BUSINESS_TERMINAL_VIEW"], [draftRevision]);
    await fireEvent.click(await screen.findByRole("button", { name: "详情" }));
    const dialog = await screen.findByRole("dialog", { name: "业务终端详情" });
    await waitFor(() =>
      expect(within(dialog).getByText("https://example.test/app")).toBeTruthy(),
    );
    expect(within(dialog).queryByRole("button", { name: "校验" })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: "发布" })).toBeNull();
  });

  it("reports refresh failure without misreporting a successful publish", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useBusinessTerminalsStore();
    const published = {
      ...draftRevision,
      lifecycle_status: "PUBLISHED" as const,
      row_version: 2,
    };
    vi.spyOn(apiClient, "publish_environment_terminal_access_revision").mockResolvedValue({
      data: published,
      correlation_id: "publish-correlation",
    });
    vi.spyOn(apiClient, "get_business_terminal").mockRejectedValue(new Error("network down"));

    await expect(store.publishRevision(draftRevision, terminal, "发布")).resolves.toEqual(
      published,
    );
    expect(store.errorMessage).toContain("已发布");
    expect(store.errorMessage).toContain("刷新失败");
  });
});
