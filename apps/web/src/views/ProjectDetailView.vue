<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PermissionGate from "../components/PermissionGate.vue";
import { useProjectsStore } from "../stores/projects";

const projects = useProjectsStore();
const route = useRoute();
const router = useRouter();
const projectId = computed(() => String(route.params.id));
const editVisible = ref(false);
const transitionVisible = ref(false);
const transitionAction = ref<"disable" | "recover" | "archive">("disable");
const editForm = reactive({ display_name: "", reason: "" });
const transitionReason = ref("");
const localError = ref("");

watch(
  () => projects.current,
  (project) => {
    if (project?.project_id === projectId.value) {
      editForm.display_name = project.display_name ?? "";
      editForm.reason = "";
    }
  },
  { immediate: true },
);

watch(
  projectId,
  (id) => {
    editVisible.value = false;
    transitionVisible.value = false;
    localError.value = "";
    void projects.loadProject(id).catch(() => undefined);
  },
  { immediate: true },
);

const transitionTitle = computed(() => {
  const labels = { disable: "停用项目", recover: "恢复项目", archive: "归档项目" };
  return labels[transitionAction.value];
});

function openTransition(action: "disable" | "recover" | "archive"): void {
  transitionAction.value = action;
  transitionReason.value = "";
  localError.value = "";
  transitionVisible.value = true;
}

async function saveProject(): Promise<void> {
  const project = projects.current;
  if (!project) return;
  localError.value = "";
  try {
    await projects.updateProject(project.project_id, {
      expected_version: project.row_version,
      display_name: editForm.display_name.trim() || null,
      reason: editForm.reason.trim() || null,
    });
    editVisible.value = false;
    ElMessage.success("项目基础信息已保存。");
  } catch {
    // The operation-specific message remains visible in this page.
  }
}

async function submitTransition(): Promise<void> {
  const project = projects.current;
  if (!project) return;
  if (!transitionReason.value.trim()) {
    localError.value = "请填写状态变更原因。";
    return;
  }
  localError.value = "";
  try {
    await projects.transitionProject(project.project_id, transitionAction.value, {
      expected_version: project.row_version,
      reason: transitionReason.value.trim(),
    });
    transitionVisible.value = false;
    ElMessage.success(`${transitionTitle.value}已完成。`);
  } catch {
    // The operation-specific message remains visible in this page.
  }
}
</script>

<template>
  <section class="project-page" aria-labelledby="project-detail-title">
    <div class="page-heading">
      <div>
        <el-button link type="primary" @click="router.push({ name: 'projects.list' })">
          ← 返回项目列表
        </el-button>
        <h2 id="project-detail-title">{{ projects.current?.display_name || "项目详情" }}</h2>
        <p class="monospace">{{ projects.current?.project_code }}</p>
      </div>
      <div v-if="projects.current" class="page-actions">
        <PermissionGate permission="PROJECT_EDIT">
          <el-button
            v-if="projects.current.lifecycle_status === 'ACTIVE'"
            @click="editVisible = true"
          >
            编辑基础信息
          </el-button>
          <el-button
            v-if="projects.current.lifecycle_status === 'ACTIVE'"
            type="warning"
            plain
            @click="openTransition('disable')"
          >
            停用项目
          </el-button>
          <el-button
            v-if="projects.current.lifecycle_status === 'DISABLED'"
            type="success"
            plain
            @click="openTransition('recover')"
          >
            恢复项目
          </el-button>
        </PermissionGate>
        <PermissionGate permission="PROJECT_ARCHIVE">
          <el-button
            v-if="projects.current.lifecycle_status === 'DISABLED'"
            type="danger"
            plain
            @click="openTransition('archive')"
          >
            归档项目
          </el-button>
        </PermissionGate>
      </div>
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

    <div v-if="projects.status === 'loading'" class="project-loading" v-loading="true"></div>
    <template v-else-if="projects.current">
      <div class="project-detail-grid">
        <el-card shadow="never">
          <template #header><strong>项目信息</strong></template>
          <dl class="identity-list">
            <dt>项目编码</dt><dd class="monospace">{{ projects.current.project_code }}</dd>
            <dt>项目名称</dt><dd>{{ projects.current.display_name || "未设置" }}</dd>
            <dt>生命周期</dt>
            <dd><el-tag type="success">{{ projects.current.lifecycle_status }}</el-tag></dd>
            <dt>当前版本</dt><dd>v{{ projects.current.row_version }}</dd>
            <dt>项目 ID</dt><dd class="monospace">{{ projects.current.project_id }}</dd>
          </dl>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="section-heading">
              <div><strong>项目负责人</strong><p>ACTIVE 成员与 Owner 职责共同派生项目范围</p></div>
              <el-tag type="info">{{ projects.current.owners.length }} 人</el-tag>
            </div>
          </template>
          <div class="owner-list">
            <div v-for="owner in projects.current.owners" :key="owner.user_id" class="owner-row">
              <div>
                <strong>{{ owner.display_name || "未设置名称" }}</strong>
                <p class="monospace">{{ owner.user_id }}</p>
              </div>
              <el-tag type="success">{{ owner.membership_status }}</el-tag>
            </div>
          </div>
          <p class="scope-note">Owner ALL 仅限当前 project_id，不代表全平台范围。</p>
        </el-card>
      </div>
    </template>

    <el-dialog v-model="editVisible" title="编辑项目基础信息" width="min(520px, 92vw)">
      <el-form label-position="top" @submit.prevent="saveProject">
        <el-form-item label="项目名称">
          <el-input v-model="editForm.display_name" maxlength="255" />
        </el-form-item>
        <el-form-item label="变更原因">
          <el-input v-model="editForm.reason" type="textarea" maxlength="1000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="projects.status === 'saving'" @click="saveProject">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="transitionVisible" :title="transitionTitle" width="min(500px, 92vw)">
      <el-alert
        v-if="localError || projects.errorMessage"
        :title="localError || projects.errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      />
      <p class="muted">该操作将按 LC-007 校验当前状态和版本，服务端拒绝任何非法转换。</p>
      <el-form label-position="top" @submit.prevent="submitTransition">
        <el-form-item label="操作原因" required>
          <el-input v-model="transitionReason" type="textarea" maxlength="1000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transitionVisible = false">取消</el-button>
        <el-button
          :type="transitionAction === 'archive' ? 'danger' : 'primary'"
          :loading="projects.status === 'transitioning'"
          @click="submitTransition"
        >
          确认{{ transitionTitle }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
