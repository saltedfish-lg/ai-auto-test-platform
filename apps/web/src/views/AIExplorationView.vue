<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, watch } from "vue";
import { useRoute } from "vue-router";

import { enumLabel, statusLabel } from "../presentation/labels";
import { useAIExplorationsStore } from "../stores/aiExplorations";
import { useBusinessTerminalsStore } from "../stores/businessTerminals";
import { useEnvironmentsStore } from "../stores/environments";
import { useExecutionBindingsStore } from "../stores/executionBindings";
import { useProjectsStore } from "../stores/projects";
import { useRunnersStore } from "../stores/runners";

const route = useRoute();
const explorations = useAIExplorationsStore();
const projects = useProjectsStore();
const bindings = useExecutionBindingsStore();
const environments = useEnvironmentsStore();
const terminals = useBusinessTerminalsStore();
const runners = useRunnersStore();
const form = reactive({
  project_id: typeof route.query.project_id === "string" ? route.query.project_id : "",
  objective: "",
  target_url: "",
  execution_attempt_id:
    typeof route.query.execution_attempt_id === "string" ? route.query.execution_attempt_id : "",
});
let pollTimer: ReturnType<typeof setTimeout> | undefined;

const activeProjects = computed(() =>
  projects.items.filter((project) => project.lifecycle_status === "ACTIVE"),
);
const session = computed(() => explorations.current);
const readyBindings = computed(() => bindings.items.filter((item) => item.status === "READY"));

function bindingLabel(attemptId: string): string {
  const binding = readyBindings.value.find((item) => item.execution_attempt_id === attemptId);
  if (!binding) return "已就绪执行绑定";
  const environment = environments.items.find((item) => item.environment_id === binding.environment_id);
  const terminal = terminals.items.find((item) => item.business_terminal_id === binding.business_terminal_id);
  const runner = runners.items.find((item) => item.runner_id === binding.runner_id);
  const terminalType = terminal?.terminal_type === "MANAGEMENT" ? "管理端" : terminal?.terminal_type === "CLIENT" ? "客户端" : terminal?.terminal_type === "PDA" ? "PDA" : "业务终端";
  return [environment?.display_name || environment?.environment_code || "执行环境", terminal?.display_name || terminal?.terminal_code || terminalType, runner?.display_name || runner?.runner_code || "Runner", "已就绪执行实例"].join(" · ");
}

async function loadBindingOptions(projectId: string): Promise<void> {
  if (!projectId) return;
  await Promise.all([
    bindings.load(projectId, "READY").catch(() => undefined),
    environments.load(projectId, undefined, 1, 200).catch(() => undefined),
    terminals.load(projectId, {}, 1, 200).catch(() => undefined),
    runners.load(projectId, {}, 1, 200).catch(() => undefined),
  ]);
  if (!form.execution_attempt_id && readyBindings.value.length === 1) {
    form.execution_attempt_id = readyBindings.value[0]?.execution_attempt_id ?? "";
  }
}
const failureMessages: Record<string, string> = {
  AI_EXPLORATION_MODEL_UNAVAILABLE: "AI 探索默认模型当前不可用，请稍后重试。",
  AI_EXPLORATION_MODEL_RESPONSE_INVALID: "模型未返回有效的结构化探索计划。",
  AI_EXPLORATION_PLANNING_FAILED: "初始探索计划生成失败，请稍后重试。",
  AI_EXPLORATION_PLANNING_INTERRUPTED: "上次探索规划已中断，请重新发起规划。",
  AI_EXPLORATION_PREFLIGHT_FAILED: "执行实例或冻结执行绑定未通过启动检查。",
  AI_EXPLORATION_MODEL_CALL_FAILED: "冻结模型未能生成下一步浏览器动作。",
  AI_EXPLORATION_ACTION_FAILED: "Runner 执行浏览器动作失败。",
  AI_EXPLORATION_LEASE_LOST: "执行资源租约或隔离代次已失效。",
  AI_EXPLORATION_TIMEOUT: "探索达到冻结的总超时时间。",
  AI_EXPLORATION_MAX_STEPS: "探索达到冻结的最大步骤数。",
  AI_EXPLORATION_RUNNER_UNAVAILABLE: "已绑定 Runner 当前不可用。",
};
const statusType = computed(() =>
  ["READY", "SUCCEEDED"].includes(session.value?.lifecycle_status ?? "")
    ? "success"
    : session.value?.lifecycle_status === "RUNNING"
      ? "warning"
      : session.value?.lifecycle_status === "FAILED"
        ? "danger"
        : "info",
);
const failureTitle = computed(() => {
  const code = session.value?.failure_code;
  return failureMessages[code ?? ""] ?? session.value?.failure_message ?? "AI 探索规划失败。";
});

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer);
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
  if (form.project_id) await loadBindingOptions(form.project_id);
});

