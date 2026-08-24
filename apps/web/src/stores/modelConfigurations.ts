import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getCorrelationId, getModelConfigurationErrorMessage } from "../api/errors";
import type {
  CreateModelConfigRequest,
  ModelConfigResource,
  UpdateModelConfigRequest,
} from "../generated/types";

export type ModelConfigurationStatus =
  | "idle"
  | "loading"
  | "creating"
  | "saving"
  | "transitioning"
  | "testing"
  | "binding";

export type ModelConnectionResult = Awaited<
  ReturnType<typeof apiClient.test_model_config_connection>
>["data"];

const MODEL_CONFIG_PAGE_SIZE = 200;

async function fetchAllConfigurations(reviewMode: boolean): Promise<ModelConfigResource[]> {
  const allItems: ModelConfigResource[] = [];
  let page = 1;
  while (true) {
    const options = { query: { page, page_size: MODEL_CONFIG_PAGE_SIZE } };
    const response = reviewMode
      ? await apiClient.list_model_config_reviews(options)
      : await apiClient.list_model_config(options);
    allItems.push(...response.items);
    if (
      allItems.length >= response.page.total ||
      response.items.length < MODEL_CONFIG_PAGE_SIZE
    ) {
      return allItems;
    }
    page += 1;
  }
}

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

function mutationOptions(): { headers: { "Idempotency-Key": string } } {
  return { headers: { "Idempotency-Key": idempotencyKey() } };
}

