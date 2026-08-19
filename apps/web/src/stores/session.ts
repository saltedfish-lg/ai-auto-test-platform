import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";

import { apiClient, bindAuthTransport } from "../api/client";
import { useProjectsStore } from "./projects";
import type {
  AuthenticationResponse,
  ChangePasswordRequest,
  CurrentUserResource,
  LoginRequest,
} from "../generated/types";

export type SessionStatus =
  | "idle"
  | "restoring"
  | "authenticating"
  | "loading-user"
  | "changing-password"
  | "logging-out";

export const useSessionStore = defineStore("session", () => {
  const accessToken = shallowRef<string | null>(null);
  const currentUser = ref<CurrentUserResource | null>(null);
  const status = ref<SessionStatus>("idle");
  const initialized = ref(false);
  let refreshPromise: Promise<void> | undefined;
  let authenticationLostHandler: (() => void) | undefined;

  const isAuthenticated = computed(() => accessToken.value !== null && currentUser.value !== null);
  const requiresPasswordChange = computed(() => currentUser.value?.force_password_change === true);

  function acceptAuthentication(response: AuthenticationResponse): void {
    if (currentUser.value?.user_id !== response.data.current_user.user_id) {
      useProjectsStore().clearProjects();
    }
    accessToken.value = response.data.access_token;
    currentUser.value = response.data.current_user;
  }

  function clearSession(): void {
    useProjectsStore().clearProjects();
    accessToken.value = null;
    currentUser.value = null;
  }

  async function refreshAccessToken(): Promise<void> {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      const response = await apiClient.refresh_platform_session();
      acceptAuthentication(response);
    })();
    try {
      await refreshPromise;
    } finally {
      refreshPromise = undefined;
    }
  }

  bindAuthTransport({
    getAccessToken: () => accessToken.value,
    refreshAccessToken,
    onAuthenticationLost: () => {
      clearSession();
      initialized.value = true;
      authenticationLostHandler?.();
    },
  });

  function setAuthenticationLostHandler(handler: () => void): void {
    authenticationLostHandler = handler;
  }

  async function restoreSession(): Promise<boolean> {
    if (initialized.value) return isAuthenticated.value;
    status.value = "restoring";
    try {
      await refreshAccessToken();
      return true;
    } catch {
      clearSession();
      return false;
    } finally {
      initialized.value = true;
      status.value = "idle";
    }
  }

  async function login(credentials: LoginRequest): Promise<void> {
    status.value = "authenticating";
    try {
      const response = await apiClient.login_platform_user(credentials);
      acceptAuthentication(response);
      initialized.value = true;
    } finally {
      status.value = "idle";
    }
  }

  async function loadCurrentUser(): Promise<void> {
    status.value = "loading-user";
    try {
      const response = await apiClient.get_current_user();
      currentUser.value = response.data;
    } finally {
      status.value = "idle";
    }
  }

  async function changePassword(
    request: ChangePasswordRequest,
    idempotencyKey: string,
  ): Promise<void> {
    status.value = "changing-password";
    try {
      await apiClient.change_current_user_password(request, {
        headers: { "Idempotency-Key": idempotencyKey },
      });
      clearSession();
      initialized.value = true;
    } finally {
      status.value = "idle";
    }
  }

  async function logout(): Promise<void> {
    status.value = "logging-out";
    try {
      await apiClient.logout_platform_user();
    } finally {
      clearSession();
      initialized.value = true;
      status.value = "idle";
    }
  }

  function hasPermission(permission: string): boolean {
    return currentUser.value?.permissions.includes(permission) ?? false;
  }

  return {
    accessToken,
    currentUser,
    status,
    initialized,
    isAuthenticated,
    requiresPasswordChange,
    restoreSession,
    login,
    loadCurrentUser,
    changePassword,
    logout,
    clearSession,
    setAuthenticationLostHandler,
    hasPermission,
  };
});
