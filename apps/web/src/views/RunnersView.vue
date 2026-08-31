<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type { RunnerResource } from "../generated/types";
import { type RunnerLifecycleAction, useRunnersStore } from "../stores/runners";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const runners = useRunnersStore();
const session = useSessionStore();
const projectInput = ref(String(route.query.project_id ?? ""));
const projectId = computed(() =>
  route.params.projectId ? String(route.params.projectId) : projectInput.value.trim(),
);
const hasProjectScope = computed(() => projectId.value.length === 26);
const filters = reactive({ lifecycleStatus: "", healthStatus: "", capabilityCode: "" });
const selected = ref<RunnerResource | null>(null);
const detailVisible = ref(false);
const createVisible = ref(false);
const credentialVisible = ref(false);
const editVisible = ref(false);
const commandVisible = ref(false);
const tokenVisible = ref(false);
const command = ref<RunnerLifecycleAction | "rotate" | "revoke">("enable");
const createForm = reactive({ runner_code: "", display_name: "", reason: "" });
const editForm = reactive({ display_name: "", reason: "" });
const commandReason = ref("");
const localError = ref("");

watch(
  projectId,
  (value) => {
    if (value.length === 26) void runners.load(value).catch(() => undefined);
  },
  { immediate: true },
);

async function openProjectScope(): Promise<void> {
  if (!hasProjectScope.value) {
    localError.value = "请输入 26 位 Project ID。";
    return;
  }
  localError.value = "";
  await router.replace({ name: "runners.manage", query: { project_id: projectId.value } });
  await refresh(1);
}

async function refresh(page = runners.page.page): Promise<void> {
  await runners
    .load(
      projectId.value,
      {
        lifecycleStatus: filters.lifecycleStatus || undefined,
        healthStatus: filters.healthStatus || undefined,
        capabilityCode: filters.capabilityCode || undefined,
      },
      page,
      runners.page.page_size,
    )
    .catch(() => undefined);
}

function openCreate(): void {
  Object.assign(createForm, { runner_code: "", display_name: "", reason: "" });
  localError.value = "";
  createVisible.value = true;
}

async function submitCreate(): Promise<void> {
  if (!createForm.runner_code.trim() || !createForm.reason.trim()) {
    localError.value = "请填写 Runner Code 和创建原因。";
    return;
  }
  try {
    await runners.createEnrollment({
      project_id: projectId.value,
      runner_code: createForm.runner_code.trim(),
      display_name: createForm.display_name.trim() || null,
      reason: createForm.reason.trim(),
    });
    createVisible.value = false;
    credentialVisible.value = true;
  } catch {
    // Store exposes the operation-specific error.
  }
}

function openDetail(runner: RunnerResource): void {
  selected.value = runner;
  detailVisible.value = true;
}

function openEdit(runner: RunnerResource): void {
  selected.value = runner;
  editForm.display_name = runner.display_name ?? "";
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
    await runners.updateName(
      selected.value,
      editForm.display_name.trim() || null,
      editForm.reason.trim(),
    );
    editVisible.value = false;
    ElMessage.success("Runner 显示信息已更新。");
  } catch {
    // Store exposes the operation-specific error.
  }
}

function openCommand(
  runner: RunnerResource,
  action: RunnerLifecycleAction | "rotate" | "revoke",
): void {
  selected.value = runner;
  command.value = action;
  commandReason.value = "";
  localError.value = "";
  commandVisible.value = true;
}

async function submitCommand(): Promise<void> {
  if (!selected.value || !commandReason.value.trim()) {
    localError.value = "请填写操作原因。";
    return;
  }
  try {
    if (command.value === "rotate") {
      await runners.rotateToken(selected.value, commandReason.value.trim());
      commandVisible.value = false;
      tokenVisible.value = true;
      return;
    }
    if (command.value === "revoke") {
      await runners.revokeToken(selected.value, commandReason.value.trim());
    } else {
      await runners.lifecycle(selected.value, command.value, commandReason.value.trim());
    }
    commandVisible.value = false;
    ElMessage.success("Runner 操作已完成。");
  } catch {
    // Store exposes the operation-specific error.
  }
}

function lifecycleActions(runner: RunnerResource): RunnerLifecycleAction[] {
  if (runner.lifecycle_status === "REGISTERED") return ["enable", "disable"];
  if (runner.lifecycle_status === "ACTIVE") return ["disable"];
  if (runner.lifecycle_status === "DISABLED") return ["enable", "archive"];
  return [];
}

