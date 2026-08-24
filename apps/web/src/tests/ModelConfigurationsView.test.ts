import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type { ModelConfigResource } from "../generated/types";
import { useModelConfigurationsStore } from "../stores/modelConfigurations";
import { useSessionStore } from "../stores/session";
import ModelConfigurationsView from "../views/ModelConfigurationsView.vue";
import { authenticationResponse, currentUser } from "./auth-fixtures";

const SECRET_VALUE = "test-secret-must-never-render";

function configuration(overrides: Partial<ModelConfigResource> = {}): ModelConfigResource {
  return {
    model_config_id: "01JMODEL000000000000000001",
    config_code: "OPENAI-PRIMARY",
    display_name: "主探索模型",
    provider_code: "OPENAI",
    model_name: "gpt-test",
    request_timeout_seconds: 30,
    lifecycle_status: "CONFIGURING",
    secret_configured: true,
    is_ai_exploration_default: false,
    ai_exploration_default_version: null,
    row_version: 1,
    created_at: "2026-08-24T00:00:00Z",
    updated_at: "2026-08-24T00:00:00Z",
    ...overrides,
  };
}

function listResponse(items: ModelConfigResource[]) {
  return { items, page: { page: 1, page_size: 20, total: items.length } };
}

function pageResponse(items: ModelConfigResource[], page: number, total: number) {
  return { items, page: { page, page_size: 200, total } };
}

async function renderAuthenticated(permissions = ["MODEL_CONFIGURATION_MANAGE"]) {
  const pinia = createPinia();
  setActivePinia(pinia);
  vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
    authenticationResponse(currentUser({ permissions })),
  );
  await useSessionStore().login({ username: "model-admin", password: "input-only" });
  return render(ModelConfigurationsView, {
    global: { plugins: [pinia, ElementPlus] },
  });
}

