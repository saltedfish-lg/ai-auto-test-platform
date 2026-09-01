<script setup lang="ts">
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import type { EnvironmentResource } from "../generated/types";
import { type EnvironmentLifecycleAction, useEnvironmentsStore } from "../stores/environments";

const route = useRoute();
const router = useRouter();
const environments = useEnvironmentsStore();
const projectId = computed(() => String(route.params.projectId));
const createVisible = ref(false);
const editVisible = ref(false);
const detailVisible = ref(false);
const lifecycleFilter = ref("");
const currentPage = ref(1);
const pageSize = ref(50);
const selected = ref<EnvironmentResource | null>(null);
const createForm = reactive({ environment_code: "", display_name: "", reason: "" });
const editForm = reactive({ display_name: "", reason: "" });

watch(
  projectId,
  (id) => {
    currentPage.value = 1;
    void environments.load(id, undefined, currentPage.value, pageSize.value).catch(() => undefined);
  },
  { immediate: true },
);

function openCreate(): void {
  Object.assign(createForm, { environment_code: "", display_name: "", reason: "" });
  createVisible.value = true;
}

function openDetail(environment: EnvironmentResource): void {
  selected.value = environment;
  detailVisible.value = true;
}

function openEdit(environment: EnvironmentResource): void {
  selected.value = environment;
  Object.assign(editForm, { display_name: environment.display_name ?? "", reason: "" });
  editVisible.value = true;
}

async function submitCreate(): Promise<void> {
  if (!createForm.environment_code.trim()) return;
  try {
    await environments.create({
      project_id: projectId.value,
      environment_code: createForm.environment_code.trim(),
      display_name: createForm.display_name.trim() || null,
      reason: createForm.reason.trim() || null,
    });
    createVisible.value = false;
    ElMessage.success("环境已创建并进入 CONFIGURING。 ");
  } catch {
    // Store exposes the formal backend error.
  }
}

async function submitEdit(): Promise<void> {
  if (!selected.value) return;
  try {
    await environments.update(selected.value, {
      display_name: editForm.display_name.trim() || null,
      reason: editForm.reason.trim() || null,
    });
    editVisible.value = false;
    ElMessage.success("环境名称已更新。");
  } catch {
    // Store exposes the formal backend error.
  }
}

async function toggleEnablement(environment: EnvironmentResource): Promise<void> {
  const disabling = environment.enablement_state === "ENABLED";
  const action = disabling ? "停用" : "恢复";
  try {
    const { value } = await ElMessageBox.prompt(`请填写${action}原因`, `${action}环境`, {
      inputPattern: /\S+/,
      inputErrorMessage: "操作原因不能为空。",
      confirmButtonText: `确认${action}`,
      cancelButtonText: "取消",
      type: disabling ? "warning" : "info",
    });
    await environments.update(environment, {
      enablement_state: disabling ? "DISABLED" : "ENABLED",
      reason: value.trim(),
    });
    ElMessage.success(`${action}操作已完成。`);
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      // Store exposes the formal backend error.
    }
  }
}

const lifecycleActionCopy: Record<EnvironmentLifecycleAction, { label: string; title: string }> = {
  validate: { label: "提交校验", title: "提交环境校验" },
  reconfigure: { label: "退回配置", title: "退回环境配置" },
  activate: { label: "激活", title: "激活环境" },
};

function lifecycleCopy(
  environment: EnvironmentResource,
  action: EnvironmentLifecycleAction,
): { label: string; title: string } {
  if (environment.lifecycle_status === "RECOVERING" && action === "activate") {
    return { label: "完成恢复", title: "完成环境恢复" };
  }
  return lifecycleActionCopy[action];
}

function lifecycleActions(environment: EnvironmentResource): EnvironmentLifecycleAction[] {
  if (environment.lifecycle_status === "CONFIGURING") return ["validate"];
  if (environment.lifecycle_status === "VALIDATING") return ["reconfigure", "activate"];
  if (environment.lifecycle_status === "RECOVERING") return ["activate"];
  return [];
}

async function runLifecycle(
  environment: EnvironmentResource,
  action: EnvironmentLifecycleAction,
): Promise<void> {
  const copy = lifecycleCopy(environment, action);
  try {
    const { value } = await ElMessageBox.prompt(`请填写${copy.label}原因`, copy.title, {
      inputPattern: /\S+/,
      inputErrorMessage: "操作原因不能为空。",
      confirmButtonText: `确认${copy.label}`,
      cancelButtonText: "取消",
      type: action === "activate" ? "success" : "info",
    });
    await environments.lifecycle(environment, action, value.trim());
    ElMessage.success(`${copy.label}操作已完成。`);
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      // Store exposes the formal backend error.
    }
  }
}

async function applyFilter(): Promise<void> {
  currentPage.value = 1;
  await loadPage();
}

async function loadPage(): Promise<void> {
  await environments
    .load(projectId.value, lifecycleFilter.value || undefined, currentPage.value, pageSize.value)
    .catch(() => undefined);
}

async function changePage(page: number): Promise<void> {
  currentPage.value = page;
  await loadPage();
}

async function changePageSize(size: number): Promise<void> {
  pageSize.value = size;
  currentPage.value = 1;
  await loadPage();
}
</script>

