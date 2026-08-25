import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { ApiRequestError } from "../api/errors";
import type { AIExplorationSessionResource, ProjectResource } from "../generated/types";
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
  project_id: project.project_id,
  source_case_id: null,
  objective: "验证有效用户能够登录并进入工作台",
  target_url: "https://example.test/login",
  lifecycle_status: "READY",
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
  created_by: "01JUSER0000000000000000001",
  created_at: "2026-08-25T00:00:00Z",
  updated_at: "2026-08-25T00:00:01Z",
};

async function renderView() {
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
    expect(screen.getByText("READY")).toBeTruthy();
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
});
