<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { getAuthenticationErrorMessage, getCorrelationId } from "../api/errors";
import PermissionGate from "./PermissionGate.vue";
import { useSessionStore } from "../stores/session";

const session = useSessionStore();
const router = useRouter();
const errorMessage = ref("");
const correlationId = ref<string>();

async function reloadIdentity(): Promise<void> {
  errorMessage.value = "";
  correlationId.value = undefined;
  try {
    await session.loadCurrentUser();
  } catch (error) {
    errorMessage.value = getAuthenticationErrorMessage(error, "当前用户信息刷新失败，请稍后重试。");
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
  <div class="workspace-shell">
    <aside class="workspace-sidebar">
      <div class="sidebar-brand">
        <div class="brand-mark compact" aria-hidden="true">AT</div>
        <div>
          <strong>AI 测试平台</strong>
          <span>R4.2 · P1</span>
        </div>
      </div>
      <nav aria-label="主导航">
        <a class="nav-item active" href="#identity">
          <span aria-hidden="true">◫</span>
          身份工作台
        </a>
      </nav>
      <div class="sidebar-foot">权限由服务端实时校验</div>
    </aside>

    <main class="workspace-main">
      <header class="workspace-header">
        <div>
          <p class="eyebrow">IDENTITY WORKSPACE</p>
          <h1>
            欢迎回来，{{ session.currentUser?.display_name || session.currentUser?.username }}
          </h1>
        </div>
        <div class="header-actions">
          <el-button plain @click="router.push('/change-password')">修改密码</el-button>
          <el-button :loading="session.status === 'logging-out'" @click="logout">
            退出登录
          </el-button>
        </div>
      </header>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="workspace-alert"
      >
        <template v-if="correlationId" #default>
          <span class="correlation-id">请求标识：{{ correlationId }}</span>
        </template>
      </el-alert>

      <section id="identity" class="workspace-grid" aria-label="当前身份概览">
        <el-card class="identity-card" shadow="never">
          <template #header>
            <div class="section-heading">
              <div>
                <h2>当前身份</h2>
                <p>来自认证服务的实时用户信息</p>
              </div>
              <el-button
                text
                type="primary"
                :loading="session.status === 'loading-user'"
                @click="reloadIdentity"
              >
                刷新身份
              </el-button>
            </div>
          </template>
          <dl class="identity-list">
            <dt>用户名</dt>
            <dd>{{ session.currentUser?.username }}</dd>
            <dt>显示名称</dt>
            <dd>{{ session.currentUser?.display_name || "未设置" }}</dd>
            <dt>账号状态</dt>
            <dd>
              <el-tag type="success">{{ session.currentUser?.lifecycle_status }}</el-tag>
            </dd>
            <dt>用户标识</dt>
            <dd class="monospace">{{ session.currentUser?.user_id }}</dd>
          </dl>
        </el-card>

        <el-card class="security-card" shadow="never">
          <template #header>
            <div class="section-heading">
              <div>
                <h2>会话安全</h2>
                <p>Access Token 仅保存在本页运行时内存</p>
              </div>
              <el-tag type="success" effect="plain">已保护</el-tag>
            </div>
          </template>
          <div class="security-status">
            <span class="status-dot" aria-hidden="true"></span>
            <div>
              <strong>当前会话有效</strong>
              <p>Refresh Session 由 HttpOnly Cookie 承载并按服务端策略轮换。</p>
            </div>
          </div>
        </el-card>

        <el-card class="authorization-card" shadow="never">
          <template #header>
            <div class="section-heading">
              <div>
                <h2>角色与实时权限</h2>
                <p>权限显示仅用于体验，服务端授权始终是安全边界</p>
              </div>
              <el-tag type="info">{{ session.currentUser?.permissions.length ?? 0 }} 项</el-tag>
            </div>
          </template>
          <div class="authorization-columns">
            <div>
              <h3>角色</h3>
              <div class="tag-list">
                <el-tag v-for="role in session.currentUser?.roles" :key="role" effect="dark">
                  {{ role }}
                </el-tag>
                <span v-if="!session.currentUser?.roles.length" class="empty-copy">暂无角色</span>
              </div>
            </div>
            <div>
              <h3>权限</h3>
              <div class="permission-list">
                <code v-for="permission in session.currentUser?.permissions" :key="permission">
                  {{ permission }}
                </code>
                <span v-if="!session.currentUser?.permissions.length" class="empty-copy">
                  暂无权限
                </span>
              </div>
            </div>
          </div>

          <PermissionGate permission="USER_CREATE">
            <el-alert
              title="当前身份具备用户创建权限；用户治理功能将在对应正式模块实现。"
              type="success"
              :closable="false"
              show-icon
              class="permission-notice"
            />
            <template #fallback>
              <el-alert
                title="当前身份未获得用户创建权限。"
                type="info"
                :closable="false"
                show-icon
                class="permission-notice"
              />
            </template>
          </PermissionGate>
        </el-card>
      </section>
    </main>
  </div>
</template>
