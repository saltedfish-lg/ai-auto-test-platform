import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId } from "../api/errors";
import type {
  CreateProjectRequest,
  ProjectLifecycleRequest,
  ProjectResource,
  UpdateProjectRequest,
} from "../generated/types";

export type ProjectStatus = "idle" | "loading" | "creating" | "saving" | "transitioning";

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export const useProjectsStore = defineStore("projects", () => {
  const items = ref<ProjectResource[]>([]);
  const current = ref<ProjectResource | null>(null);
  const status = ref<ProjectStatus>("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();
  let cacheGeneration = 0;
  let listRequestId = 0;
  let detailRequestId = 0;

  function clearProjects(): void {
    cacheGeneration += 1;
    listRequestId += 1;
    detailRequestId += 1;
    items.value = [];
    current.value = null;
    status.value = "idle";
    clearError();
  }

  function clearError(): void {
    errorMessage.value = "";
    correlationId.value = undefined;
  }

  function captureError(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    throw error;
  }

  async function loadProjects(): Promise<void> {
    const generation = cacheGeneration;
    const requestId = ++listRequestId;
    status.value = "loading";
    items.value = [];
    clearError();
    try {
      const response = await apiClient.list_project();
      if (generation === cacheGeneration && requestId === listRequestId) {
        items.value = response.items;
      }
    } catch (error) {
      if (generation === cacheGeneration && requestId === listRequestId) {
        items.value = [];
        captureError(error, "项目列表加载失败，请稍后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration && requestId === listRequestId) status.value = "idle";
    }
  }

  async function loadProject(projectId: string): Promise<ProjectResource> {
    const generation = cacheGeneration;
    const requestId = ++detailRequestId;
    status.value = "loading";
    current.value = null;
    clearError();
    try {
      const response = await apiClient.get_project(projectId);
      if (generation === cacheGeneration && requestId === detailRequestId) {
        current.value = response.data;
      }
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration && requestId === detailRequestId) {
        current.value = null;
        captureError(error, "项目详情加载失败，请稍后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration && requestId === detailRequestId) status.value = "idle";
    }
  }

  async function createProject(body: CreateProjectRequest): Promise<ProjectResource> {
    const generation = cacheGeneration;
    status.value = "creating";
    clearError();
    try {
      const response = await apiClient.create_project(body, {
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      if (generation === cacheGeneration) {
        items.value = [response.data, ...items.value];
        current.value = response.data;
      }
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration) {
        captureError(error, "项目创建失败，请检查输入后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration) status.value = "idle";
    }
  }

  async function updateProject(
    projectId: string,
    body: UpdateProjectRequest,
  ): Promise<ProjectResource> {
    const generation = cacheGeneration;
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.update_project(projectId, body, {
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      if (generation === cacheGeneration) replaceProject(response.data);
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration) captureError(error, "项目保存失败，请稍后重试。");
      throw error;
    } finally {
      if (generation === cacheGeneration) status.value = "idle";
    }
  }

  async function transitionProject(
    projectId: string,
    action: "disable" | "recover" | "archive",
    body: ProjectLifecycleRequest,
  ): Promise<ProjectResource> {
    const generation = cacheGeneration;
    status.value = "transitioning";
    clearError();
    try {
      const options = { headers: { "Idempotency-Key": idempotencyKey() } };
      const response =
        action === "disable"
          ? await apiClient.disable_project(projectId, body, options)
          : action === "recover"
            ? await apiClient.recover_project(projectId, body, options)
            : await apiClient.archive_project(projectId, body, options);
      if (generation === cacheGeneration) replaceProject(response.data);
      return response.data;
    } catch (error) {
      if (generation === cacheGeneration) {
        captureError(error, "项目状态操作失败，请刷新后重试。");
      }
      throw error;
    } finally {
      if (generation === cacheGeneration) status.value = "idle";
    }
  }

  function replaceProject(project: ProjectResource): void {
    current.value = project;
    const index = items.value.findIndex((item) => item.project_id === project.project_id);
    if (index === -1) items.value.unshift(project);
    else items.value.splice(index, 1, project);
  }

  return {
    items,
    current,
    status,
    errorMessage,
    correlationId,
    clearProjects,
    clearError,
    loadProjects,
    loadProject,
    createProject,
    updateProject,
    transitionProject,
  };
});
