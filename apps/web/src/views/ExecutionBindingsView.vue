<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type {
  CreateRuntimePolicyRevisionRequest,
  ExecutionBindingInput,
  ExecutionBindingSnapshotResource,
  RuntimePolicyRevisionResource,
} from "../generated/types";
import {
  capabilityLabel,
  enumLabel,
  preflightCheckLabel,
  statusLabel,
} from "../presentation/labels";
import { useBusinessTerminalsStore } from "../stores/businessTerminals";
import { useEnvironmentsStore } from "../stores/environments";
import { type BindingCommand, useExecutionBindingsStore } from "../stores/executionBindings";
import { useRunnersStore } from "../stores/runners";
import { useTestAccountsStore } from "../stores/testAccounts";

const route = useRoute();
const router = useRouter();
const bindings = useExecutionBindingsStore();
const environments = useEnvironmentsStore();
const terminals = useBusinessTerminalsStore();
const accounts = useTestAccountsStore();
const runners = useRunnersStore();
const projectId = computed(() => String(route.params.projectId ?? ""));

const statusFilter = ref("");
const selected = ref<ExecutionBindingSnapshotResource | null>(null);
const detailVisible = ref(false);
const createVisible = ref(false);
const policyVisible = ref(false);
const commandVisible = ref(false);
const commandAction = ref<BindingCommand>("release");
const commandReason = ref("");
const recoveryEvidence = ref("");
const localError = ref("");
const executionOwnerReason = ref("准备 AI 探索执行实例");
const allowedOriginsText = ref("");
const authenticationOriginsText = ref("");

const form = reactive<ExecutionBindingInput>({
  execution_attempt_id: "",
  project_id: projectId.value,
  environment_id: "",
  business_terminal_id: "",
  test_account_id: "",
  runner_id: "",
  runtime_policy_revision_id: "",
  runner_resource_type: "FORMAL_EXECUTION_SLOT",
  runner_resource_identity: "",
  owner_execution_identity: "",
  required_capabilities: [],
});

const policyForm = reactive<CreateRuntimePolicyRevisionRequest>({
  project_id: projectId.value,
  browser_runtime: "CHROMIUM",
  artifact_policy: "SCREENSHOT",
  timeout_seconds: 30,
  max_steps: 20,
  total_exploration_timeout_seconds: 600,
  model_transient_retry_per_step: 1,
  allowed_origins: [],
  authentication_redirect_origins: [],
  retry_mode: "UNIFIED_OWNER",
  network_requirement: "INTERNET",
  serial_execution_policy: "SINGLE_PROCESS_UNIFIED_RETRY",
  reason: "",
});

