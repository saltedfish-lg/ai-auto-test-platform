<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type {
  BusinessTerminalResource,
  EnvironmentTerminalAccessRevisionResource,
} from "../generated/types";
import { useBusinessTerminalsStore } from "../stores/businessTerminals";
import { useEnvironmentsStore } from "../stores/environments";

const route = useRoute();
const router = useRouter();
const terminals = useBusinessTerminalsStore();
const environments = useEnvironmentsStore();
const projectId = computed(() => String(route.params.projectId));
const currentPage = ref(1);
const pageSize = ref(50);
const environmentFilter = ref("");
const typeFilter = ref("");
const lifecycleFilter = ref("");
const selected = ref<BusinessTerminalResource | null>(null);
const createVisible = ref(false);
const editVisible = ref(false);
const detailVisible = ref(false);
const revisionVisible = ref(false);
const createForm = reactive({
  environment_id: "",
  terminal_code: "",
  display_name: "",
  terminal_type: "MANAGEMENT",
  reason: "",
});
const editForm = reactive({ display_name: "", reason: "" });
const revisionForm = reactive({
  entry_url: "",
  login_url: "",
  login_strategy_id: "",
  display_name: "",
  reason: "",
});

watch(
  projectId,
  async (id) => {
    currentPage.value = 1;
    await Promise.all([
      environments.load(id, undefined, 1, 200),
      terminals.load(id, {}, 1, pageSize.value),
      terminals.loadStrategies(id),
    ]).catch(() => undefined);
  },
  { immediate: true },
);

async function loadPage(): Promise<void> {
  await terminals
    .load(
      projectId.value,
      {
        environmentId: environmentFilter.value || undefined,
        terminalType: typeFilter.value || undefined,
        lifecycleStatus: lifecycleFilter.value || undefined,
      },
      currentPage.value,
      pageSize.value,
    )
    .catch(() => undefined);
}

function changePage(value: number): void {
  currentPage.value = value;
  void loadPage();
}

function changePageSize(value: number): void {
  pageSize.value = value;
  currentPage.value = 1;
  void loadPage();
}

function openCreate(): void {
  Object.assign(createForm, {
    environment_id: environmentFilter.value,
    terminal_code: "",
    display_name: "",
    terminal_type: "MANAGEMENT",
    reason: "",
  });
  createVisible.value = true;
}

async function submitCreate(): Promise<void> {
  if (!createForm.environment_id || !createForm.terminal_code.trim()) return;
  try {
    await terminals.create({
      environment_id: createForm.environment_id,
      terminal_code: createForm.terminal_code.trim(),
      display_name: createForm.display_name.trim() || null,
      terminal_type: createForm.terminal_type as "MANAGEMENT" | "CLIENT" | "PDA",
      reason: createForm.reason.trim() || null,
    });
    createVisible.value = false;
    await loadPage();
    ElMessage.success("业务终端已创建；访问修订需单独创建。 ");
  } catch {
    /* store exposes formal error */
  }
}

async function openDetail(terminal: BusinessTerminalResource): Promise<void> {
  selected.value = terminal;
  detailVisible.value = true;
  await terminals.loadRevisions(terminal.business_terminal_id).catch(() => undefined);
}

function openEdit(terminal: BusinessTerminalResource): void {
  selected.value = terminal;
  Object.assign(editForm, { display_name: terminal.display_name ?? "", reason: "" });
  editVisible.value = true;
}

async function submitEdit(): Promise<void> {
  if (!selected.value) return;
  try {
    await terminals.updateName(
      selected.value,
      editForm.display_name.trim() || null,
      editForm.reason.trim() || null,
    );
    editVisible.value = false;
    ElMessage.success("终端名称已更新。 ");
  } catch {
    /* store exposes formal error */
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
): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt("请输入操作原因", "业务终端生命周期操作", {
      inputPattern: /\S+/,
      inputErrorMessage: "原因不能为空。",
    });
    const changed = await terminals.lifecycle(terminal, action, value.trim());
    selected.value = changed;
    ElMessage.success(`终端已进入 ${changed.lifecycle_status}。`);
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      /* store exposes formal error */
    }
  }
}

function openRevision(): void {
  Object.assign(revisionForm, {
    entry_url: "",
    login_url: "",
    login_strategy_id: "",
    display_name: "",
    reason: "",
  });
  revisionVisible.value = true;
}

async function submitRevision(): Promise<void> {
  if (!selected.value || !revisionForm.entry_url.trim()) return;
  try {
    await terminals.createRevision({
      business_terminal_id: selected.value.business_terminal_id,
      entry_url: revisionForm.entry_url.trim(),
      login_url: revisionForm.login_url.trim() || null,
      login_strategy_id: revisionForm.login_strategy_id || null,
      display_name: revisionForm.display_name.trim() || null,
      reason: revisionForm.reason.trim() || null,
    });
    revisionVisible.value = false;
    ElMessage.success("DRAFT 访问修订已单独创建。 ");
  } catch {
    /* store exposes formal error */
  }
}

