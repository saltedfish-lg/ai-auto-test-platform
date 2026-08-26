import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required by the isolated project acceptance Gate`);
  return value;
}

async function login(page: Page, username: string, password: string) {
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  const response = page.waitForResponse(
    (candidate) =>
      candidate.url().endsWith("/api/v1/auth/login") && candidate.request().method() === "POST",
  );
  await page.getByRole("button", { name: "登录" }).click();
  return response;
}

function lifecycle(page: Page) {
  return page.locator("dt", { hasText: "生命周期" }).locator("xpath=following-sibling::dd[1]");
}

test("project management browser closure", async ({ page, request }) => {
  const authorizedUsername = requiredEnvironment("ATP_PROJECT_E2E_AUTHORIZED_USERNAME");
  const authorizedPassword = requiredEnvironment("ATP_PROJECT_E2E_AUTHORIZED_PASSWORD");
  const unauthorizedUsername = requiredEnvironment("ATP_PROJECT_E2E_UNAUTHORIZED_USERNAME");
  const unauthorizedPassword = requiredEnvironment("ATP_PROJECT_E2E_UNAUTHORIZED_PASSWORD");
  const platformAdminUsername = requiredEnvironment("ATP_PROJECT_E2E_PLATFORM_ADMIN_USERNAME");
  const platformAdminPassword = requiredEnvironment("ATP_PROJECT_E2E_PLATFORM_ADMIN_PASSWORD");
  const eligibleOwnerId = requiredEnvironment("ATP_PROJECT_E2E_ELIGIBLE_OWNER_ID");
  const ineligibleOwnerId = requiredEnvironment("ATP_PROJECT_E2E_INELIGIBLE_OWNER_ID");
  const projectCode = requiredEnvironment("ATP_PROJECT_E2E_CODE");
  const initialName = "浏览器验收项目";
  const updatedName = "浏览器验收项目（已更新）";
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const expectedUnauthenticatedRestore =
      message.text().startsWith("Failed to load resource:") &&
      /\/api\/v1\/auth\/(?:refresh|me)$/.test(message.location().url) &&
      /status of 401/.test(message.text());
    if (!expectedUnauthenticatedRestore) consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  const authorizedLogin = await login(page, authorizedUsername, authorizedPassword);
  expect(authorizedLogin.status()).toBe(200);
  await expect(page).toHaveURL(/\/$/);

  await page.getByRole("link", { name: "项目管理" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await page.getByRole("button", { name: "创建项目" }).first().click();
  const createDialog = page.getByRole("dialog", { name: "创建项目" });
  await createDialog.getByLabel("项目编码").fill(projectCode);
  await createDialog.getByLabel("项目名称").fill(initialName);
  await createDialog.getByLabel("创建原因").fill("验证 LC-007 原子项目初始化");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/project") &&
      response.request().method() === "POST",
  );
  await createDialog.getByRole("button", { name: "创建并启用" }).click();
  const created = await createdResponse;
  expect(created.status()).toBe(201);
  const createdProject = (await created.json()).data;
  expect(createdProject.lifecycle_status).toBe("ACTIVE");
  const projectId = createdProject.project_id as string;

  await expect(page).toHaveURL(/\/projects\/[0-9A-Z]{26}$/);
  await expect(page.getByRole("heading", { name: initialName })).toBeVisible();
  await expect(lifecycle(page)).toContainText("ACTIVE");
  await expect(page.getByText("Owner ALL 仅限当前 project_id，不代表全平台范围。")).toBeVisible();

  await page.getByRole("button", { name: "环境管理" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/environments$`));
  await page.getByRole("button", { name: "创建环境" }).click();
  const environmentDialog = page.getByRole("dialog", { name: "创建环境" });
  const environmentCode = `ENV-${projectCode}`;
  await environmentDialog.getByLabel("环境编码").fill(environmentCode);
  await environmentDialog.getByLabel("环境名称").fill("浏览器验收环境");
  const environmentResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/environment") &&
      response.request().method() === "POST",
  );
  await environmentDialog.getByRole("button", { name: "确认创建" }).click();
  const createdEnvironmentResponse = await environmentResponse;
  expect(createdEnvironmentResponse.status()).toBe(201);
  const createdEnvironment = (await createdEnvironmentResponse.json()).data;
  expect(createdEnvironment.lifecycle_status).toBe("CONFIGURING");
  expect(createdEnvironment.environment_terminal_access_revision_id).toBeUndefined();
  const environmentId = createdEnvironment.environment_id as string;

  const directAuthorizedLogin = await request.post("/api/v1/auth/login", {
    data: { username: authorizedUsername, password: authorizedPassword },
  });
  expect(directAuthorizedLogin.status()).toBe(200);
  const directAuthorizedToken = (await directAuthorizedLogin.json()).data.access_token as string;
  const authorizedHeaders = { Authorization: `Bearer ${directAuthorizedToken}` };
  const environmentUpdateKey = `environment-update-${projectCode}`;
  const environmentUpdateBody = {
    expected_version: 1,
    display_name: "真实事务更新环境",
    reason: "验证 Environment CAS、幂等、审计与 Outbox 同事务",
  };
  const environmentUpdate = await request.patch(`/api/v1/environment/${environmentId}`, {
    headers: { ...authorizedHeaders, "Idempotency-Key": environmentUpdateKey },
    data: environmentUpdateBody,
  });
  expect(environmentUpdate.status()).toBe(200);
  expect((await environmentUpdate.json()).data.row_version).toBe(2);
  const environmentReplay = await request.patch(`/api/v1/environment/${environmentId}`, {
    headers: { ...authorizedHeaders, "Idempotency-Key": environmentUpdateKey },
    data: environmentUpdateBody,
  });
  expect(environmentReplay.status()).toBe(200);
  expect((await environmentReplay.json()).data.row_version).toBe(2);
  const environmentMismatchedReplay = await request.patch(`/api/v1/environment/${environmentId}`, {
    headers: { ...authorizedHeaders, "Idempotency-Key": environmentUpdateKey },
    data: { ...environmentUpdateBody, display_name: "不同载荷不得复用" },
  });
  expect(environmentMismatchedReplay.status()).toBe(409);
  const staleEnvironmentUpdate = await request.patch(`/api/v1/environment/${environmentId}`, {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-stale-${projectCode}` },
    data: { expected_version: 1, display_name: "陈旧版本不得覆盖" },
  });
  expect(staleEnvironmentUpdate.status()).toBe(409);
  expect((await staleEnvironmentUpdate.json()).code).toBe("ENVIRONMENT_CONCURRENCY_CONFLICT");
  const deferredTerminalBinding = await request.patch(`/api/v1/environment/${environmentId}`, {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-terminal-${projectCode}` },
    data: { expected_version: 2, environment_terminal_access_revision_id: null },
  });
  expect(deferredTerminalBinding.status()).toBe(409);
  expect((await deferredTerminalBinding.json()).code).toBe(
    "ENVIRONMENT_TERMINAL_ACCESS_BINDING_DEFERRED",
  );
  const duplicateEnvironment = await request.post("/api/v1/environment", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-duplicate-${projectCode}` },
    data: { project_id: projectId, environment_code: environmentCode },
  });
  expect(duplicateEnvironment.status()).toBe(409);
  expect((await duplicateEnvironment.json()).code).toBe("ENVIRONMENT_CODE_CONFLICT");

  const crossProject = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-cross-project-${projectCode}` },
    data: { project_code: `ENV-CROSS-${projectCode}` },
  });
  expect(crossProject.status()).toBe(201);
  const crossProjectId = (await crossProject.json()).data.project_id as string;
  const crossProjectEnvironment = await request.post("/api/v1/environment", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-cross-create-${projectCode}` },
    data: { project_id: crossProjectId, environment_code: environmentCode },
  });
  expect(crossProjectEnvironment.status()).toBe(201);
  const missingProjectEnvironment = await request.post("/api/v1/environment", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-missing-${projectCode}` },
    data: { project_id: "Z".repeat(26), environment_code: "MISSING-PROJECT" },
  });
  expect(missingProjectEnvironment.status()).toBe(404);
  expect((await missingProjectEnvironment.json()).code).toBe("ENVIRONMENT_NOT_FOUND");
  await expect(page.getByText(environmentCode, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /返回项目详情/ }).click();

  await page.getByRole("button", { name: /返回项目列表/ }).click();
  await expect(page.getByText(projectCode, { exact: true })).toBeVisible();
  const projectRow = page.getByRole("row").filter({
    has: page.getByText(projectCode, { exact: true }),
  });
  await projectRow.getByRole("button", { name: "查看详情" }).click();

  await page.getByRole("button", { name: "编辑基础信息" }).click();
  const editDialog = page.getByRole("dialog", { name: "编辑项目基础信息" });
  await editDialog.getByLabel("项目名称").fill(updatedName);
  await editDialog.getByLabel("变更原因").fill("浏览器验收允许字段更新");
  const updatedResponse = page.waitForResponse(
    (response) =>
      /\/api\/v1\/project\/[0-9A-Z]{26}$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "PATCH",
  );
  await editDialog.getByRole("button", { name: "保存" }).click();
  expect((await updatedResponse).status()).toBe(200);
  await expect(page.getByRole("heading", { name: updatedName })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: updatedName })).toBeVisible();

  async function transition(actionLabel: string, reason: string, expectedStatus: string) {
    await page.getByRole("button", { name: actionLabel }).click();
    const dialog = page.getByRole("dialog", { name: actionLabel });
    await dialog.getByLabel("操作原因").fill(reason);
    const response = page.waitForResponse(
      (candidate) =>
        candidate.request().method() === "POST" &&
        /\/api\/v1\/project\/[0-9A-Z]{26}\/(?:disable|recover|archive)$/.test(
          new URL(candidate.url()).pathname,
        ),
    );
    await dialog.getByRole("button", { name: `确认${actionLabel}` }).click();
    expect((await response).status()).toBe(200);
    await expect(lifecycle(page)).toContainText(expectedStatus);
  }

  await transition("停用项目", "浏览器验收停用", "DISABLED");
  await transition("恢复项目", "浏览器验收恢复", "ACTIVE");
  await transition("停用项目", "归档前按规则停用", "DISABLED");
  await transition("归档项目", "浏览器验收归档", "ARCHIVED");

  const retryCode = `RETRY-${projectCode}`;
  const retryKey = `retry-${projectCode}`;
  const ineligible = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": retryKey },
    data: { project_code: retryCode, owner_user_id: ineligibleOwnerId },
  });
  expect(ineligible.status()).toBe(403);
  expect((await ineligible.json()).code).toBe("PROJECT_OWNER_NOT_ELIGIBLE");

  const correctedBody = { project_code: retryCode, display_name: "失败修正后重试项目" };
  const corrected = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": retryKey },
    data: correctedBody,
  });
  expect(corrected.status()).toBe(201);
  const correctedProjectId = (await corrected.json()).data.project_id as string;
  const replay = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": retryKey },
    data: correctedBody,
  });
  expect(replay.status()).toBe(201);
  expect((await replay.json()).data.project_id).toBe(correctedProjectId);
  const mismatchedReplay = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": retryKey },
    data: { ...correctedBody, display_name: "不同载荷" },
  });
  expect(mismatchedReplay.status()).toBe(409);

  const duplicate = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `duplicate-${projectCode}` },
    data: { project_code: projectCode },
  });
  expect(duplicate.status()).toBe(409);
  expect((await duplicate.json()).code).toBe("PROJECT_CODE_CONFLICT");

  const serviceAccountCode = `SERVICE-${projectCode}`;
  const serviceAccountOwner = await request.post("/api/v1/project", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `service-${projectCode}` },
    data: { project_code: serviceAccountCode, owner_user_id: "S".repeat(26) },
  });
  expect(serviceAccountOwner.status()).toBe(403);
  expect((await serviceAccountOwner.json()).code).toBe("PROJECT_OWNER_NOT_ELIGIBLE");

  const stale = await request.patch(`/api/v1/project/${projectId}`, {
    headers: { ...authorizedHeaders, "Idempotency-Key": `stale-${projectCode}` },
    data: { expected_version: 0, display_name: "陈旧版本不得覆盖" },
  });
  expect(stale.status()).toBe(409);
  expect((await stale.json()).code).toBe("PROJECT_CONCURRENCY_CONFLICT");

  const platformAdminLogin = await request.post("/api/v1/auth/login", {
    data: { username: platformAdminUsername, password: platformAdminPassword },
  });
  expect(platformAdminLogin.status()).toBe(200);
  const platformAdminToken = (await platformAdminLogin.json()).data.access_token as string;
  const delegated = await request.post("/api/v1/project", {
    headers: {
      Authorization: `Bearer ${platformAdminToken}`,
      "Idempotency-Key": `delegated-${projectCode}`,
    },
    data: {
      project_code: `DELEGATED-${projectCode}`,
      owner_user_id: eligibleOwnerId,
      reason: "平台管理员代建并指定合格负责人",
    },
  });
  expect(delegated.status()).toBe(201);
  const delegatedProject = (await delegated.json()).data;
  expect(delegatedProject.lifecycle_status).toBe("ACTIVE");
  expect(delegatedProject.owners).toContainEqual(
    expect.objectContaining({ user_id: eligibleOwnerId, membership_status: "ACTIVE" }),
  );

  await page.getByRole("button", { name: "退出登录" }).click();
  expect((await login(page, unauthorizedUsername, unauthorizedPassword)).status()).toBe(200);
  await expect(
    page.getByText("当前身份不能创建新项目；可见项目仍由服务端实时权限与范围决定。"),
  ).toBeVisible();
  await page.getByRole("link", { name: "项目管理" }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByRole("button", { name: "创建项目" })).toHaveCount(0);
  await expect(page.getByText(projectCode, { exact: true })).toHaveCount(0);

  const apiLogin = await request.post("/api/v1/auth/login", {
    data: { username: unauthorizedUsername, password: unauthorizedPassword },
  });
  expect(apiLogin.status()).toBe(200);
  const accessToken = (await apiLogin.json()).data.access_token as string;
  const denied = await request.post("/api/v1/project", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Idempotency-Key": `deny-${projectCode}`,
    },
    data: { project_code: `DENIED-${projectCode}` },
  });
  expect(denied.status()).toBe(403);
  expect((await denied.json()).code).toBe("AUTH_PERMISSION_DENIED");

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