function closeEnrollmentCredential(): void {
  credentialVisible.value = false;
  runners.clearIssuedSecrets();
  void refresh(1);
}

function closeRotatedToken(): void {
  tokenVisible.value = false;
  runners.clearIssuedSecrets();
}

const commandLabels: Record<RunnerLifecycleAction | "rotate" | "revoke", string> = {
  enable: "启用",
  disable: "停用",
  archive: "归档",
  rotate: "轮换 Agent Token",
  revoke: "撤销 Agent Token",
};
</script>

<template>
  <section aria-labelledby="runner-title">
    <div class="page-heading">
      <div>
        <el-button
          v-if="route.params.projectId && session.hasPermission('PROJECT_VIEW')"
          link
          type="primary"
          @click="router.push({ name: 'projects.detail', params: { id: projectId } })"
        >
          ← 返回项目详情
        </el-button>
        <h2 id="runner-title">Runner 管理</h2>
        <p>管理 Project 归属、Agent 注册、分离生命周期与运行健康，以及受控能力事实。</p>
      </div>
      <PermissionGate permission="RUNNER_BIND">
        <el-button type="primary" @click="openCreate">创建 Enrollment</el-button>
      </PermissionGate>
    </div>

    <el-card v-if="!route.params.projectId" shadow="never" class="filter-card">
      <el-form inline @submit.prevent="openProjectScope">
        <el-form-item label="Project ID">
          <el-input v-model="projectInput" maxlength="26" placeholder="输入授权范围内的 Project ID" />
        </el-form-item>
        <el-button type="primary" @click="openProjectScope">打开 Runner Project</el-button>
      </el-form>
      <p>Project 范围由服务端按 Runner 管理权限实时校验。</p>
    </el-card>

    <el-alert
      v-if="runners.errorMessage"
      :title="runners.errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="workspace-alert"
    >
      <template v-if="runners.correlationId" #default>
        请求标识：{{ runners.correlationId }}
      </template>
    </el-alert>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="生命周期">
          <el-select v-model="filters.lifecycleStatus" clearable style="width: 160px">
            <el-option
              v-for="value in ['REGISTERED', 'ACTIVE', 'DISABLED', 'ARCHIVED']"
              :key="value"
              :value="value"
              :label="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="健康">
          <el-select v-model="filters.healthStatus" clearable style="width: 150px">
            <el-option
              v-for="value in ['UNKNOWN', 'HEALTHY', 'DEGRADED', 'UNHEALTHY']"
              :key="value"
              :value="value"
              :label="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="能力">
          <el-input v-model="filters.capabilityCode" clearable placeholder="Capability Code" />
        </el-form-item>
        <el-button type="primary" @click="refresh(1)">查询</el-button>
      </el-form>
    </el-card>

    <el-table
      :data="runners.items"
      v-loading="runners.status === 'loading'"
      empty-text="暂无已注册 Runner"
    >
      <el-table-column prop="runner_code" label="Runner Code" min-width="160" />
      <el-table-column prop="display_name" label="显示名称" min-width="140" />
      <el-table-column prop="project_id" label="Project" min-width="210" />
      <el-table-column prop="lifecycle_status" label="生命周期" width="125" />
      <el-table-column label="运行状态" min-width="180">
        <template #default="scope">
          {{ scope.row.connection_status }} / {{ scope.row.health_status }}
        </template>
      </el-table-column>
      <el-table-column prop="last_heartbeat_at" label="最后心跳" min-width="190" />
      <el-table-column label="能力" min-width="260">
        <template #default="scope">
          <el-tag
            v-for="capability in scope.row.capabilities.filter(
              (item: { availability_status: string }) => item.availability_status === 'CONFIGURED',
            )"
            :key="capability.capability_code"
            class="terminal-tag"
          >
            {{ capability.capability_code }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" min-width="190" />
      <el-table-column label="操作" fixed="right" min-width="300">
        <template #default="scope">
          <el-button link type="primary" @click="openDetail(scope.row)">详情</el-button>
          <PermissionGate permission="RUNNER_REGISTER">
            <el-button
              v-if="scope.row.lifecycle_status !== 'ARCHIVED'"
              link
              type="primary"
              @click="openEdit(scope.row)"
              >编辑</el-button
            >
            <el-dropdown
              v-if="scope.row.lifecycle_status !== 'ARCHIVED'"
              @command="
                (value: string) =>
                  openCommand(scope.row, value as RunnerLifecycleAction | 'rotate' | 'revoke')
              "
            >
              <el-button link type="primary">管理</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="action in lifecycleActions(scope.row)"
                    :key="action"
                    :command="action"
                    >{{ commandLabels[action] }}</el-dropdown-item
                  >
                  <el-dropdown-item command="rotate">轮换 Agent Token</el-dropdown-item>
                  <el-dropdown-item command="revoke">撤销 Agent Token</el-dropdown-item>
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
      :current-page="runners.page.page"
      :page-size="runners.page.page_size"
      :total="runners.page.total"
      @current-change="refresh"
    />

    <el-dialog v-model="createVisible" title="创建 Project-scoped Enrollment" width="560px">
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top">
        <el-form-item label="Runner Code"
          ><el-input v-model="createForm.runner_code"
        /></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="createForm.display_name" /></el-form-item>
        <el-form-item label="原因"
          ><el-input v-model="createForm.reason" type="textarea"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="runners.status === 'saving'" @click="submitCreate"
          >创建</el-button
        >
      </template>
    </el-dialog>

    <el-dialog
      v-model="credentialVisible"
      title="一次性 Enrollment Credential"
      width="620px"
      :close-on-click-modal="false"
      @closed="closeEnrollmentCredential"
    >
      <el-alert
        title="该凭据只显示一次。请立即安全交付给目标 Runner Agent；平台无法恢复明文。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-input
        v-if="runners.issuedEnrollment"
        :model-value="runners.issuedEnrollment.enrollment_credential"
        readonly
        type="textarea"
        :rows="3"
        class="secret-delivery"
      />
      <template #footer
        ><el-button type="primary" @click="closeEnrollmentCredential"
          >我已安全保存</el-button
        ></template
      >
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑 Runner" width="520px">
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top">
        <el-form-item label="显示名称"><el-input v-model="editForm.display_name" /></el-form-item>
        <el-form-item label="原因"
          ><el-input v-model="editForm.reason" type="textarea"
        /></el-form-item>
      </el-form>
      <template #footer><el-button type="primary" @click="submitEdit">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="commandVisible" :title="commandLabels[command]" width="520px">
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top">
        <el-form-item label="操作原因"
          ><el-input v-model="commandReason" type="textarea"
        /></el-form-item>
      </el-form>
      <template #footer><el-button type="primary" @click="submitCommand">确认</el-button></template>
    </el-dialog>

    <el-dialog
      v-model="tokenVisible"
      title="新的 Runner Agent Token"
      width="620px"
      :close-on-click-modal="false"
      @closed="closeRotatedToken"
    >
      <el-alert
        title="新 token 只显示一次，旧 token 已立即失效。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-input
        v-if="runners.issuedToken"
        :model-value="runners.issuedToken.agent_token"
        readonly
        type="textarea"
        :rows="3"
        class="secret-delivery"
      />
      <template #footer
        ><el-button type="primary" @click="closeRotatedToken">我已安全保存</el-button></template
      >
    </el-dialog>

    <el-drawer v-model="detailVisible" title="Runner 详情" size="580px">
      <el-descriptions v-if="selected" :column="1" border>
        <el-descriptions-item label="Runner Code">{{ selected.runner_code }}</el-descriptions-item>
        <el-descriptions-item label="显示名称">{{
          selected.display_name || "—"
        }}</el-descriptions-item>
        <el-descriptions-item label="Project">{{ selected.project_id }}</el-descriptions-item>
        <el-descriptions-item label="生命周期">{{
          selected.lifecycle_status
        }}</el-descriptions-item>
        <el-descriptions-item label="连接 / 健康"
          >{{ selected.connection_status }} / {{ selected.health_status }}</el-descriptions-item
        >
        <el-descriptions-item label="启用状态">{{ selected.enable_status }}</el-descriptions-item>
        <el-descriptions-item label="最后心跳">{{
          selected.last_heartbeat_at || "尚未心跳"
        }}</el-descriptions-item>
        <el-descriptions-item label="能力">
          <pre>{{ JSON.stringify(selected.capabilities, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="Runtime Metadata">
          <pre>{{ JSON.stringify(selected.runtime_metadata, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ selected.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </section>
</template>
