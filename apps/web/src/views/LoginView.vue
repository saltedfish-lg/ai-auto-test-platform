<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";

import { getAuthenticationErrorMessage, getCorrelationId } from "../api/errors";
import type { LoginRequest } from "../generated/types";
import { useSessionStore } from "../stores/session";

const formRef = ref<FormInstance>();
const form = reactive<LoginRequest>({ username: "", password: "" });
const passwordVisible = ref(false);
const errorMessage = ref("");
const correlationId = ref<string>();
const session = useSessionStore();
const router = useRouter();
const route = useRoute();

const rules: FormRules<LoginRequest> = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { max: 191, message: "用户名不能超过 191 个字符", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { max: 128, message: "密码不能超过 128 个字符", trigger: "blur" },
  ],
};

function safeRedirect(): string {
  const redirect = route.query.redirect;
  return typeof redirect === "string" && redirect.startsWith("/") && !redirect.startsWith("//")
    ? redirect
    : "/";
}

async function submit(): Promise<void> {
  errorMessage.value = "";
  correlationId.value = undefined;
  if (!form.username || !form.password) {
    errorMessage.value = "请输入用户名和密码。";
    void formRef.value?.validate().catch(() => undefined);
    return;
  }
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  try {
    await session.login({ username: form.username, password: form.password });
    await router.replace(session.requiresPasswordChange ? "/change-password" : safeRedirect());
  } catch (error) {
    errorMessage.value = getAuthenticationErrorMessage(error, "登录请求失败，请稍后重试。");
    correlationId.value = getCorrelationId(error);
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-hero" aria-label="平台介绍">
      <div class="brand-mark" aria-hidden="true">AT</div>
      <p class="eyebrow">AI AUTOMATED TESTING</p>
      <h2>AI 自动化测试执行平台</h2>
      <p class="hero-copy">以统一身份与实时权限，安全进入测试工程工作台。</p>
      <ul class="hero-points">
        <li>受控会话与实时 RBAC</li>
        <li>全链路关联标识</li>
        <li>企业级安全基线</li>
      </ul>
    </section>

    <section class="auth-panel" aria-labelledby="login-title">
      <div class="auth-card">
        <p class="eyebrow">WELCOME BACK</p>
        <h1 id="login-title">登录平台</h1>
        <p class="muted">使用管理员为你创建的平台账号登录。</p>

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
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              aria-label="用户名"
              autocomplete="username"
              maxlength="191"
              placeholder="请输入用户名"
              size="large"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              aria-label="密码"
              autocomplete="current-password"
              maxlength="128"
              placeholder="请输入密码"
              size="large"
              :type="passwordVisible ? 'text' : 'password'"
              @keyup.enter="submit"
            >
              <template #suffix>
                <button
                  type="button"
                  class="password-toggle"
                  :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
                  @click="passwordVisible = !passwordVisible"
                >
                  {{ passwordVisible ? "隐藏" : "显示" }}
                </button>
              </template>
            </el-input>
          </el-form-item>
          <el-button
            class="auth-submit"
            type="primary"
            size="large"
            native-type="submit"
            :loading="session.status === 'authenticating'"
            :disabled="session.status === 'authenticating'"
          >
            登录
          </el-button>
        </el-form>
        <p class="security-note">Refresh 凭证仅由安全的 HttpOnly Cookie 承载。</p>
      </div>
    </section>
  </main>
</template>