async function validateRevision(
  revision: EnvironmentTerminalAccessRevisionResource,
): Promise<void> {
  try {
    await terminals.validateRevision(revision, "校验终端访问修订");
  } catch {
    /* store exposes formal error */
  }
}

async function publishRevision(revision: EnvironmentTerminalAccessRevisionResource): Promise<void> {
  if (!selected.value) return;
  try {
    await terminals.publishRevision(revision, selected.value, "发布终端访问修订");
    selected.value = terminals.current;
  } catch {
    /* store exposes formal error */
  }
}
</script>

<template>
  <section class="project-page" aria-labelledby="terminal-title">
    <div class="page-heading">
      <div>
        <el-button
          link
          type="primary"
          @click="router.push({ name: 'projects.detail', params: { id: projectId } })"
          >← 返回项目详情</el-button
        >
        <h2 id="terminal-title">业务终端</h2>
        <p class="muted">
          管理端、客户端与 PDA 均为 Web 终端；访问配置由终端自己的不可变 Revision 发布。
        </p>
      </div>
      <PermissionGate permission="BUSINESS_TERMINAL_CREATE"
        ><el-button type="primary" @click="openCreate">创建业务终端</el-button></PermissionGate
      >
    </div>
    <el-alert
      v-if="terminals.errorMessage"
      :title="terminals.errorMessage"
      type="error"
      :closable="false"
      show-icon
    />
    <el-card shadow="never">
      <div class="environment-toolbar">
        <el-select
          v-model="environmentFilter"
          placeholder="全部环境"
          clearable
          aria-label="环境筛选"
        >
          <el-option
            v-for="item in environments.items"
            :key="item.environment_id"
            :label="item.display_name || item.environment_code"
            :value="item.environment_id"
          />
        </el-select>
        <el-select
          v-model="typeFilter"
          placeholder="全部终端类型"
          clearable
          aria-label="终端类型筛选"
        >
          <el-option
            v-for="value in ['MANAGEMENT', 'CLIENT', 'PDA']"
            :key="value"
            :label="value"
            :value="value"
          />
        </el-select>
        <el-select
          v-model="lifecycleFilter"
          placeholder="全部状态"
          clearable
          aria-label="终端状态筛选"
        >
          <el-option
            v-for="value in [
              'CONFIGURING',
              'VALIDATING',
              'ACTIVE',
              'UNREACHABLE',
              'DISABLED',
              'RECOVERING',
              'ARCHIVED',
            ]"
            :key="value"
            :label="value"
            :value="value"
          />
        </el-select>
        <el-button
          @click="
            currentPage = 1;
            loadPage();
          "
          >筛选</el-button
        >
      </div>
      <el-table
        :data="terminals.items"
        v-loading="terminals.status === 'loading'"
        empty-text="当前项目暂无业务终端"
      >
        <el-table-column prop="terminal_code" label="终端编码" min-width="150" />
        <el-table-column prop="display_name" label="终端名称" min-width="150" />
        <el-table-column prop="environment_id" label="Environment" min-width="210" />
        <el-table-column prop="terminal_type" label="终端类型" min-width="120" />
        <el-table-column
          prop="current_published_revision_id"
          label="当前发布 Revision"
          min-width="220"
        />
        <el-table-column prop="lifecycle_status" label="状态" min-width="120" />
        <el-table-column prop="updated_at" label="更新时间" min-width="190" />
        <el-table-column label="操作" width="290" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <PermissionGate permission="BUSINESS_TERMINAL_EDIT">
              <el-button
                link
                type="primary"
                :disabled="row.lifecycle_status === 'ARCHIVED'"
                @click="openEdit(row)"
                >编辑</el-button
              >
              <el-button
                v-if="row.lifecycle_status === 'CONFIGURING'"
                link
                @click="lifecycle(row, 'validate')"
                >校验</el-button
              >
              <el-button
                v-if="['VALIDATING', 'RECOVERING'].includes(row.lifecycle_status)"
                link
                type="success"
                @click="lifecycle(row, 'activate')"
                >启用</el-button
              >
              <el-button
                v-if="row.lifecycle_status === 'ACTIVE'"
                link
                type="warning"
                @click="lifecycle(row, 'disable')"
                >停用</el-button
              >
              <el-button
                v-if="['UNREACHABLE', 'DISABLED'].includes(row.lifecycle_status)"
                link
                type="success"
                @click="lifecycle(row, 'recover')"
                >恢复</el-button
              >
            </PermissionGate>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :current-page="currentPage"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="terminals.page.total"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </el-card>

    <el-dialog v-model="createVisible" title="创建业务终端" width="min(560px, 92vw)"
      ><el-form label-position="top">
        <el-form-item label="Environment" required
          ><el-select v-model="createForm.environment_id"
            ><el-option
              v-for="item in environments.items"
              :key="item.environment_id"
              :label="item.display_name || item.environment_code"
              :value="item.environment_id" /></el-select
        ></el-form-item>
        <el-form-item label="终端编码" required
          ><el-input v-model="createForm.terminal_code" maxlength="191"
        /></el-form-item>
        <el-form-item label="终端名称"
          ><el-input v-model="createForm.display_name" maxlength="255"
        /></el-form-item>
        <el-form-item label="Web 终端类型" required
          ><el-select v-model="createForm.terminal_type"
            ><el-option
              v-for="value in ['MANAGEMENT', 'CLIENT', 'PDA']"
              :key="value"
              :label="value"
              :value="value" /></el-select
        ></el-form-item>
        <el-form-item label="原因"
          ><el-input v-model="createForm.reason" type="textarea"
        /></el-form-item>
        <p class="security-form-note">创建终端不会隐式创建占位 Revision。</p> </el-form
      ><template #footer
        ><el-button @click="createVisible = false">取消</el-button
        ><el-button type="primary" @click="submitCreate">确认创建</el-button></template
      ></el-dialog
    >

    <el-dialog v-model="editVisible" title="编辑业务终端" width="min(520px, 92vw)"
      ><el-form label-position="top">
        <el-form-item label="终端编码"
          ><el-input :model-value="selected?.terminal_code" disabled
        /></el-form-item>
        <el-form-item label="终端名称"><el-input v-model="editForm.display_name" /></el-form-item>
        <el-form-item label="原因"
          ><el-input v-model="editForm.reason" type="textarea"
        /></el-form-item> </el-form
      ><template #footer
        ><el-button @click="editVisible = false">取消</el-button
        ><el-button type="primary" @click="submitEdit">保存</el-button></template
      ></el-dialog
    >

    <el-dialog v-model="detailVisible" title="业务终端详情" width="min(900px, 94vw)">
      <dl v-if="selected" class="identity-list">
        <dt>Terminal ID</dt>
        <dd class="monospace">{{ selected.business_terminal_id }}</dd>
        <dt>终端类型</dt>
        <dd>{{ selected.terminal_type }}</dd>
        <dt>状态</dt>
        <dd>{{ selected.lifecycle_status }}</dd>
        <dt>当前发布 Revision</dt>
        <dd class="monospace">{{ selected.current_published_revision_id || "未发布" }}</dd>
      </dl>
      <div class="page-heading">
        <h3>Terminal Access Revisions</h3>
        <PermissionGate permission="BUSINESS_TERMINAL_EDIT"
          ><el-button type="primary" @click="openRevision">新建访问修订</el-button></PermissionGate
        >
      </div>
      <el-table :data="terminals.revisions" empty-text="尚无访问修订"
        ><el-table-column prop="revision_no" label="Revision" width="90" /><el-table-column
          prop="entry_url"
          label="入口 URL"
          min-width="230"
        /><el-table-column prop="login_url" label="登录 URL" min-width="220" /><el-table-column
          prop="lifecycle_status"
          label="状态"
          width="120"
        /><el-table-column label="操作" width="150"
          ><template #default="{ row }"
            ><PermissionGate permission="BUSINESS_TERMINAL_EDIT"
              ><el-button
                v-if="row.lifecycle_status === 'DRAFT'"
                link
                @click="validateRevision(row)"
                >校验</el-button
              ><el-button
                v-if="row.lifecycle_status === 'VALIDATING'"
                link
                type="success"
                @click="publishRevision(row)"
                >发布</el-button
              ></PermissionGate
            ></template
          ></el-table-column
        ></el-table
      >
    </el-dialog>

    <el-dialog v-model="revisionVisible" title="新建 DRAFT 访问修订" width="min(600px,92vw)"
      ><el-form label-position="top"
        ><el-form-item label="入口 URL" required
          ><el-input
            v-model="revisionForm.entry_url"
            placeholder="https://example.test/app" /></el-form-item
        ><el-form-item label="登录 URL"><el-input v-model="revisionForm.login_url" /></el-form-item
        ><el-form-item label="Login Strategy"
          ><el-select v-model="revisionForm.login_strategy_id" clearable
            ><el-option
              v-for="item in terminals.strategies.filter(
                (value) => value.lifecycle_status === 'ACTIVE',
              )"
              :key="item.login_strategy_id"
              :label="item.display_name || item.login_strategy_id"
              :value="item.login_strategy_id" /></el-select></el-form-item
        ><el-form-item label="名称"><el-input v-model="revisionForm.display_name" /></el-form-item
        ><el-form-item label="原因"
          ><el-input v-model="revisionForm.reason" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="revisionVisible = false">取消</el-button
        ><el-button type="primary" @click="submitRevision">创建 DRAFT</el-button></template
      ></el-dialog
    >
  </section>
</template>