<template>
  <section class="project-page" aria-labelledby="environment-title">
    <div class="page-heading">
      <div>
        <el-button
          link
          type="primary"
          @click="router.push({ name: 'projects.detail', params: { id: projectId } })"
        >
          ← 返回项目详情
        </el-button>
        <h2 id="environment-title">环境管理</h2>
        <p class="muted">
          Environment 只维护环境级事实；访问配置由各业务终端自己的 Revision 维护。
        </p>
      </div>
      <PermissionGate permission="PROJECT_EDIT">
        <el-button type="primary" @click="openCreate">创建环境</el-button>
      </PermissionGate>
    </div>

    <el-alert
      v-if="environments.errorMessage"
      :title="environments.errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="workspace-alert"
    >
      <template v-if="environments.correlationId" #default>
        <span class="correlation-id">请求标识：{{ environments.correlationId }}</span>
      </template>
    </el-alert>

    <el-card shadow="never">
      <div class="environment-toolbar">
        <el-select
          v-model="lifecycleFilter"
          aria-label="生命周期筛选"
          placeholder="全部生命周期"
          clearable
        >
          <el-option
            v-for="status in [
              'CONFIGURING',
              'VALIDATING',
              'ACTIVE',
              'UNREACHABLE',
              'DISABLED',
              'RECOVERING',
              'ARCHIVED',
            ]"
            :key="status"
            :label="status"
            :value="status"
          />
        </el-select>
        <el-button @click="applyFilter">筛选</el-button>
      </div>
      <el-table
        :data="environments.items"
        v-loading="environments.status === 'loading'"
        empty-text="当前项目暂无环境"
      >
        <el-table-column prop="environment_code" label="环境编码" min-width="160" />
        <el-table-column prop="display_name" label="环境名称" min-width="160" />
        <el-table-column prop="lifecycle_status" label="生命周期" min-width="130" />
        <el-table-column prop="enablement_state" label="启用状态" min-width="110" />
        <el-table-column prop="accessibility_state" label="可达性" min-width="110" />
        <el-table-column prop="updated_at" label="更新时间" min-width="190" />
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <PermissionGate permission="PROJECT_EDIT">
              <el-button
                link
                type="primary"
                :disabled="row.lifecycle_status === 'ARCHIVED'"
                @click="openEdit(row)"
                >编辑</el-button
              >
              <el-button
                v-if="['ACTIVE', 'DISABLED'].includes(row.lifecycle_status)"
                link
                :type="row.enablement_state === 'ENABLED' ? 'warning' : 'success'"
                :disabled="environments.status === 'saving'"
                @click="toggleEnablement(row)"
              >
                {{ row.enablement_state === "ENABLED" ? "停用" : "恢复" }}
              </el-button>
              <el-button
                v-for="action in lifecycleActions(row)"
                :key="action"
                link
                :type="action === 'activate' ? 'success' : 'primary'"
                :disabled="environments.status === 'saving'"
                @click="runLifecycle(row, action)"
              >
                {{ lifecycleCopy(row, action).label }}
              </el-button>
            </PermissionGate>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="environment-pagination"
        background
        layout="total, sizes, prev, pager, next"
        :current-page="currentPage"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="environments.page.total"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </el-card>

    <el-dialog v-model="createVisible" title="创建环境" width="min(540px, 92vw)">
      <el-form label-position="top" @submit.prevent="submitCreate">
        <el-form-item label="环境编码" required
          ><el-input v-model="createForm.environment_code" maxlength="191"
        /></el-form-item>
        <el-form-item label="环境名称"
          ><el-input v-model="createForm.display_name" maxlength="255"
        /></el-form-item>
        <el-form-item label="创建原因"
          ><el-input v-model="createForm.reason" type="textarea" maxlength="1000"
        /></el-form-item>
        <p class="security-form-note">
          新环境进入 CONFIGURING；此阶段不要求 Terminal Access Revision。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="environments.status === 'saving'" @click="submitCreate"
          >确认创建</el-button
        >
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑环境" width="min(520px, 92vw)">
      <el-form label-position="top" @submit.prevent="submitEdit">
        <el-form-item label="环境编码"
          ><el-input :model-value="selected?.environment_code" disabled
        /></el-form-item>
        <el-form-item label="环境名称"
          ><el-input v-model="editForm.display_name" maxlength="255"
        /></el-form-item>
        <el-form-item label="变更原因"
          ><el-input v-model="editForm.reason" type="textarea" maxlength="1000"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="environments.status === 'saving'" @click="submitEdit"
          >保存</el-button
        >
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="环境详情" width="min(620px, 92vw)">
      <dl v-if="selected" class="identity-list">
        <dt>Environment ID</dt>
        <dd class="monospace">{{ selected.environment_id }}</dd>
        <dt>Project ID</dt>
        <dd class="monospace">{{ selected.project_id }}</dd>
        <dt>环境编码</dt>
        <dd>{{ selected.environment_code }}</dd>
        <dt>生命周期</dt>
        <dd>{{ selected.lifecycle_status }}</dd>
        <dt>当前版本</dt>
        <dd>v{{ selected.row_version }}</dd>
      </dl>
    </el-dialog>
  </section>
</template>
