import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { ApiRequestError } from "../api/errors";
import type {
  AIExplorationSessionResource,
  AIExplorationStepResource,
  ProjectResource,
} from "../generated/types";
import { useAIExplorationsStore } from "../stores/aiExplorations";
import { useProjectsStore } from "../stores/projects";
import AIExplorationView from "../views/AIExplorationView.vue";

const project: ProjectResource = {
  project_id: "01JPROJECT00000000000000001",
  project_code: "ATP-DEMO",
  display_name: "自动化平台",
  lifecycle_status: "ACTIVE",
  row_version: 3,
  owners: [],
  created_at: "2026-08-25T00:00:00Z",
  updated_at: "2026-08-25T00:00:00Z",
};

const readySession: AIExplorationSessionResource = {
  session_id: "01JSESSION00000000000000001",
  ai_task_id: "01JTASK000000000000000000001",
  execution_attempt_id: null,
  execution_binding_snapshot_id: null,
  browser_session_id: null,
  project_id: project.project_id,
  source_case_id: null,
  objective: "验证有效用户能够登录并进入工作台",
  target_url: "https://example.test/login",
  lifecycle_status: "READY",
  current_step_sequence: 0,
  current_observation_id: null,
  max_steps: 50,
  total_timeout_seconds: 1800,
  model_transient_retry_per_step: 2,
  row_version: 1,
  resolved_model_config_id: "01JMODEL000000000000000001",
  resolved_model_display_name: "AI探索默认模型",
  resolved_provider_code: "OPENAI",
  resolved_model_name: "gpt-test",
  plan: {
    goal: "进入工作台",
    assumptions: ["已存在有效账号"],
    steps: [
      {
        sequence: 1,
        intent: "打开登录页",
        expected_observation: "页面展示登录表单",
      },
    ],
  },
  failure_code: null,
  failure_message: null,
  total_deadline_at: null,
  started_at: null,
  terminal_at: null,
  cancel_requested_at: null,
  created_by: "01JUSER0000000000000000001",
  created_at: "2026-08-25T00:00:00Z",
  updated_at: "2026-08-25T00:00:01Z",
};

const runningSession: AIExplorationSessionResource = {
  ...readySession,
  execution_attempt_id: "01JATTEMPT0000000000000001",
  execution_binding_snapshot_id: "01JBINDING0000000000000001",
  browser_session_id: null,
  lifecycle_status: "RUNNING",
  max_steps: 50,
  total_timeout_seconds: 1800,
  model_transient_retry_per_step: 2,
  row_version: 2,
  started_at: "2026-08-25T00:00:02Z",
  total_deadline_at: "2026-08-25T00:30:02Z",
};

const completedStep: AIExplorationStepResource = {
  ai_exploration_step_id: "01JSTEP000000000000000001",
  session_id: readySession.session_id,
  execution_attempt_id: runningSession.execution_attempt_id!,
  sequence: 1,
  model_call_identity: "01JCALL000000000000000001",
  observation_identity: "01JOBSERVATION000000000001",
  action_identity: "01JACTION0000000000000001",
  status: "COMPLETION_PROPOSED",
  observation: { current_url: "https://example.test/dashboard", title: "Dashboard" },
  action: { type: "goal_completed", reason: "Dashboard is visible" },
  action_result: { status: "COMPLETION_ACCEPTED" },
  sanitized_reason: "Dashboard is visible",
  failure_code: null,
  state_version: 3,
  identity_lease_generation: 1,
  runner_lease_generation: 1,
  started_at: "2026-08-25T00:00:03Z",
  completed_at: "2026-08-25T00:00:04Z",
};

