import { createRouter, createWebHistory } from "vue-router";

import PlatformShell from "../components/PlatformShell.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "platform-foundation",
      component: PlatformShell,
    },
  ],
});
