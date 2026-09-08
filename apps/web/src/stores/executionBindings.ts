import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId, getProblemCode } from "../api/errors";
import type {
  CreateRuntimePolicyRevisionRequest,
  ExecutionBindingInput,
  ExecutionBindingPreflightResult,
  ExecutionAttemptResource,
  ExecutionBindingSnapshotResource,
  ExecutionSlotResource,
  PageMeta,
  RunTaskResource,
  RuntimePolicyRevisionResource,
} from "../generated/types";

function mutationOptions() {
  return { headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } };
}

function requestFingerprint(body: object): string {
  return JSON.stringify(body);
}

export type BindingCommand = "consume" | "renew" | "release" | "recover";

export const useExecutionBindingsStore = defineStore("execution-bindings", () => {
  const items = ref<ExecutionBindingSnapshotResource[]>([]);
  const page = ref<PageMeta>({ page: 1, page_size: 50, total: 0 });
  const current = ref<ExecutionBindingSnapshotResource | null>(null);
  const preflight = ref<ExecutionBindingPreflightResult | null>(null);
  const policies = ref<RuntimePolicyRevisionResource[]>([]);
  const slots = ref<ExecutionSlotResource[]>([]);
  const preparedRunTask = ref<RunTaskResource | null>(null);
  const preparedExecutionAttempt = ref<ExecutionAttemptResource | null>(null);
  const preparedRunTaskScope = ref<string>();
  const preparedAttemptScope = ref<string>();
  const pendingOwnerKeys = new Map<string, { fingerprint: string; key: string }>();
  const status = ref<"idle" | "loading" | "saving">("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();
  const errorCode = ref<string>();

  function clearError(): void {
    errorMessage.value = "";
    correlationId.value = undefined;
    errorCode.value = undefined;
  }

  function capture(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    errorCode.value = getProblemCode(error);
    throw error;
  }

  async function load(projectId: string, bindingStatus?: string, pageNumber = 1): Promise<void> {
    status.value = "loading";
    clearError();
    try {
      const response = await apiClient.list_execution_binding_snapshots({
        query: {
          project_id: projectId,
          status: bindingStatus as "READY" | "IN_USE" | "RELEASED" | "EXPIRED" | undefined,
          page: pageNumber,
          page_size: page.value.page_size,
        },
      });
      items.value = response.items;
      page.value = response.page;
    } catch (error) {
      items.value = [];
      capture(error, "执行绑定列表加载失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function loadSlots(projectId: string, runnerId: string): Promise<void> {
    clearError();
    slots.value = [];
    if (!projectId || !runnerId) return;
    try {
      const response = await apiClient.list_execution_slot({
        query: {
          project_id: projectId,
          runner_id: runnerId,
          lifecycle_status: "ACTIVE",
          available_only: true,
          page: 1,
          page_size: 50,
        },
      });
      slots.value = response.items;
    } catch (error) {
      slots.value = [];
      capture(error, "正式执行资源加载失败。");
    }
  }

  async function loadPolicies(projectId: string): Promise<void> {
    try {
      policies.value = (
        await apiClient.list_project_runtime_policy_revisions({ query: { project_id: projectId } })
      ).items;
    } catch (error) {
      policies.value = [];
      capture(error, "运行策略修订加载失败。");
    }
  }

  async function createPolicy(
    body: CreateRuntimePolicyRevisionRequest,
  ): Promise<RuntimePolicyRevisionResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_project_runtime_policy_revision(
        body,
        mutationOptions(),
      );
      policies.value.unshift(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "运行策略修订创建发布失败。");
    } finally {
      status.value = "idle";
    }
  }

  function ownerMutationOptions(operation: string, body: object) {
    const fingerprint = requestFingerprint(body);
    const pending = pendingOwnerKeys.get(operation);
    if (pending?.fingerprint === fingerprint) {
      return { headers: { "Idempotency-Key": pending.key } };
    }
    const key = globalThis.crypto.randomUUID();
    pendingOwnerKeys.set(operation, { fingerprint, key });
    return { headers: { "Idempotency-Key": key } };
  }

  async function prepareExplorationExecutionOwner(
    projectId: string,
    environmentId: string,
    runnerId: string,
    reason: string,
  ): Promise<{ runTask: RunTaskResource; attempt: ExecutionAttemptResource }> {
    status.value = "saving";
    clearError();
    try {
      const runTaskScope = `${projectId}:${environmentId}`;
      if (preparedRunTaskScope.value !== runTaskScope) {
        preparedRunTask.value = null;
        preparedExecutionAttempt.value = null;
        preparedRunTaskScope.value = runTaskScope;
        preparedAttemptScope.value = undefined;
        pendingOwnerKeys.delete("create_run_task");
        pendingOwnerKeys.delete("create_execution_attempt");
      }
      if (!preparedRunTask.value) {
        const runTaskBody = {
          project_id: projectId,
          environment_id: environmentId,
          task_type: "AI_EXPLORATION" as const,
          display_name: "AI Exploration",
          reason,
          final_result: "UNKNOWN" as const,
        };
        const runTask = await apiClient.create_run_task(
          runTaskBody,
          ownerMutationOptions("create_run_task", runTaskBody),
        );
        preparedRunTask.value = runTask.data;
        pendingOwnerKeys.delete("create_run_task");
      }
      const attemptScope = `${preparedRunTask.value.run_task_id}:${runnerId}`;
      if (preparedAttemptScope.value !== attemptScope) {
        preparedExecutionAttempt.value = null;
        preparedAttemptScope.value = attemptScope;
        pendingOwnerKeys.delete("create_execution_attempt");
      }
      if (!preparedExecutionAttempt.value) {
        const attemptBody = {
          run_task_id: preparedRunTask.value.run_task_id,
          runner_id: runnerId,
          display_name: "AI Exploration Attempt",
          reason,
        };
        const attempt = await apiClient.create_execution_attempt(
          attemptBody,
          ownerMutationOptions("create_execution_attempt", attemptBody),
        );
        preparedExecutionAttempt.value = attempt.data;
        pendingOwnerKeys.delete("create_execution_attempt");
      }
      return {
        runTask: preparedRunTask.value,
        attempt: preparedExecutionAttempt.value,
      };
    } catch (error) {
      return capture(error, "AI 探索执行所有者准备失败。");
    } finally {
      status.value = "idle";
    }
  }

  function resetPreparedExecutionOwner(): void {
    preparedRunTask.value = null;
    preparedExecutionAttempt.value = null;
    preparedRunTaskScope.value = undefined;
    preparedAttemptScope.value = undefined;
    pendingOwnerKeys.delete("create_run_task");
    pendingOwnerKeys.delete("create_execution_attempt");
  }

  async function runPreflight(
    body: ExecutionBindingInput,
  ): Promise<ExecutionBindingPreflightResult> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.preflight_execution_binding_snapshot(
        body,
        mutationOptions(),
      );
      preflight.value = response.data;
      correlationId.value = response.correlation_id;
      return response.data;
    } catch (error) {
      return capture(error, "执行预检查失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function create(body: ExecutionBindingInput): Promise<ExecutionBindingSnapshotResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_execution_binding_snapshot(body, mutationOptions());
      current.value = response.data;
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "执行绑定原子创建失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function command(
    binding: ExecutionBindingSnapshotResource,
    action: BindingCommand,
    reason: string,
    recoveryEvidence = "",
  ): Promise<ExecutionBindingSnapshotResource> {
    status.value = "saving";
    clearError();
    const body = {
      owner_execution_identity: binding.owner_execution_identity,
      expected_version: binding.row_version,
      identity_lease_generation: binding.identity_lease.fencing_generation,
      runner_lease_generation: binding.runner_lease.fencing_generation,
      reason,
    };
    try {
      const response =
        action === "consume"
          ? await apiClient.consume_execution_binding_snapshot(
              binding.execution_binding_snapshot_id,
              body,
              mutationOptions(),
            )
          : action === "renew"
            ? await apiClient.renew_execution_binding_snapshot_leases(
                binding.execution_binding_snapshot_id,
                body,
                mutationOptions(),
              )
            : action === "release"
              ? await apiClient.release_execution_binding_snapshot(
                  binding.execution_binding_snapshot_id,
                  body,
                  mutationOptions(),
                )
              : await apiClient.recover_execution_binding_snapshot(
                  binding.execution_binding_snapshot_id,
                  { ...body, recovery_evidence: recoveryEvidence },
                  mutationOptions(),
                );
      current.value = response.data;
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "执行绑定命令失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  function replace(value: ExecutionBindingSnapshotResource): void {
    const index = items.value.findIndex(
      (item) => item.execution_binding_snapshot_id === value.execution_binding_snapshot_id,
    );
    if (index >= 0) items.value.splice(index, 1, value);
    else items.value.unshift(value);
  }

  return {
    items,
    page,
    current,
    preflight,
    policies,
    slots,
    preparedRunTask,
    preparedExecutionAttempt,
    status,
    errorMessage,
    correlationId,
    errorCode,
    load,
    loadPolicies,
    loadSlots,
    createPolicy,
    prepareExplorationExecutionOwner,
    resetPreparedExecutionOwner,
    runPreflight,
    create,
    command,
  };
});
