import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type { ExecutionBindingSnapshotResource } from "../generated/types";
import { useSessionStore } from "../stores/session";
import ExecutionBindingsView from "../views/ExecutionBindingsView.vue";
import { authenticationResponse, currentUser } from "./auth-fixtures";

const projectId = "P".repeat(26);
const binding: ExecutionBindingSnapshotResource = {
  execution_binding_snapshot_id: "B".repeat(26),
  execution_attempt_id: "A".repeat(26),
  project_id: projectId,
  environment_id: "E".repeat(26),
  business_terminal_id: "T".repeat(26),
  terminal_access_revision_id: "V".repeat(26),
  login_strategy_id: "L".repeat(26),
  login_strategy_row_version: 3,
  test_account_id: "C".repeat(26),
  credential_revision_id: "D".repeat(26),
  account_mapping_revision_id: "M".repeat(26),
  runner_id: "R".repeat(26),
  runner_row_version: 5,
  runner_heartbeat_at: "2026-09-08T00:00:00Z",
  runner_capabilities: [],
  runtime_policy: {
    runtime_policy_revision_id: "Y".repeat(26),
    revision_no: 2,
    browser_runtime: "CHROMIUM",
    artifact_policy: "SCREENSHOT",
    timeout_seconds: 600,
    max_steps: 50,
    total_exploration_timeout_seconds: 1800,
    model_transient_retry_per_step: 2,
    allowed_origins: [],
    authentication_redirect_origins: [],
    retry_mode: "UNIFIED_OWNER",
    network_requirement: "INTRANET",
    serial_execution_policy: "SINGLE_PROCESS_UNIFIED_RETRY",
  },
  identity_lease: {
    resource_lease_id: "I".repeat(26),
    resource_type: "IDENTITY",
    resource_identity: "project:environment:identity",
    owner_type: "FORMAL_ROOT_EXECUTION_TASK",
    owner_id: "Q".repeat(26),
    status: "ACTIVE",
    acquired_at: "2026-09-08T00:00:00Z",
    expires_at: "2026-09-08T00:10:00Z",
    fencing_generation: 7,
    row_version: 1,
  },
  runner_lease: {
    resource_lease_id: "N".repeat(26),
    resource_type: "RUNNER",
    resource_identity: `R${"R".repeat(25)}:FORMAL_EXECUTION_SLOT:${"S".repeat(26)}`,
    owner_type: "EXECUTION_ATTEMPT",
    owner_id: "A".repeat(26),
    status: "ACTIVE",
    acquired_at: "2026-09-08T00:00:00Z",
    expires_at: "2026-09-08T00:02:00Z",
    fencing_generation: 11,
    row_version: 1,
  },
  owner_execution_identity: "Q".repeat(26),
  correlation_id: "binding-correlation",
  status: "READY",
  row_version: 1,
  created_at: "2026-09-08T00:00:00Z",
  updated_at: "2026-09-08T00:00:00Z",
};

describe("Execution binding business UI", () => {
  beforeEach(() => vi.restoreAllMocks());

  async function setup() {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(
        currentUser({ permissions: ["PROJECT_VIEW", "PROJECT_EDIT", "RUN_TASK_CREATE"] }),
      ),
    );
    await useSessionStore().login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "list_execution_binding_snapshots").mockResolvedValue({
      items: [binding],
      page: { page: 1, page_size: 50, total: 1 },
    });
    vi.spyOn(apiClient, "list_project_runtime_policy_revisions").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "list_environment").mockResolvedValue({
      items: [
        {
          environment_id: "E".repeat(26),
          project_id: projectId,
          environment_code: "UAT",
          display_name: "UAT 环境",
          lifecycle_status: "ACTIVE",
          enablement_state: "ENABLED",
        } as any,
      ],
      page: { page: 1, page_size: 200, total: 1 },
    });
    vi.spyOn(apiClient, "list_runner").mockResolvedValue({
      items: [
        {
          runner_id: "R".repeat(26),
          project_id: projectId,
          runner_code: "RUNNER-01",
          display_name: "本机 Runner",
          lifecycle_status: "ACTIVE",
          registration_status: "REGISTERED",
          enable_status: "ENABLED",
          project_binding_status: "BOUND",
          connection_status: "ONLINE",
          health_status: "HEALTHY",
          version_compatibility: "COMPATIBLE",
          scheduling_status: "IDLE",
          resource_status: "AVAILABLE",
        } as any,
      ],
      page: { page: 1, page_size: 200, total: 1 },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects/:projectId/execution-bindings", component: ExecutionBindingsView },
        { path: "/projects/:id", name: "projects.detail", component: { template: "<div />" } },
        { path: "/ai-exploration", name: "ai.exploration", component: { template: "<div />" } },
      ],
    });
    await router.push(`/projects/${projectId}/execution-bindings`);
    await router.isReady();
    render(ExecutionBindingsView, { global: { plugins: [pinia, ElementPlus, router] } });
    return router;
  }

  it("renders binding and lease states in Chinese", async () => {
    await setup();
    expect(await screen.findByText("就绪")).toBeTruthy();
    expect(screen.getByText("生效中 · 第 7 代")).toBeTruthy();
    expect(screen.getByText("生效中 · 第 11 代")).toBeTruthy();
    expect(screen.queryByText("READY")).toBeNull();
  });

  it("opens a business-selector form instead of editable relation ID fields", async () => {
    await setup();
    await fireEvent.click(screen.getByRole("button", { name: "新建执行绑定" }));
    expect(await screen.findByRole("dialog", { name: "新建执行绑定" })).toBeTruthy();
    for (const label of ["执行环境", "执行 Runner", "业务终端", "测试账号", "运行策略", "正式执行资源"]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    for (const legacy of ["Environment ID", "Runner ID", "TestAccount ID", "Runner Resource Identity", "ExecutionAttempt ID"]) {
      expect(screen.queryByLabelText(legacy)).toBeNull();
    }
    expect(screen.getByText("AI 探索")).toBeTruthy();
    expect(screen.getByText("正式执行")).toBeTruthy();
  });

  it("routes a ready binding into AI exploration without asking for an Attempt ID", async () => {
    const router = await setup();
    await fireEvent.click(await screen.findByRole("button", { name: "详情" }));
    await fireEvent.click(await screen.findByRole("button", { name: "使用此绑定进行 AI 探索" }));
    await waitFor(() => {
      expect(router.currentRoute.value.name).toBe("ai.exploration");
      expect(router.currentRoute.value.query.execution_attempt_id).toBe(binding.execution_attempt_id);
    });
  });

  it("uses Chinese runtime-policy terminology", async () => {
    await setup();
    await fireEvent.click(screen.getByRole("button", { name: "新建运行策略" }));
    expect(await screen.findByRole("dialog", { name: "创建并发布运行策略修订" })).toBeTruthy();
    expect(screen.getByText("浏览器运行时")).toBeTruthy();
    expect(screen.getByText("制品策略")).toBeTruthy();
    expect(screen.getByText("网络要求")).toBeTruthy();
  });
});