export const useModelConfigurationsStore = defineStore("model-configurations", () => {
  const items = ref<ModelConfigResource[]>([]);
  const current = ref<ModelConfigResource | null>(null);
  const status = ref<ModelConfigurationStatus>("idle");
  const activeItemId = ref<string>();
  const errorMessage = ref("");
  const correlationId = ref<string>();
  const connectionResults = ref<Partial<Record<string, ModelConnectionResult>>>({});
  let cacheGeneration = 0;
  let listRequestId = 0;
  let detailRequestId = 0;

  function clearError(): void {
    errorMessage.value = "";
    correlationId.value = undefined;
  }

  function clearConfigurations(): void {
    cacheGeneration += 1;
    listRequestId += 1;
    detailRequestId += 1;
    items.value = [];
    current.value = null;
    connectionResults.value = {};
    status.value = "idle";
    activeItemId.value = undefined;
    clearError();
  }

  function captureError(error: unknown, fallback: string): never {
    errorMessage.value = getModelConfigurationErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    throw error;
  }

  function replaceConfiguration(configuration: ModelConfigResource): void {
    const previous = items.value.find(
      (item) => item.model_config_id === configuration.model_config_id,
    );
    if (
      previous &&
      (previous.row_version !== configuration.row_version ||
        previous.lifecycle_status !== configuration.lifecycle_status)
    ) {
      const nextResults = { ...connectionResults.value };
      delete nextResults[configuration.model_config_id];
      connectionResults.value = nextResults;
    }
    if (current.value?.model_config_id === configuration.model_config_id) {
      current.value = configuration;
    }
    const index = items.value.findIndex(
      (item) => item.model_config_id === configuration.model_config_id,
    );
    if (index === -1) items.value.unshift(configuration);
    else items.value.splice(index, 1, configuration);
  }

  async function loadConfigurations(reviewMode = false): Promise<void> {
    const generation = cacheGeneration;
    const requestId = ++listRequestId;
    status.value = "loading";
    clearError();
    try {
      const responseItems = await fetchAllConfigurations(reviewMode);
      if (generation === cacheGeneration && requestId === listRequestId) {
        items.value = responseItems;
        if (current.value) {
          current.value =
            responseItems.find(
              (item) => item.model_config_id === current.value?.model_config_id,
            ) ?? null;
        }
      }
    } catch (error) {
      if (generation === cacheGeneration && requestId === listRequestId) {
        items.value = [];
        current.value = null;
        captureError(error, "模型配置列表加载失败，请稍后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration && requestId === listRequestId) status.value = "idle";
    }
  }

  async function loadConfiguration(
    modelConfigId: string,
    reviewMode = false,
  ): Promise<ModelConfigResource> {
    const generation = cacheGeneration;
    const requestId = ++detailRequestId;
    status.value = "loading";
    clearError();
    try {
      const response = reviewMode
        ? await apiClient.get_model_config_review(modelConfigId)
        : await apiClient.get_model_config(modelConfigId);
      if (generation === cacheGeneration && requestId === detailRequestId) {
        current.value = response.data;
        replaceConfiguration(response.data);
      }
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration && requestId === detailRequestId) {
        current.value = null;
        captureError(error, "模型配置详情加载失败，请稍后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration && requestId === detailRequestId) status.value = "idle";
    }
  }

  async function createConfiguration(body: CreateModelConfigRequest): Promise<ModelConfigResource> {
    const generation = cacheGeneration;
    status.value = "creating";
    clearError();
    try {
      const response = await apiClient.create_model_config(body, mutationOptions());
      if (generation === cacheGeneration) replaceConfiguration(response.data);
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration) {
        captureError(error, "模型配置创建失败，请检查输入后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration) status.value = "idle";
    }
  }

  async function updateConfiguration(
    modelConfigId: string,
    body: UpdateModelConfigRequest,
  ): Promise<ModelConfigResource> {
    return saveResource(
      "saving",
      modelConfigId,
      () => apiClient.update_model_config(modelConfigId, body, mutationOptions()),
      "模型配置保存失败，请稍后重试。",
    );
  }

  async function submitReview(
    configuration: ModelConfigResource,
    reason: string,
  ): Promise<ModelConfigResource> {
    const auditReason = requiredLifecycleReason(reason);
    return saveResource(
      "transitioning",
      configuration.model_config_id,
      () =>
        apiClient.submit_model_config_review(
          configuration.model_config_id,
          { expected_version: configuration.row_version, reason: auditReason },
          mutationOptions(),
        ),
      "模型配置提交审核失败，请刷新后重试。",
    );
  }

  async function activate(
    configuration: ModelConfigResource,
    reason: string,
  ): Promise<ModelConfigResource> {
    const auditReason = requiredLifecycleReason(reason);
    return saveResource(
      "transitioning",
      configuration.model_config_id,
      () =>
        apiClient.activate_model_config(
          configuration.model_config_id,
          { expected_version: configuration.row_version, reason: auditReason },
          mutationOptions(),
        ),
      "模型配置激活失败，请确认审核权限和当前状态。",
    );
  }

  async function returnToConfiguring(
    configuration: ModelConfigResource,
    reason: string,
  ): Promise<ModelConfigResource> {
    const auditReason = requiredLifecycleReason(reason);
    return saveResource(
      "transitioning",
      configuration.model_config_id,
      () =>
        apiClient.return_model_config_to_configuring(
          configuration.model_config_id,
          { expected_version: configuration.row_version, reason: auditReason },
          mutationOptions(),
        ),
      "模型配置退回失败，请刷新后重试。",
    );
  }

  async function disable(
    configuration: ModelConfigResource,
    reason: string,
  ): Promise<ModelConfigResource> {
    const auditReason = requiredLifecycleReason(reason);
    return saveResource(
      "transitioning",
      configuration.model_config_id,
      () =>
        apiClient.disable_model_config(
          configuration.model_config_id,
          { expected_version: configuration.row_version, reason: auditReason },
          mutationOptions(),
        ),
      "模型配置禁用失败；当前默认模型必须先解除或切换。",
    );
  }

  async function recover(
    configuration: ModelConfigResource,
    reason: string,
  ): Promise<ModelConfigResource> {
    const auditReason = requiredLifecycleReason(reason);
    return saveResource(
      "transitioning",
      configuration.model_config_id,
      () =>
        apiClient.recover_model_config(
          configuration.model_config_id,
          { expected_version: configuration.row_version, reason: auditReason },
          mutationOptions(),
        ),
      "模型配置恢复启动失败，请刷新后重试。",
    );
  }

  async function archive(
    configuration: ModelConfigResource,
    reason: string,
  ): Promise<ModelConfigResource> {
    const auditReason = requiredLifecycleReason(reason);
    return saveResource(
      "transitioning",
      configuration.model_config_id,
      () =>
        apiClient.archive_model_config(
          configuration.model_config_id,
          { expected_version: configuration.row_version, reason: auditReason },
          mutationOptions(),
        ),
      "模型配置归档失败，请刷新后重试。",
    );
  }

  async function testConnection(
    configuration: ModelConfigResource,
    reason?: string,
  ): Promise<ModelConnectionResult> {
    const generation = cacheGeneration;
    status.value = "testing";
    activeItemId.value = configuration.model_config_id;
    clearError();
    try {
      const response = await apiClient.test_model_config_connection(
        configuration.model_config_id,
        { reason: reason || null },
        mutationOptions(),
      );
      if (generation === cacheGeneration) {
        connectionResults.value = {
          ...connectionResults.value,
          [configuration.model_config_id]: response.data,
        };
      }
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration) {
        captureError(error, "模型连接测试请求失败，请稍后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration) {
        status.value = "idle";
        activeItemId.value = undefined;
      }
    }
  }

  async function setAiExplorationDefault(configuration: ModelConfigResource): Promise<void> {
    const generation = cacheGeneration;
    const currentDefault = items.value.find((item) => item.is_ai_exploration_default);
    status.value = "binding";
    activeItemId.value = configuration.model_config_id;
    clearError();
    try {
      await apiClient.set_capability_default_model(
        "AI_EXPLORATION",
        {
          model_config_id: configuration.model_config_id,
          ...(currentDefault?.ai_exploration_default_version != null
            ? { expected_version: currentDefault.ai_exploration_default_version }
            : {}),
          reason: "设置 AI 探索默认模型",
        },
        mutationOptions(),
      );
      if (generation === cacheGeneration) await loadConfigurations();
    } catch (error) {
      if (generation === cacheGeneration) {
        captureError(error, "AI_EXPLORATION 默认模型设置失败，请刷新后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration) {
        status.value = "idle";
        activeItemId.value = undefined;
      }
    }
  }

  async function clearAiExplorationDefault(configuration: ModelConfigResource): Promise<void> {
    const generation = cacheGeneration;
    if (configuration.ai_exploration_default_version == null) {
      errorMessage.value = "默认模型绑定版本缺失，请刷新列表后重试。";
      throw new Error("AI_EXPLORATION default binding version is unavailable");
    }
    status.value = "binding";
    activeItemId.value = configuration.model_config_id;
    clearError();
    try {
      await apiClient.clear_capability_default_model(
        "AI_EXPLORATION",
        {
          expected_version: configuration.ai_exploration_default_version,
          reason: "解除 AI 探索默认模型",
        },
        mutationOptions(),
      );
      if (generation === cacheGeneration) await loadConfigurations();
    } catch (error) {
      if (generation === cacheGeneration) {
        captureError(error, "AI_EXPLORATION 默认模型解除失败，请刷新后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration) {
        status.value = "idle";
        activeItemId.value = undefined;
      }
    }
  }

  async function saveResource(
    nextStatus: "saving" | "transitioning",
    modelConfigId: string,
    request: () => Promise<{ data: ModelConfigResource }>,
    fallback: string,
  ): Promise<ModelConfigResource> {
    const generation = cacheGeneration;
    status.value = nextStatus;
    activeItemId.value = modelConfigId;
    clearError();
    try {
      const response = await request();
      if (generation === cacheGeneration) replaceConfiguration(response.data);
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration) captureError(error, fallback);
      throw error;
    } finally {
      if (generation === cacheGeneration) {
        status.value = "idle";
        activeItemId.value = undefined;
      }
    }
  }

  function requiredLifecycleReason(reason: string): string {
    const normalized = reason.trim();
    if (normalized) return normalized;
    errorMessage.value = "请填写生命周期操作原因。";
    throw new Error("Model configuration lifecycle reason is required");
  }

  return {
    items,
    current,
    status,
    activeItemId,
    errorMessage,
    correlationId,
    connectionResults,
    clearConfigurations,
    clearError,
    loadConfigurations,
    loadConfiguration,
    createConfiguration,
    updateConfiguration,
    submitReview,
    returnToConfiguring,
    activate,
    disable,
    recover,
    archive,
    testConnection,
    setAiExplorationDefault,
    clearAiExplorationDefault,
  };
});
