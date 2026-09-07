import { fireEvent, render, screen, waitFor, within } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type { RunnerCapabilityResource, RunnerResource } from "../generated/types";
import { useSessionStore } from "../stores/session";
import RunnersView from "../views/RunnersView.vue";
import { authenticationResponse, currentUser } from "./auth-fixtures";

const projectId = "P".repeat(26);
const runner: RunnerResource = {
  runner_id: "R".repeat(26),
  project_id: projectId,
  runner_code: "RUNNER-01",
  display_name: "本地 Runner",
  lifecycle_status: "REGISTERED",
  registration_status: "REGISTERED",
  connection_status: "OFFLINE",
  health_status: "UNKNOWN",
  enable_status: "DISABLED",
  project_binding_status: "BOUND",
  scheduling_status: "UNSCHEDULABLE",
  resource_status: "AVAILABLE",
  version_compatibility: "UNKNOWN",
  last_heartbeat_at: null,
  registered_at: "2026-08-29T00:00:00Z",
  runtime_metadata: null,
  capabilities: [],
  row_version: 1,
  created_at: "2026-08-29T00:00:00Z",
  updated_at: "2026-08-29T00:00:00Z",
};

const pendingCapability: RunnerCapabilityResource = {
  runner_capability_id: "C".repeat(26),
  capability_code: "BROWSER_CHROMIUM",
  capability_type: "BROWSER",
  availability_status: "CONFIGURED",
  validation_status: "PENDING",
  observed_version: "1.62.1",
  observed_metadata: { browser: "chromium" },
  lifecycle_status: "ACTIVE",
  reported_at: "2026-09-03T00:00:00Z",
  row_version: 3,
};

describe("Runner management view", () => {
  beforeEach(() => vi.restoreAllMocks());

  async function setup(runnerValue: RunnerResource = runner) {
    const pinia = createPinia();
    setActivePinia(pinia);
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
      authenticationResponse(
        currentUser({ permissions: ["PROJECT_VIEW", "RUNNER_BIND", "RUNNER_REGISTER"] }),
      ),
    );
    await useSessionStore().login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "list_runner").mockResolvedValue({
      items: [runnerValue],
      page: { page: 1, page_size: 50, total: 1 },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects/:projectId/runners", component: RunnersView },
        { path: "/projects/:id", name: "projects.detail", component: { template: "<div />" } },
      ],
    });
    await router.push(`/projects/${projectId}/runners`);
    await router.isReady();
    render(RunnersView, { global: { plugins: [pinia, ElementPlus, router] } });
  }

  it("loads only the route Project and renders separated Runner facts", async () => {
    await setup();

    expect(await screen.findByText("RUNNER-01")).toBeTruthy();
    expect(screen.getByText("OFFLINE / UNKNOWN")).toBeTruthy();
    expect(screen.getAllByText("REGISTERED").length).toBeGreaterThan(0);
    expect(apiClient.list_runner).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ project_id: projectId }),
      }),
    );
  });

  it("creates a project-scoped enrollment and shows its credential once", async () => {
    await setup();
    const create = vi.spyOn(apiClient, "create_runner_enrollment").mockResolvedValue({
      data: {
        enrollment_id: "E".repeat(26),
        project_id: projectId,
        runner_code: "RUNNER-02",
        display_name: null,
        enrollment_status: "PENDING",
        enrollment_credential: "enr_" + "e".repeat(48),
        row_version: 1,
        created_at: "2026-08-29T00:00:00Z",
      },
      correlation_id: "runner-enrollment-correlation",
    });

    await fireEvent.click(screen.getByRole("button", { name: "创建 Enrollment" }));
    await fireEvent.update(screen.getByLabelText("Runner Code"), "RUNNER-02");
    await fireEvent.update(screen.getByLabelText("原因"), "bootstrap local runner");
    const dialog = screen.getByRole("dialog", { name: "创建 Project-scoped Enrollment" });
    await fireEvent.click(dialog.querySelector("button.el-button--primary")!);

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0]?.[0]).toMatchObject({
      project_id: projectId,
      runner_code: "RUNNER-02",
      reason: "bootstrap local runner",
    });
    expect(await screen.findByDisplayValue("enr_" + "e".repeat(48))).toBeTruthy();
    expect(screen.getByText(/平台无法恢复明文/)).toBeTruthy();
  });

  it("validates only a machine-reported pending capability with evidence", async () => {
    const readyRunner: RunnerResource = {
      ...runner,
      lifecycle_status: "ACTIVE",
      connection_status: "ONLINE",
      health_status: "HEALTHY",
      enable_status: "ENABLED",
      scheduling_status: "IDLE",
      last_heartbeat_at: "2026-09-03T00:00:00Z",
      capabilities: [pendingCapability],
      row_version: 7,
    };
    await setup(readyRunner);
    const validate = vi.spyOn(apiClient, "validate_runner_capability").mockResolvedValue({
      data: {
        ...readyRunner,
        row_version: 8,
        capabilities: [{ ...pendingCapability, validation_status: "VALID", row_version: 4 }],
      },
      correlation_id: "corr-capability",
    });

    await fireEvent.click(await screen.findByRole("button", { name: "验证能力" }));
    const dialog = screen.getByRole("dialog", { name: "验证 Runner Capability" });
    await fireEvent.update(
      within(dialog).getByLabelText("运行证据摘要"),
      "Chromium launched and reached the approved UAT origin",
    );
    await fireEvent.update(within(dialog).getByLabelText("验证原因"), "Runner 真机验证");
    await fireEvent.click(within(dialog).getByRole("button", { name: "确认验证" }));

    await waitFor(() => expect(validate).toHaveBeenCalledTimes(1));
    expect(validate.mock.calls[0]?.slice(0, 3)).toEqual([
      runner.runner_id,
      "BROWSER_CHROMIUM",
      {
        expected_capability_version: 3,
        evidence_summary: "Chromium launched and reached the approved UAT origin",
        reason: "Runner 真机验证",
      },
    ]);
  });
});