async function renderView() {
  vi.spyOn(apiClient, "list_execution_binding_snapshots").mockResolvedValue({
    items: [
      {
        execution_binding_snapshot_id: "01JBINDING0000000000000001",
        execution_attempt_id: "01JATTEMPT0000000000000001",
        project_id: project.project_id,
        environment_id: "01JENV00000000000000000001",
        business_terminal_id: "01JTERM0000000000000000001",
        runner_id: "01JRUNNER00000000000000001",
        status: "READY",
      } as any,
    ],
    page: { page: 1, page_size: 50, total: 1 },
  });
  vi.spyOn(apiClient, "list_environment").mockResolvedValue({
    items: [{ environment_id: "01JENV00000000000000000001", environment_code: "UAT", display_name: "UAT 环境", lifecycle_status: "ACTIVE" } as any],
    page: { page: 1, page_size: 200, total: 1 },
  });
  vi.spyOn(apiClient, "list_business_terminal").mockResolvedValue({
    items: [{ business_terminal_id: "01JTERM0000000000000000001", terminal_code: "ADMIN", display_name: "管理端", terminal_type: "MANAGEMENT", lifecycle_status: "ACTIVE" } as any],
    page: { page: 1, page_size: 200, total: 1 },
  });
  vi.spyOn(apiClient, "list_runner").mockResolvedValue({
    items: [{ runner_id: "01JRUNNER00000000000000001", runner_code: "RUNNER-01", display_name: "本机 Runner" } as any],
    page: { page: 1, page_size: 200, total: 1 },
  });
  const pinia = createPinia();
  setActivePinia(pinia);
  const projects = useProjectsStore();
  projects.items = [project];
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/ai-exploration", component: AIExplorationView }],
  });
  await router.push(`/ai-exploration?project_id=${project.project_id}`);
  await router.isReady();
  render(AIExplorationView, { global: { plugins: [pinia, ElementPlus, router] } });
  return { pinia, router };
}

