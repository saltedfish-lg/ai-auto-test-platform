<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type { TestAccountResource } from "../generated/types";
import { useBusinessTerminalsStore } from "../stores/businessTerminals";
import { useEnvironmentsStore } from "../stores/environments";
import { type TestAccountLifecycleAction, useTestAccountsStore } from "../stores/testAccounts";

const route = useRoute();
const router = useRouter();
const accounts = useTestAccountsStore();
const environments = useEnvironmentsStore();
const terminals = useBusinessTerminalsStore();
const projectId = computed(() => String(route.params.projectId));

const filters = reactive({ environmentId: "", businessTerminalId: "", lifecycleStatus: "" });
const createVisible = ref(false);
const editVisible = ref(false);
const secretVisible = ref(false);
const lifecycleVisible = ref(false);
const detailVisible = ref(false);
const selected = ref<TestAccountResource | null>(null);
const lifecycleAction = ref<TestAccountLifecycleAction>("validate");
const createForm = reactive({
  environment_id: "",
  account_identifier: "",
  display_name: "",
  business_terminal_ids: [] as string[],
  secret_value: "",
  reason: "",
});
const editForm = reactive({ display_name: "", reason: "" });
const secretForm = reactive({ secret_value: "", reason: "" });
const lifecycleReason = ref("");
const localError = ref("");

const availableTerminals = computed(() =>
  terminals.items.filter(
    (item) => !createForm.environment_id || item.environment_id === createForm.environment_id,
  ),
);

watch(
  projectId,
  (id) => {
    void Promise.all([
      accounts.load(id),
      environments.load(id, undefined, 1, 200),
      terminals.load(id, {}, 1, 200),
    ]).catch(() => undefined);
  },
  { immediate: true },
);

watch(
  () => createForm.environment_id,
  () => {
    createForm.business_terminal_ids = createForm.business_terminal_ids.filter((id) =>
      availableTerminals.value.some((terminal) => terminal.business_terminal_id === id),
    );
  },
);

function environmentName(id: string): string {
  const item = environments.items.find((environment) => environment.environment_id === id);
  return item?.display_name || item?.environment_code || id;
}

async function refresh(page = accounts.page.page): Promise<void> {
  await accounts
    .load(
      projectId.value,
      {
        environmentId: filters.environmentId || undefined,
        businessTerminalId: filters.businessTerminalId || undefined,
        lifecycleStatus: filters.lifecycleStatus || undefined,
      },
      page,
      accounts.page.page_size,
    )
    .catch(() => undefined);
}

function openCreate(): void {
  Object.assign(createForm, {
    environment_id: filters.environmentId,
    account_identifier: "",
    display_name: "",
    business_terminal_ids: filters.businessTerminalId ? [filters.businessTerminalId] : [],
    secret_value: "",
    reason: "",
  });
  localError.value = "";
  createVisible.value = true;
}

async function submitCreate(): Promise<void> {
  if (
    !createForm.environment_id ||
    !createForm.account_identifier.trim() ||
    !createForm.business_terminal_ids.length ||
    !createForm.secret_value ||
    !createForm.reason.trim()
  ) {
    localError.value = "请完整填写环境、账号标识、适用终端、凭据和原因。";
    return;
  }
  try {
    await accounts.create({
      environment_id: createForm.environment_id,
      account_identifier: createForm.account_identifier.trim(),
      display_name: createForm.display_name.trim() || null,
      business_terminal_ids: [...createForm.business_terminal_ids],
      secret_value: createForm.secret_value,
      reason: createForm.reason.trim(),
    });
    createForm.secret_value = "";
    createVisible.value = false;
    await refresh(1);
    ElMessage.success("测试账号已创建，凭据不会回显。");
  } catch {
    createForm.secret_value = "";
  }
}

function openDetail(account: TestAccountResource): void {
  selected.value = account;
  detailVisible.value = true;
}

function openEdit(account: TestAccountResource): void {
  selected.value = account;
  editForm.display_name = account.display_name ?? "";
  editForm.reason = "";
  localError.value = "";
  editVisible.value = true;
}

