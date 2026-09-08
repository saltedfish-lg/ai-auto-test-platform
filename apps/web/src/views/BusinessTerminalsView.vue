<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type {
  BusinessTerminalResource,
  EnvironmentTerminalAccessRevisionResource,
} from "../generated/types";
import { enumLabel, statusLabel } from "../presentation/labels";
import { useBusinessTerminalsStore } from "../stores/businessTerminals";
import { useEnvironmentsStore } from "../stores/environments";

const route = useRoute();
const router = useRouter();
const terminals = useBusinessTerminalsStore();
const environments = useEnvironmentsStore();
const projectId = computed(() => String(route.params.projectId));

function environmentName(id: string): string {
  const item = environments.items.find((environment) => environment.environment_id === id);
  return item?.display_name || item?.environment_code || "未命名环境";
}

function loginStrategyName(id: string | null | undefined): string {
  if (!id) return "未配置";
  const item = terminals.strategies.find((strategy) => strategy.login_strategy_id === id);
  return item?.display_name || "未命名登录策略";
}
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
const revisionReadOnlyVisible = ref(false);
const editingRevision = ref<EnvironmentTerminalAccessRevisionResource | null>(null);
const viewedRevision = ref<EnvironmentTerminalAccessRevisionResource | null>(null);
const loginStrategyVisible = ref(false);
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
  login_prerequisites: "",
  network_requirements: "",
  reason: "",
});
const loginStrategyForm = reactive({
  display_name: "",
  captcha_policy: "NONE" as "NONE" | "RESPONSE_HEADER",
  captcha_request_header_name: "",
  captcha_request_header_value: "",
  captcha_response_header_name: "",
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

function openLoginStrategy(): void {
  Object.assign(loginStrategyForm, {
    display_name: "",
    captcha_policy: "NONE",
    captcha_request_header_name: "",
    captcha_request_header_value: "",
    captcha_response_header_name: "",
    reason: "",
  });
  loginStrategyVisible.value = true;
}

async function submitLoginStrategy(): Promise<void> {
  if (!loginStrategyForm.display_name.trim() || !loginStrategyForm.reason.trim()) return;
  if (
    loginStrategyForm.captcha_policy === "RESPONSE_HEADER" &&
    (!loginStrategyForm.captcha_request_header_name.trim() ||
      !loginStrategyForm.captcha_request_header_value.trim() ||
      !loginStrategyForm.captcha_response_header_name.trim())
  ) {
    ElMessage.warning("RESPONSE_HEADER 策略必须填写完整的请求头与响应头配置。");
    return;
  }
  try {
    const strategy = await terminals.createAndActivateLoginStrategy({
      project_id: projectId.value,
      display_name: loginStrategyForm.display_name.trim(),
      captcha_policy: loginStrategyForm.captcha_policy,
      captcha_request_header_name:
        loginStrategyForm.captcha_policy === "RESPONSE_HEADER"
          ? loginStrategyForm.captcha_request_header_name.trim()
          : null,
      captcha_request_header_value:
        loginStrategyForm.captcha_policy === "RESPONSE_HEADER"
          ? loginStrategyForm.captcha_request_header_value.trim()
          : null,
      captcha_response_header_name:
        loginStrategyForm.captcha_policy === "RESPONSE_HEADER"
          ? loginStrategyForm.captcha_response_header_name.trim()
          : null,
      reason: loginStrategyForm.reason.trim(),
    });
    loginStrategyVisible.value = false;
    ElMessage.success(`登录策略 ${strategy.display_name || strategy.login_strategy_id} 已启用。`);
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

function openRevision(source?: EnvironmentTerminalAccessRevisionResource): void {
  editingRevision.value = source?.lifecycle_status === "DRAFT" ? source : null;
  Object.assign(revisionForm, {
    entry_url: source?.entry_url ?? "",
    login_url: source?.login_url ?? "",
    login_strategy_id: source?.login_strategy_id ?? "",
    display_name: source?.display_name ?? "",
    login_prerequisites: source?.login_prerequisites
      ? JSON.stringify(source.login_prerequisites, null, 2)
      : "",
    network_requirements: source?.network_requirements
      ? JSON.stringify(source.network_requirements, null, 2)
      : "",
    reason: "",
  });
  revisionVisible.value = true;
}

function parseOptionalJson(value: string, label: string): Record<string, unknown> | null {
  if (!value.trim()) return null;
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label}必须是 JSON 对象。`);
  }
  return parsed as Record<string, unknown>;
}

async function submitRevision(): Promise<void> {
  if (!selected.value || !revisionForm.entry_url.trim()) return;
  try {
    const values = {
      entry_url: revisionForm.entry_url.trim(),
      login_url: revisionForm.login_url.trim() || null,
      login_strategy_id: revisionForm.login_strategy_id || null,
      display_name: revisionForm.display_name.trim() || null,
      login_prerequisites: parseOptionalJson(revisionForm.login_prerequisites, "登录前置条件"),
      network_requirements: parseOptionalJson(revisionForm.network_requirements, "网络要求"),
      reason: revisionForm.reason.trim() || "保存终端访问修订",
    };
    if (editingRevision.value) {
      await terminals.updateRevision(editingRevision.value, values);
    } else {
      await terminals.createRevision({
        business_terminal_id: selected.value.business_terminal_id,
        ...values,
      });
    }
    revisionVisible.value = false;
    ElMessage.success(editingRevision.value ? "草稿访问修订已更新。" : "草稿访问修订已创建。");
  } catch (error) {
    if (
      error instanceof SyntaxError ||
      (error instanceof Error && error.message.includes("JSON"))
    ) {
      ElMessage.warning(error instanceof Error ? error.message : "JSON 格式错误。");
    }
  }
}

function viewRevision(revision: EnvironmentTerminalAccessRevisionResource): void {
  viewedRevision.value = revision;
  revisionReadOnlyVisible.value = true;
}

async function abandonRevision(revision: EnvironmentTerminalAccessRevisionResource): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt("请输入放弃原因", "放弃草稿访问修订", {
      inputPattern: /\S+/,
      inputErrorMessage: "原因不能为空。",
    });
    await terminals.abandonRevision(revision, value.trim());
    ElMessage.success("草稿访问修订已安全放弃。");
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      /* store exposes formal error */
    }
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

async function returnRevisionToDraft(
  revision: EnvironmentTerminalAccessRevisionResource,
): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt("请输入返回草稿原因", "返回草稿访问修订", {
      inputPattern: /\S+/,
      inputErrorMessage: "原因不能为空。",
    });
    await terminals.returnRevisionToDraft(revision, value.trim());
    ElMessage.success("访问修订已返回草稿，可继续编辑修正。");
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      /* store exposes formal error */
    }
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
          管理端、客户端与 PDA 均为 Web 终端；访问配置由终端自己的不可变访问修订发布。
        </p>
      </div>
      <div>
        <PermissionGate permission="PROJECT_EDIT"
          ><el-button @click="openLoginStrategy">新建登录策略</el-button></PermissionGate
        >
        <PermissionGate permission="BUSINESS_TERMINAL_CREATE"
          ><el-button type="primary" @click="openCreate">创建业务终端</el-button></PermissionGate
        >
      </div>
    </div>
    <el-alert
      v-if="terminals.errorMessage"
      :title="terminals.errorMessage"
      type="error"
      :closable="false"
      show-icon
    >
      <template v-if="terminals.errorCode || terminals.correlationId" #default>
        <span v-if="terminals.errorCode">错误代码：{{ terminals.errorCode }}</span>
        <span v-if="terminals.errorCode && terminals.correlationId"> · </span>
        <span v-if="terminals.correlationId">请求标识：{{ terminals.correlationId }}</span>
      </template>
    </el-alert>
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
            :label="enumLabel('terminalType', value)"
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
            :label="statusLabel('lifecycle', value)"
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
        <el-table-column label="环境" min-width="170"><template #default="{ row }">{{ environmentName(row.environment_id) }}</template></el-table-column>
        <el-table-column label="终端类型" min-width="120"><template #default="{ row }">{{ enumLabel('terminalType', row.terminal_type) }}</template></el-table-column>
        <el-table-column label="访问配置" min-width="160"><template #default="{ row }">{{ row.current_published_revision_id ? "已发布" : "未发布" }}</template></el-table-column>
        <el-table-column label="状态" min-width="120"><template #default="{ row }">{{ statusLabel('lifecycle', row.lifecycle_status) }}</template></el-table-column>
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
        <el-form-item label="环境" required
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
              :label="enumLabel('terminalType', value)"
              :value="value" /></el-select
        ></el-form-item>
        <el-form-item label="原因"
          ><el-input v-model="createForm.reason" type="textarea"
        /></el-form-item>
        <p class="security-form-note">创建终端不会隐式创建占位访问修订。</p> </el-form
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

    <el-dialog v-model="loginStrategyVisible" title="新建并启用登录策略" width="min(620px, 92vw)">
      <el-form label-position="top">
        <el-form-item label="策略名称" required>
          <el-input v-model="loginStrategyForm.display_name" maxlength="255" />
        </el-form-item>
        <el-form-item label="验证码策略" required>
          <el-select v-model="loginStrategyForm.captcha_policy">
            <el-option :label="enumLabel('captchaPolicy', 'NONE')" value="NONE" />
            <el-option :label="enumLabel('captchaPolicy', 'RESPONSE_HEADER')" value="RESPONSE_HEADER" />
          </el-select>
        </el-form-item>
        <template v-if="loginStrategyForm.captcha_policy === 'RESPONSE_HEADER'">
          <el-form-item label="验证码请求头名称" required>
            <el-input v-model="loginStrategyForm.captcha_request_header_name" />
          </el-form-item>
          <el-form-item label="验证码请求头值" required>
            <el-input
              v-model="loginStrategyForm.captcha_request_header_value"
              type="password"
              show-password
            />
          </el-form-item>
          <el-form-item label="验证码响应头名称" required>
            <el-input v-model="loginStrategyForm.captcha_response_header_name" />
          </el-form-item>
        </template>
        <el-form-item label="原因" required>
          <el-input v-model="loginStrategyForm.reason" type="textarea" />
        </el-form-item>
        <p class="security-form-note">
          此操作复用正式自动化资产 → 登录策略 → 配置草稿 → 启用路径；失败重试会复用已创建对象。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="loginStrategyVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="terminals.status === 'saving'"
          @click="submitLoginStrategy"
          >创建并启用</el-button
        >
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="业务终端详情" width="min(900px, 94vw)">
      <dl v-if="selected" class="identity-list">
        <dt>环境</dt><dd>{{ environmentName(selected.environment_id) }}</dd>
        <dt>终端类型</dt><dd>{{ enumLabel('terminalType', selected.terminal_type) }}</dd>
        <dt>状态</dt><dd>{{ statusLabel('lifecycle', selected.lifecycle_status) }}</dd>
        <dt>访问配置</dt><dd>{{ selected.current_published_revision_id ? "已有发布修订" : "未发布" }}</dd>
      </dl>
      <el-collapse v-if="selected"><el-collapse-item title="技术信息" name="technical"><p>终端标识：<code>{{ selected.business_terminal_id }}</code></p><p>当前发布修订标识：<code>{{ selected.current_published_revision_id || "—" }}</code></p></el-collapse-item></el-collapse>
      <div class="page-heading">
        <h3>终端访问修订</h3>
        <PermissionGate permission="BUSINESS_TERMINAL_EDIT"
          ><el-button type="primary" @click="openRevision()"
            >新建访问修订</el-button
          ></PermissionGate
        >
      </div>
      <el-table :data="terminals.revisions" empty-text="尚无访问修订">
        <el-table-column prop="revision_no" label="修订号" width="110" />
        <el-table-column label="当前" width="75">
          <template #default="{ row }">{{
            row.environment_terminal_access_revision_id === selected?.current_published_revision_id
              ? "是"
              : "否"
          }}</template>
        </el-table-column>
        <el-table-column prop="entry_url" label="入口 URL" min-width="230" />
        <el-table-column prop="login_url" label="登录 URL" min-width="220" />
        <el-table-column label="登录策略" min-width="180"><template #default="{ row }">{{ loginStrategyName(row.login_strategy_id) }}</template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column prop="published_at" label="发布时间" min-width="180" />
        <el-table-column label="状态" width="120"><template #default="{ row }">{{ statusLabel('lifecycle', row.lifecycle_status) }}</template></el-table-column>
        <el-table-column label="操作" min-width="320" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewRevision(row)">查看</el-button>
            <PermissionGate permission="BUSINESS_TERMINAL_EDIT">
              <el-button
                v-if="row.lifecycle_status === 'DRAFT'"
                link
                type="primary"
                @click="openRevision(row)"
                >编辑</el-button
              >
              <el-button v-if="row.lifecycle_status === 'DRAFT'" link @click="validateRevision(row)"
                >校验</el-button
              >
              <el-button v-if="row.lifecycle_status === 'DRAFT'" link disabled title="请先完成校验"
                >发布</el-button
              >
              <el-button
                v-if="row.lifecycle_status === 'DRAFT'"
                link
                type="danger"
                @click="abandonRevision(row)"
                >放弃</el-button
              >
              <el-button
                v-if="row.lifecycle_status === 'VALIDATING'"
                link
                type="primary"
                @click="returnRevisionToDraft(row)"
                >返回草稿</el-button
              >
              <el-button
                v-if="row.lifecycle_status === 'VALIDATING'"
                link
                type="success"
                @click="publishRevision(row)"
                >发布</el-button
              >
              <el-button
                v-if="
                  row.lifecycle_status === 'PUBLISHED' &&
                  row.environment_terminal_access_revision_id ===
                    selected?.current_published_revision_id
                "
                link
                @click="openRevision(row)"
                >基于此创建新修订</el-button
              >
            </PermissionGate>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="revisionVisible"
      :title="editingRevision ? '编辑草稿访问修订' : '新建草稿访问修订'"
      width="min(600px,92vw)"
      ><el-form label-position="top"
        ><el-form-item label="入口 URL" required
          ><el-input
            v-model="revisionForm.entry_url"
            placeholder="https://example.test/app" /></el-form-item
        ><el-form-item label="登录 URL"><el-input v-model="revisionForm.login_url" /></el-form-item
        ><el-form-item label="登录策略"
          ><el-select v-model="revisionForm.login_strategy_id" clearable
            ><el-option
              v-for="item in terminals.strategies.filter(
                (value) => value.lifecycle_status === 'ACTIVE',
              )"
              :key="item.login_strategy_id"
              :label="item.display_name || '未命名登录策略'"
              :value="item.login_strategy_id" /></el-select></el-form-item
        ><el-form-item label="名称"><el-input v-model="revisionForm.display_name" /></el-form-item
        ><el-form-item label="登录前置条件（JSON 对象）"
          ><el-input
            v-model="revisionForm.login_prerequisites"
            type="textarea"
            :rows="3" /></el-form-item
        ><el-form-item label="网络要求（JSON 对象）"
          ><el-input
            v-model="revisionForm.network_requirements"
            type="textarea"
            :rows="3" /></el-form-item
        ><el-form-item label="原因"
          ><el-input v-model="revisionForm.reason" /></el-form-item></el-form
      ><template #footer
        ><el-button @click="revisionVisible = false">取消</el-button
        ><el-button type="primary" @click="submitRevision">{{
          editingRevision ? "保存草稿" : "创建草稿"
        }}</el-button></template
      ></el-dialog
    >
    <el-dialog v-model="revisionReadOnlyVisible" title="查看访问修订" width="min(680px,92vw)">
      <dl v-if="viewedRevision" class="identity-list">
        <dt>修订号</dt>
        <dd>{{ viewedRevision.revision_no }}</dd>
        <dt>状态</dt>
        <dd>{{ statusLabel('lifecycle', viewedRevision.lifecycle_status) }}</dd>
        <dt>入口 URL</dt>
        <dd>{{ viewedRevision.entry_url }}</dd>
        <dt>登录 URL</dt>
        <dd>{{ viewedRevision.login_url || "—" }}</dd>
        <dt>登录策略</dt>
        <dd>{{ loginStrategyName(viewedRevision.login_strategy_id) }}</dd>
        <dt>创建时间</dt>
        <dd>{{ viewedRevision.created_at }}</dd>
        <dt>发布时间</dt>
        <dd>{{ viewedRevision.published_at || "未发布" }}</dd>
      </dl>
    </el-dialog>
  </section>
</template>
