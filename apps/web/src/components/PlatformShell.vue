<script setup lang="ts">
const releaseId = "PDBR-2026.08.06-R4.1";
</script>

<template>
  <main class="platform-shell">
    <el-card class="foundation-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>AI 自动化测试执行平台</span>
          <el-tag type="info">P0 工程底座</el-tag>
        </div>
      </template>
      <p>前端工程已启动。本页面不承载任何正式业务菜单或业务状态。</p>
      <dl>
        <dt>冻结基线</dt>
        <dd>{{ releaseId }}</dd>
        <dt>数据库运行门禁</dt>
        <dd>NOT_EXECUTED</dd>
        <dt>真实平台验收</dt>
        <dd>NOT_EXECUTED</dd>
      </dl>
    </el-card>
  </main>
</template>
