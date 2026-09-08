<script setup lang="ts">
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import type { ModelConfigResource, UpdateModelConfigRequest } from "../generated/types";
import { statusLabel } from "../presentation/labels";
import { useModelConfigurationsStore } from "../stores/modelConfigurations";
import { useSessionStore } from "../stores/session";

type ProviderCode = ModelConfigResource["provider_code"];
type TransitionAction =
  | "submit-review"
  | "return-to-configuring"
  | "activate"
  | "disable"
  | "recover"
  | "archive";

const configurations = useModelConfigurationsStore();
const session = useSessionStore();
const createVisible = ref(false);
const editVisible = ref(false);
const detailVisible = ref(false);
const transitionVisible = ref(false);
const transitionAction = ref<TransitionAction>("submit-review");
const transitionTarget = ref<ModelConfigResource | null>(null);
const transitionReason = ref("");
const validationMessage = ref("");

const providerOptions: Array<{ value: ProviderCode; label: string }> = [
  { value: "OPENAI", label: "OpenAI" },
  { value: "ANTHROPIC", label: "Anthropic" },
  { value: "DEEPSEEK", label: "DeepSeek" },
  { value: "QWEN", label: "Qwen" },
  { value: "DOUBAO", label: "Doubao" },
];

const createForm = reactive({
  config_code: "",
  display_name: "",
  provider_code: "OPENAI" as ProviderCode,
  model_name: "",
  secret_value: "",
  request_timeout_seconds: 30,
});

const editForm = reactive({
  display_name: "",
  provider_code: "OPENAI" as ProviderCode,
  model_name: "",
  secret_value: "",
  request_timeout_seconds: 30,
  reason: "",
});

const activeCount = computed(
  () => configurations.items.filter((item) => item.lifecycle_status === "ACTIVE").length,
);
const validatingCount = computed(
  () => configurations.items.filter((item) => item.lifecycle_status === "VALIDATING").length,
);
const defaultConfiguration = computed(
  () => configurations.items.find((item) => item.is_ai_exploration_default) ?? null,
);
const reviewOnly = computed(
  () =>
    !session.hasPermission("MODEL_CONFIGURATION_MANAGE") &&
    session.hasPermission("MODEL_VERSION_REVIEW"),
);
const connectionResult = computed(() => {
  const id = configurations.current?.model_config_id;
  return id ? configurations.connectionResults[id] : undefined;
});
const transitionTitle = computed(() => {
  const labels: Record<TransitionAction, string> = {
    "submit-review": "提交模型配置审核",
    "return-to-configuring": "退回模型配置修复",
    activate: "激活模型配置",
    disable: "禁用模型配置",
    recover: "启动模型配置恢复",
    archive: "归档模型配置",
  };
  return labels[transitionAction.value];
});

onMounted(() => {
  void configurations.loadConfigurations(reviewOnly.value).catch(() => undefined);
});

function providerLabel(code: ProviderCode): string {
  return providerOptions.find((provider) => provider.value === code)?.label ?? code;
}

function providerMark(code: ProviderCode): string {
  const marks: Record<ProviderCode, string> = {
    OPENAI: "OA",
    ANTHROPIC: "AN",
    DEEPSEEK: "DS",
    QWEN: "QW",
    DOUBAO: "DB",
  };
  return marks[code];
}

function statusTagType(
  status: ModelConfigResource["lifecycle_status"],
): "" | "success" | "warning" | "info" | "danger" {
  if (status === "ACTIVE") return "success";
  if (status === "VALIDATING") return "warning";
  if (status === "UNAVAILABLE" || status === "DEGRADED") return "danger";
  return "info";
}

function resetCreateForm(): void {
  createForm.config_code = "";
  createForm.display_name = "";
  createForm.provider_code = "OPENAI";
  createForm.model_name = "";
  createForm.secret_value = "";
  createForm.request_timeout_seconds = 30;
  validationMessage.value = "";
}

