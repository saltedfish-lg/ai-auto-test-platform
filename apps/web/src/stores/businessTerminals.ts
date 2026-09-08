import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId, getProblemCode } from "../api/errors";
import type {
  BusinessTerminalResource,
  CreateLoginStrategyRequest,
  CreateBusinessTerminalRequest,
  CreateEnvironmentTerminalAccessRevisionRequest,
  EnvironmentTerminalAccessRevisionResource,
  LoginStrategyResource,
  PageMeta,
  UpdateEnvironmentTerminalAccessRevisionRequest,
} from "../generated/types";

function mutationOptions(key: string = globalThis.crypto.randomUUID()) {
  return { headers: { "Idempotency-Key": key } };
}

type LoginStrategyWorkflow = {
  fingerprint: string;
  assetKey: string;
  strategyKey: string;
  configureKey: string;
  activateKey: string;
  automationAssetId?: string;
  loginStrategyId?: string;
};

function loginStrategyWorkflowKey(projectId: string, displayName: string): string {
  return `business-terminal:login-strategy:${projectId}:${displayName.trim()}`;
}

function readWorkflow(key: string, fingerprint: string): LoginStrategyWorkflow | undefined {
  try {
    const raw = globalThis.sessionStorage?.getItem(key);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as LoginStrategyWorkflow;
    return parsed.fingerprint === fingerprint ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function writeWorkflow(key: string, value: LoginStrategyWorkflow): void {
  try {
    globalThis.sessionStorage?.setItem(key, JSON.stringify(value));
  } catch {
    /* Session storage is only recovery assistance; server idempotency remains authoritative. */
  }
}

function clearWorkflow(key: string): void {
  try {
    globalThis.sessionStorage?.removeItem(key);
  } catch {
    /* A completed server workflow must not be reported as failed because storage is unavailable. */
  }
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
  const errorCode = ref<string>();

  function capture(error: unknown, fallback: string): never {
    errorMessage.value = getApiErrorMessage(error, fallback);
    correlationId.value = getCorrelationId(error);
    errorCode.value = getProblemCode(error);
    throw error;
  }

  function clearError() {
    errorMessage.value = "";
    correlationId.value = undefined;
    errorCode.value = undefined;
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

  async function createAndActivateLoginStrategy(
    body: Omit<CreateLoginStrategyRequest, "automation_asset_id">,
  ): Promise<LoginStrategyResource> {
    status.value = "saving";
    clearError();
    try {
      const fingerprint = JSON.stringify(body);
      const workflowKey = loginStrategyWorkflowKey(body.project_id, body.display_name ?? "");
      const existing = strategies.value.find(
        (item) =>
          ["CREATED", "DRAFT"].includes(item.lifecycle_status) &&
          item.project_id === body.project_id &&
          item.display_name === body.display_name &&
          item.captcha_policy === body.captcha_policy &&
          item.captcha_request_header_name === (body.captcha_request_header_name ?? null) &&
          item.captcha_request_header_value === (body.captcha_request_header_value ?? null) &&
          item.captcha_response_header_name === (body.captcha_response_header_name ?? null),
      );
      const workflow = readWorkflow(workflowKey, fingerprint) ?? {
        fingerprint,
        assetKey: globalThis.crypto.randomUUID(),
        strategyKey: globalThis.crypto.randomUUID(),
        configureKey: globalThis.crypto.randomUUID(),
        activateKey: globalThis.crypto.randomUUID(),
        loginStrategyId: existing?.login_strategy_id,
        automationAssetId: existing?.automation_asset_id,
      };
      writeWorkflow(workflowKey, workflow);
      if (!workflow.automationAssetId) {
        const asset = await apiClient.create_automation_asset(
          {
            project_id: body.project_id,
            display_name: body.display_name,
            reason: body.reason,
          },
          mutationOptions(workflow.assetKey),
        );
        workflow.automationAssetId = asset.data.automation_asset_id;
        writeWorkflow(workflowKey, workflow);
      }
      let strategy = existing;
      if (!workflow.loginStrategyId) {
        const created = await apiClient.create_login_strategy(
          { ...body, automation_asset_id: workflow.automationAssetId! },
          mutationOptions(workflow.strategyKey),
        );
        strategy = created.data;
        workflow.loginStrategyId = created.data.login_strategy_id;
        writeWorkflow(workflowKey, workflow);
      } else if (!strategy) {
        strategy = (await apiClient.get_login_strategy(workflow.loginStrategyId)).data;
      }
      if (strategy.lifecycle_status === "CREATED") {
        strategy = (
          await apiClient.update_login_strategy(
            strategy.login_strategy_id,
            {
              expected_version: strategy.row_version,
              display_name: body.display_name,
              local_storage_presets: body.local_storage_presets ?? [],
              refresh_after_local_storage: body.refresh_after_local_storage ?? false,
              captcha_policy: body.captcha_policy ?? "NONE",
              captcha_request_header_name: body.captcha_request_header_name ?? null,
              captcha_request_header_value: body.captcha_request_header_value ?? null,
              captcha_response_header_name: body.captcha_response_header_name ?? null,
              session_policy: body.session_policy ?? null,
              reason: body.reason,
            },
            mutationOptions(workflow.configureKey),
          )
        ).data;
      }
      const activated = await apiClient.activate_login_strategy(
        strategy.login_strategy_id,
        {
          expected_version: strategy.row_version,
          reason: body.reason?.trim() || "Activate login strategy",
        },
        mutationOptions(workflow.activateKey),
      );
      clearWorkflow(workflowKey);
      strategies.value = strategies.value.filter(
        (item) => item.login_strategy_id !== activated.data.login_strategy_id,
      );
      strategies.value.unshift(activated.data);
      return activated.data;
    } catch (error) {
      return capture(error, "登录策略创建或启用失败；已完成的前置资源会保留，请刷新后核对。");
    } finally {
      status.value = "idle";
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

  async function returnRevisionToDraft(
    revision: EnvironmentTerminalAccessRevisionResource,
    reason: string,
  ) {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.return_to_draft_environment_terminal_access_revision(
        revision.environment_terminal_access_revision_id,
        { expected_version: revision.row_version, reason },
        mutationOptions(),
      );
      replaceRevision(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "访问修订返回草稿失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function updateRevision(
    revision: EnvironmentTerminalAccessRevisionResource,
    changes: Omit<UpdateEnvironmentTerminalAccessRevisionRequest, "expected_version">,
  ) {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.update_environment_terminal_access_revision(
        revision.environment_terminal_access_revision_id,
        { ...changes, expected_version: revision.row_version },
        mutationOptions(),
      );
      replaceRevision(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "访问修订编辑失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function abandonRevision(
    revision: EnvironmentTerminalAccessRevisionResource,
    reason: string,
  ) {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.abandon_environment_terminal_access_revision(
        revision.environment_terminal_access_revision_id,
        { expected_version: revision.row_version, reason },
        mutationOptions(),
      );
      revisions.value = revisions.value.filter(
        (item) =>
          item.environment_terminal_access_revision_id !==
          revision.environment_terminal_access_revision_id,
      );
      return response.data;
    } catch (error) {
      return capture(error, "访问修订放弃失败，请刷新后重试。");
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
        const revisionList = await apiClient.list_environment_terminal_access_revision({
          query: {
            page: 1,
            page_size: 200,
            filter: `business_terminal_id=${terminal.business_terminal_id}`,
          },
        });
        revisions.value = revisionList.items;
      } catch (refreshError) {
        errorMessage.value = getApiErrorMessage(
          refreshError,
          "访问修订已发布，但终端或修订列表刷新失败；请刷新页面确认当前指针。",
        );
        correlationId.value = getCorrelationId(refreshError);
        errorCode.value = getProblemCode(refreshError);
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
    errorCode,
    clearError,
    load,
    create,
    updateName,
    lifecycle,
    loadStrategies,
    createAndActivateLoginStrategy,
    loadRevisions,
    createRevision,
    updateRevision,
    validateRevision,
    returnRevisionToDraft,
    abandonRevision,
    publishRevision,
  };
});
