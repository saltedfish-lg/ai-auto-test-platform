import { fireEvent, render, screen, waitFor, within } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type {
  AutomationAssetResource,
  BusinessTerminalResource,
  EnvironmentResource,
  EnvironmentTerminalAccessRevisionResource,
  LoginStrategyResource,
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

const validatingRevision: EnvironmentTerminalAccessRevisionResource = {
  ...draftRevision,
  lifecycle_status: "VALIDATING",
  row_version: 2,
};

const automationAsset: AutomationAssetResource = {
  automation_asset_id: "A".repeat(26),
  project_id: projectId,
  display_name: "11c 登录资产",
  lifecycle_status: "CREATED",
  row_version: 1,
  created_at: "2026-09-03T00:00:00Z",
  updated_at: "2026-09-03T00:00:00Z",
};

const createdLoginStrategy: LoginStrategyResource = {
  login_strategy_id: "L".repeat(26),
  automation_asset_id: automationAsset.automation_asset_id,
  project_id: projectId,
  display_name: "11c 登录策略",
  local_storage_presets: [],
  refresh_after_local_storage: false,
  captcha_policy: "NONE",
  captcha_request_header_name: null,
  captcha_request_header_value: null,
  captcha_response_header_name: null,
  session_policy: null,
  lifecycle_status: "CREATED",
  row_version: 1,
  created_at: "2026-09-03T00:00:00Z",
  updated_at: "2026-09-03T00:00:00Z",
};

describe("Business Terminal management view", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  async function setup(
    permissions = [
      "PROJECT_VIEW",
      "BUSINESS_TERMINAL_VIEW",
      "BUSINESS_TERMINAL_CREATE",
      "BUSINESS_TERMINAL_EDIT",
      "PROJECT_EDIT",
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

  it("creates and activates a login strategy through the formal asset path", async () => {
    await setup();
    const createAsset = vi.spyOn(apiClient, "create_automation_asset").mockResolvedValue({
      data: automationAsset,
      correlation_id: "corr-asset",
    });
    const createStrategy = vi.spyOn(apiClient, "create_login_strategy").mockResolvedValue({
      data: createdLoginStrategy,
      correlation_id: "corr-strategy",
    });
    const configureStrategy = vi.spyOn(apiClient, "update_login_strategy").mockResolvedValue({
      data: { ...createdLoginStrategy, lifecycle_status: "DRAFT", row_version: 2 },
      correlation_id: "corr-configure",
    });
    const activateStrategy = vi.spyOn(apiClient, "activate_login_strategy").mockResolvedValue({
      data: { ...createdLoginStrategy, lifecycle_status: "ACTIVE", row_version: 3 },
      correlation_id: "corr-activate",
    });

    await fireEvent.click(screen.getByRole("button", { name: "新建登录策略" }));
    const dialog = screen.getByRole("dialog", { name: "新建并启用登录策略" });
    await fireEvent.update(within(dialog).getByLabelText("策略名称"), "11c 登录策略");
    await fireEvent.update(within(dialog).getByLabelText("原因"), "配置 11c 真机登录");
    await fireEvent.click(within(dialog).getByRole("button", { name: "创建并启用" }));

    await waitFor(() => expect(activateStrategy).toHaveBeenCalledTimes(1));
    expect(createAsset.mock.calls[0]?.[0]).toMatchObject({
      project_id: projectId,
      display_name: "11c 登录策略",
    });
    expect(createStrategy.mock.calls[0]?.[0]).toMatchObject({
      project_id: projectId,
      automation_asset_id: automationAsset.automation_asset_id,
      captcha_policy: "NONE",
    });
    expect(configureStrategy.mock.calls[0]?.[1]).toMatchObject({
      expected_version: 1,
      captcha_policy: "NONE",
      reason: "配置 11c 真机登录",
    });
    expect(activateStrategy.mock.calls[0]?.[1]).toEqual({
      expected_version: 2,
      reason: "配置 11c 真机登录",
    });
  });

  it("reuses a created strategy when configure fails and the workflow is retried", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useBusinessTerminalsStore();
    const createAsset = vi.spyOn(apiClient, "create_automation_asset").mockResolvedValue({
      data: automationAsset,
      correlation_id: "corr-asset",
    });
    const createStrategy = vi.spyOn(apiClient, "create_login_strategy").mockResolvedValue({
      data: createdLoginStrategy,
      correlation_id: "corr-strategy",
    });
    vi.spyOn(apiClient, "get_login_strategy").mockResolvedValue({
      data: createdLoginStrategy,
      correlation_id: "corr-get",
    });
    const configure = vi
      .spyOn(apiClient, "update_login_strategy")
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce({
        data: { ...createdLoginStrategy, lifecycle_status: "DRAFT", row_version: 2 },
        correlation_id: "corr-configure",
      });
    vi.spyOn(apiClient, "activate_login_strategy").mockResolvedValue({
      data: { ...createdLoginStrategy, lifecycle_status: "ACTIVE", row_version: 3 },
      correlation_id: "corr-activate",
    });
    const body = {
      project_id: projectId,
      display_name: "11c 登录策略",
      captcha_policy: "NONE" as const,
      reason: "正式配置",
    };

    await expect(store.createAndActivateLoginStrategy(body)).rejects.toThrow();
    await expect(store.createAndActivateLoginStrategy(body)).resolves.toMatchObject({
      lifecycle_status: "ACTIVE",
    });

    expect(createAsset).toHaveBeenCalledTimes(1);
    expect(createStrategy).toHaveBeenCalledTimes(1);
    expect(configure).toHaveBeenCalledTimes(2);
    expect(configure.mock.calls[0]?.[2]).toEqual(configure.mock.calls[1]?.[2]);
  });

  it("reuses the configured strategy when activation fails and is retried", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useBusinessTerminalsStore();
    vi.spyOn(apiClient, "create_automation_asset").mockResolvedValue({
      data: automationAsset,
      correlation_id: "corr-asset",
    });
    const createStrategy = vi.spyOn(apiClient, "create_login_strategy").mockResolvedValue({
      data: createdLoginStrategy,
      correlation_id: "corr-strategy",
    });
    const draft: LoginStrategyResource = {
      ...createdLoginStrategy,
      lifecycle_status: "DRAFT",
      row_version: 2,
    };
    const configure = vi.spyOn(apiClient, "update_login_strategy").mockResolvedValue({
      data: draft,
      correlation_id: "corr-configure",
    });
    vi.spyOn(apiClient, "get_login_strategy").mockResolvedValue({
      data: draft,
      correlation_id: "corr-get",
    });
    const activate = vi
      .spyOn(apiClient, "activate_login_strategy")
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce({
        data: { ...draft, lifecycle_status: "ACTIVE", row_version: 3 },
        correlation_id: "corr-activate",
      });
    const body = {
      project_id: projectId,
      display_name: "11c 登录策略",
      captcha_policy: "NONE" as const,
      reason: "正式配置",
    };

    await expect(store.createAndActivateLoginStrategy(body)).rejects.toThrow();
    await expect(store.createAndActivateLoginStrategy(body)).resolves.toMatchObject({
      lifecycle_status: "ACTIVE",
    });

    expect(createStrategy).toHaveBeenCalledTimes(1);
    expect(configure).toHaveBeenCalledTimes(1);
    expect(activate).toHaveBeenCalledTimes(2);
    expect(activate.mock.calls[0]?.[2]).toEqual(activate.mock.calls[1]?.[2]);
  });

  it("hides revision mutation actions from a view-only principal", async () => {
    await setup(["PROJECT_VIEW", "BUSINESS_TERMINAL_VIEW"], [draftRevision]);
    await fireEvent.click(await screen.findByRole("button", { name: "详情" }));
    const dialog = await screen.findByRole("dialog", { name: "业务终端详情" });
    await waitFor(() => expect(within(dialog).getByText("https://example.test/app")).toBeTruthy());
    expect(within(dialog).queryByRole("button", { name: "校验" })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: "发布" })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: "编辑" })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: "放弃" })).toBeNull();
  });

  it("offers edit validate abandon and gated publish for a DRAFT revision", async () => {
    await setup(undefined, [draftRevision]);
    await fireEvent.click(await screen.findByRole("button", { name: "详情" }));
    const dialog = await screen.findByRole("dialog", { name: "业务终端详情" });

    expect(within(dialog).getByRole("button", { name: "编辑" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "校验" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "放弃" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "发布" })).toHaveProperty("disabled", true);
  });

  it("offers return-to-draft and publish for a VALIDATING revision", async () => {
    await setup(undefined, [validatingRevision]);
    await fireEvent.click(await screen.findByRole("button", { name: "详情" }));
    const dialog = await screen.findByRole("dialog", { name: "业务终端详情" });

    expect(within(dialog).getByRole("button", { name: "返回草稿" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "发布" })).toBeTruthy();
    expect(within(dialog).queryByRole("button", { name: "编辑" })).toBeNull();
  });

  it("returns a VALIDATING revision to DRAFT through the formal command", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useBusinessTerminalsStore();
    store.revisions.push(validatingRevision);
    const returned = {
      ...validatingRevision,
      lifecycle_status: "DRAFT" as const,
      row_version: 3,
    };
    const command = vi
      .spyOn(apiClient, "return_to_draft_environment_terminal_access_revision")
      .mockResolvedValue({
        data: returned,
        correlation_id: "return-correlation",
      });

    await expect(
      store.returnRevisionToDraft(validatingRevision, "修正校验发现的配置错误"),
    ).resolves.toEqual(returned);

    expect(command).toHaveBeenCalledWith(
      validatingRevision.environment_terminal_access_revision_id,
      {
        expected_version: validatingRevision.row_version,
        reason: "修正校验发现的配置错误",
      },
      expect.any(Object),
    );
    expect(store.revisions[0]).toEqual(returned);
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

  it("refreshes the terminal pointer and full revision history after publish", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useBusinessTerminalsStore();
    store.revisions.push(draftRevision);
    const published = {
      ...draftRevision,
      lifecycle_status: "PUBLISHED" as const,
      published_at: "2026-09-04T07:52:22Z",
      row_version: 2,
    };
    const previous = {
      ...draftRevision,
      environment_terminal_access_revision_id: "S".repeat(26),
      revision_no: 0,
      lifecycle_status: "SUPERSEDED" as const,
    };
    const refreshedTerminal = {
      ...terminal,
      current_published_revision_id: published.environment_terminal_access_revision_id,
      row_version: 2,
    };
    vi.spyOn(apiClient, "publish_environment_terminal_access_revision").mockResolvedValue({
      data: published,
      correlation_id: "publish-correlation",
    });
    vi.spyOn(apiClient, "get_business_terminal").mockResolvedValue({
      data: refreshedTerminal,
      correlation_id: "terminal-correlation",
    });
    vi.spyOn(apiClient, "list_environment_terminal_access_revision").mockResolvedValue({
      items: [published, previous],
      page: { page: 1, page_size: 200, total: 2 },
    });

    await expect(store.publishRevision(draftRevision, terminal, "发布")).resolves.toEqual(
      published,
    );
    expect(store.current).toEqual(refreshedTerminal);
    expect(store.revisions).toEqual([published, previous]);
  });
});