function openCreate(): void {
  resetCreateForm();
  createVisible.value = true;
}

function closeCreate(): void {
  resetCreateForm();
  createVisible.value = false;
}

async function submitCreate(): Promise<void> {
  if (!createForm.config_code.trim()) {
    validationMessage.value = "请输入配置编码。";
    return;
  }
  if (!createForm.model_name.trim()) {
    validationMessage.value = "请输入 Provider 原生模型标识。";
    return;
  }
  if (!createForm.secret_value) {
    validationMessage.value = "请输入模型 API Secret。";
    return;
  }
  validationMessage.value = "";
  try {
    const created = await configurations.createConfiguration({
      config_code: createForm.config_code.trim(),
      display_name: createForm.display_name.trim() || null,
      provider_code: createForm.provider_code,
      model_name: createForm.model_name.trim(),
      secret_value: createForm.secret_value,
      request_timeout_seconds: createForm.request_timeout_seconds,
    });
    createForm.secret_value = "";
    createVisible.value = false;
    ElMessage.success("模型配置已安全保存，当前处于配置中状态。");
    await openDetail(created);
  } catch {
    createForm.secret_value = "";
    // The store exposes a sanitized operation-specific error. The secret is always cleared.
  }
}

function openEdit(configuration: ModelConfigResource): void {
  configurations.current = configuration;
  editForm.display_name = configuration.display_name ?? "";
  editForm.provider_code = configuration.provider_code;
  editForm.model_name = configuration.model_name;
  editForm.secret_value = "";
  editForm.request_timeout_seconds = configuration.request_timeout_seconds;
  editForm.reason = "";
  validationMessage.value = "";
  editVisible.value = true;
}

function clearEditSecret(): void {
  editForm.secret_value = "";
  validationMessage.value = "";
}

function closeEdit(): void {
  clearEditSecret();
  editVisible.value = false;
}

async function submitEdit(): Promise<void> {
  const current = configurations.current;
  if (!current) return;
  const canEditSensitiveFields = current.lifecycle_status === "CONFIGURING";
  if (canEditSensitiveFields && !editForm.model_name.trim()) {
    validationMessage.value = "请输入 Provider 原生模型标识。";
    return;
  }
  validationMessage.value = "";
  try {
    const update: UpdateModelConfigRequest = {
      expected_version: current.row_version,
      display_name: editForm.display_name.trim() || null,
      reason: editForm.reason.trim() || null,
    };
    if (canEditSensitiveFields) {
      update.provider_code = editForm.provider_code;
      update.model_name = editForm.model_name.trim();
      update.request_timeout_seconds = editForm.request_timeout_seconds;
      if (editForm.secret_value) update.secret_value = editForm.secret_value;
    }
    await configurations.updateConfiguration(current.model_config_id, update);
    editForm.secret_value = "";
    editVisible.value = false;
    ElMessage.success("模型配置已保存。");
  } catch {
    editForm.secret_value = "";
    // Never retain a submitted secret after either a success or a failure.
  }
}

async function openDetail(configuration: ModelConfigResource): Promise<void> {
  detailVisible.value = true;
  await configurations
    .loadConfiguration(configuration.model_config_id, reviewOnly.value)
    .catch(() => undefined);
}

function openTransition(action: TransitionAction, configuration: ModelConfigResource): void {
  transitionAction.value = action;
  transitionTarget.value = configuration;
  transitionReason.value = "";
  validationMessage.value = "";
  transitionVisible.value = true;
}

