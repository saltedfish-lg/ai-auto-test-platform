<script setup lang="ts">
import { useSessionStore } from "../stores/session";

const props = defineProps<{ permission: string }>();
const session = useSessionStore();
</script>

<template>
  <slot v-if="session.hasPermission(props.permission)" />
  <slot v-else name="fallback" />
</template>
