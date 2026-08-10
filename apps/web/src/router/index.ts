import { createRouter, createWebHistory, type Router, type RouterHistory } from "vue-router";

import PlatformShell from "../components/PlatformShell.vue";
import { useSessionStore } from "../stores/session";
import ChangePasswordView from "../views/ChangePasswordView.vue";
import LoginView from "../views/LoginView.vue";

export function createPlatformRouter(history: RouterHistory = createWebHistory()): Router {
  const platformRouter = createRouter({
    history,
    routes: [
      {
        path: "/login",
        name: "login",
        component: LoginView,
      },
      {
        path: "/change-password",
        name: "change-password",
        component: ChangePasswordView,
        meta: { requiresAuth: true, allowForcedPasswordChange: true },
      },
      {
        path: "/",
        name: "platform-home",
        component: PlatformShell,
        meta: { requiresAuth: true },
      },
      { path: "/:pathMatch(.*)*", redirect: "/" },
    ],
  });

  platformRouter.beforeEach(async (to) => {
    const session = useSessionStore();
    session.setAuthenticationLostHandler(() => {
      if (platformRouter.currentRoute.value.name !== "login") {
        void platformRouter.replace({ name: "login" });
      }
    });
    await session.restoreSession();

    if (to.meta.requiresAuth && !session.isAuthenticated) {
      return {
        name: "login",
        query: { redirect: to.fullPath },
      };
    }
    if (session.isAuthenticated && to.name === "login") {
      return { name: session.requiresPasswordChange ? "change-password" : "platform-home" };
    }
    if (
      session.isAuthenticated &&
      session.requiresPasswordChange &&
      !to.meta.allowForcedPasswordChange
    ) {
      return { name: "change-password" };
    }
    return true;
  });

  return platformRouter;
}

export const router = createPlatformRouter();
