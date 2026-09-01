import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId } from "../api/errors";
import type {
  ExecutionBindingInput,
  ExecutionBindingPreflightResult,
  ExecutionBindingSnapshotResource,
  PageMeta,
  RuntimePolicyRevisionResource,
} from "../generated/types";

function mutationOptions() {
  return { headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } };
}

export type BindingCommand = "consume" | "renew" | "release" | "recover";

export const useExecutionBindingsStore = defineStore("execution-bindings", () => {
  const items = ref<ExecutionBindingSnapshotResource[]>([]);
  const page = ref<PageMeta>({ page: 1, page_size: 50, total: 0 });
  const current = ref<ExecutionBindingSnapshotResource | null>(null);
  const preflight = ref<ExecutionBindingPreflightResult | null>(null);
  const policies = ref<RuntimePolicyRevisionResource[]>([]);
  const status = ref<"idle" | "loading" | "saving">("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();

  function clearError(): void {
    errorMessage.value = "";
    correlationId.value = undefined;
  }

  function capture(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
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

  async function loadPolicies(projectId: string): Promise<void> {
    try {
      policies.value = (
        await apiClient.list_project_runtime_policy_revisions({ query: { project_id: projectId } })
      ).items;
    } catch (error) {
      policies.value = [];
      capture(error, "RuntimePolicy Revision 加载失败。");
    }
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
      return capture(error, "执行绑定 Preflight 失败。");
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
    status,
    errorMessage,
    correlationId,
    load,
    loadPolicies,
    runPreflight,
    create,
    command,
  };
});
