import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required by the isolated authentication browser Gate`);
  return value;
}

async function submitLogin(page: Page, username: string, password: string) {
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  const response = page.waitForResponse(
    (candidate) =>
      candidate.url().endsWith("/api/v1/auth/login") && candidate.request().method() === "POST",
  );
  await page.getByRole("button", { name: "登录" }).click();
  return response;
}

test("authentication browser closure", async ({ page, context }) => {
  const initialPassword = requiredEnvironment("ATP_AUTH_E2E_ADMIN_INITIAL_PASSWORD");
  const changedPassword = requiredEnvironment("ATP_AUTH_E2E_ADMIN_CHANGED_PASSWORD");
  const normalUsername = requiredEnvironment("ATP_AUTH_E2E_NORMAL_USERNAME");
  const normalPassword = requiredEnvironment("ATP_AUTH_E2E_NORMAL_PASSWORD");
  const disabledUsername = requiredEnvironment("ATP_AUTH_E2E_DISABLED_USERNAME");
  const disabledPassword = requiredEnvironment("ATP_AUTH_E2E_DISABLED_PASSWORD");
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const requestFailureChecks: Promise<string | null>[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const location = message.location().url;
    const expectedNegativeAuthResponse =
      message.text().startsWith("Failed to load resource:") &&
      ((/\/api\/v1\/auth\/(?:login|refresh|me)$/.test(location) &&
        /status of (?:401|403)/.test(message.text())) ||
        (/\/api\/v1\/auth\/logout$/.test(location) && /status of 500/.test(message.text())));
    if (!expectedNegativeAuthResponse) consoleErrors.push(`${location}: ${message.text()}`);
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    requestFailureChecks.push(
      (async () => {
        const response = await request.response();
        const expectedEmptyLogoutResponse =
          request.url().endsWith("/api/v1/auth/logout") &&
          response?.status() === 204 &&
          request.failure()?.errorText === "net::ERR_ABORTED";
        return expectedEmptyLogoutResponse
          ? null
          : `${request.url()}: ${request.failure()?.errorText ?? "unknown failure"}`;
      })(),
    );
  });

  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  await expect(page.getByRole("heading", { name: "登录平台" })).toBeVisible();

  const adminLogin = await submitLogin(page, "admin", initialPassword);
  expect(adminLogin.status()).toBe(200);
  await expect(page).toHaveURL(/\/change-password$/);
  await page.evaluate(() => {
    window.history.pushState(null, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page).toHaveURL(/\/change-password$/);
  await expect(page.getByRole("heading", { name: "修改登录密码" })).toBeVisible();

  await page.getByLabel("当前密码", { exact: true }).fill(initialPassword);
  await page.getByLabel("新密码", { exact: true }).fill(changedPassword);
  await page.getByLabel("确认新密码", { exact: true }).fill(changedPassword);
  let refreshRequestsAfterPasswordSubmit = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/auth/refresh")) refreshRequestsAfterPasswordSubmit += 1;
  });
  const changePasswordResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/auth/change-password") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "保存新密码" }).click();
  const changed = await changePasswordResponse;
  expect(changed.status()).toBe(204);
  expect(await changed.body()).toHaveLength(0);
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "登录平台" })).toBeVisible();
  expect(refreshRequestsAfterPasswordSubmit).toBe(0);

  const changedPasswordLogin = await submitLogin(page, "admin", changedPassword);
  expect(changedPasswordLogin.status()).toBe(200);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /欢迎回来/ })).toBeVisible();
  await expect(page.getByText("ROLE-SUPER-ADMIN", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /欢迎回来/ })).toBeVisible();

  let simulatedExpiry = false;
  let refreshRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/auth/refresh")) refreshRequests += 1;
  });
  await page.route("**/api/v1/auth/me", async (route) => {
    if (!simulatedExpiry) {
      simulatedExpiry = true;
      await route.fulfill({
        status: 401,
        contentType: "application/problem+json",
        body: JSON.stringify({
          type: "about:blank",
          title: "Expired access token",
          status: 401,
          code: "AUTH_TOKEN_EXPIRED",
          detail: "The access token has expired.",
          correlation_id: "browser-expiry-probe",
        }),
      });
      return;
    }
    await route.continue();
  });
  const refreshesBeforeProbe = refreshRequests;
  const refreshResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/auth/refresh") && response.status() === 200,
  );
  const recoveredIdentityResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/auth/me") && response.status() === 200,
  );
  await page.getByRole("button", { name: "刷新身份" }).click();
  await Promise.all([refreshResponse, recoveredIdentityResponse]);
  await expect.poll(() => refreshRequests).toBeGreaterThan(refreshesBeforeProbe);
  await expect(page.getByText("ROLE-SUPER-ADMIN", { exact: true })).toBeVisible();
  await page.unroute("**/api/v1/auth/me");

  const refreshCookie = (await context.cookies()).find((cookie) => cookie.name === "atp_refresh");
  expect(refreshCookie).toBeDefined();
  expect(refreshCookie?.httpOnly).toBe(true);
  expect(refreshCookie?.sameSite).toBe("Strict");
  expect(refreshCookie?.path).toBe("/api/v1/auth");
  expect(refreshCookie?.secure).toBe(false);
  const browserStorage = await page.evaluate(async () => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
    indexed: (await indexedDB.databases()).map((database) => database.name),
    readableCookie: document.cookie,
  }));
  expect(browserStorage.local).toEqual([]);
  expect(browserStorage.session).toEqual([]);
  expect(browserStorage.indexed).toEqual([]);
  expect(browserStorage.readableCookie).not.toContain("atp_refresh");
  await page.screenshot({ path: "test-results/auth-workspace.png", fullPage: true });

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);

  const normalLogin = await submitLogin(page, normalUsername, normalPassword);
  expect(normalLogin.status()).toBe(200);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("当前身份未获得用户创建权限。")).toBeVisible();

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "about:blank",
        title: "Expired access token",
        status: 401,
        code: "AUTH_TOKEN_EXPIRED",
        detail: "The access token has expired.",
        correlation_id: "browser-terminal-expiry",
      }),
    });
  });
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "about:blank",
        title: "Session revoked",
        status: 401,
        code: "AUTH_SESSION_REVOKED",
        detail: "The Refresh session is no longer valid.",
        correlation_id: "browser-terminal-refresh",
      }),
    });
  });
  await page.getByRole("button", { name: "刷新身份" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.unroute("**/api/v1/auth/me");
  await page.unroute("**/api/v1/auth/refresh");

  const normalRelogin = await submitLogin(page, normalUsername, normalPassword);
  expect(normalRelogin.status()).toBe(200);
  await expect(page).toHaveURL(/\/$/);
  await page.route("**/api/v1/auth/logout", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "about:blank",
        title: "Synthetic logout failure",
        status: 500,
        code: "INTERNAL_ERROR",
        correlation_id: "browser-logout-failure",
      }),
    });
  });
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.unroute("**/api/v1/auth/logout");

  const disabledLogin = await submitLogin(page, disabledUsername, disabledPassword);
  expect(disabledLogin.status()).toBe(403);
  await expect(page.getByText("账号已停用，请联系管理员。")).toBeVisible();

  const missingLogin = await submitLogin(page, `missing-${Date.now()}`, `Missing-${Date.now()}-9`);
  expect(missingLogin.status()).toBe(401);
  await expect(page.getByText("用户名或密码不正确。")).toBeVisible();

  const wrongPassword = `Wrong-${Date.now()}-9`;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const failedLogin = await submitLogin(page, "admin", wrongPassword);
    expect(failedLogin.status()).toBe(401);
    await expect(page.getByText("用户名或密码不正确。")).toBeVisible();
  }
  const lockedLogin = await submitLogin(page, "admin", changedPassword);
  expect(lockedLogin.status()).toBe(403);
  await expect(page.getByText(/账号已被临时锁定/)).toBeVisible();

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  const requestFailures = (await Promise.all(requestFailureChecks)).filter(
    (failure): failure is string => failure !== null,
  );
  expect(requestFailures).toEqual([]);
});