describe("AI 模型配置页面", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows governed fields and configured status without ever rendering the stored secret or base URL", async () => {
    const item = configuration();
    vi.spyOn(apiClient, "list_model_config").mockResolvedValue(listResponse([item]));
    vi.spyOn(apiClient, "get_model_config").mockResolvedValue({
      data: item,
      correlation_id: "model-detail",
    });
    await renderAuthenticated();

    expect(await screen.findByText("OPENAI-PRIMARY")).toBeTruthy();
    expect(screen.getByText("gpt-test")).toBeTruthy();
    expect(screen.getByText("已配置")).toBeTruthy();
    expect(screen.queryByText(SECRET_VALUE)).toBeNull();
    expect(screen.queryByLabelText(/Base URL/i)).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: "查看详情" }));
    expect(await screen.findByRole("heading", { name: "模型配置详情" })).toBeTruthy();
    expect(await screen.findByText("安全与能力")).toBeTruthy();
    expect(screen.queryByText(SECRET_VALUE)).toBeNull();

    await fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    const resetSecret = screen.getByLabelText("重设 API Secret") as HTMLInputElement;
    expect(resetSecret.value).toBe("");
    expect(screen.getByText(/旧 Secret 永不回填/)).toBeTruthy();
    await fireEvent.update(resetSecret, SECRET_VALUE);
    await fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(resetSecret.value).toBe(""));
  });

  it("creates a whitelist configuration and submits the secret only in the write request", async () => {
    const created = configuration();
    vi.spyOn(apiClient, "list_model_config").mockResolvedValue(listResponse([]));
    const create = vi.spyOn(apiClient, "create_model_config").mockResolvedValue({
      data: created,
      correlation_id: "model-create",
    });
    vi.spyOn(apiClient, "get_model_config").mockResolvedValue({
      data: created,
      correlation_id: "model-detail",
    });
    await renderAuthenticated();

    await fireEvent.click(await screen.findByRole("button", { name: "新增模型配置" }));
    await fireEvent.update(screen.getByLabelText("配置编码"), "OPENAI-PRIMARY");
    await fireEvent.update(screen.getByLabelText("显示名称"), "主探索模型");
    await fireEvent.update(screen.getByLabelText("Model", { exact: true }), "gpt-test");
    await fireEvent.update(screen.getByLabelText("API Secret", { exact: true }), SECRET_VALUE);
    await fireEvent.click(screen.getByRole("button", { name: "安全保存" }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0]?.[0]).toMatchObject({
      config_code: "OPENAI-PRIMARY",
      provider_code: "OPENAI",
      model_name: "gpt-test",
      secret_value: SECRET_VALUE,
    });
    expect(await screen.findByText("配置身份")).toBeTruthy();
    expect(screen.queryByText(SECRET_VALUE)).toBeNull();
  });

  it("updates display metadata on ACTIVE without resubmitting governed connection fields", async () => {
    const active = configuration({ lifecycle_status: "ACTIVE", row_version: 3 });
    const updated = { ...active, display_name: "新显示名称", row_version: 4 };
    vi.spyOn(apiClient, "list_model_config").mockResolvedValue(listResponse([active]));
    vi.spyOn(apiClient, "get_model_config").mockResolvedValue({
      data: active,
      correlation_id: "model-detail",
    });
    const update = vi.spyOn(apiClient, "update_model_config").mockResolvedValue({
      data: updated,
      correlation_id: "model-update",
    });
    await renderAuthenticated();
    const store = useModelConfigurationsStore();
    store.connectionResults[active.model_config_id] = {
      status: "SUCCESS",
      provider_code: "OPENAI",
      model_name: "gpt-test",
      latency_ms: 10,
      error_code: null,
      message: "ok",
    };

    await fireEvent.click(await screen.findByRole("button", { name: "查看详情" }));
    await fireEvent.click(await screen.findByRole("button", { name: "编辑" }));
    await fireEvent.update(screen.getByLabelText("显示名称"), "新显示名称");
    await fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    const body = update.mock.calls[0]?.[1];
    expect(body).toEqual({
      expected_version: 3,
      display_name: "新显示名称",
      reason: null,
    });
    expect(body).not.toHaveProperty("provider_code");
    expect(body).not.toHaveProperty("model_name");
    expect(body).not.toHaveProperty("request_timeout_seconds");
    expect(body).not.toHaveProperty("secret_value");
    expect(store.connectionResults[active.model_config_id]).toBeUndefined();
  });

  it("renders a structured connection failure and can switch the active AI_EXPLORATION default", async () => {
    const active = configuration({ lifecycle_status: "ACTIVE", row_version: 3 });
    const bound = {
      ...active,
      is_ai_exploration_default: true,
      ai_exploration_default_version: 1,
    };
    vi.spyOn(apiClient, "list_model_config")
      .mockResolvedValueOnce(listResponse([active]))
      .mockResolvedValueOnce(listResponse([bound]))
      .mockResolvedValueOnce(listResponse([active]));
    const connection = vi.spyOn(apiClient, "test_model_config_connection").mockResolvedValue({
      data: {
        status: "AUTHENTICATION_FAILED",
        provider_code: "OPENAI",
        model_name: "gpt-test",
        latency_ms: 42,
        error_code: "MODEL_PROVIDER_AUTHENTICATION_FAILED",
        message: "Provider 拒绝了凭据。",
      },
      correlation_id: "connection-test",
    });
    const setDefault = vi.spyOn(apiClient, "set_capability_default_model").mockResolvedValue({
      data: {
        capability_code: "AI_EXPLORATION",
        model_config_id: active.model_config_id,
        row_version: 1,
        updated_at: "2026-08-24T00:01:00Z",
      },
      correlation_id: "capability-default",
    });
    const clearDefault = vi.spyOn(apiClient, "clear_capability_default_model").mockResolvedValue({
      data: { capability_code: "AI_EXPLORATION", cleared: true },
      correlation_id: "capability-default-clear",
    });
    await renderAuthenticated();

    await fireEvent.click(await screen.findByRole("button", { name: "测试连接" }));
    expect(await screen.findByText("AUTHENTICATION_FAILED", { exact: true })).toBeTruthy();
    expect(screen.getByText("MODEL_PROVIDER_AUTHENTICATION_FAILED")).toBeTruthy();
    expect(connection).toHaveBeenCalledWith(
      active.model_config_id,
      { reason: "管理端即时连接诊断" },
      expect.objectContaining({ headers: expect.any(Object) }),
    );

    await fireEvent.click(screen.getByRole("button", { name: "设为默认" }));
    await waitFor(() => expect(setDefault).toHaveBeenCalledTimes(1));
    expect(setDefault.mock.calls[0]?.[0]).toBe("AI_EXPLORATION");
    expect(await screen.findByText("当前默认", { exact: true })).toBeTruthy();
    expect((screen.getByRole("button", { name: "禁用" }) as HTMLButtonElement).disabled).toBe(true);

    await fireEvent.click(screen.getByRole("button", { name: "解除默认" }));
    await waitFor(() => expect(clearDefault).toHaveBeenCalledTimes(1));
    expect(clearDefault.mock.calls[0]?.[1]).toEqual({
      expected_version: 1,
      reason: "解除 AI 探索默认模型",
    });
    await waitFor(() => expect(screen.queryByText("当前默认", { exact: true })).toBeNull());
  });

  it("keeps submit-review with managers and activation with independent reviewers", async () => {
    const configuring = configuration();
    const validating = configuration({ lifecycle_status: "VALIDATING", row_version: 2 });
    vi.spyOn(apiClient, "list_model_config").mockResolvedValue(listResponse([configuring]));
    const submitReview = vi.spyOn(apiClient, "submit_model_config_review").mockResolvedValue({
      data: validating,
      correlation_id: "submit-review",
    });
    const managerRender = await renderAuthenticated();

    await fireEvent.click(await screen.findByRole("button", { name: "提交审核" }));
    await fireEvent.click(screen.getByRole("button", { name: "确认提交模型配置审核" }));
    expect(screen.getByText("请填写生命周期操作原因。")).toBeTruthy();
    expect(submitReview).not.toHaveBeenCalled();
    await fireEvent.update(screen.getByLabelText("操作原因"), "配置完成，提交独立审核");
    await fireEvent.click(screen.getByRole("button", { name: "确认提交模型配置审核" }));
    await waitFor(() => expect(submitReview).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("button", { name: "审核并激活" })).toBeNull();
    managerRender.unmount();

    vi.restoreAllMocks();
    vi.spyOn(apiClient, "list_model_config_reviews").mockResolvedValue(listResponse([validating]));
    const activate = vi.spyOn(apiClient, "activate_model_config").mockResolvedValue({
      data: { ...validating, lifecycle_status: "ACTIVE", row_version: 3 },
      correlation_id: "activate",
    });
    await renderAuthenticated(["MODEL_VERSION_REVIEW"]);

    await fireEvent.click(await screen.findByRole("button", { name: "审核并激活" }));
    await fireEvent.update(screen.getByLabelText("操作原因"), "独立审核通过");
    await fireEvent.click(screen.getByRole("button", { name: "确认激活模型配置" }));
    await waitFor(() => expect(activate).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("button", { name: "新增模型配置" })).toBeNull();
  });

  it("loads every page so switching a default always carries the binding version", async () => {
    setActivePinia(createPinia());
    const target = configuration({
      model_config_id: "T".repeat(26),
      lifecycle_status: "ACTIVE",
    });
    const firstPage = [
      target,
      ...Array.from({ length: 199 }, (_, index) =>
        configuration({
          model_config_id: `P${String(index).padStart(25, "0")}`,
          config_code: `CONFIG-${index}`,
          lifecycle_status: "ACTIVE",
        }),
      ),
    ];
    const oldDefault = configuration({
      model_config_id: "D".repeat(26),
      config_code: "OLD-DEFAULT",
      lifecycle_status: "ACTIVE",
      is_ai_exploration_default: true,
      ai_exploration_default_version: 7,
    });
    const list = vi
      .spyOn(apiClient, "list_model_config")
      .mockResolvedValueOnce(pageResponse(firstPage, 1, 201))
      .mockResolvedValueOnce(pageResponse([oldDefault], 2, 201))
      .mockResolvedValueOnce(pageResponse(firstPage, 1, 201))
      .mockResolvedValueOnce(
        pageResponse(
          [
            {
              ...target,
              is_ai_exploration_default: true,
              ai_exploration_default_version: 8,
            },
          ],
          2,
          201,
        ),
      );
    const setDefault = vi.spyOn(apiClient, "set_capability_default_model").mockResolvedValue({
      data: {
        capability_code: "AI_EXPLORATION",
        model_config_id: target.model_config_id,
        row_version: 8,
        updated_at: "2026-08-24T00:02:00Z",
      },
      correlation_id: "capability-switch",
    });
    const store = useModelConfigurationsStore();

    await store.loadConfigurations();
    expect(store.items).toHaveLength(201);
    expect(list.mock.calls[0]?.[0]).toEqual({ query: { page: 1, page_size: 200 } });
    expect(list.mock.calls[1]?.[0]).toEqual({ query: { page: 2, page_size: 200 } });

    await store.setAiExplorationDefault(target);
    expect(setDefault.mock.calls[0]?.[1]).toMatchObject({ expected_version: 7 });
  });
});
