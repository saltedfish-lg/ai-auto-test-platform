<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type { RunnerCapabilityResource, RunnerResource } from "../generated/types";
import { capabilityLabel, statusLabel } from "../presentation/labels";
import { useProjectsStore } from "../stores/projects";
import { type RunnerLifecycleAction, useRunnersStore } from "../stores/runners";
import { useSessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const runners = useRunnersStore();
const projects = useProjectsStore();
const session = useSessionStore();
const projectInput = ref(String(route.query.project_id ?? ""));
const projectId = computed(() =>
  route.params.projectId ? String(route.params.projectId) : projectInput.value.trim(),
);
const hasProjectScope = computed(() => projectId.value.length === 26);
const activeProjects = computed(() =>
  projects.items.filter((project) => project.lifecycle_status === "ACTIVE"),
);
const selectedProject = computed(() =>
  projects.items.find((project) => project.project_id === projectId.value),
);
const capabilityOptions = computed(() =>
  [...new Set(runners.items.flatMap((runner) => runner.capabilities.map((item) => item.capability_code)))].sort(),
);
const filters = reactive({ lifecycleStatus: "", healthStatus: "", capabilityCode: "" });
const selected = ref<RunnerResource | null>(null);
const detailVisible = ref(false);
const createVisible = ref(false);
const credentialVisible = ref(false);
const editVisible = ref(false);
const commandVisible = ref(false);
const tokenVisible = ref(false);
const capabilityVisible = ref(false);
const command = ref<RunnerLifecycleAction | "rotate" | "revoke">("enable");
const createForm = reactive({ runner_code: "", display_name: "", reason: "" });
const editForm = reactive({ display_name: "", reason: "" });
const commandReason = ref("");
const capabilityForm = reactive({ capability_code: "", evidence_summary: "", reason: "" });
const localError = ref("");


onMounted(async () => {
  if (projects.items.length === 0) {
    await projects.loadProjects().catch(() => undefined);
  }
  if (!route.params.projectId && !projectInput.value && activeProjects.value.length === 1) {
    projectInput.value = activeProjects.value[0]?.project_id ?? "";
  }
});

watch(
  projectId,
  (value) => {
    if (value.length === 26) void runners.load(value).catch(() => undefined);
  },
  { immediate: true },
);

async function openProjectScope(): Promise<void> {
  if (!hasProjectScope.value) {
    localError.value = "请选择要管理 Runner 的项目。";
    return;
  }
  localError.value = "";
  await router.replace({ name: "runners.manage", query: { project_id: projectId.value } });
  await refresh(1);
}

async function refresh(page = runners.page.page): Promise<void> {
  if (!hasProjectScope.value) {
    localError.value = "请先选择要管理 Runner 的项目。";
    return;
  }
  localError.value = "";
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
  if (!hasProjectScope.value) {
    return;
  }

  Object.assign(createForm, {
    runner_code: "",
    display_name: "",
    reason: "",
  });

  localError.value = "";
  createVisible.value = true;
}

async function submitCreate(): Promise<void> {
  if (!hasProjectScope.value) {
    localError.value = "请先选择要管理 Runner 的项目。";
    return;
  }

  if (!createForm.runner_code.trim() || !createForm.reason.trim()) {
    localError.value = "请填写 Runner 编码 和创建原因。";
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

function pendingCapabilities(runner: RunnerResource): RunnerCapabilityResource[] {
  return runner.capabilities.filter(
    (item) =>
      item.availability_status === "CONFIGURED" &&
      item.lifecycle_status === "ACTIVE" &&
      item.validation_status === "PENDING",
  );
}

function openCapabilityValidation(runner: RunnerResource): void {
  selected.value = runner;
  const first = pendingCapabilities(runner)[0];
  Object.assign(capabilityForm, {
    capability_code: first?.capability_code ?? "",
    evidence_summary: "",
    reason: "",
  });
  localError.value = "";
  capabilityVisible.value = true;
}

async function submitCapabilityValidation(): Promise<void> {
  if (
    !selected.value ||
    !capabilityForm.capability_code ||
    !capabilityForm.evidence_summary.trim() ||
    !capabilityForm.reason.trim()
  ) {
    localError.value = "请选择已上报的待验证能力，并填写运行证据与验证原因。";
    return;
  }
  const capability = selected.value.capabilities.find(
    (item) => item.capability_code === capabilityForm.capability_code,
  );
  if (!capability) {
    localError.value = "所选能力已不在当前 Runner 上报快照中，请刷新。";
    return;
  }
  try {
    const updated = await runners.validateCapability(
      selected.value,
      capability,
      capabilityForm.evidence_summary.trim(),
      capabilityForm.reason.trim(),
    );
    selected.value = updated;
    capabilityVisible.value = false;
    ElMessage.success("Runner 能力已完成正式验证。");
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
  rotate: "轮换 Agent 令牌",
  revoke: "撤销 Agent 令牌",
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
        <p>管理 项目归属、Agent 注册、分离生命周期与运行健康，以及受控能力事实。</p>
      </div>
      <PermissionGate permission="RUNNER_BIND">
        <el-tooltip
          :disabled="hasProjectScope"
          content="请先选择项目"
          placement="bottom"
        >
          <span>
            <el-button type="primary" :disabled="!hasProjectScope" @click="openCreate">
              创建注册凭据
            </el-button>
          </span>
        </el-tooltip>
      </PermissionGate>
    </div>
    <el-card v-if="!route.params.projectId" shadow="never" class="filter-card">
      <el-alert
        v-if="localError"
        :title="localError"
        type="error"
        :closable="false"
        show-icon
        class="workspace-alert"
      />
      <el-form inline @submit.prevent="openProjectScope">
        <el-form-item label="项目">
          <el-select
            v-model="projectInput"
            filterable
            clearable
            style="width: 320px"
            placeholder="选择有权访问的项目"
            :loading="projects.status === 'loading'"
          >
            <el-option
              v-for="project in activeProjects"
              :key="project.project_id"
              :label="project.display_name || project.project_code"
              :value="project.project_id"
            />
          </el-select>
        </el-form-item>

        <el-button type="primary" @click="openProjectScope">打开 Runner 管理</el-button>
      </el-form>

      <p>项目范围由服务端按 Runner 管理权限实时校验。</p>
    </el-card>

    <el-alert
      v-if="runners.errorMessage"
      :title="runners.errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="workspace-alert"
    >
      <template v-if="runners.errorCode || runners.correlationId" #default>
        <span v-if="runners.errorCode">错误代码：{{ runners.errorCode }}</span>
        <span v-if="runners.errorCode && runners.correlationId"> · </span>
        <span v-if="runners.correlationId">请求标识：{{ runners.correlationId }}</span>
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
              :label="statusLabel('lifecycle', value)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="健康">
          <el-select v-model="filters.healthStatus" clearable style="width: 150px">
            <el-option
              v-for="value in ['UNKNOWN', 'HEALTHY', 'DEGRADED', 'UNHEALTHY']"
              :key="value"
              :value="value"
              :label="statusLabel('health', value)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="能力">
          <el-select v-model="filters.capabilityCode" clearable filterable style="width: 200px" placeholder="选择能力">
            <el-option v-for="code in capabilityOptions" :key="code" :value="code" :label="capabilityLabel(code)" />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="refresh(1)">查询</el-button>
      </el-form>
    </el-card>

    <el-table
      :data="runners.items"
      v-loading="runners.status === 'loading'"
      empty-text="暂无已注册 Runner"
    >
      <el-table-column prop="runner_code" label="Runner 编码" min-width="160" />
      <el-table-column prop="display_name" label="显示名称" min-width="140" />
      <el-table-column label="项目" min-width="180">
        <template #default>{{ selectedProject?.display_name || selectedProject?.project_code || "当前项目" }}</template>
      </el-table-column>
      <el-table-column label="生命周期" width="125">
        <template #default="scope">{{ statusLabel('lifecycle', scope.row.lifecycle_status) }}</template>
      </el-table-column>
      <el-table-column label="运行状态" min-width="180">
        <template #default="scope">
          {{ statusLabel('connection', scope.row.connection_status) }} / {{ statusLabel('health', scope.row.health_status) }}
        </template>
      </el-table-column>
      <el-table-column label="调度状态" min-width="150">
        <template #default="scope">{{ statusLabel('scheduling', scope.row.scheduling_status) }}</template>
      </el-table-column>
      <el-table-column label="版本兼容性" min-width="150">
        <template #default="scope">{{ statusLabel('compatibility', scope.row.version_compatibility) }}</template>
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
            {{ capabilityLabel(capability.capability_code) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" min-width="190" />
      <el-table-column label="操作" fixed="right" min-width="300">
        <template #default="scope">
          <el-button link type="primary" @click="openDetail(scope.row)">详情</el-button>
          <PermissionGate permission="RUNNER_REGISTER">
            <el-button
              v-if="pendingCapabilities(scope.row).length > 0"
              link
              type="success"
              @click="openCapabilityValidation(scope.row)"
              >验证能力</el-button
            >
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
                  <el-dropdown-item command="rotate">轮换 Agent 令牌</el-dropdown-item>
                  <el-dropdown-item command="revoke">撤销 Agent 令牌</el-dropdown-item>
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

    <el-dialog v-model="createVisible" title="创建 Runner 注册凭据" width="560px">
      <el-alert v-if="localError" :title="localError" type="error" :closable="false" />
      <el-form label-position="top">
        <el-form-item label="所属项目" required>
          <el-text>{{ selectedProject?.display_name || selectedProject?.project_code || "当前项目" }}</el-text>
        </el-form-item>

        <el-form-item label="Runner 编码" required>
          <el-input v-model="createForm.runner_code" />
        </el-form-item>

        <el-form-item label="显示名称">
          <el-input v-model="createForm.display_name" />
        </el-form-item>

        <el-form-item label="原因" required>
          <el-input v-model="createForm.reason" type="textarea" />
        </el-form-item>
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
      title="一次性 Runner 注册凭据"
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

    <el-dialog v-model="capabilityVisible" title="验证 Runner 能力" width="600px">
      <el-alert
        v-if="localError"
        :title="localError"
        type="error"
        :closable="false"
        class="workspace-alert"
      />
      <el-alert
        title="验证只作用于真实 Runner 当前上报的待验证能力，不会改变 Runner 的连接、健康或启用状态。"
        type="info"
        :closable="false"
        class="workspace-alert"
      />
      <el-form v-if="selected" label-position="top">
        <el-form-item label="能力" required>
          <el-select v-model="capabilityForm.capability_code" style="width: 100%">
            <el-option
              v-for="capability in pendingCapabilities(selected)"
              :key="capability.runner_capability_id"
              :label="`${capabilityLabel(capability.capability_code)} · 上报版本 ${capability.row_version}`"
              :value="capability.capability_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="运行证据摘要" required>
          <el-input v-model="capabilityForm.evidence_summary" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="验证原因" required>
          <el-input v-model="capabilityForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="capabilityVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="runners.status === 'saving'"
          @click="submitCapabilityValidation"
          >确认验证</el-button
        >
      </template>
    </el-dialog>

    <el-dialog
      v-model="tokenVisible"
      title="新的 Runner Agent 令牌"
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
        <el-descriptions-item label="Runner 编码">{{ selected.runner_code }}</el-descriptions-item>
        <el-descriptions-item label="显示名称">{{
          selected.display_name || "—"
        }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ selectedProject?.display_name || selectedProject?.project_code || "当前项目" }}</el-descriptions-item>
        <el-descriptions-item label="生命周期">{{ statusLabel('lifecycle', selected.lifecycle_status) }}</el-descriptions-item>
        <el-descriptions-item label="连接 / 健康">{{ statusLabel('connection', selected.connection_status) }} / {{ statusLabel('health', selected.health_status) }}</el-descriptions-item>
        <el-descriptions-item label="启用状态">{{ statusLabel('enablement', selected.enable_status) }}</el-descriptions-item>
        <el-descriptions-item label="项目绑定">{{ statusLabel('binding', selected.project_binding_status) }}</el-descriptions-item>
        <el-descriptions-item label="调度状态">{{ statusLabel('scheduling', selected.scheduling_status) }}</el-descriptions-item>
        <el-descriptions-item label="资源状态">{{ statusLabel('resource', selected.resource_status) }}</el-descriptions-item>
        <el-descriptions-item label="版本兼容性">{{ statusLabel('compatibility', selected.version_compatibility) }}</el-descriptions-item>
        <el-descriptions-item label="最后心跳">{{
          selected.last_heartbeat_at || "尚未心跳"
        }}</el-descriptions-item>
        <el-descriptions-item label="能力">
          <el-space wrap>
            <el-tag v-for="capability in selected.capabilities" :key="capability.runner_capability_id">
              {{ capabilityLabel(capability.capability_code) }} · {{ statusLabel('capabilityValidation', capability.validation_status) }}
            </el-tag>
          </el-space>
        </el-descriptions-item>
        <el-descriptions-item label="技术信息">
          <el-collapse>
            <el-collapse-item title="内部标识与运行元数据" name="technical">
              <p>Runner 标识：<code>{{ selected.runner_id }}</code></p>
              <p>项目标识：<code>{{ selected.project_id }}</code></p>
              <pre>{{ JSON.stringify(selected.runtime_metadata, null, 2) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ selected.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </section>
</template>