const activeEnvironments = computed(() =>
  environments.items.filter(
    (item) => item.lifecycle_status === "ACTIVE" && item.enablement_state === "ENABLED",
  ),
);
const eligibleRunners = computed(() =>
  runners.items.filter(
    (item) =>
      item.lifecycle_status === "ACTIVE" &&
      item.registration_status === "REGISTERED" &&
      item.enable_status === "ENABLED" &&
      item.project_binding_status === "BOUND" &&
      item.connection_status === "ONLINE" &&
      item.health_status === "HEALTHY" &&
      item.version_compatibility === "COMPATIBLE" &&
      ["IDLE", "PARTIALLY_OCCUPIED"].includes(item.scheduling_status),
  ),
);
const activeTerminals = computed(() =>
  terminals.items.filter((item) => item.lifecycle_status === "ACTIVE"),
);
const activeAccounts = computed(() =>
  accounts.items.filter(
    (item) =>
      item.lifecycle_status === "ACTIVE" &&
      item.credential_state === "VALID" &&
      item.business_terminals.some(
        (terminal) => terminal.business_terminal_id === form.business_terminal_id,
      ),
  ),
);
const publishedPolicies = computed(() =>
  bindings.policies.filter((item) => item.lifecycle_status === "PUBLISHED"),
);
const selectedPolicy = computed(() =>
  publishedPolicies.value.find(
    (item) => item.runtime_policy_revision_id === form.runtime_policy_revision_id,
  ),
);
const selectedTerminal = computed(() =>
  activeTerminals.value.find((item) => item.business_terminal_id === form.business_terminal_id),
);
const requiredCapabilities = computed(() => {
  const result = new Set<string>([
    "AI_EXPLORATION",
    "FORMAL_EXECUTION",
    "MODE_HEADLESS",
    "CONTEXT_ISOLATION",
  ]);
  const terminalMap: Record<string, string> = {
    MANAGEMENT: "TERMINAL_ADMIN_WEB",
    CLIENT: "TERMINAL_CLIENT_WEB",
    PDA: "TERMINAL_PDA_WEB",
  };
  const browserMap: Record<string, string> = {
    CHROMIUM: "BROWSER_CHROMIUM",
    CHROME: "BROWSER_CHROME",
    EDGE: "BROWSER_EDGE",
  };
  const artifactMap: Record<string, string> = {
    SCREENSHOT: "CAPTURE_SCREENSHOT",
    VIDEO: "CAPTURE_VIDEO",
    TRACE: "CAPTURE_TRACE",
  };
  const networkMap: Record<string, string> = {
    INTRANET: "INTRANET_ACCESS",
    PROXY: "PROXY_ACCESS",
  };
  if (selectedTerminal.value) result.add(terminalMap[selectedTerminal.value.terminal_type] ?? "");
  if (selectedPolicy.value) {
    result.add(browserMap[selectedPolicy.value.browser_runtime] ?? "");
    result.add(artifactMap[selectedPolicy.value.artifact_policy] ?? "");
    const network = networkMap[selectedPolicy.value.network_requirement];
    if (network) result.add(network);
  }
  result.delete("");
  return [...result];
});
const canPrepareExecution = computed(
  () => Boolean(form.environment_id && form.runner_id && executionOwnerReason.value.trim()),
);
const canPreflight = computed(
  () =>
    Boolean(
      form.execution_attempt_id &&
        form.owner_execution_identity &&
        form.environment_id &&
        form.business_terminal_id &&
        form.test_account_id &&
        form.runner_id &&
        form.runtime_policy_revision_id &&
        form.runner_resource_identity,
    ),
);

watch(
  projectId,
  (value) => {
    form.project_id = value;
    policyForm.project_id = value;
    resetScopedForm();
    if (value.length === 26) {
      void Promise.all([
        bindings.load(value).catch(() => undefined),
        bindings.loadPolicies(value).catch(() => undefined),
        environments.load(value, "ACTIVE", 1, 200).catch(() => undefined),
        runners.load(value, {}, 1, 200).catch(() => undefined),
      ]);
    }
  },
  { immediate: true },
);

watch(
  () => form.environment_id,
  (value, previous) => {
    if (value === previous) return;
    form.business_terminal_id = "";
    form.test_account_id = "";
    resetPreparedExecution();
    terminals.items = [];
    accounts.items = [];
    if (value) {
      void terminals
        .load(projectId.value, { environmentId: value, lifecycleStatus: "ACTIVE" }, 1, 200)
        .catch(() => undefined);
    }
  },
);

watch(
  () => form.business_terminal_id,
  (value, previous) => {
    if (value === previous) return;
    form.test_account_id = "";
    if (value && form.environment_id) {
      void accounts
        .load(
          projectId.value,
          {
            environmentId: form.environment_id,
            businessTerminalId: value,
            lifecycleStatus: "ACTIVE",
          },
          1,
          200,
        )
        .catch(() => undefined);
    }
  },
);

watch(
  () => form.runner_id,
  async (value, previous) => {
    if (value === previous) return;
    form.runner_resource_identity = "";
    resetPreparedExecution();
    if (!value) {
      bindings.slots = [];
      return;
    }
    await bindings.loadSlots(projectId.value, value).catch(() => undefined);
    if (bindings.slots.length === 1) {
      form.runner_resource_identity = bindings.slots[0]?.execution_slot_id ?? "";
    }
  },
);

function resetPreparedExecution(): void {
  bindings.resetPreparedExecutionOwner();
  form.execution_attempt_id = "";
  form.owner_execution_identity = "";
}

function resetScopedForm(): void {
  Object.assign(form, {
    project_id: projectId.value,
    environment_id: "",
    business_terminal_id: "",
    test_account_id: "",
    runner_id: "",
    runtime_policy_revision_id: "",
    runner_resource_type: "FORMAL_EXECUTION_SLOT",
    runner_resource_identity: "",
  });
  resetPreparedExecution();
}

function payload(): ExecutionBindingInput {
  return {
    ...form,
    project_id: projectId.value,
    runner_resource_type: "FORMAL_EXECUTION_SLOT",
    required_capabilities: requiredCapabilities.value,
  };
}