watch(
  () => form.project_id,
  (value, previous) => {
    if (!value || value === previous) return;
    if (!route.query.execution_attempt_id) form.execution_attempt_id = "";
    void loadBindingOptions(value);
  },
);

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

async function refreshExecution(): Promise<void> {
  const sessionId = session.value?.session_id;
  if (!sessionId) return;
  try {
    const current = await explorations.load(sessionId);
    await explorations.loadSteps(sessionId);
    if (current.lifecycle_status === "RUNNING") {
      pollTimer = setTimeout(refreshExecution, 1000);
    }
  } catch {
    pollTimer = setTimeout(refreshExecution, 2000);
  }
}

async function startBrowserLoop(): Promise<void> {
  if (session.value?.lifecycle_status !== "READY" || !form.execution_attempt_id) return;
  try {
    await explorations.start(session.value.session_id, {
      execution_attempt_id: form.execution_attempt_id.trim(),
      expected_row_version: session.value.row_version,
    });
    await refreshExecution();
  } catch {
    // Sanitized store error is rendered below.
  }
}

async function cancelBrowserLoop(): Promise<void> {
  if (session.value?.lifecycle_status !== "RUNNING") return;
  try {
    await explorations.cancel(session.value.session_id, {
      expected_row_version: session.value.row_version,
    });
    if (pollTimer) clearTimeout(pollTimer);
    await explorations.loadSteps(session.value.session_id);
  } catch {
    // Sanitized store error is rendered below.
  }
}

function observationSummary(observation: Record<string, unknown>): string {
  const title = typeof observation.title === "string" ? observation.title : "";
  const url = typeof observation.current_url === "string" ? observation.current_url : "";
  return [title, url].filter(Boolean).join(" · ") || "已记录结构化观察";
}
</script>

