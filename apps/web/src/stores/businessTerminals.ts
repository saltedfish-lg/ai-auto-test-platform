import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId } from "../api/errors";
import type {
  BusinessTerminalResource,
  CreateBusinessTerminalRequest,
  CreateEnvironmentTerminalAccessRevisionRequest,
  EnvironmentTerminalAccessRevisionResource,
  LoginStrategyResource,
  PageMeta,
} from "../generated/types";

function mutationOptions() {
  return { headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } };
}

export const useBusinessTerminalsStore = defineStore("business-terminals", () => {
  const items = ref<BusinessTerminalResource[]>([]);
  const page = ref<PageMeta>({ page: 1, page_size: 50, total: 0 });
  const current = ref<BusinessTerminalResource | null>(null);
  const strategies = ref<LoginStrategyResource[]>([]);
  const revisions = ref<EnvironmentTerminalAccessRevisionResource[]>([]);
  const status = ref<"idle" | "loading" | "saving">("idle");
  const errorMessage = ref("");
  const correlationId = ref<string>();

  function capture(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    throw error;
  }

  function clearError() {
    errorMessage.value = "";
    correlationId.value = undefined;
  }

  async function load(
    projectId: string,
    options: { environmentId?: string; terminalType?: string; lifecycleStatus?: string } = {},
    pageNumber = 1,
    pageSize = 50,
  ): Promise<void> {
    status.value = "loading";
    clearError();
    try {
      const filter = [
        `project_id=${projectId}`,
        options.environmentId ? `environment_id=${options.environmentId}` : "",
        options.terminalType ? `terminal_type=${options.terminalType}` : "",
        options.lifecycleStatus ? `lifecycle_status=${options.lifecycleStatus}` : "",
      ]
        .filter(Boolean)
        .join(";");
      const response = await apiClient.list_business_terminal({
        query: { page: pageNumber, page_size: pageSize, sort: "terminal_code", filter },
      });
      items.value = response.items;
      page.value = response.page;
    } catch (error) {
      items.value = [];
      capture(error, "业务终端列表加载失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function create(body: CreateBusinessTerminalRequest): Promise<BusinessTerminalResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_business_terminal(body, mutationOptions());
      current.value = response.data;
      return response.data;
    } catch (error) {
      return capture(error, "业务终端创建失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function updateName(
    terminal: BusinessTerminalResource,
    displayName: string | null,
    reason: string | null,
  ): Promise<BusinessTerminalResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.update_business_terminal(
        terminal.business_terminal_id,
        { expected_version: terminal.row_version, display_name: displayName, reason },
        mutationOptions(),
      );
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "业务终端修改失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function lifecycle(
    terminal: BusinessTerminalResource,
    action:
      | "validate"
      | "reconfigure"
      | "activate"
      | "mark-unreachable"
      | "recover"
      | "disable"
      | "archive",
    reason: string,
  ): Promise<BusinessTerminalResource> {
    const methods = {
      validate: apiClient.validate_business_terminal.bind(apiClient),
      reconfigure: apiClient.reconfigure_business_terminal.bind(apiClient),
      activate: apiClient.activate_business_terminal.bind(apiClient),
      "mark-unreachable": apiClient.mark_unreachable_business_terminal.bind(apiClient),
      recover: apiClient.recover_business_terminal.bind(apiClient),
      disable: apiClient.disable_business_terminal.bind(apiClient),
      archive: apiClient.archive_business_terminal.bind(apiClient),
    };
    status.value = "saving";
    clearError();
    try {
      const response = await methods[action](
        terminal.business_terminal_id,
        { expected_version: terminal.row_version, reason },
        mutationOptions(),
      );
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "业务终端生命周期操作失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function loadStrategies(projectId: string): Promise<void> {
    clearError();
    try {
      const response = await apiClient.list_login_strategy({
        query: { page: 1, page_size: 200, filter: `project_id=${projectId}` },
      });
      strategies.value = response.items;
    } catch (error) {
      strategies.value = [];
      capture(error, "登录策略列表加载失败。");
    }
  }

  async function loadRevisions(terminalId: string): Promise<void> {
    clearError();
    try {
      const response = await apiClient.list_environment_terminal_access_revision({
        query: { page: 1, page_size: 200, filter: `business_terminal_id=${terminalId}` },
      });
      revisions.value = response.items;
    } catch (error) {
      revisions.value = [];
      capture(error, "访问修订列表加载失败。");
    }
  }

  async function createRevision(body: CreateEnvironmentTerminalAccessRevisionRequest) {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_environment_terminal_access_revision(
        body,
        mutationOptions(),
      );
      revisions.value.unshift(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "访问修订创建失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function validateRevision(
    revision: EnvironmentTerminalAccessRevisionResource,
    reason: string,
  ) {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.validate_environment_terminal_access_revision(
        revision.environment_terminal_access_revision_id,
        { expected_version: revision.row_version, reason },
        mutationOptions(),
      );
      replaceRevision(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "访问修订校验失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function publishRevision(
    revision: EnvironmentTerminalAccessRevisionResource,
    terminal: BusinessTerminalResource,
    reason: string,
  ) {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.publish_environment_terminal_access_revision(
        revision.environment_terminal_access_revision_id,
        {
          expected_version: revision.row_version,
          expected_terminal_version: terminal.row_version,
          reason,
        },
        mutationOptions(),
      );
      replaceRevision(response.data);
      try {
        const refreshed = await apiClient.get_business_terminal(terminal.business_terminal_id);
        replace(refreshed.data);
      } catch (refreshError) {
        errorMessage.value = getApiErrorMessage(
          refreshError,
          "访问修订已发布，但终端详情刷新失败；请刷新页面确认当前指针。",
        );
        correlationId.value = getCorrelationId(refreshError);
      }
      return response.data;
    } catch (error) {
      return capture(error, "访问修订发布失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  function replace(value: BusinessTerminalResource) {
    const index = items.value.findIndex(
      (item) => item.business_terminal_id === value.business_terminal_id,
    );
    if (index >= 0) items.value.splice(index, 1, value);
    current.value = value;
  }

  function replaceRevision(value: EnvironmentTerminalAccessRevisionResource) {
    const index = revisions.value.findIndex(
      (item) =>
        item.environment_terminal_access_revision_id ===
        value.environment_terminal_access_revision_id,
    );
    if (index >= 0) revisions.value.splice(index, 1, value);
  }

  return {
    items,
    page,
    current,
    strategies,
    revisions,
    status,
    errorMessage,
    correlationId,
    clearError,
    load,
    create,
    updateName,
    lifecycle,
    loadStrategies,
    loadRevisions,
    createRevision,
    validateRevision,
    publishRevision,
  };
});
