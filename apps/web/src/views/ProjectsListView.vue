<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import { useProjectsStore } from "../stores/projects";

const projects = useProjectsStore();
const router = useRouter();
const createVisible = ref(false);
const validationMessage = ref("");
const createForm = reactive({
  project_code: "",
  display_name: "",
  owner_user_id: "",
  reason: "",
});

onMounted(() => {
  void projects.loadProjects().catch(() => undefined);
});

function ownerNames(owners: Array<{ user_id: string; display_name?: string | null }>): string {
  return owners.map((owner) => owner.display_name || owner.user_id).join("、");
}

function openCreate(): void {
  validationMessage.value = "";
  createVisible.value = true;
}

async function submitCreate(): Promise<void> {
  const projectCode = createForm.project_code.trim();
  if (!projectCode) {
    validationMessage.value = "请输入项目编码。";
    return;
  }
  validationMessage.value = "";
  try {
    const created = await projects.createProject({
      project_code: projectCode,
      display_name: createForm.display_name.trim() || null,
      owner_user_id: createForm.owner_user_id.trim() || null,
      reason: createForm.reason.trim() || null,
    });
    createVisible.value = false;
    ElMessage.success("项目已创建并完成初始化。");
    await router.push({ name: "projects.detail", params: { id: created.project_id } });
  } catch {
    // The store exposes the operation-specific message and correlation id in the dialog.
  }
}
</script>

<template>
  <section class="project-page" aria-labelledby="projects-title">
    <div class="page-heading">
      <div>
        <p class="eyebrow">PROJECTS</p>
        <h2 id="projects-title">项目管理</h2>
        <p>查看授权项目，维护基础信息和生命周期。</p>
      </div>
      <PermissionGate permission="PROJECT_CREATE">
        <el-button type="primary" @click="openCreate">创建项目</el-button>
      </PermissionGate>
    </div>

    <el-alert
      v-if="projects.errorMessage"
      :title="projects.errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="workspace-alert"
    >
      <template v-if="projects.correlationId" #default>
        <span class="correlation-id">请求标识：{{ projects.correlationId }}</span>
      </template>
    </el-alert>

    <el-card class="project-list-card" shadow="never" v-loading="projects.status === 'loading'">
      <el-empty
        v-if="projects.status !== 'loading' && projects.items.length === 0"
        description="当前范围内暂无项目"
      >
        <PermissionGate permission="PROJECT_CREATE">
          <el-button type="primary" plain @click="openCreate">创建第一个项目</el-button>
        </PermissionGate>
      </el-empty>
      <el-table v-else :data="projects.items" row-key="project_id">
        <el-table-column prop="project_code" label="项目编码" min-width="170" />
        <el-table-column label="项目名称" min-width="180">
          <template #default="{ row }">{{ row.display_name || "未设置" }}</template>
        </el-table-column>
        <el-table-column label="负责人" min-width="200">
          <template #default="{ row }">{{ ownerNames(row.owners) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.lifecycle_status === 'ACTIVE' ? 'success' : 'info'">
              {{ row.lifecycle_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="86">
          <template #default="{ row }">v{{ row.row_version }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              @click="router.push({ name: 'projects.detail', params: { id: row.project_id } })"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="创建项目" width="min(560px, 92vw)">
      <el-alert
        v-if="validationMessage || projects.errorMessage"
        :title="validationMessage || projects.errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      />
      <el-form label-position="top" @submit.prevent="submitCreate">
        <el-form-item label="项目编码" required>
          <el-input v-model="createForm.project_code" maxlength="191" autocomplete="off" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="createForm.display_name" maxlength="255" autocomplete="off" />
        </el-form-item>
        <el-form-item label="首任负责人用户 ID">
          <el-input
            v-model="createForm.owner_user_id"
            maxlength="26"
            placeholder="留空时使用当前合格创建者"
            autocomplete="off"
          />
        </el-form-item>
        <el-form-item label="创建原因">
          <el-input v-model="createForm.reason" type="textarea" maxlength="1000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="projects.status === 'creating'"
          @click="submitCreate"
        >
          创建并启用
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
