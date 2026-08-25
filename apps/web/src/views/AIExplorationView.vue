<script setup lang="ts">
import { computed, onMounted, reactive } from "vue";
import { useRoute } from "vue-router";

import { useAIExplorationsStore } from "../stores/aiExplorations";
import { useProjectsStore } from "../stores/projects";

const route = useRoute();
const explorations = useAIExplorationsStore();
const projects = useProjectsStore();
const form = reactive({
  project_id: typeof route.query.project_id === "string" ? route.query.project_id : "",
  objective: "",
  target_url: "",
});

const activeProjects = computed(() =>
  projects.items.filter((project) => project.lifecycle_status === "ACTIVE"),
);
const session = computed(() => explorations.current);
const failureMessages: Record<string, string> = {
  AI_EXPLORATION_MODEL_UNAVAILABLE: "AI 探索默认模型当前不可用，请稍后重试。",
  AI_EXPLORATION_MODEL_RESPONSE_INVALID: "模型未返回有效的结构化探索计划。",
  AI_EXPLORATION_PLANNING_FAILED: "初始探索计划生成失败，请稍后重试。",
  AI_EXPLORATION_PLANNING_INTERRUPTED: "上次探索规划已中断，请重新发起规划。",
};
const statusType = computed(() =>
  session.value?.lifecycle_status === "READY"
    ? "success"
    : session.value?.lifecycle_status === "FAILED"
      ? "danger"
      : "info",
);
const failureTitle = computed(() => {
  const code = session.value?.failure_code;
  return failureMessages[code ?? ""] ?? session.value?.failure_message ?? "AI 探索规划失败。";
});

onMounted(async () => {
  if (projects.items.length === 0) {
    try {
      await projects.loadProjects();
    } catch {
      // The project store renders its structured error below.
    }
  }
  if (!form.project_id && activeProjects.value.length === 1) {
    form.project_id = activeProjects.value[0]?.project_id ?? "";
  }
});

async function startPlanning(): Promise<void> {
  if (!form.project_id || !form.objective.trim() || !form.target_url.trim()) return;
  try {
    await explorations.create({
      project_id: form.project_id,
      objective: form.objective.trim(),
      target_url: form.target_url.trim(),
    });
  } catch {
    // The store exposes the sanitized API failure and correlation id.
  }
}
</script>

<template>
  <section class="exploration-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">AI EXPLORATION</p>
        <h2>AI 探索规划</h2>
        <p>根据测试目标生成结构化初始计划；本阶段不会打开或操作目标页面。</p>
      </div>
    </header>

    <el-card class="planning-card" shadow="never">
      <template #header>
        <div class="card-heading">
          <strong>创建探索会话</strong>
          <span>模型由 AI_EXPLORATION 平台默认绑定实时解析</span>
        </div>
      </template>
      <el-form label-position="top" @submit.prevent="startPlanning">
        <el-form-item label="项目" required>
          <el-select
            v-model="form.project_id"
            aria-label="项目"
            placeholder="选择有权访问的 ACTIVE 项目"
            :loading="projects.status === 'loading'"
            filterable
          >
            <el-option
              v-for="project in activeProjects"
              :key="project.project_id"
              :label="project.display_name || project.project_code"
              :value="project.project_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="测试目标" required>
          <el-input
            v-model="form.objective"
            aria-label="测试目标"
            type="textarea"
            :rows="4"
            maxlength="4000"
            show-word-limit
            placeholder="例如：验证有效用户能够登录并进入工作台"
          />
        </el-form-item>
        <el-form-item label="目标页面地址" required>
          <el-input
            v-model="form.target_url"
            aria-label="目标页面地址"
            type="url"
            maxlength="2048"
            placeholder="https://example.test/login"
          />
        </el-form-item>
        <el-button
          native-type="submit"
          type="primary"
          :loading="explorations.status === 'planning'"
          :disabled="!form.project_id || !form.objective.trim() || !form.target_url.trim()"
        >
          {{ explorations.status === "planning" ? "AI 正在规划" : "创建并开始规划" }}
        </el-button>
      </el-form>
      <el-alert
        v-if="projects.errorMessage"
        class="feedback-alert"
        type="error"
        :closable="false"
        :title="projects.errorMessage"
      />
      <el-alert
        v-if="explorations.errorMessage"
        class="feedback-alert"
        type="error"
        :closable="false"
        :title="explorations.errorMessage"
      >
        <template v-if="explorations.correlationId" #default>
          请求标识：{{ explorations.correlationId }}
        </template>
      </el-alert>
    </el-card>

    <el-card v-if="session" class="result-card" shadow="never">
      <template #header>
        <div class="result-heading">
          <div>
            <p class="eyebrow">SESSION {{ session.session_id }}</p>
            <strong>初始探索计划</strong>
          </div>
          <el-tag :type="statusType">{{ session.lifecycle_status }}</el-tag>
        </div>
      </template>

      <div class="model-snapshot" aria-label="模型运行快照">
        <span>本次实际模型</span>
        <strong>{{ session.resolved_model_display_name || "未命名模型" }}</strong>
        <code>{{ session.resolved_provider_code }} / {{ session.resolved_model_name }}</code>
      </div>

      <el-alert
        v-if="session.lifecycle_status === 'FAILED'"
        type="error"
        :closable="false"
        :title="failureTitle"
      >
        <template #default>错误码：{{ session.failure_code }}</template>
      </el-alert>

      <div v-if="session.plan" class="plan-content">
        <div class="plan-goal">
          <span>目标</span>
          <p>{{ session.plan.goal }}</p>
        </div>
        <div v-if="session.plan.assumptions.length" class="assumptions">
          <span>规划假设</span>
          <ul>
            <li v-for="assumption in session.plan.assumptions" :key="assumption">
              {{ assumption }}
            </li>
          </ul>
        </div>
        <ol class="plan-steps" aria-label="探索步骤">
          <li v-for="step in session.plan.steps" :key="step.sequence">
            <div class="step-sequence">{{ step.sequence }}</div>
            <div>
              <strong>{{ step.intent }}</strong>
              <p>预期观察：{{ step.expected_observation }}</p>
            </div>
          </li>
        </ol>
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.exploration-page {
  display: grid;
  gap: 20px;
}

.page-heading h2 {
  margin: 4px 0 8px;
  font-size: 28px;
}

.page-heading p,
.card-heading span,
.plan-steps p {
  color: var(--el-text-color-secondary);
}

.planning-card,
.result-card {
  max-width: 960px;
}

.card-heading,
.result-heading,
.model-snapshot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-heading span {
  font-size: 13px;
}

.feedback-alert {
  margin-top: 16px;
}

.model-snapshot {
  justify-content: flex-start;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
}

.model-snapshot > span,
.plan-goal > span,
.assumptions > span {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.model-snapshot code {
  color: var(--el-color-primary);
}

.plan-content {
  margin-top: 20px;
}

.plan-goal p {
  margin: 6px 0 18px;
  font-size: 18px;
  font-weight: 600;
}

.assumptions ul {
  margin: 8px 0 22px;
  padding-left: 20px;
}

.plan-steps {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.plan-steps li {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.step-sequence {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: var(--el-color-primary);
  font-weight: 700;
}

.plan-steps p {
  margin: 6px 0 0;
}

@media (max-width: 720px) {
  .card-heading,
  .result-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