async function submitTransition(): Promise<void> {
  const target = transitionTarget.value;
  if (!target) return;
  const auditReason = transitionReason.value.trim();
  if (!auditReason) {
    validationMessage.value = "请填写生命周期操作原因。";
    return;
  }
  validationMessage.value = "";
  try {
    if (transitionAction.value === "submit-review") {
      await configurations.submitReview(target, auditReason);
    } else if (transitionAction.value === "return-to-configuring") {
      await configurations.returnToConfiguring(target, auditReason);
    } else if (transitionAction.value === "activate") {
      await configurations.activate(target, auditReason);
    } else if (transitionAction.value === "disable") {
      await configurations.disable(target, auditReason);
    } else if (transitionAction.value === "recover") {
      await configurations.recover(target, auditReason);
    } else {
      await configurations.archive(target, auditReason);
    }
    transitionVisible.value = false;
    ElMessage.success(`${transitionTitle.value}已完成。`);
  } catch {
    // The store presents the safe error and correlation id.
  }
}

async function runConnectionTest(configuration: ModelConfigResource): Promise<void> {
  configurations.current = configuration;
  detailVisible.value = true;
  try {
    const result = await configurations.testConnection(configuration, "管理端即时连接诊断");
    if (result.status === "SUCCESS") ElMessage.success("模型连接测试成功。");
  } catch {
    // Transport/authorization failures are shown separately from structured provider results.
  }
}

async function setDefault(configuration: ModelConfigResource): Promise<void> {
  try {
    await configurations.setAiExplorationDefault(configuration);
    ElMessage.success("AI 探索默认模型已更新。");
  } catch {
    // Store error stays visible.
  }
}

async function clearDefault(configuration: ModelConfigResource): Promise<void> {
  try {
    await configurations.clearAiExplorationDefault(configuration);
    ElMessage.success("AI 探索默认模型已解除。");
  } catch {
    // Store error stays visible.
  }
}
</script>

