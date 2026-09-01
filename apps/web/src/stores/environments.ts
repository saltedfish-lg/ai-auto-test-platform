import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId } from "../api/errors";
import type {
  CreateEnvironmentRequest,
  EnvironmentResource,
  PageMeta,
  UpdateEnvironmentRequest,
} from "../generated/types";

export type EnvironmentLifecycleAction = "validate" | "reconfigure" | "activate";

function mutationOptions() {
  return { headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } };
}

export const useEnvironmentsStore = defineStore("environments", () => {
  const items = ref<EnvironmentResource[]>([]);
  const page = ref<PageMeta>({ page: 1, page_size: 50, total: 0 });
  const current = ref<EnvironmentResource | null>(null);
  const status = ref<"idle" | "loading" | "saving">("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();
  const activeProjectId = ref("");
  const activeLifecycleStatus = ref<string>();

  function clearError() {
    errorMessage.value = "";
    correlationId.value = undefined;
  }

  function capture(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    throw error;
  }

  function applyResource(environmentId: string, resource: EnvironmentResource): void {
    const index = items.value.findIndex((item) => item.environment_id === environmentId);
    const stillMatches =
      !activeLifecycleStatus.value || resource.lifecycle_status === activeLifecycleStatus.value;
    if (index >= 0 && !stillMatches) {
      items.value.splice(index, 1);
      page.value = { ...page.value, total: Math.max(0, page.value.total - 1) };
    } else if (index >= 0) {
      items.value.splice(index, 1, resource);
      items.value.sort((left, right) =>
        (left.environment_code ?? "").localeCompare(right.environment_code ?? ""),
      );
    }
    current.value = resource;
  }

  async function load(
    projectId: string,
    lifecycleStatus?: string,
    pageNumber = 1,
    pageSize = 50,
  ): Promise<void> {
    status.value = "loading";
    clearError();
    activeProjectId.value = projectId;
    activeLifecycleStatus.value = lifecycleStatus;
    try {
      const filter = [
        `project_id=${projectId}`,
        lifecycleStatus ? `lifecycle_status=${lifecycleStatus}` : "",
      ]
        .filter(Boolean)
        .join(";");
      const response = await apiClient.list_environment({
        query: { page: pageNumber, page_size: pageSize, sort: "environment_code", filter },
      });
      items.value = response.items;
      page.value = response.page;
    } catch (error) {
      items.value = [];
      page.value = { page: pageNumber, page_size: pageSize, total: 0 };
      capture(error, "环境列表加载失败，请稍后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function create(body: CreateEnvironmentRequest): Promise<EnvironmentResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_environment(body, mutationOptions());
      const matchesQuery =
        body.project_id === activeProjectId.value &&
        (!activeLifecycleStatus.value ||
          response.data.lifecycle_status === activeLifecycleStatus.value);
      if (matchesQuery) {
        page.value = { ...page.value, total: page.value.total + 1 };
        if (page.value.page === 1) {
          items.value = [...items.value, response.data]
            .sort((left, right) =>
              (left.environment_code ?? "").localeCompare(right.environment_code ?? ""),
            )
            .slice(0, page.value.page_size);
        }
      }
      current.value = response.data;
      return response.data;
    } catch (error) {
      return capture(error, "环境创建失败，请检查输入后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function update(
    environment: EnvironmentResource,
    changes: Omit<UpdateEnvironmentRequest, "expected_version">,
  ): Promise<EnvironmentResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.update_environment(
        environment.environment_id,
        { expected_version: environment.row_version, ...changes },
        mutationOptions(),
      );
      applyResource(environment.environment_id, response.data);
      return response.data;
    } catch (error) {
      return capture(error, "环境保存失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function lifecycle(
    environment: EnvironmentResource,
    action: EnvironmentLifecycleAction,
    reason: string,
  ): Promise<EnvironmentResource> {
    status.value = "saving";
    clearError();
    const body = { expected_version: environment.row_version, reason };
    try {
      const response =
        action === "validate"
          ? await apiClient.validate_environment(
              environment.environment_id,
              body,
              mutationOptions(),
            )
          : action === "reconfigure"
            ? await apiClient.reconfigure_environment(
                environment.environment_id,
                body,
                mutationOptions(),
              )
            : await apiClient.activate_environment(
                environment.environment_id,
                body,
                mutationOptions(),
              );
      applyResource(environment.environment_id, response.data);
      return response.data;
    } catch (error) {
      return capture(error, "环境生命周期操作失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  return {
    items,
    page,
    current,
    status,
    errorMessage,
    correlationId,
    clearError,
    load,
    create,
    update,
    lifecycle,
  };
});