async function submitEdit(): Promise<void> {
  if (!selected.value || !editForm.reason.trim()) {
    localError.value = "请填写修改原因。";
    return;
  }
  try {
    await accounts.updateName(
      selected.value,
      editForm.display_name.trim() || null,
      editForm.reason.trim(),
    );
    editVisible.value = false;
    ElMessage.success("测试账号非敏感信息已更新。");
  } catch {
    // Store exposes the operation-specific error.
  }
}

function openSecret(account: TestAccountResource): void {
  selected.value = account;
  secretForm.secret_value = "";
  secretForm.reason = "";
  localError.value = "";
  secretVisible.value = true;
}

async function submitSecret(): Promise<void> {
  if (!selected.value || !secretForm.secret_value || !secretForm.reason.trim()) {
    localError.value = "请填写新凭据和轮换原因。";
    return;
  }
  try {
    await accounts.rotateSecret(selected.value, secretForm.secret_value, secretForm.reason.trim());
    secretForm.secret_value = "";
    secretVisible.value = false;
    ElMessage.success("凭据已安全轮换，旧值不会回显。");
  } catch {
    secretForm.secret_value = "";
  }
}

function openLifecycle(account: TestAccountResource, action: TestAccountLifecycleAction): void {
  selected.value = account;
  lifecycleAction.value = action;
  lifecycleReason.value = "";
  localError.value = "";
  lifecycleVisible.value = true;
}

function handleLifecycleCommand(
  account: TestAccountResource,
  action: string | number | object,
): void {
  openLifecycle(account, action as TestAccountLifecycleAction);
}

async function submitLifecycle(): Promise<void> {
  if (!selected.value || !lifecycleReason.value.trim()) {
    localError.value = "请填写状态变更原因。";
    return;
  }
  try {
    await accounts.lifecycle(selected.value, lifecycleAction.value, lifecycleReason.value.trim());
    lifecycleVisible.value = false;
    ElMessage.success("测试账号状态已更新。");
  } catch {
    // Store exposes the operation-specific error.
  }
}

function actions(account: TestAccountResource): TestAccountLifecycleAction[] {
  const mapping: Record<string, TestAccountLifecycleAction[]> = {
    CONFIGURING: ["validate"],
    VALIDATING: ["reconfigure", "activate"],
    ACTIVE: ["mark-credential-expired", "disable"],
    CREDENTIAL_EXPIRED: ["recover"],
    RECOVERING: ["activate"],
    DISABLED: ["recover", "archive"],
  };
  return mapping[account.lifecycle_status] ?? [];
}

const lifecycleLabel: Record<TestAccountLifecycleAction, string> = {
  validate: "提交校验",
  reconfigure: "退回配置",
  activate: "激活",
  "mark-credential-expired": "标记凭据失效",
  recover: "开始恢复",
  disable: "停用",
  archive: "归档",
};
</script>

