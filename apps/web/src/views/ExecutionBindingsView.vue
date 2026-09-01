<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type { ExecutionBindingInput, ExecutionBindingSnapshotResource } from "../generated/types";
import { type BindingCommand, useExecutionBindingsStore } from "../stores/executionBindings";

const route = useRoute();
const router = useRouter();
const bindings = useExecutionBindingsStore();
const projectId = computed(() => String(route.params.projectId ?? ""));
const statusFilter = ref("");
const selected = ref<ExecutionBindingSnapshotResource | null>(null);
const detailVisible = ref(false);
const createVisible = ref(false);
const commandVisible = ref(false);
const commandAction = ref<BindingCommand>("release");
const commandReason = ref("");
const recoveryEvidence = ref("");
const localError = ref("");
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
const capabilitiesText = ref("");

watch(
  projectId,
  (value) => {
    form.project_id = value;
    if (value.length === 26) {
      void Promise.all([
        bindings.load(value).catch(() => undefined),
        bindings.loadPolicies(value).catch(() => undefined),
      ]);
    }
  },
  { immediate: true },
);

function payload(): ExecutionBindingInput {
  return {
    ...form,
    project_id: projectId.value,
    required_capabilities: capabilitiesText.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

async function preflight(): Promise<void> {
  localError.value = "";
  const result = await bindings.runPreflight(payload()).catch(() => undefined);
  if (result)
    ElMessage[result.ready ? "success" : "warning"](
      result.ready ? "Preflight 通过。" : "Preflight 未通过，未创建 Binding。",
    );
}

async function createBinding(): Promise<void> {
  localError.value = "";
  const result = await bindings.runPreflight(payload()).catch(() => undefined);
  if (!result?.ready) {
    localError.value = "Preflight 未通过；不会创建 Binding、Lease、Audit 或 Outbox。";
    return;
  }
  const created = await bindings.create(payload()).catch(() => undefined);
  if (created) {
    createVisible.value = false;
    openDetail(created);
    ElMessage.success("执行绑定与两类 Lease 已原子创建。");
  }
}

function openDetail(binding: ExecutionBindingSnapshotResource): void {
  selected.value = binding;
  bindings.current = binding;
  detailVisible.value = true;
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
    localError.value = "Recover 必须填写 stale recovery 证据。";
    return;
  }
  const value = await bindings
    .command(
      selected.value,
      commandAction.value,
      commandReason.value.trim(),
      recoveryEvidence.value.trim(),
    )
    .catch(() => undefined);
  if (value) {
    selected.value = value;
    commandVisible.value = false;
    ElMessage.success("命令已按 owner/fencing 约束执行。");
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
        <el-button
          link
          type="primary"
          @click="router.push({ name: 'projects.detail', params: { id: projectId } })"
          >← 返回项目详情</el-button
        >
        <h2 id="binding-title">执行绑定</h2>
        <p>
          冻结 ExecutionAttempt 的 Project、Environment、Terminal、账号、Runner、RuntimePolicy
          Revision 与两类 Lease。
        </p>
      </div>
      <PermissionGate permission="PROJECT_EDIT">
        <el-button type="primary" @click="createVisible = true">新建执行绑定</el-button>
      </PermissionGate>
    </div>

    <el-alert
      v-if="localError || bindings.errorMessage"
      :title="localError || bindings.errorMessage"
      type="error"
      :closable="false"
      show-icon
    />
    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable style="width: 160px">
            <el-option
              v-for="value in ['READY', 'IN_USE', 'RELEASED', 'EXPIRED']"
              :key="value"
              :label="value"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-button @click="bindings.load(projectId, statusFilter || undefined)">刷新</el-button>
      </el-form>
    </el-card>

    <el-table
      :data="bindings.items"
      v-loading="bindings.status === 'loading'"
      row-key="execution_binding_snapshot_id"
    >
      <el-table-column prop="execution_binding_snapshot_id" label="Binding ID" min-width="230" />
      <el-table-column prop="execution_attempt_id" label="ExecutionAttempt" min-width="230" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column label="Identity Lease" min-width="180">
        <template #default="{ row }"
          >{{ row.identity_lease.status }} / gen
          {{ row.identity_lease.fencing_generation }}</template
        >
      </el-table-column>
      <el-table-column label="Runner Lease" min-width="180">
        <template #default="{ row }"
          >{{ row.runner_lease.status }} / gen {{ row.runner_lease.fencing_generation }}</template
        >
      </el-table-column>
      <el-table-column label="操作" fixed="right" min-width="300">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'READY'"
            link
            type="primary"
            @click="openCommand(row, 'consume')"
            >投入使用</el-button
          >
          <el-button
            v-if="['READY', 'IN_USE'].includes(row.status)"
            link
            type="primary"
            @click="openCommand(row, 'renew')"
            >续租</el-button
          >
          <el-button
            v-if="['READY', 'IN_USE'].includes(row.status)"
            link
            type="danger"
            @click="openCommand(row, 'release')"
            >释放</el-button
          >
          <el-button
            v-if="['READY', 'IN_USE'].includes(row.status)"
            link
            type="warning"
            @click="openCommand(row, 'recover')"
            >异常回收</el-button
          >
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" title="新建 ExecutionBindingSnapshot" width="760px">
      <el-form label-width="190px">
        <el-form-item label="ExecutionAttempt ID"
          ><el-input v-model="form.execution_attempt_id"
        /></el-form-item>
        <el-form-item label="Environment ID"
          ><el-input v-model="form.environment_id"
        /></el-form-item>
        <el-form-item label="BusinessTerminal ID"
          ><el-input v-model="form.business_terminal_id"
        /></el-form-item>
        <el-form-item label="TestAccount ID"
          ><el-input v-model="form.test_account_id"
        /></el-form-item>
        <el-form-item label="Runner ID"><el-input v-model="form.runner_id" /></el-form-item>
        <el-form-item label="RuntimePolicy Revision">
          <el-select v-model="form.runtime_policy_revision_id" style="width: 100%">
            <el-option
              v-for="policy in bindings.policies"
              :key="policy.runtime_policy_revision_id"
              :label="`Revision ${policy.revision_no} · ${policy.browser_runtime}`"
              :value="policy.runtime_policy_revision_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Runner Resource Type"
          ><el-select v-model="form.runner_resource_type"
            ><el-option label="Formal execution slot" value="FORMAL_EXECUTION_SLOT" /><el-option
              label="Browser session"
              value="BROWSER_SESSION" /></el-select
        ></el-form-item>
        <el-form-item label="Runner Resource Identity"
          ><el-input v-model="form.runner_resource_identity"
        /></el-form-item>
        <el-form-item label="Owner Execution Identity"
          ><el-input v-model="form.owner_execution_identity"
        /></el-form-item>
        <el-form-item label="额外能力（逗号分隔）"
          ><el-input v-model="capabilitiesText"
        /></el-form-item>
      </el-form>
      <el-card v-if="bindings.preflight" shadow="never">
        <strong>Preflight：{{ bindings.preflight.ready ? "PASS" : "FAIL" }}</strong>
        <ul>
          <li v-for="check in bindings.preflight.checks" :key="check.code">
            {{ check.code }} · {{ check.status }} · {{ check.detail }}
          </li>
        </ul>
      </el-card>
      <template #footer
        ><el-button @click="preflight">执行 Preflight</el-button
        ><el-button type="primary" :loading="bindings.status === 'saving'" @click="createBinding"
          >原子创建</el-button
        ></template
      >
    </el-dialog>

    <el-drawer v-model="detailVisible" title="执行绑定详情" size="55%">
      <el-descriptions v-if="selected" :column="1" border>
        <el-descriptions-item label="Binding">{{
          selected.execution_binding_snapshot_id
        }}</el-descriptions-item>
        <el-descriptions-item label="ExecutionAttempt">{{
          selected.execution_attempt_id
        }}</el-descriptions-item>
        <el-descriptions-item label="冻结终端 Revision">{{
          selected.terminal_access_revision_id
        }}</el-descriptions-item>
        <el-descriptions-item label="冻结 Credential Revision">{{
          selected.credential_revision_id
        }}</el-descriptions-item>
        <el-descriptions-item label="冻结 RuntimePolicy"
          >{{ selected.runtime_policy.runtime_policy_revision_id }} / revision
          {{ selected.runtime_policy.revision_no }}</el-descriptions-item
        >
        <el-descriptions-item label="Identity Lease"
          >{{ selected.identity_lease.resource_identity }} · {{ selected.identity_lease.status }} ·
          generation {{ selected.identity_lease.fencing_generation }} ·
          {{ selected.identity_lease.expires_at }}</el-descriptions-item
        >
        <el-descriptions-item label="Runner Lease"
          >{{ selected.runner_lease.resource_identity }} · {{ selected.runner_lease.status }} ·
          generation {{ selected.runner_lease.fencing_generation }} ·
          {{ selected.runner_lease.expires_at }}</el-descriptions-item
        >
      </el-descriptions>
    </el-drawer>

    <el-dialog v-model="commandVisible" :title="commandLabel" width="560px">
      <el-form label-width="110px">
        <el-form-item label="原因"
          ><el-input v-model="commandReason" type="textarea"
        /></el-form-item>
        <el-form-item v-if="commandAction === 'recover'" label="回收证据"
          ><el-input v-model="recoveryEvidence" type="textarea"
        /></el-form-item>
      </el-form>
      <p>
        命令携带当前 owner、row_version 及 Identity/Runner fencing generation；旧 generation 将
        fail-closed。
      </p>
      <template #footer
        ><el-button @click="commandVisible = false">取消</el-button
        ><el-button type="primary" @click="submitCommand">确认</el-button></template
      >
    </el-dialog>
  </section>
</template>
