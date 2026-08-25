import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getAIExplorationErrorMessage, getCorrelationId } from "../api/errors";
import type {
  AIExplorationSessionResource,
  CreateAiExplorationSessionRequest,
} from "../generated/types";

export type AIExplorationStatus = "idle" | "planning";

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export const useAIExplorationsStore = defineStore("aiExplorations", () => {
  const current = ref<AIExplorationSessionResource | null>(null);
  const status = ref<AIExplorationStatus>("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();
  let pendingFingerprint: string | undefined;
  let pendingIdempotencyKey: string | undefined;

  function resetPendingRequest(): void {
    pendingFingerprint = undefined;
    pendingIdempotencyKey = undefined;
  }

  function clear(): void {
    current.value = null;
    status.value = "idle";
    errorMessage.value = "";
    correlationId.value = undefined;
    resetPendingRequest();
  }

  async function create(
    body: CreateAiExplorationSessionRequest,
  ): Promise<AIExplorationSessionResource> {
    status.value = "planning";
    current.value = null;
    errorMessage.value = "";
    correlationId.value = undefined;
    const fingerprint = JSON.stringify(body);
    if (pendingFingerprint !== fingerprint || !pendingIdempotencyKey) {
      pendingFingerprint = fingerprint;
      pendingIdempotencyKey = idempotencyKey();
    }
    try {
      const response = await apiClient.create_ai_exploration_session(body, {
        headers: { "Idempotency-Key": pendingIdempotencyKey },
      });
      current.value = response.data;
      correlationId.value = response.correlation_id;
      resetPendingRequest();
      return response.data;
    } catch (error) {
      errorMessage.value = getAIExplorationErrorMessage(error, "AI 探索规划失败，请稍后重试。");
      correlationId.value = getCorrelationId(error);
      throw error;
    } finally {
      status.value = "idle";
    }
  }

  return { current, status, errorMessage, correlationId, clear, create };
});
