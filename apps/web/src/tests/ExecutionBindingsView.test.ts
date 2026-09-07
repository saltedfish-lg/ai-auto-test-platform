import { fireEvent, render, screen, waitFor, within } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type {
  ExecutionBindingSnapshotResource,
  RuntimePolicyRevisionResource,
} from "../generated/types";
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
  runner_heartbeat_at: "2026-09-01T00:00:00Z",
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
    retry_mode: "UNIFIED",
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
    acquired_at: "2026-09-01T00:00:00Z",
    expires_at: "2026-09-01T00:10:00Z",
    fencing_generation: 7,
    row_version: 1,
  },
  runner_lease: {
    resource_lease_id: "N".repeat(26),
    resource_type: "RUNNER",
    resource_identity: "runner:FORMAL_EXECUTION_SLOT:slot-1",
    owner_type: "EXECUTION_ATTEMPT",
    owner_id: "A".repeat(26),
    status: "ACTIVE",
    acquired_at: "2026-09-01T00:00:00Z",
    expires_at: "2026-09-01T00:02:00Z",
    fencing_generation: 11,
    row_version: 1,
  },
  owner_execution_identity: "attempt-owner-1",
  correlation_id: "binding-correlation",
  status: "READY",
  row_version: 1,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const publishedPolicy: RuntimePolicyRevisionResource = {
  runtime_policy_revision_id: "Y".repeat(26),
  project_id: projectId,
  revision_no: 1,
  browser_runtime: "CHROMIUM",
  artifact_policy: "SCREENSHOT",
  timeout_seconds: 30,
  max_steps: 20,
  total_exploration_timeout_seconds: 600,
  model_transient_retry_per_step: 1,
  allowed_origins: ["https://ecloud-uat.galasystec.net.cn"],
  authentication_redirect_origins: ["https://ecloud-uat.galasystec.net.cn"],
  retry_mode: "UNIFIED_OWNER",
  network_requirement: "INTERNET",
  serial_execution_policy: "SINGLE_PROCESS_UNIFIED_RETRY",
  lifecycle_status: "PUBLISHED",
  row_version: 1,
};

describe("Execution binding management view", () => {
  beforeEach(() => vi.restoreAllMocks());

  async function setup(): Promise<void> {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(currentUser({ permissions: ["PROJECT_VIEW", "PROJECT_EDIT"] })),
    );
    await useSessionStore().login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "list_execution_binding_snapshots").mockResolvedValue({
      items: [binding],
      page: { page: 1, page_size: 50, total: 1 },
    });
    vi.spyOn(apiClient, "list_project_runtime_policy_revisions").mockResolvedValue({
      items: [],
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects/:projectId/execution-bindings", component: ExecutionBindingsView },
        { path: "/projects/:id", name: "projects.detail", component: { template: "<div />" } },
      ],
    });
    await router.push(`/projects/${projectId}/execution-bindings`);
    await router.isReady();
    render(ExecutionBindingsView, { global: { plugins: [pinia, ElementPlus, router] } });
  }

  it("shows frozen facts and submits an owner/fencing-aware release", async () => {
    await setup();
    expect(await screen.findByText("B".repeat(26))).toBeTruthy();
    expect(screen.getByText("ACTIVE / gen 7")).toBeTruthy();
    expect(screen.getByText("ACTIVE / gen 11")).toBeTruthy();

    const release = vi.spyOn(apiClient, "release_execution_binding_snapshot").mockResolvedValue({
      data: {
        ...binding,
        status: "RELEASED",
        row_version: 2,
        identity_lease: { ...binding.identity_lease, status: "RELEASED" },
        runner_lease: { ...binding.runner_lease, status: "RELEASED" },
      },
      correlation_id: "release-correlation",
    });
    await fireEvent.click(screen.getByRole("button", { name: "释放" }));
    await fireEvent.update(screen.getByLabelText("原因"), "normal completion");
    await fireEvent.click(screen.getByRole("button", { name: "确认" }));

    await waitFor(() => expect(release).toHaveBeenCalledTimes(1));
    expect(release.mock.calls[0]?.[1]).toEqual({
      owner_execution_identity: "attempt-owner-1",
      expected_version: 1,
      identity_lease_generation: 7,
      runner_lease_generation: 11,
      reason: "normal completion",
    });
  });

  it("creates and publishes an immutable RuntimePolicy revision", async () => {
    await setup();
    const create = vi
      .spyOn(apiClient, "create_project_runtime_policy_revision")
      .mockResolvedValue({ data: publishedPolicy, correlation_id: "policy-correlation" });

    await fireEvent.click(screen.getByRole("button", { name: "新建 RuntimePolicy" }));
    const dialog = screen.getByRole("dialog", {
      name: "创建并发布 RuntimePolicy Revision",
    });
    await fireEvent.update(
      within(dialog).getByLabelText("Allowed Origins"),
      "https://ecloud-uat.galasystec.net.cn",
    );
    await fireEvent.update(within(dialog).getByLabelText("创建发布原因"), "Runner 真机闭环");
    await fireEvent.click(within(dialog).getByRole("button", { name: "创建并发布" }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0]?.[0]).toMatchObject({
      project_id: projectId,
      browser_runtime: "CHROMIUM",
      allowed_origins: ["https://ecloud-uat.galasystec.net.cn"],
      reason: "Runner 真机闭环",
    });
  });
});