describe("AI 探索规划页面（组件测试，API 为 mock）", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("creates a session and renders the resolved model snapshot and structured plan", async () => {
    const create = vi.spyOn(apiClient, "create_ai_exploration_session").mockResolvedValue({
      data: readySession,
      correlation_id: "exploration-correlation",
    });
    await renderView();

    await fireEvent.update(screen.getByLabelText("测试目标"), "验证有效用户能够登录并进入工作台");
    await fireEvent.update(screen.getByLabelText("目标页面地址"), "https://example.test/login");
    await fireEvent.click(screen.getByRole("button", { name: "创建并开始规划" }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0]?.[0]).toEqual({
      project_id: project.project_id,
      objective: "验证有效用户能够登录并进入工作台",
      target_url: "https://example.test/login",
    });
    expect(await screen.findByText("AI探索默认模型")).toBeTruthy();
    expect(screen.getByText("OPENAI / gpt-test")).toBeTruthy();
    expect(screen.getByText("进入工作台")).toBeTruthy();
    expect(screen.getByText("打开登录页")).toBeTruthy();
    expect(screen.getByText("预期观察：页面展示登录表单")).toBeTruthy();
    expect(screen.getByText("就绪")).toBeTruthy();
  });

  it("renders a persisted FAILED result without inventing a plan", async () => {
    await renderView();
    const explorations = useAIExplorationsStore();
    explorations.current = {
      ...readySession,
      lifecycle_status: "FAILED",
      plan: null,
      failure_code: "AI_EXPLORATION_MODEL_UNAVAILABLE",
      failure_message: "The configured AI exploration model is currently unavailable.",
    };

    expect(await screen.findByText("AI 探索默认模型当前不可用，请稍后重试。")).toBeTruthy();
    expect(screen.getByText("错误码：AI_EXPLORATION_MODEL_UNAVAILABLE")).toBeTruthy();
    expect(screen.queryByLabelText("探索步骤")).toBeNull();
  });

  it("reuses the idempotency key after an uncertain network result", async () => {
    const create = vi
      .spyOn(apiClient, "create_ai_exploration_session")
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce({ data: readySession, correlation_id: "retry-correlation" });
    const { pinia } = await renderView();
    const explorations = useAIExplorationsStore(pinia);
    const request = {
      project_id: project.project_id,
      objective: readySession.objective,
      target_url: readySession.target_url,
    };

    await expect(explorations.create(request)).rejects.toThrow("network unavailable");
    await explorations.create(request);

    expect(create.mock.calls[0]?.[1].headers["Idempotency-Key"]).toBe(
      create.mock.calls[1]?.[1].headers["Idempotency-Key"],
    );
  });

  it.each([
    [409, "request is still planning"],
    [500, "response outcome is uncertain"],
  ])("reuses the idempotency key after HTTP %i", async (status, message) => {
    const create = vi
      .spyOn(apiClient, "create_ai_exploration_session")
      .mockRejectedValueOnce(new ApiRequestError(status, message))
      .mockResolvedValueOnce({ data: readySession, correlation_id: "retry-correlation" });
    const { pinia } = await renderView();
    const explorations = useAIExplorationsStore(pinia);
    const request = {
      project_id: project.project_id,
      objective: readySession.objective,
      target_url: readySession.target_url,
    };

    await expect(explorations.create(request)).rejects.toThrow(message);
    await explorations.create(request);

    expect(create.mock.calls[0]?.[1].headers["Idempotency-Key"]).toBe(
      create.mock.calls[1]?.[1].headers["Idempotency-Key"],
    );
  });

  it("rotates the idempotency key when the request body changes", async () => {
    const create = vi
      .spyOn(apiClient, "create_ai_exploration_session")
      .mockRejectedValueOnce(new ApiRequestError(422, "invalid request"))
      .mockResolvedValueOnce({ data: readySession, correlation_id: "retry-correlation" });
    const { pinia } = await renderView();
    const explorations = useAIExplorationsStore(pinia);
    const request = {
      project_id: project.project_id,
      objective: readySession.objective,
      target_url: readySession.target_url,
    };

    await expect(explorations.create(request)).rejects.toThrow("invalid request");
    await explorations.create({ ...request, objective: `${request.objective} updated` });

    expect(create.mock.calls[0]?.[1].headers["Idempotency-Key"]).not.toBe(
      create.mock.calls[1]?.[1].headers["Idempotency-Key"],
    );
  });

  it("starts the bound Attempt, refreshes ordered evidence, and renders terminal state", async () => {
    const start = vi.spyOn(apiClient, "start_ai_exploration_session").mockResolvedValue({
      data: runningSession,
      correlation_id: "start-correlation",
    });
    vi.spyOn(apiClient, "get_ai_exploration_session").mockResolvedValue({
      data: {
        ...runningSession,
        lifecycle_status: "SUCCEEDED",
        current_step_sequence: 1,
        current_observation_id: completedStep.observation_identity,
        row_version: 5,
        terminal_at: completedStep.completed_at,
      },
      correlation_id: "status-correlation",
    });
    vi.spyOn(apiClient, "list_ai_exploration_steps").mockResolvedValue({
      items: [completedStep],
      correlation_id: "steps-correlation",
    });
    const { pinia } = await renderView();
    const explorations = useAIExplorationsStore(pinia);
    explorations.current = readySession;

    expect(await screen.findByLabelText("执行绑定 / 执行实例")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "启动已绑定 Runner" }));

    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    expect(start.mock.calls[0]?.[1]).toEqual({
      execution_attempt_id: runningSession.execution_attempt_id,
      expected_row_version: readySession.row_version,
    });
    expect(await screen.findByText("成功")).toBeTruthy();
    expect(await screen.findByText("goal_completed")).toBeTruthy();
    expect(screen.getByText("Dashboard · https://example.test/dashboard")).toBeTruthy();
  });

  it("reuses Start Idempotency-Key after an uncertain response", async () => {
    const start = vi
      .spyOn(apiClient, "start_ai_exploration_session")
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce({ data: runningSession, correlation_id: "start-correlation" });
    const { pinia } = await renderView();
    const explorations = useAIExplorationsStore(pinia);
    explorations.current = readySession;
    const body = {
      execution_attempt_id: runningSession.execution_attempt_id!,
      expected_row_version: readySession.row_version,
    };

    await expect(explorations.start(readySession.session_id, body)).rejects.toThrow(
      "network unavailable",
    );
    await explorations.start(readySession.session_id, body);

    expect(start.mock.calls[0]?.[2].headers["Idempotency-Key"]).toBe(
      start.mock.calls[1]?.[2].headers["Idempotency-Key"],
    );
  });
});