function parseOrigins(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function policySummary(policy: RuntimePolicyRevisionResource): string {
  return `修订 ${policy.revision_no} · ${enumLabel("browser", policy.browser_runtime)} · ${enumLabel("artifact", policy.artifact_policy)} · ${policy.total_exploration_timeout_seconds} 秒`;
}

async function createPolicy(): Promise<void> {
  localError.value = "";
  const allowed = parseOrigins(allowedOriginsText.value);
  if (allowed.length === 0 || !policyForm.reason.trim()) {
    localError.value = "请填写至少一个允许访问来源和创建发布原因。";
    return;
  }
  const created = await bindings
    .createPolicy({
      ...policyForm,
      project_id: projectId.value,
      allowed_origins: allowed,
      authentication_redirect_origins: parseOrigins(authenticationOriginsText.value),
      reason: policyForm.reason.trim(),
    })
    .catch(() => undefined);
  if (created) {
    form.runtime_policy_revision_id = created.runtime_policy_revision_id;
    policyVisible.value = false;
    ElMessage.success(`运行策略修订 ${created.revision_no} 已创建并发布。`);
  }
}

function openCreateBinding(): void {
  resetScopedForm();
  executionOwnerReason.value = "准备 AI 探索执行实例";
  localError.value = "";
  createVisible.value = true;
}

async function prepareExecutionOwner(): Promise<void> {
  localError.value = "";
  if (!canPrepareExecution.value) {
    localError.value = "请先选择执行环境和 Runner，并填写准备原因。";
    return;
  }
  const result = await bindings
    .prepareExplorationExecutionOwner(
      projectId.value,
      form.environment_id,
      form.runner_id,
      executionOwnerReason.value.trim(),
    )
    .catch(() => undefined);
  if (result) {
    form.execution_attempt_id = result.attempt.execution_attempt_id;
    form.owner_execution_identity = result.runTask.run_task_id;
    ElMessage.success("执行实例已准备，请继续完成业务终端、账号、运行策略和正式资源选择。");
  }
}

async function preflight(): Promise<void> {
  localError.value = "";
  if (!canPreflight.value) {
    localError.value = "请完成全部业务关系选择并准备执行实例。";
    return;
  }
  const result = await bindings.runPreflight(payload()).catch(() => undefined);
  if (result) ElMessage[result.ready ? "success" : "warning"](result.ready ? "执行预检查通过。" : "执行预检查未通过。");
}

async function createBinding(): Promise<void> {
  localError.value = "";
  if (!canPreflight.value) {
    localError.value = "请完成全部业务关系选择并准备执行实例。";
    return;
  }
  const result = await bindings.runPreflight(payload()).catch(() => undefined);
  if (!result?.ready) {
    localError.value = "执行预检查未通过；不会创建执行绑定或资源租约。";
    return;
  }
  const created = await bindings.create(payload()).catch(() => undefined);
  if (created) {
    createVisible.value = false;
    openDetail(created);
    ElMessage.success("执行绑定与两类租约已原子创建。");
  }
}

function openDetail(binding: ExecutionBindingSnapshotResource): void {
  selected.value = binding;
  bindings.current = binding;
  detailVisible.value = true;
}

async function openAIExploration(binding: ExecutionBindingSnapshotResource): Promise<void> {
  detailVisible.value = false;
  await router.push({
    name: "ai.exploration",
    query: { project_id: projectId.value, execution_attempt_id: binding.execution_attempt_id },
  });
}

function openCommand(binding: ExecutionBindingSnapshotResource, action: BindingCommand): void {
  selected.value = binding;
  commandAction.value = action;
  commandReason.value = "";
  recoveryEvidence.value = "";
  commandVisible.value = true;
}

async function submitCommand(): Promise<void> {
  if (!selected.value || !commandReason.value.trim()) {
    localError.value = "请填写命令原因。";
    return;
  }
  if (commandAction.value === "recover" && !recoveryEvidence.value.trim()) {
    localError.value = "异常回收必须填写恢复证据。";
    return;
  }
  const value = await bindings
    .command(selected.value, commandAction.value, commandReason.value.trim(), recoveryEvidence.value.trim())
    .catch(() => undefined);
  if (value) {
    selected.value = value;
    commandVisible.value = false;
    if (commandAction.value === "release" || commandAction.value === "recover") {
      await bindings.loadSlots(projectId.value, value.runner_id).catch(() => undefined);
    }
    ElMessage.success("命令已按执行所有者和 fencing 约束完成。");
  }
}

const commandLabel = computed(
  () =>
    ({ consume: "投入使用", renew: "续租", release: "正常释放", recover: "异常回收" })[
      commandAction.value
    ],
);
</script>

<template>
  <section aria-labelledby="binding-title">
    <div class="page-heading">
      <div>
        <el-button link type="primary" @click="router.push({ name: 'projects.detail', params: { id: projectId } })">← 返回项目详情</el-button>
        <h2 id="binding-title">执行绑定</h2>
        <p>通过业务名称选择执行关系，系统内部冻结稳定标识并以租约保证独占执行资源。</p>
      </div>
      <PermissionGate permission="PROJECT_EDIT">
        <el-button @click="policyVisible = true">新建运行策略</el-button>
        <el-button type="primary" @click="openCreateBinding">新建执行绑定</el-button>
      </PermissionGate>
    </div>

    <el-alert v-if="localError || bindings.errorMessage" :title="localError || bindings.errorMessage" type="error" :closable="false" show-icon>
      <template v-if="bindings.errorCode || bindings.correlationId" #default>
        <span v-if="bindings.errorCode">错误代码：{{ bindings.errorCode }}</span>
        <span v-if="bindings.errorCode && bindings.correlationId"> · </span>
        <span v-if="bindings.correlationId">请求标识：{{ bindings.correlationId }}</span>
      </template>
    </el-alert>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable style="width: 160px">
            <el-option v-for="value in ['READY', 'IN_USE', 'RELEASED', 'EXPIRED']" :key="value" :label="statusLabel('executionBinding', value)" :value="value" />
          </el-select>
        </el-form-item>
        <el-button @click="bindings.load(projectId, statusFilter || undefined)">刷新</el-button>
      </el-form>
    </el-card>

    <el-table :data="bindings.items" v-loading="bindings.status === 'loading'" row-key="execution_binding_snapshot_id">
      <el-table-column label="执行绑定" min-width="190">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }"><el-tag>{{ statusLabel('executionBinding', row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="账号租约" min-width="170">
        <template #default="{ row }">{{ statusLabel('lease', row.identity_lease.status) }} · 第 {{ row.identity_lease.fencing_generation }} 代</template>
      </el-table-column>
      <el-table-column label="Runner 资源租约" min-width="190">
        <template #default="{ row }">{{ statusLabel('lease', row.runner_lease.status) }} · 第 {{ row.runner_lease.fencing_generation }} 代</template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" min-width="300">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'READY'" link type="primary" @click="openCommand(row, 'consume')">投入使用</el-button>
          <el-button v-if="['READY', 'IN_USE'].includes(row.status)" link type="primary" @click="openCommand(row, 'renew')">续租</el-button>
          <el-button v-if="['READY', 'IN_USE'].includes(row.status)" link type="danger" @click="openCommand(row, 'release')">释放</el-button>
          <el-button v-if="['READY', 'IN_USE'].includes(row.status)" link type="warning" @click="openCommand(row, 'recover')">异常回收</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="policyVisible" title="创建并发布运行策略修订" width="680px">
      <el-form label-width="150px">
        <el-form-item label="浏览器运行时"><el-select v-model="policyForm.browser_runtime"><el-option v-for="value in ['CHROMIUM', 'CHROME', 'EDGE']" :key="value" :label="enumLabel('browser', value)" :value="value" /></el-select></el-form-item>
        <el-form-item label="制品策略"><el-select v-model="policyForm.artifact_policy"><el-option v-for="value in ['SCREENSHOT', 'VIDEO', 'TRACE']" :key="value" :label="enumLabel('artifact', value)" :value="value" /></el-select></el-form-item>
        <el-form-item label="单步超时（秒）"><el-input-number v-model="policyForm.timeout_seconds" :min="1" /></el-form-item>
        <el-form-item label="最大步骤数"><el-input-number v-model="policyForm.max_steps" :min="1" /></el-form-item>
        <el-form-item label="总探索超时（秒）"><el-input-number v-model="policyForm.total_exploration_timeout_seconds" :min="1" /></el-form-item>
        <el-form-item label="模型瞬态重试/步"><el-input-number v-model="policyForm.model_transient_retry_per_step" :min="0" :max="10" /></el-form-item>
        <el-form-item label="允许访问来源" required><el-input v-model="allowedOriginsText" type="textarea" placeholder="每行一个 origin，例如 https://example.internal" /></el-form-item>
        <el-form-item label="认证跳转来源"><el-input v-model="authenticationOriginsText" type="textarea" placeholder="每行一个允许的认证跳转 origin" /></el-form-item>
        <el-form-item label="网络要求"><el-select v-model="policyForm.network_requirement"><el-option v-for="value in ['INTERNET', 'INTRANET', 'PROXY']" :key="value" :label="enumLabel('network', value)" :value="value" /></el-select></el-form-item>
        <el-form-item label="重试模式">{{ enumLabel('retry', policyForm.retry_mode) }}</el-form-item>
        <el-form-item label="串行执行策略">{{ enumLabel('serialExecution', policyForm.serial_execution_policy) }}</el-form-item>
        <el-form-item label="创建发布原因" required><el-input v-model="policyForm.reason" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="policyVisible = false">取消</el-button><el-button type="primary" :loading="bindings.status === 'saving'" @click="createPolicy">创建并发布</el-button></template>
    </el-dialog>

    <el-dialog v-model="createVisible" title="新建执行绑定" width="760px">
      <el-form label-width="150px">
        <el-form-item label="执行环境" required>
          <el-select v-model="form.environment_id" filterable style="width: 100%" placeholder="选择已启用环境">
            <el-option v-for="environment in activeEnvironments" :key="environment.environment_id" :label="environment.display_name || environment.environment_code" :value="environment.environment_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行 Runner" required>
          <el-select v-model="form.runner_id" filterable style="width: 100%" placeholder="选择在线、健康、兼容且可调度的 Runner">
            <el-option v-for="runner in eligibleRunners" :key="runner.runner_id" :label="`${runner.display_name || runner.runner_code} · ${statusLabel('connection', runner.connection_status)} · ${statusLabel('health', runner.health_status)} · ${statusLabel('scheduling', runner.scheduling_status)}`" :value="runner.runner_id" />
          </el-select>
        </el-form-item>
        <PermissionGate permission="RUN_TASK_CREATE">
          <el-form-item label="执行实例准备原因"><el-input v-model="executionOwnerReason" type="textarea" /></el-form-item>
          <el-form-item label="执行实例">
            <el-button :disabled="!canPrepareExecution" :loading="bindings.status === 'saving'" @click="prepareExecutionOwner">准备执行实例</el-button>
            <el-tag v-if="bindings.preparedExecutionAttempt" type="success" style="margin-left: 12px">已准备 · 第 {{ bindings.preparedExecutionAttempt.attempt_no }} 次尝试</el-tag>
          </el-form-item>
        </PermissionGate>
        <el-form-item label="业务终端" required>
          <el-select v-model="form.business_terminal_id" :disabled="!form.environment_id" filterable style="width: 100%" placeholder="选择当前环境的业务终端">
            <el-option v-for="terminal in activeTerminals" :key="terminal.business_terminal_id" :label="`${terminal.display_name || terminal.terminal_code} · ${terminal.terminal_type === 'MANAGEMENT' ? '管理端' : terminal.terminal_type === 'CLIENT' ? '客户端' : 'PDA'}`" :value="terminal.business_terminal_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="测试账号" required>
          <el-select v-model="form.test_account_id" :disabled="!form.business_terminal_id" filterable style="width: 100%" placeholder="选择已激活且映射到当前终端的账号">
            <el-option v-for="account in activeAccounts" :key="account.test_account_id" :label="account.display_name || account.account_identifier" :value="account.test_account_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="运行策略" required>
          <el-select v-model="form.runtime_policy_revision_id" style="width: 100%" placeholder="选择已发布运行策略">
            <el-option v-for="policy in publishedPolicies" :key="policy.runtime_policy_revision_id" :label="policySummary(policy)" :value="policy.runtime_policy_revision_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="正式执行资源" required>
          <el-select v-model="form.runner_resource_identity" :disabled="!form.runner_id || bindings.slots.length === 0" style="width: 100%" placeholder="系统发现当前可用槽位">
            <el-option v-for="slot in bindings.slots" :key="slot.execution_slot_id" :label="`${slot.display_name || `槽位 ${Number(slot.slot_no ?? 0) + 1}`} · ${statusLabel('resource', slot.availability_status)}`" :value="slot.execution_slot_id" />
          </el-select>
          <el-alert v-if="form.runner_id && bindings.slots.length === 0" type="warning" :closable="false" title="当前 Runner 没有可用的正式执行槽位。请检查 Runner 正式执行能力、资源状态或现有执行占用。" style="margin-top: 8px" />
        </el-form-item>
        <el-form-item label="所需能力">
          <el-space wrap><el-tag v-for="code in requiredCapabilities" :key="code">{{ capabilityLabel(code) }}</el-tag></el-space>
        </el-form-item>
        <el-collapse v-if="form.execution_attempt_id || form.runner_resource_identity">
          <el-collapse-item title="技术信息 / 诊断信息" name="technical">
            <p>执行实例：<code>{{ form.execution_attempt_id || '—' }}</code></p>
            <p>执行所有者：<code>{{ form.owner_execution_identity || '—' }}</code></p>
            <p>执行槽位：<code>{{ form.runner_resource_identity || '—' }}</code></p>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <el-card v-if="bindings.preflight" shadow="never">
        <strong>执行预检查：{{ bindings.preflight.ready ? "通过" : "未通过" }}</strong>
        <ul>
          <li v-for="check in bindings.preflight.checks" :key="check.code">
            {{ preflightCheckLabel(check.code) }} · {{ check.status === "PASS" ? "通过" : "未通过" }}
          </li>
        </ul>
        <el-collapse>
          <el-collapse-item title="技术诊断信息" name="preflight-tech">
            <ul><li v-for="check in bindings.preflight.checks" :key="`tech-${check.code}`"><code>{{ check.code }}</code> · <code>{{ check.status }}</code> · {{ check.detail }}</li></ul>
          </el-collapse-item>
        </el-collapse>
      </el-card>
      <template #footer><el-button :disabled="!canPreflight" @click="preflight">执行预检查</el-button><el-button type="primary" :disabled="!canPreflight" :loading="bindings.status === 'saving'" @click="createBinding">创建执行绑定</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="执行绑定详情" size="55%">
      <el-descriptions v-if="selected" :column="1" border>
        <el-descriptions-item label="状态">{{ statusLabel('executionBinding', selected.status) }}</el-descriptions-item>
        <el-descriptions-item label="运行策略">修订 {{ selected.runtime_policy.revision_no }} · {{ enumLabel('browser', selected.runtime_policy.browser_runtime) }} · {{ enumLabel('artifact', selected.runtime_policy.artifact_policy) }}</el-descriptions-item>
        <el-descriptions-item label="账号租约">{{ statusLabel('lease', selected.identity_lease.status) }} · 第 {{ selected.identity_lease.fencing_generation }} 代</el-descriptions-item>
        <el-descriptions-item label="Runner 资源租约">{{ statusLabel('lease', selected.runner_lease.status) }} · 第 {{ selected.runner_lease.fencing_generation }} 代</el-descriptions-item>
      </el-descriptions>
      <el-collapse v-if="selected" style="margin-top: 16px"><el-collapse-item title="技术信息" name="ids"><p>执行绑定标识：<code>{{ selected.execution_binding_snapshot_id }}</code></p><p>执行实例标识：<code>{{ selected.execution_attempt_id }}</code></p><p>终端访问修订标识：<code>{{ selected.terminal_access_revision_id }}</code></p><p>凭据修订标识：<code>{{ selected.credential_revision_id }}</code></p></el-collapse-item></el-collapse>
      <template #footer><el-button v-if="selected?.status === 'READY'" type="primary" @click="openAIExploration(selected)">使用此绑定进行 AI 探索</el-button></template>
    </el-drawer>

    <el-dialog v-model="commandVisible" :title="commandLabel" width="560px">
      <el-form label-width="110px"><el-form-item label="原因"><el-input v-model="commandReason" type="textarea" /></el-form-item><el-form-item v-if="commandAction === 'recover'" label="回收证据"><el-input v-model="recoveryEvidence" type="textarea" /></el-form-item></el-form>
      <template #footer><el-button @click="commandVisible = false">取消</el-button><el-button type="primary" @click="submitCommand">确认</el-button></template>
    </el-dialog>
  </section>
</template>
