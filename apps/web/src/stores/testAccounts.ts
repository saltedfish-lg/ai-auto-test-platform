import { ref } from "vue";
import { defineStore } from "pinia";

import { apiClient } from "../api/client";
import { getApiErrorMessage, getCorrelationId, getProblemCode } from "../api/errors";
import type { CreateTestAccountRequest, PageMeta, TestAccountResource } from "../generated/types";

function mutationOptions() {
  return { headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } };
}

export type TestAccountLifecycleAction =
  | "validate"
  | "reconfigure"
  | "activate"
  | "mark-credential-expired"
  | "recover"
  | "disable"
  | "archive";

export const useTestAccountsStore = defineStore("test-accounts", () => {
  const items = ref<TestAccountResource[]>([]);
  const page = ref<PageMeta>({ page: 1, page_size: 50, total: 0 });
  const current = ref<TestAccountResource | null>(null);
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
    options: { environmentId?: string; businessTerminalId?: string; lifecycleStatus?: string } = {},
    pageNumber = 1,
    pageSize = 50,
  ): Promise<void> {
    status.value = "loading";
    clearError();
    try {
      const filter = [
        `project_id=${projectId}`,
        options.environmentId ? `environment_id=${options.environmentId}` : "",
        options.businessTerminalId ? `business_terminal_id=${options.businessTerminalId}` : "",
        options.lifecycleStatus ? `lifecycle_status=${options.lifecycleStatus}` : "",
      ]
        .filter(Boolean)
        .join(";");
      const response = await apiClient.list_test_account({
        query: { page: pageNumber, page_size: pageSize, sort: "account_identifier", filter },
      });
      items.value = response.items;
      page.value = response.page;
    } catch (error) {
      items.value = [];
      capture(error, "测试账号列表加载失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function create(body: CreateTestAccountRequest): Promise<TestAccountResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.create_test_account(body, mutationOptions());
      current.value = response.data;
      items.value.unshift(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "测试账号创建失败。");
    } finally {
      status.value = "idle";
    }
  }

  async function updateName(
    account: TestAccountResource,
    displayName: string | null,
    reason: string,
  ): Promise<TestAccountResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.update_test_account(
        account.test_account_id,
        { expected_version: account.row_version, display_name: displayName, reason },
        mutationOptions(),
      );
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "测试账号修改失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function rotateSecret(
    account: TestAccountResource,
    secretValue: string,
    reason: string,
  ): Promise<TestAccountResource> {
    status.value = "saving";
    clearError();
    try {
      const response = await apiClient.rotate_test_account_secret(
        account.test_account_id,
        { expected_version: account.row_version, secret_value: secretValue, reason },
        mutationOptions(),
      );
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "测试账号凭据更新失败，请刷新后重试。");
    } finally {
      status.value = "idle";
    }
  }

  async function lifecycle(
    account: TestAccountResource,
    action: TestAccountLifecycleAction,
    reason: string,
  ): Promise<TestAccountResource> {
    const methods = {
      validate: apiClient.validate_test_account.bind(apiClient),
      reconfigure: apiClient.reconfigure_test_account.bind(apiClient),
      activate: apiClient.activate_test_account.bind(apiClient),
      "mark-credential-expired": apiClient.mark_credential_expired_test_account.bind(apiClient),
      recover: apiClient.recover_test_account.bind(apiClient),
      disable: apiClient.disable_test_account.bind(apiClient),
      archive: apiClient.archive_test_account.bind(apiClient),
    };
    status.value = "saving";
    clearError();
    try {
      const response = await methods[action](
        account.test_account_id,
        { expected_version: account.row_version, reason },
        mutationOptions(),
      );
      replace(response.data);
      return response.data;
    } catch (error) {
      return capture(error, "测试账号生命周期操作失败。");
    } finally {
      status.value = "idle";
    }
  }

  function replace(value: TestAccountResource): void {
    const index = items.value.findIndex((item) => item.test_account_id === value.test_account_id);
    if (index >= 0) items.value.splice(index, 1, value);
    current.value = value;
  }

  return {
    items,
    page,
    current,
    status,
    errorMessage,
    correlationId,
    errorCode,
    clearError,
    load,
    create,
    updateName,
    rotateSecret,
    lifecycle,
  };
});
