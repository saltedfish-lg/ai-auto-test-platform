<script setup lang="ts">
import { useRouter } from "vue-router";

import { useSessionStore } from "../stores/session";

const session = useSessionStore();
const router = useRouter();

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
          <span>项目与资源工作台</span>
        </div>
      </div>
      <nav aria-label="主导航">
        <RouterLink class="nav-item" active-class="active" :to="{ name: 'platform-home' }">
          <span aria-hidden="true">◫</span>
          身份工作台
        </RouterLink>
        <RouterLink
          v-if="session.hasPermission('PROJECT_VIEW')"
          class="nav-item"
          active-class="active"
          :to="{ name: 'projects.list' }"
        >
          <span aria-hidden="true">▦</span>
          项目管理
        </RouterLink>
      </nav>
      <div class="sidebar-foot">权限与项目范围由服务端实时校验</div>
    </aside>

    <main class="workspace-main">
      <header class="workspace-header">
        <div>
          <p class="eyebrow">PLATFORM WORKSPACE</p>
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

      <RouterView />
    </main>
  </div>
</template>