<template>
  <section class="exploration-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">AI EXPLORATION</p>
        <h2>AI 浏览器探索</h2>
        <p>先生成结构化计划，再选择已就绪的执行绑定，由系统使用冻结的 Runner 和执行资源完成可审计浏览器循环。</p>
      </div>
    </header>

    <el-card class="planning-card" shadow="never">
      <template #header>
        <div class="card-heading">
          <strong>创建探索会话</strong>
          <span>模型由 AI 探索能力的平台默认绑定实时解析</span>
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
        <template v-if="explorations.errorCode || explorations.correlationId" #default>
          <span v-if="explorations.errorCode">错误代码：{{ explorations.errorCode }}</span>
          <span v-if="explorations.errorCode && explorations.correlationId"> · </span>
          <span v-if="explorations.correlationId">请求标识：{{ explorations.correlationId }}</span>
        </template>
      </el-alert>
    </el-card>

    <el-card v-if="session?.lifecycle_status === 'READY'" class="execution-card" shadow="never">
      <template #header>
        <div class="card-heading">
          <strong>启动浏览器探索循环</strong>
          <span>只使用执行绑定已冻结的 Runner、运行策略与两类资源租约</span>
        </div>
      </template>
      <el-form label-position="top" @submit.prevent="startBrowserLoop">
        <el-form-item label="执行绑定 / 执行实例" required>
          <el-select
            v-model="form.execution_attempt_id"
            aria-label="执行绑定 / 执行实例"
            filterable
            style="width: 100%"
            placeholder="选择当前项目下已就绪的执行绑定"
          >
            <el-option
              v-for="binding in readyBindings"
              :key="binding.execution_binding_snapshot_id"
              :label="bindingLabel(binding.execution_attempt_id)"
              :value="binding.execution_attempt_id"
            />
          </el-select>
          <el-alert
            v-if="form.project_id && readyBindings.length === 0"
            type="warning"
            :closable="false"
            title="当前项目没有可启动的就绪执行绑定，请先在执行绑定页面完成资源选择与预检查。"
            style="margin-top: 8px"
          />
        </el-form-item>
        <el-button
          native-type="submit"
          type="primary"
          :loading="explorations.status === 'starting'"
          :disabled="!form.execution_attempt_id"
        >
          启动已绑定 Runner
        </el-button>
      </el-form>
    </el-card>

    <el-card v-if="session" class="result-card" shadow="never">
      <template #header>
        <div class="result-heading">
          <div>
            <p class="eyebrow">AI 探索执行</p>
            <strong>探索会话</strong>
          </div>
          <div class="status-actions">
            <el-tag :type="statusType">{{ statusLabel("ai", session.lifecycle_status) }}</el-tag>
            <el-button
              v-if="session.lifecycle_status === 'RUNNING'"
              type="danger"
              plain
              :loading="explorations.status === 'cancelling'"
              @click="cancelBrowserLoop"
            >
              取消探索
            </el-button>
          </div>
        </div>
      </template>

      <div class="model-snapshot" aria-label="模型运行快照">
        <span>本次实际模型</span>
        <strong>{{ session.resolved_model_display_name || "未命名模型" }}</strong>
        <code>{{ session.resolved_provider_code }} / {{ session.resolved_model_name }}</code>
      </div>

      <div v-if="session.execution_attempt_id" class="binding-snapshot">
        <span>执行资源：已绑定</span>
        <span>步骤：{{ session.current_step_sequence }} / {{ session.max_steps }}</span>
      </div>

      <el-collapse class="technical-details">
        <el-collapse-item title="技术信息 / 诊断信息" name="technical">
          <p>会话标识：<code>{{ session.session_id }}</code></p>
          <p v-if="session.execution_attempt_id">执行实例：<code>{{ session.execution_attempt_id }}</code></p>
          <p v-if="session.execution_binding_snapshot_id">执行绑定：<code>{{ session.execution_binding_snapshot_id }}</code></p>
        </el-collapse-item>
      </el-collapse>

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

      <div v-if="explorations.steps.length" class="step-evidence">
        <h3>浏览器探索步骤证据</h3>
        <ol aria-label="浏览器探索步骤证据">
          <li v-for="step in explorations.steps" :key="step.ai_exploration_step_id">
            <div class="step-sequence">{{ step.sequence }}</div>
            <div>
              <div class="step-title">
                <strong>{{ enumLabel("browserAction", step.action?.type || "DECIDING") }}</strong>
                <el-tag size="small">{{ statusLabel("aiStep", step.status) }}</el-tag>
              </div>
              <p>{{ observationSummary(step.observation) }}</p>
              <p v-if="step.sanitized_reason">{{ step.sanitized_reason }}</p>
              <code v-if="step.failure_code">{{ step.failure_code }}</code>
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
.execution-card,
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

.binding-snapshot,
.status-actions,
.step-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.binding-snapshot {
  margin-bottom: 16px;
  color: var(--el-text-color-secondary);
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

.step-evidence {
  margin-top: 24px;
}

.step-evidence ol {
  display: grid;
  gap: 10px;
  padding: 0;
  list-style: none;
}

.step-evidence li {
  display: grid;
  grid-template-columns: 36px 1fr;
  gap: 12px;
  padding: 12px;
  border-left: 3px solid var(--el-color-primary);
  background: var(--el-fill-color-light);
}

.step-evidence p {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
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
