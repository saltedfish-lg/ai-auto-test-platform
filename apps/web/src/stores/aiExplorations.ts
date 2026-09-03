import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getAIExplorationErrorMessage, getCorrelationId } from "../api/errors";
import type {
  AIExplorationSessionResource,
  AIExplorationStepResource,
  CancelAIExplorationSessionRequest,
  CreateAiExplorationSessionRequest,
  StartAIExplorationSessionRequest,
} from "../generated/types";

export type AIExplorationStatus = "idle" | "planning" | "starting" | "loading" | "cancelling";

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export const useAIExplorationsStore = defineStore("aiExplorations", () => {
  const current = ref<AIExplorationSessionResource | null>(null);
  const steps = ref<AIExplorationStepResource[]>([]);
  const status = ref<AIExplorationStatus>("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();
  const pendingKeys = new Map<string, { fingerprint: string; key: string }>();

  function commandKey(operation: string, body: object): string {
    const fingerprint = JSON.stringify(body);
    const pending = pendingKeys.get(operation);
    if (pending?.fingerprint === fingerprint) return pending.key;
    const key = idempotencyKey();
    pendingKeys.set(operation, { fingerprint, key });
    return key;
  }

  function clear(): void {
    current.value = null;
    steps.value = [];
    status.value = "idle";
    errorMessage.value = "";
    correlationId.value = undefined;
    pendingKeys.clear();
  }

  async function create(
    body: CreateAiExplorationSessionRequest,
  ): Promise<AIExplorationSessionResource> {
    status.value = "planning";
    current.value = null;
    errorMessage.value = "";
    correlationId.value = undefined;
    const key = commandKey("create", body);
    try {
      const response = await apiClient.create_ai_exploration_session(body, {
        headers: { "Idempotency-Key": key },
      });
      current.value = response.data;
      correlationId.value = response.correlation_id;
      pendingKeys.delete("create");
      return response.data;
    } catch (error) {
      errorMessage.value = getAIExplorationErrorMessage(error, "AI 探索规划失败，请稍后重试。");
      correlationId.value = getCorrelationId(error);
      throw error;
    } finally {
      status.value = "idle";
    }
  }

  async function load(sessionId: string): Promise<AIExplorationSessionResource> {
    status.value = "loading";
    try {
      const response = await apiClient.get_ai_exploration_session(sessionId);
      current.value = response.data;
      correlationId.value = response.correlation_id;
      return response.data;
    } catch (error) {
      errorMessage.value = getAIExplorationErrorMessage(error, "AI 探索状态读取失败。");
      correlationId.value = getCorrelationId(error);
      throw error;
    } finally {
      status.value = "idle";
    }
  }

  async function loadSteps(sessionId: string): Promise<AIExplorationStepResource[]> {
    const response = await apiClient.list_ai_exploration_steps(sessionId);
    steps.value = response.items;
    correlationId.value = response.correlation_id;
    return response.items;
  }

  async function start(
    sessionId: string,
    body: StartAIExplorationSessionRequest,
  ): Promise<AIExplorationSessionResource> {
    status.value = "starting";
    errorMessage.value = "";
    const key = commandKey(`start:${sessionId}`, body);
    try {
      const response = await apiClient.start_ai_exploration_session(sessionId, body, {
        headers: { "Idempotency-Key": key },
      });
      current.value = response.data;
      correlationId.value = response.correlation_id;
      pendingKeys.delete(`start:${sessionId}`);
      return response.data;
    } catch (error) {
      errorMessage.value = getAIExplorationErrorMessage(error, "AI 浏览器探索启动失败。");
      correlationId.value = getCorrelationId(error);
      throw error;
    } finally {
      status.value = "idle";
    }
  }

  async function cancel(
    sessionId: string,
    body: CancelAIExplorationSessionRequest,
  ): Promise<AIExplorationSessionResource> {
    status.value = "cancelling";
    errorMessage.value = "";
    const key = commandKey(`cancel:${sessionId}`, body);
    try {
      const response = await apiClient.cancel_ai_exploration_session(sessionId, body, {
        headers: { "Idempotency-Key": key },
      });
      current.value = response.data;
      correlationId.value = response.correlation_id;
      pendingKeys.delete(`cancel:${sessionId}`);
      return response.data;
    } catch (error) {
      errorMessage.value = getAIExplorationErrorMessage(error, "AI 浏览器探索取消失败。");
      correlationId.value = getCorrelationId(error);
      throw error;
    } finally {
      status.value = "idle";
    }
  }

  return {
    current,
    steps,
    status,
    errorMessage,
    correlationId,
    clear,
    create,
    load,
    loadSteps,
    start,
    cancel,
  };
});
