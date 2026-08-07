<script setup lang="ts">
const releaseId = "PDBR-2026.08.07-R4.2";
</script>

<template>
  <main class="platform-shell">
    <el-card class="foundation-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>AI 自动化测试执行平台</span>
          <el-tag type="info">P1 实施准备</el-tag>
        </div>
      </template>
      <p>R4.2 认证契约已冻结，当前页面仅用于确认工程与当前编码基线已同步；P1 正式业务页面尚未实现。</p>
      <dl>
        <dt>冻结基线</dt>
        <dd>{{ releaseId }}</dd>
        <dt>数据库运行门禁</dt>
        <dd>PASS（R4.2 基线证据）</dd>
        <dt>真实平台验收</dt>
        <dd>NOT_COMPLETED</dd>
      </dl>
    </el-card>
  </main>
</template>