<template>
  <section class="account-page" aria-labelledby="test-account-title">
    <div class="page-heading">
      <div>
        <el-button
          link
          type="primary"
          @click="router.push({ name: 'projects.detail', params: { id: projectId } })"
        >
          ← 返回项目详情
        </el-button>
        <h2 id="test-account-title">测试账号</h2>
        <p>管理登录身份、加密凭据和业务终端适用范围；登录机制仍由业务终端负责。</p>
      </div>
      <PermissionGate permission="PROJECT_EDIT">
        <el-button type="primary" @click="openCreate">新建测试账号</el-button>
      </PermissionGate>
    </div>

    <el-alert
      v-if="accounts.errorMessage"
      :title="accounts.errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="workspace-alert"
    >
      <template v-if="accounts.correlationId" #default>
        <span>请求标识：{{ accounts.correlationId }}</span>
      </template>
    </el-alert>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="环境">
          <el-select
            v-model="filters.environmentId"
            clearable
            placeholder="全部环境"
            style="width: 180px"
          >
            <el-option
              v-for="item in environments.items"
              :key="item.environment_id"
              :label="item.display_name || item.environment_code || item.environment_id"
              :value="item.environment_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="业务终端">
          <el-select
            v-model="filters.businessTerminalId"
            clearable
            placeholder="全部终端"
            style="width: 180px"
          >
            <el-option
              v-for="item in terminals.items"
              :key="item.business_terminal_id"
              :label="item.display_name || item.terminal_code"
              :value="item.business_terminal_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filters.lifecycleStatus"
            clearable
            placeholder="全部状态"
            style="width: 160px"
          >
            <el-option
              v-for="status in [
                'CONFIGURING',
                'VALIDATING',
                'ACTIVE',
                'CREDENTIAL_EXPIRED',
                'DISABLED',
                'RECOVERING',
                'ARCHIVED',
              ]"
              :key="status"
              :label="status"
              :value="status"
            />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="refresh(1)">查询</el-button>
      </el-form>
    </el-card>

    <el-table
      :data="accounts.items"
      v-loading="accounts.status === 'loading'"
      empty-text="暂无测试账号"
    >
      <el-table-column prop="account_identifier" label="账号标识" min-width="150" />
      <el-table-column prop="display_name" label="显示名称" min-width="140" />
      <el-table-column label="环境" min-width="150">
        <template #default="scope">{{ environmentName(scope.row.environment_id) }}</template>
      </el-table-column>
      <el-table-column label="业务终端" min-width="220">
        <template #default="scope">
          <el-tag
            v-for="terminal in scope.row.business_terminals"
            :key="terminal.business_terminal_id"
            class="terminal-tag"
          >
            {{ terminal.display_name || terminal.terminal_code }} / {{ terminal.terminal_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="lifecycle_status" label="状态" width="170" />
      <el-table-column label="凭据" width="130">
        <template #default="scope"
          >{{ scope.row.credential_state }} · v{{ scope.row.credential_revision_no }}</template
        >
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" min-width="180" />
      <el-table-column label="操作" fixed="right" min-width="300">
        <template #default="scope">
          <el-button link type="primary" @click="openDetail(scope.row)">详情</el-button>
          <PermissionGate permission="PROJECT_EDIT">
            <el-button
              v-if="scope.row.lifecycle_status !== 'ARCHIVED'"
              link
              type="primary"
              @click="openEdit(scope.row)"
              >编辑</el-button
            >
            <el-button
              v-if="scope.row.lifecycle_status !== 'ARCHIVED'"
              link
              type="warning"
              @click="openSecret(scope.row)"
              >更新凭据</el-button
            >
            <el-dropdown
              v-if="actions(scope.row).length"
              @command="
                (action: string | number | object) => handleLifecycleCommand(scope.row, action)
              "
            >
              <el-button link type="primary">状态操作</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="action in actions(scope.row)"
                    :key="action"
                    :command="action"
                    >{{ lifecycleLabel[action] }}</el-dropdown-item
                  >
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </PermissionGate>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pagination"
      layout="prev, pager, next, total"
      :current-page="accounts.page.page"
      :page-size="accounts.page.page_size"
      :total="accounts.page.total"
      @current-change="refresh"
    />

    <el-dialog
      v-model="createVisible"
      title="新建测试账号"
      width="600px"
      @closed="createForm.secret_value = ''"
    >
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top">
        <el-form-item label="环境"
          ><el-select v-model="createForm.environment_id" style="width: 100%"
            ><el-option
              v-for="item in environments.items"
              :key="item.environment_id"
              :label="item.display_name || item.environment_code || item.environment_id"
              :value="item.environment_id" /></el-select
        ></el-form-item>
        <el-form-item label="账号标识"
          ><el-input v-model="createForm.account_identifier" autocomplete="off"
        /></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="createForm.display_name" /></el-form-item>
        <el-form-item label="适用业务终端"
          ><el-select v-model="createForm.business_terminal_ids" multiple style="width: 100%"
            ><el-option
              v-for="item in availableTerminals"
              :key="item.business_terminal_id"
              :label="`${item.display_name || item.terminal_code} / ${item.terminal_type}`"
              :value="item.business_terminal_id" /></el-select
        ></el-form-item>
        <el-form-item label="登录凭据"
          ><el-input
            v-model="createForm.secret_value"
            type="password"
            show-password
            autocomplete="new-password"
        /></el-form-item>
        <el-form-item label="创建原因"
          ><el-input v-model="createForm.reason" type="textarea"
        /></el-form-item>
      </el-form>
      <template #footer
        ><el-button @click="createVisible = false">取消</el-button
        ><el-button type="primary" :loading="accounts.status === 'saving'" @click="submitCreate"
          >创建</el-button
        ></template
      >
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑测试账号" width="520px">
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top"
        ><el-form-item label="显示名称"><el-input v-model="editForm.display_name" /></el-form-item
        ><el-form-item label="修改原因"
          ><el-input v-model="editForm.reason" type="textarea" /></el-form-item
      ></el-form>
      <template #footer
        ><el-button @click="editVisible = false">取消</el-button
        ><el-button type="primary" :loading="accounts.status === 'saving'" @click="submitEdit"
          >保存</el-button
        ></template
      >
    </el-dialog>

    <el-dialog
      v-model="secretVisible"
      title="更新登录凭据"
      width="520px"
      @closed="secretForm.secret_value = ''"
    >
      <el-alert
        title="现有凭据不会回显；提交成功或失败后输入都会立即清除。"
        type="warning"
        :closable="false"
      />
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top"
        ><el-form-item label="新凭据"
          ><el-input
            v-model="secretForm.secret_value"
            type="password"
            show-password
            autocomplete="new-password" /></el-form-item
        ><el-form-item label="轮换原因"
          ><el-input v-model="secretForm.reason" type="textarea" /></el-form-item
      ></el-form>
      <template #footer
        ><el-button @click="secretVisible = false">取消</el-button
        ><el-button type="primary" :loading="accounts.status === 'saving'" @click="submitSecret"
          >安全更新</el-button
        ></template
      >
    </el-dialog>

    <el-dialog v-model="lifecycleVisible" :title="lifecycleLabel[lifecycleAction]" width="500px">
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top"
        ><el-form-item label="操作原因"
          ><el-input v-model="lifecycleReason" type="textarea" /></el-form-item
      ></el-form>
      <template #footer
        ><el-button @click="lifecycleVisible = false">取消</el-button
        ><el-button type="primary" :loading="accounts.status === 'saving'" @click="submitLifecycle"
          >确认</el-button
        ></template
      >
    </el-dialog>

    <el-drawer v-model="detailVisible" title="测试账号详情" size="520px">
      <el-descriptions v-if="selected" :column="1" border>
        <el-descriptions-item label="账号标识">{{
          selected.account_identifier
        }}</el-descriptions-item>
        <el-descriptions-item label="显示名称">{{
          selected.display_name || "—"
        }}</el-descriptions-item>
        <el-descriptions-item label="环境">{{
          environmentName(selected.environment_id)
        }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ selected.lifecycle_status }}</el-descriptions-item>
        <el-descriptions-item label="凭据状态"
          >{{ selected.credential_state }} · revision
          {{ selected.credential_revision_no }}</el-descriptions-item
        >
        <el-descriptions-item label="适用终端"
          ><div
            v-for="terminal in selected.business_terminals"
            :key="terminal.business_terminal_id"
          >
            {{ terminal.display_name || terminal.terminal_code }} / {{ terminal.terminal_type }}
          </div></el-descriptions-item
        >
        <el-descriptions-item label="并发版本">{{ selected.row_version }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </section>
</template>

<style scoped>
.account-page {
  display: grid;
  gap: 18px;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}
.page-heading h2 {
  margin: 8px 0;
}
.page-heading p {
  margin: 0;
  color: var(--el-text-color-secondary);
}
.filter-card :deep(.el-card__body) {
  padding-bottom: 2px;
}
.workspace-alert {
  margin-bottom: 2px;
}
.terminal-tag {
  margin: 2px 6px 2px 0;
}
.pagination {
  justify-content: flex-end;
}
</style>