<template>
  <section class="model-configuration-page" aria-labelledby="model-configurations-title">
    <div class="page-heading">
      <div>
        <p class="eyebrow">AI SETTINGS</p>
        <h2 id="model-configurations-title">模型配置</h2>
        <p>集中管理受审核的 Provider 凭据、模型标识和 AI 能力默认绑定。</p>
      </div>
      <el-button
        v-if="session.hasPermission('MODEL_CONFIGURATION_MANAGE')"
        type="primary"
        @click="openCreate"
      >
        新增模型配置
      </el-button>
    </div>

    <el-alert
      v-if="configurations.errorMessage"
      :title="configurations.errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="workspace-alert"
    >
      <template v-if="configurations.errorCode || configurations.correlationId" #default>
        <span v-if="configurations.errorCode">错误代码：{{ configurations.errorCode }}</span>
        <span v-if="configurations.errorCode && configurations.correlationId"> · </span>
        <span v-if="configurations.correlationId" class="correlation-id">请求标识：{{ configurations.correlationId }}</span>
      </template>
    </el-alert>

    <div class="model-summary-grid">
      <el-card class="model-summary-card" shadow="never">
        <span>配置总数</span><strong>{{ configurations.items.length }}</strong>
      </el-card>
      <el-card class="model-summary-card" shadow="never">
        <span>已激活 / 待审核</span><strong>{{ activeCount }} / {{ validatingCount }}</strong>
      </el-card>
      <el-card class="model-summary-card" shadow="never">
        <span>AI 探索默认模型</span>
        <strong>{{
          defaultConfiguration?.display_name || defaultConfiguration?.model_name || "未绑定"
        }}</strong>
      </el-card>
    </div>

    <el-card class="model-list-card" shadow="never" v-loading="configurations.status === 'loading'">
      <el-empty
        v-if="configurations.status !== 'loading' && configurations.items.length === 0"
        description="暂无模型配置"
      >
        <el-button
          v-if="session.hasPermission('MODEL_CONFIGURATION_MANAGE')"
          type="primary"
          plain
          @click="openCreate"
        >
          创建第一个模型配置
        </el-button>
      </el-empty>
      <el-table v-else :data="configurations.items" row-key="model_config_id">
        <el-table-column label="Provider / 配置" min-width="210">
          <template #default="{ row }">
            <div class="model-provider">
              <span class="provider-mark" aria-hidden="true">{{
                providerMark(row.provider_code)
              }}</span>
              <div>
                <strong>{{ providerLabel(row.provider_code) }}</strong>
                <div class="model-code monospace">{{ row.config_code }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Model" min-width="190">
          <template #default="{ row }">
            <strong>{{ row.display_name || row.model_name }}</strong>
            <div v-if="row.display_name" class="model-code monospace">{{ row.model_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.lifecycle_status)">{{ statusLabel("lifecycle", row.lifecycle_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Secret" width="110">
          <template #default="{ row }">
            <span v-if="row.secret_configured" class="secret-configured">已配置</span>
            <span v-else class="secret-empty">未配置</span>
          </template>
        </el-table-column>
        <el-table-column label="AI 探索默认" width="160">
          <template #default="{ row }">
            <el-tag v-if="row.is_ai_exploration_default" type="success">当前默认</el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="310" fixed="right">
          <template #default="{ row }">
            <div class="model-actions">
              <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
              <template v-if="session.hasPermission('MODEL_CONFIGURATION_MANAGE')">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button
                  link
                  type="primary"
                  :loading="
                    configurations.status === 'testing' &&
                    configurations.activeItemId === row.model_config_id
                  "
                  @click="runConnectionTest(row)"
                >
                  测试连接
                </el-button>
                <el-button
                  v-if="row.lifecycle_status === 'CONFIGURING'"
                  link
                  type="primary"
                  @click="openTransition('submit-review', row)"
                >
                  提交审核
                </el-button>
                <el-button
                  v-if="row.lifecycle_status === 'ACTIVE' && !row.is_ai_exploration_default"
                  link
                  type="primary"
                  :loading="
                    configurations.status === 'binding' &&
                    configurations.activeItemId === row.model_config_id
                  "
                  @click="setDefault(row)"
                >
                  设为默认
                </el-button>
                <el-button
                  v-if="row.is_ai_exploration_default"
                  link
                  type="warning"
                  :loading="
                    configurations.status === 'binding' &&
                    configurations.activeItemId === row.model_config_id
                  "
                  @click="clearDefault(row)"
                >
                  解除默认
                </el-button>
                <el-button
                  v-if="row.lifecycle_status === 'ACTIVE'"
                  link
                  type="danger"
                  :disabled="row.is_ai_exploration_default"
                  :title="
                    row.is_ai_exploration_default
                      ? '请先解除或切换 AI 探索默认模型'
                      : undefined
                  "
                  @click="openTransition('disable', row)"
                >
                  禁用
                </el-button>
                <el-button
                  v-if="row.lifecycle_status === 'DISABLED'"
                  link
                  type="primary"
                  @click="openTransition('recover', row)"
                >
                  恢复启用
                </el-button>
                <el-button
                  v-if="row.lifecycle_status === 'DISABLED'"
                  link
                  type="danger"
                  @click="openTransition('archive', row)"
                >
                  归档
                </el-button>
              </template>
              <el-button
                v-if="
                  (row.lifecycle_status === 'VALIDATING' ||
                    row.lifecycle_status === 'RECOVERING') &&
                  session.hasPermission('MODEL_VERSION_REVIEW')
                "
                link
                type="success"
                @click="openTransition('activate', row)"
              >
                审核并激活
              </el-button>
              <el-button
                v-if="
                  row.lifecycle_status === 'VALIDATING' &&
                  session.hasPermission('MODEL_VERSION_REVIEW')
                "
                link
                type="warning"
                @click="openTransition('return-to-configuring', row)"
              >
                退回修复
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="createVisible"
      title="新增模型配置"
      width="min(600px, 94vw)"
      @closed="resetCreateForm"
    >
      <el-alert
        v-if="validationMessage || configurations.errorMessage"
        :title="validationMessage || configurations.errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      />
      <p class="security-form-note">
        Provider 请求地址由平台预置，页面不接受任意 URL。保存后配置进入
        CONFIGURING，需提交并通过独立审核后才能激活。
      </p>
      <el-form label-position="top" @submit.prevent="submitCreate">
        <el-form-item label="配置编码" required>
          <el-input v-model="createForm.config_code" maxlength="191" autocomplete="off" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="createForm.display_name" maxlength="255" autocomplete="off" />
        </el-form-item>
        <el-form-item label="Provider" required>
          <el-select v-model="createForm.provider_code" style="width: 100%">
            <el-option
              v-for="provider in providerOptions"
              :key="provider.value"
              :label="provider.label"
              :value="provider.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Model" required>
          <el-input
            v-model="createForm.model_name"
            maxlength="191"
            placeholder="输入 Provider 原生模型标识"
            autocomplete="off"
          />
        </el-form-item>
        <el-form-item label="API Secret" required>
          <el-input
            v-model="createForm.secret_value"
            type="password"
            maxlength="4096"
            autocomplete="new-password"
            placeholder="Secret 仅用于本次提交，不会回显"
          />
        </el-form-item>
        <el-form-item label="请求超时（秒）">
          <el-input-number
            v-model="createForm.request_timeout_seconds"
            :min="1"
            :max="300"
            controls-position="right"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeCreate">取消</el-button>
        <el-button
          type="primary"
          :loading="configurations.status === 'creating'"
          @click="submitCreate"
        >
          安全保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editVisible"
      title="编辑模型配置"
      width="min(600px, 94vw)"
      @closed="clearEditSecret"
    >
      <el-alert
        v-if="validationMessage || configurations.errorMessage"
        :title="validationMessage || configurations.errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      />
      <p class="security-form-note">
        当前 Secret：{{ configurations.current?.secret_configured ? "已配置" : "未配置" }}。旧
        Secret 永不回填；留空表示保持不变。
      </p>
      <el-form label-position="top" @submit.prevent="submitEdit">
        <el-form-item label="配置编码">
          <el-input :model-value="configurations.current?.config_code" disabled />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="editForm.display_name" maxlength="255" autocomplete="off" />
        </el-form-item>
        <el-form-item label="Provider" required>
          <el-select
            v-model="editForm.provider_code"
            :disabled="configurations.current?.lifecycle_status !== 'CONFIGURING'"
            style="width: 100%"
          >
            <el-option
              v-for="provider in providerOptions"
              :key="provider.value"
              :label="provider.label"
              :value="provider.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Model" required>
          <el-input
            v-model="editForm.model_name"
            :disabled="configurations.current?.lifecycle_status !== 'CONFIGURING'"
            maxlength="191"
            autocomplete="off"
          />
        </el-form-item>
        <el-form-item label="重设 API Secret">
          <el-input
            v-model="editForm.secret_value"
            :disabled="configurations.current?.lifecycle_status !== 'CONFIGURING'"
            type="password"
            maxlength="4096"
            autocomplete="new-password"
            placeholder="留空保持当前 Secret"
          />
        </el-form-item>
        <el-form-item label="请求超时（秒）">
          <el-input-number
            v-model="editForm.request_timeout_seconds"
            :disabled="configurations.current?.lifecycle_status !== 'CONFIGURING'"
            :min="1"
            :max="300"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item label="变更原因">
          <el-input v-model="editForm.reason" type="textarea" maxlength="1000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeEdit">取消</el-button>
        <el-button type="primary" :loading="configurations.status === 'saving'" @click="submitEdit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="transitionVisible" :title="transitionTitle" width="min(500px, 92vw)">
      <el-alert
        v-if="validationMessage || configurations.errorMessage"
        :title="validationMessage || configurations.errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      />
      <p v-if="transitionAction === 'activate'" class="security-form-note">
        激活表示独立审核已通过；只有拥有 MODEL_VERSION_REVIEW 的身份可以执行。
      </p>
      <p v-if="transitionAction === 'disable'" class="security-form-note">
        当前 AI 探索默认模型不能直接禁用，必须先解除或切换绑定。
      </p>
      <el-form label-position="top" @submit.prevent="submitTransition">
        <el-form-item label="操作原因" required>
          <el-input v-model="transitionReason" type="textarea" maxlength="1000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transitionVisible = false">取消</el-button>
        <el-button
          :type="transitionAction === 'disable' ? 'danger' : 'primary'"
          :loading="configurations.status === 'transitioning'"
          @click="submitTransition"
        >
          确认{{ transitionTitle }}
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="模型配置详情" size="min(720px, 96vw)">
      <div v-if="configurations.current" class="model-detail-grid">
        <el-card class="model-detail-card" shadow="never">
          <template #header><strong>配置身份</strong></template>
          <dl class="identity-list">
            <dt>配置编码</dt>
            <dd class="monospace">{{ configurations.current.config_code }}</dd>
            <dt>显示名称</dt>
            <dd>{{ configurations.current.display_name || "未设置" }}</dd>
            <dt>Provider</dt>
            <dd>{{ providerLabel(configurations.current.provider_code) }}</dd>
            <dt>Model</dt>
            <dd class="monospace">{{ configurations.current.model_name }}</dd>
            <dt>生命周期</dt>
            <dd>
              <el-tag :type="statusTagType(configurations.current.lifecycle_status)">
                {{ statusLabel("lifecycle", configurations.current.lifecycle_status) }}
              </el-tag>
            </dd>
            <dt>版本</dt>
            <dd>v{{ configurations.current.row_version }}</dd>
          </dl>
        </el-card>
        <el-card class="model-detail-card" shadow="never">
          <template #header><strong>安全与能力</strong></template>
          <dl class="identity-list">
            <dt>Secret</dt>
            <dd>
              <span v-if="configurations.current.secret_configured" class="secret-configured"
                >已配置</span
              >
              <span v-else class="secret-empty">未配置</span>
            </dd>
            <dt>超时</dt>
            <dd>{{ configurations.current.request_timeout_seconds }} 秒</dd>
            <dt>AI 探索</dt>
            <dd>
              {{ configurations.current.is_ai_exploration_default ? "当前默认模型" : "未绑定" }}
            </dd>
          </dl>
          <el-button
            v-if="session.hasPermission('MODEL_CONFIGURATION_MANAGE')"
            type="primary"
            plain
            :loading="configurations.status === 'testing'"
            style="margin-top: 18px"
            @click="runConnectionTest(configurations.current)"
          >
            测试连接
          </el-button>
        </el-card>
      </div>

      <el-card v-if="connectionResult" class="connection-result model-detail-card" shadow="never">
        <template #header>
          <div class="section-heading">
            <div>
              <strong>即时连接诊断</strong>
              <p>结果不改变模型生命周期，也不会持久化为配置字段。</p>
            </div>
            <el-tag :type="connectionResult.status === 'SUCCESS' ? 'success' : 'danger'">
              {{ statusLabel("ai", connectionResult.status) }}
            </el-tag>
          </div>
        </template>
        <dl>
          <dt>Provider</dt>
          <dd>{{ providerLabel(connectionResult.provider_code) }}</dd>
          <dt>Model</dt>
          <dd class="monospace">{{ connectionResult.model_name }}</dd>
          <template v-if="connectionResult.latency_ms != null">
            <dt>耗时</dt>
            <dd>{{ connectionResult.latency_ms }} ms</dd>
          </template>
          <template v-if="connectionResult.error_code">
            <dt>错误码</dt>
            <dd class="monospace">{{ connectionResult.error_code }}</dd>
          </template>
          <template v-if="connectionResult.message">
            <dt>说明</dt>
            <dd>{{ connectionResult.message }}</dd>
          </template>
        </dl>
      </el-card>
    </el-drawer>
  </section>
</template>
