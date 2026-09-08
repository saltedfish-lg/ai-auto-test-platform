import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId, getProblemCode } from "../api/errors";
import type {
  CreateRunnerEnrollmentRequest,
  PageMeta,
  RotateRunnerAgentTokenData,
  RunnerEnrollmentIssuedResource,
  RunnerCapabilityResource,
  RunnerResource,
} from "../generated/types";

function mutationOptions() {
  return { headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } };
}

export type RunnerLifecycleAction = "enable" | "disable" | "archive";

export const useRunnersStore = defineStore("runners", () => {
  const items = ref<RunnerResource[]>([]);
  const page = ref<PageMeta>({ page: 1, page_size: 50, total: 0 });
  const current = ref<RunnerResource | null>(null);
  const issuedEnrollment = ref<RunnerEnrollmentIssuedResource | null>(null);
  const issuedToken = ref<RotateRunnerAgentTokenData | null>(null);
  const status = ref<"idle" | "loading" | "saving">("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();
  const errorCode = ref<string>();

  function capture(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    errorCode.value = getProblemCode(error);
    throw error;
  }

  function clearError(): void {
    errorMessage.value = "";
    correlationId.value = undefined;
    errorCode.value = undefined;
  }

  async function load(
    projectId: string,
    filters: { lifecycleStatus?: string; healthStatus?: string; capabilityCode?: string } = {},
    pageNumber = 1,
    pageSize = 50,
  ): Promise<void> {
    status.value = "loading";
    clearError();
    try {
      const response = await apiClient.list_runner({
        query: {
          project_id: projectId,
          lifecycle_status: filters.lifecycleStatus as
            | "REGISTERED"
            | "ACTIVE"
            | "DISABLED"
            | "ARCHIVED"
            | undefined,
          health_status: filters.healthStatus as
            | "UNKNOWN"
            | "HEALTHY"
            | "DEGRADED"
            | "UNHEALTHY"
            | undefined,
          capability_code: filters.capabilityCode || undefined,
          page: pageNumber,
          page_size: pageSize,
        },
      });
      items.value = response.items;
      page.value = response.page;
    } catch (error) {
      items.value = [];
      capture(error, "Runner 列表加载失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function createEnrollment(
    body: CreateRunnerEnrollmentRequest,
  ): Promise<RunnerEnrollmentIssuedResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_runner_enrollment(body, mutationOptions());
      issuedEnrollment.value = response.data;
      return response.data;
    } catch (error) {
      return capture(error, "Runner enrollment 创建失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function updateName(
    runner: RunnerResource,
    displayName: string | null,
    reason: string,
  ): Promise<RunnerResource> {
    return mutate("Runner 修改失败，请刷新后重试。", async () => {
      const response = await apiClient.update_runner(
        runner.runner_id,
        { expected_version: runner.row_version, display_name: displayName, reason },
        mutationOptions(),
      );
      return response.data;
    });
  }

  async function lifecycle(
    runner: RunnerResource,
    action: RunnerLifecycleAction,
    reason: string,
  ): Promise<RunnerResource> {
    const methods = {
      enable: apiClient.enable_runner.bind(apiClient),
      disable: apiClient.disable_runner.bind(apiClient),
      archive: apiClient.archive_runner.bind(apiClient),
    };
    return mutate("Runner 生命周期操作失败。", async () => {
      const response = await methods[action](
        runner.runner_id,
        { expected_version: runner.row_version, reason },
        mutationOptions(),
      );
      return response.data;
    });
  }

  async function rotateToken(runner: RunnerResource, reason: string): Promise<void> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.rotate_runner_agent_token(
        runner.runner_id,
        { expected_version: runner.row_version, reason },
        mutationOptions(),
      );
      issuedToken.value = response.data;
      replace(response.data.runner);
    } catch (error) {
      capture(error, "Runner Agent token 轮换失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function revokeToken(runner: RunnerResource, reason: string): Promise<RunnerResource> {
    return mutate("Runner Agent token 撤销失败。", async () => {
      const response = await apiClient.revoke_runner_agent_token(
        runner.runner_id,
        { expected_version: runner.row_version, reason },
        mutationOptions(),
      );
      return response.data;
    });
  }

  async function validateCapability(
    runner: RunnerResource,
    capability: RunnerCapabilityResource,
    evidenceSummary: string,
    reason: string,
  ): Promise<RunnerResource> {
    return mutate("Runner Capability 验证失败。", async () => {
      const response = await apiClient.validate_runner_capability(
        runner.runner_id,
        capability.capability_code,
        {
          expected_capability_version: capability.row_version,
          evidence_summary: evidenceSummary,
          reason,
        },
        mutationOptions(),
      );
      return response.data;
    });
  }

  async function mutate(
    fallback: string,
    operation: () => Promise<RunnerResource>,
  ): Promise<RunnerResource> {
    status.value = "saving";
    clearError();
    try {
      const value = await operation();
      replace(value);
      return value;
    } catch (error) {
      return capture(error, fallback);
    } finally {
      status.value = "idle";
    }
  }

  function replace(value: RunnerResource): void {
    const index = items.value.findIndex((item) => item.runner_id === value.runner_id);
    if (index >= 0) items.value.splice(index, 1, value);
    current.value = value;
  }

  function clearIssuedSecrets(): void {
    issuedEnrollment.value = null;
    issuedToken.value = null;
  }

  return {
    items,
    page,
    current,
    issuedEnrollment,
    issuedToken,
    status,
    errorMessage,
    correlationId,
    errorCode,
    load,
    createEnrollment,
    updateName,
    lifecycle,
    rotateToken,
    revokeToken,
    validateCapability,
    clearIssuedSecrets,
  };
});
