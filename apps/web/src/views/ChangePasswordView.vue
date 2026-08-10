<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { useRouter } from "vue-router";

import { getAuthenticationErrorMessage, getCorrelationId } from "../api/errors";
import type { ChangePasswordRequest } from "../generated/types";
import { useSessionStore } from "../stores/session";

type PasswordForm = ChangePasswordRequest & { confirm_password: string };

const formRef = ref<FormInstance>();
const form = reactive<PasswordForm>({
  current_password: "",
  new_password: "",
  confirm_password: "",
});
const passwordVisibility = reactive({ current: false, next: false, confirm: false });
const errorMessage = ref("");
const correlationId = ref<string>();
const session = useSessionStore();
const router = useRouter();

const rules: FormRules<PasswordForm> = {
  current_password: [
    { required: true, message: "请输入当前密码", trigger: "blur" },
    { max: 128, message: "密码不能超过 128 个字符", trigger: "blur" },
  ],
  new_password: [
    { required: true, message: "请输入新密码", trigger: "blur" },
    { min: 12, max: 128, message: "密码长度需为 12–128 个字符", trigger: "blur" },
    {
      validator: (_rule, value: string, callback) => {
        if (/^\s|\s$/.test(value)) callback(new Error("密码首尾不能包含空白"));
        else if (!/[A-Za-z]/.test(value) || !/[0-9]/.test(value))
          callback(new Error("密码必须同时包含字母和数字"));
        else if (value.toLocaleLowerCase() === session.currentUser?.username.toLocaleLowerCase())
          callback(new Error("密码不能与用户名相同"));
        else if (value === form.current_password) callback(new Error("新密码不能与当前密码相同"));
        else callback();
      },
      trigger: "blur",
    },
  ],
  confirm_password: [
    { required: true, message: "请再次输入新密码", trigger: "blur" },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.new_password) callback(new Error("两次输入的新密码不一致"));
        else callback();
      },
      trigger: "blur",
    },
  ],
};

async function submit(): Promise<void> {
  errorMessage.value = "";
  correlationId.value = undefined;
  if (!form.current_password || !form.new_password || !form.confirm_password) {
    errorMessage.value = "请完整填写密码表单。";
    void formRef.value?.validate().catch(() => undefined);
    return;
  }
  if (form.new_password !== form.confirm_password) {
    errorMessage.value = "两次输入的新密码不一致";
    return;
  }
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  try {
    await session.changePassword({
      current_password: form.current_password,
      new_password: form.new_password,
    });
    ElMessage.success("密码已更新，旧会话已安全撤销。");
    await router.replace("/");
  } catch (error) {
    errorMessage.value = getAuthenticationErrorMessage(
      error,
      "密码修改失败，请检查当前密码和新密码策略。",
    );
    correlationId.value = getCorrelationId(error);
  }
}

async function logout(): Promise<void> {
  try {
    await session.logout();
  } catch {
    // Local logout must complete even when the server cannot confirm revocation.
  } finally {
    await router.replace("/login");
  }
}
</script>

<template>
  <main class="change-password-page">
    <section class="change-password-card" aria-labelledby="change-password-title">
      <div class="brand-mark compact" aria-hidden="true">AT</div>
      <el-tag v-if="session.requiresPasswordChange" type="warning" effect="light">
        首次登录安全步骤
      </el-tag>
      <h1 id="change-password-title">修改登录密码</h1>
      <p class="muted">
        {{
          session.requiresPasswordChange
            ? "临时密码仅用于首次登录。完成改密后即可进入工作台。"
            : "修改后，其他旧会话会立即失效。"
        }}
      </p>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="form-alert"
      >
        <template v-if="correlationId" #default>
          <span class="correlation-id">请求标识：{{ correlationId }}</span>
        </template>
      </el-alert>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="submit"
      >
        <input
          class="visually-hidden"
          type="text"
          name="username"
          autocomplete="username"
          :value="session.currentUser?.username"
          tabindex="-1"
          aria-hidden="true"
        />
        <el-form-item label="当前密码" prop="current_password">
          <el-input
            v-model="form.current_password"
            aria-label="当前密码"
            autocomplete="current-password"
            maxlength="128"
            :type="passwordVisibility.current ? 'text' : 'password'"
          >
            <template #suffix>
              <button
                type="button"
                class="password-toggle"
                :aria-label="passwordVisibility.current ? '隐藏当前密码' : '显示当前密码'"
                @click="passwordVisibility.current = !passwordVisibility.current"
              >
                {{ passwordVisibility.current ? "隐藏" : "显示" }}
              </button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            aria-label="新密码"
            autocomplete="new-password"
            maxlength="128"
            :type="passwordVisibility.next ? 'text' : 'password'"
          >
            <template #suffix>
              <button
                type="button"
                class="password-toggle"
                :aria-label="passwordVisibility.next ? '隐藏新密码' : '显示新密码'"
                @click="passwordVisibility.next = !passwordVisibility.next"
              >
                {{ passwordVisibility.next ? "隐藏" : "显示" }}
              </button>
            </template>
          </el-input>
        </el-form-item>
        <p class="password-hint">12–128 个字符，至少包含一个字母和一个数字。</p>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            aria-label="确认新密码"
            autocomplete="new-password"
            maxlength="128"
            :type="passwordVisibility.confirm ? 'text' : 'password'"
            @keyup.enter="submit"
          >
            <template #suffix>
              <button
                type="button"
                class="password-toggle"
                :aria-label="passwordVisibility.confirm ? '隐藏确认密码' : '显示确认密码'"
                @click="passwordVisibility.confirm = !passwordVisibility.confirm"
              >
                {{ passwordVisibility.confirm ? "隐藏" : "显示" }}
              </button>
            </template>
          </el-input>
        </el-form-item>
        <div class="form-actions">
          <el-button
            type="primary"
            native-type="submit"
            :loading="session.status === 'changing-password'"
            :disabled="session.status === 'changing-password'"
          >
            保存新密码
          </el-button>
          <el-button :disabled="session.status !== 'idle'" @click="logout"> 退出登录 </el-button>
        </div>
      </el-form>
    </section>
  </main>
</template>
