import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { useSessionStore } from "../stores/session";
import { authenticationResponse, currentUser, currentUserResponse } from "./auth-fixtures";

describe("Pinia 会话（组件/状态层测试）", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("logs in and out without writing Access Token to Web Storage", async () => {
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(authenticationResponse());
    vi.spyOn(apiClient, "logout_platform_user").mockResolvedValue(undefined);
    const session = useSessionStore();

    await session.login({ username: "admin", password: "input-only" });
    expect(session.isAuthenticated).toBe(true);
    expect(session.currentUser?.username).toBe("admin");
    expect(storageWrite).not.toHaveBeenCalled();

    await session.logout();
    expect(session.isAuthenticated).toBe(false);
    expect(session.accessToken).toBeNull();
    expect(storageWrite).not.toHaveBeenCalled();
  });

  it("restores a browser session with one shared refresh request", async () => {
    let resolveRefresh: ((value: ReturnType<typeof authenticationResponse>) => void) | undefined;
    const refreshResult = new Promise<ReturnType<typeof authenticationResponse>>((resolve) => {
      resolveRefresh = resolve;
    });
    const refresh = vi.spyOn(apiClient, "refresh_platform_session").mockReturnValue(refreshResult);
    const session = useSessionStore();

    const first = session.restoreSession();
    const second = session.restoreSession();
    resolveRefresh?.(authenticationResponse());

    await expect(first).resolves.toBe(true);
    await expect(second).resolves.toBe(true);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(session.isAuthenticated).toBe(true);
  });

  it("reloads current user roles and permissions from the formal me response", async () => {
    const session = useSessionStore();
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(authenticationResponse());
    await session.login({ username: "admin", password: "input-only" });
    vi.spyOn(apiClient, "get_current_user").mockResolvedValue(
      currentUserResponse(
        currentUser({
          permissions: ["PROJECT_VIEW"],
          display_name: "更新后的名称",
        }),
      ),
    );

    await session.loadCurrentUser();
    expect(session.currentUser?.display_name).toBe("更新后的名称");
    expect(session.hasPermission("USER_CREATE")).toBe(false);
  });

  it("clears only the in-memory session after a terminal password-change 204", async () => {
    vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(authenticationResponse());
    const change = vi.spyOn(apiClient, "change_current_user_password").mockResolvedValue(undefined);
    const refresh = vi.spyOn(apiClient, "refresh_platform_session");
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    const session = useSessionStore();
    await session.login({ username: "admin", password: "input-only" });

    await session.changePassword(
      { current_password: "input-only", new_password: "NewSecurePassword123" },
      "password-change-terminal",
    );

    expect(change).toHaveBeenCalledWith(
      { current_password: "input-only", new_password: "NewSecurePassword123" },
      { headers: { "Idempotency-Key": "password-change-terminal" } },
    );
    expect(session.accessToken).toBeNull();
    expect(session.currentUser).toBeNull();
    expect(session.initialized).toBe(true);
    expect(refresh).not.toHaveBeenCalled();
    expect(storageWrite).not.toHaveBeenCalled();
  });
});
