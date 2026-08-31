import { expect, test, type Page } from "@playwright/test";

test.setTimeout(180_000);

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
  const runnerAdminUsername = requiredEnvironment("ATP_PROJECT_E2E_RUNNER_ADMIN_USERNAME");
  const runnerAdminPassword = requiredEnvironment("ATP_PROJECT_E2E_RUNNER_ADMIN_PASSWORD");
  const runnerProjectId = requiredEnvironment("ATP_PROJECT_E2E_RUNNER_PROJECT_ID");
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
      response.url().endsWith("/api/v1/project") && response.request().method() === "POST",
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

  const directAuthorizedLogin = await request.post("/api/v1/auth/login", {
    data: { username: authorizedUsername, password: authorizedPassword },
  });
  expect(directAuthorizedLogin.status()).toBe(200);
  const directAuthorizedToken = (await directAuthorizedLogin.json()).data.access_token as string;
  const authorizedHeaders = { Authorization: `Bearer ${directAuthorizedToken}` };

  const directRunnerAdminLogin = await request.post("/api/v1/auth/login", {
    data: { username: runnerAdminUsername, password: runnerAdminPassword },
  });
  expect(directRunnerAdminLogin.status()).toBe(200);
  const directRunnerAdminToken = (await directRunnerAdminLogin.json()).data.access_token as string;
  const runnerAdminHeaders = { Authorization: `Bearer ${directRunnerAdminToken}` };

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  const runnerAdminLogin = await login(page, runnerAdminUsername, runnerAdminPassword);
  expect(runnerAdminLogin.status()).toBe(200);
  await page.goto(`/projects/${runnerProjectId}/runners`);
  await expect(page).toHaveURL(new RegExp(`/projects/${runnerProjectId}/runners$`));
  await page.getByRole("button", { name: "创建 Enrollment" }).click();
  const enrollmentDialog = page.getByRole("dialog", {
    name: "创建 Project-scoped Enrollment",
  });
  const runnerCode = `RUNNER-${projectCode}`;
  await enrollmentDialog.getByLabel("Runner Code").fill(runnerCode);
  await enrollmentDialog.getByLabel("显示名称").fill("浏览器验收 Runner");
  await enrollmentDialog.getByLabel("原因").fill("验证 project-scoped 一次性 enrollment");
  const enrollmentResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/runner-enrollments") &&
      response.request().method() === "POST",
  );
  await enrollmentDialog.getByRole("button", { name: "创建" }).click();
  const issuedEnrollmentResponse = await enrollmentResponse;
  expect(issuedEnrollmentResponse.status()).toBe(201);
  const issuedEnrollment = (await issuedEnrollmentResponse.json()).data;
  const enrollmentCredential = issuedEnrollment.enrollment_credential as string;
  expect(issuedEnrollment.project_id).toBe(runnerProjectId);
  expect(issuedEnrollment.runner_code).toBe(runnerCode);
  const enrollmentCredentialDialog = page.getByRole("dialog", {
    name: "一次性 Enrollment Credential",
  });
  await expect(enrollmentCredentialDialog.locator("textarea")).toHaveValue(
    enrollmentCredential,
  );
  await expect(page.getByText(/平台无法恢复明文/)).toBeVisible();
  await page.getByRole("button", { name: "我已安全保存" }).click();

  const registeredResponse = await request.post("/api/v1/runners/register", {
    headers: { "Idempotency-Key": `runner-register-${projectCode}` },
    data: {
      enrollment_credential: enrollmentCredential,
      machine_fingerprint: `machine-${projectCode}`,
      agent_version: "1.0.0-e2e",
      runtime_metadata: { os: "Windows", architecture: "x86_64" },
      capabilities: [
        {
          capability_code: "AGENT_VERSION",
          availability_status: "CONFIGURED",
          observed_version: "1.0.0-e2e",
          observed_metadata: null,
        },
      ],
    },
  });
  expect(registeredResponse.status()).toBe(201);
  const registered = (await registeredResponse.json()).data;
  const runnerId = registered.runner.runner_id as string;
  const firstAgentToken = registered.agent_token as string;
  expect(registered.runner.project_id).toBe(runnerProjectId);
  expect(registered.runner.project_binding_status).toBe("BOUND");
  expect(registered.runner.lifecycle_status).toBe("REGISTERED");
  expect(registered.runner.enable_status).toBe("DISABLED");

  const consumedEnrollment = await request.post("/api/v1/runners/register", {
    headers: { "Idempotency-Key": `runner-register-replay-${projectCode}` },
    data: {
      enrollment_credential: enrollmentCredential,
      machine_fingerprint: `machine-${projectCode}`,
      agent_version: "1.0.0-e2e",
      runtime_metadata: null,
      capabilities: [],
    },
  });
  expect(consumedEnrollment.status()).toBe(401);
  expect((await consumedEnrollment.json()).code).toBe("RUNNER_AGENT_UNAUTHENTICATED");

  const firstHeartbeat = await request.post(`/api/v1/runners/${runnerId}/heartbeat`, {
    headers: { "X-Runner-Agent-Token": firstAgentToken },
    data: {
      health_status: "HEALTHY",
      agent_version: "1.0.0-e2e",
      runtime_metadata: { os: "Windows", architecture: "x86_64" },
      capabilities: null,
    },
  });
  expect(firstHeartbeat.status()).toBe(200);
  const heartbeatRunner = (await firstHeartbeat.json()).data;
  expect(heartbeatRunner.connection_status).toBe("ONLINE");
  expect(heartbeatRunner.health_status).toBe("HEALTHY");
  expect(heartbeatRunner.lifecycle_status).toBe("REGISTERED");
  expect(heartbeatRunner.enable_status).toBe("DISABLED");

  const capabilityResponse = await request.post(`/api/v1/runners/${runnerId}/capabilities`, {
    headers: { "X-Runner-Agent-Token": firstAgentToken },
    data: {
      capabilities: [
        {
          capability_code: "AGENT_VERSION",
          availability_status: "CONFIGURED",
          observed_version: "1.0.0-e2e",
          observed_metadata: null,
        },
        {
          capability_code: "BROWSER_CHROMIUM",
          availability_status: "CONFIGURED",
          observed_version: "143",
          observed_metadata: { channel: "chromium" },
        },
        {
          capability_code: "CONTEXT_ISOLATION",
          availability_status: "CONFIGURED",
          observed_version: null,
          observed_metadata: null,
        },
      ],
    },
  });
  expect(capabilityResponse.status()).toBe(200);
  const capabilityRunner = (await capabilityResponse.json()).data;
  expect(capabilityRunner.capabilities).toHaveLength(3);

  await page.reload();
  const runnerRow = page.getByRole("row").filter({
    has: page.getByText(runnerCode, { exact: true }),
  });
  await expect(runnerRow).toContainText("ONLINE / HEALTHY");
  await expect(runnerRow).toContainText("BROWSER_CHROMIUM");
  await expect(runnerRow).toContainText("CONTEXT_ISOLATION");

  const rotatedResponse = await request.post(`/api/v1/runner/${runnerId}/agent-token/rotate`, {
    headers: {
      ...runnerAdminHeaders,
      "Idempotency-Key": `runner-token-rotate-${projectCode}`,
    },
    data: {
      expected_version: capabilityRunner.row_version,
      reason: "验证 opaque Agent token rotate",
    },
  });
  expect(rotatedResponse.status()).toBe(200);
  const rotated = (await rotatedResponse.json()).data;
  const rotatedAgentToken = rotated.agent_token as string;
  expect(rotatedAgentToken).not.toBe(firstAgentToken);
  expect(rotated.token_version).toBe(2);

  const oldTokenHeartbeat = await request.post(`/api/v1/runners/${runnerId}/heartbeat`, {
    headers: { "X-Runner-Agent-Token": firstAgentToken },
    data: {
      health_status: "HEALTHY",
      agent_version: "1.0.0-e2e",
      runtime_metadata: null,
      capabilities: null,
    },
  });
  expect(oldTokenHeartbeat.status()).toBe(401);

  const rotatedTokenHeartbeat = await request.post(`/api/v1/runners/${runnerId}/heartbeat`, {
    headers: { "X-Runner-Agent-Token": rotatedAgentToken },
    data: {
      health_status: "HEALTHY",
      agent_version: "1.0.0-e2e",
      runtime_metadata: null,
      capabilities: null,
    },
  });
  expect(rotatedTokenHeartbeat.status()).toBe(200);
  const rotatedHeartbeatRunner = (await rotatedTokenHeartbeat.json()).data;

  const revokedResponse = await request.post(`/api/v1/runner/${runnerId}/agent-token/revoke`, {
    headers: {
      ...runnerAdminHeaders,
      "Idempotency-Key": `runner-token-revoke-${projectCode}`,
    },
    data: {
      expected_version: rotatedHeartbeatRunner.row_version,
      reason: "验证 opaque Agent token revoke",
    },
  });
  expect(revokedResponse.status()).toBe(200);
  expect((await revokedResponse.json()).data.registration_status).toBe("REGISTERED");
  const revokedTokenHeartbeat = await request.post(`/api/v1/runners/${runnerId}/heartbeat`, {
    headers: { "X-Runner-Agent-Token": rotatedAgentToken },
    data: {
      health_status: "HEALTHY",
      agent_version: "1.0.0-e2e",
      runtime_metadata: null,
      capabilities: null,
    },
  });
  expect(revokedTokenHeartbeat.status()).toBe(401);
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  const restoredAuthorizedLogin = await login(page, authorizedUsername, authorizedPassword);
  expect(restoredAuthorizedLogin.status()).toBe(200);
  await page.goto(`/projects/${projectId}`);

  await page.getByRole("button", { name: "环境管理" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/environments$`));
  await page.getByRole("button", { name: "创建环境" }).click();
  const environmentDialog = page.getByRole("dialog", { name: "创建环境" });
  const environmentCode = `ENV-${projectCode}`;
  await environmentDialog.getByLabel("环境编码").fill(environmentCode);
  await environmentDialog.getByLabel("环境名称").fill("浏览器验收环境");
  const environmentResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/environment") && response.request().method() === "POST",
  );
  await environmentDialog.getByRole("button", { name: "确认创建" }).click();
  const createdEnvironmentResponse = await environmentResponse;
  expect(createdEnvironmentResponse.status()).toBe(201);
  const createdEnvironment = (await createdEnvironmentResponse.json()).data;
  expect(createdEnvironment.lifecycle_status).toBe("CONFIGURING");
  expect(createdEnvironment.environment_terminal_access_revision_id).toBeUndefined();
  const environmentId = createdEnvironment.environment_id as string;

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
  const duplicateEnvironment = await request.post("/api/v1/environment", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `environment-duplicate-${projectCode}` },
    data: { project_id: projectId, environment_code: environmentCode },
  });
  expect(duplicateEnvironment.status()).toBe(409);
  expect((await duplicateEnvironment.json()).code).toBe("ENVIRONMENT_CODE_CONFLICT");

  const crossProject = await request.post("/api/v1/project", {
    headers: {
      ...authorizedHeaders,
      "Idempotency-Key": `environment-cross-project-${projectCode}`,
    },
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

  const automationAsset = await request.post("/api/v1/automation-asset", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `automation-asset-${projectCode}` },
    data: { project_id: projectId, display_name: "浏览器验收自动化资产" },
  });
  expect(automationAsset.status()).toBe(201);
  const automationAssetId = (await automationAsset.json()).data.automation_asset_id as string;
  const loginStrategy = await request.post("/api/v1/login-strategy", {
    headers: { ...authorizedHeaders, "Idempotency-Key": `login-strategy-${projectCode}` },
    data: {
      project_id: projectId,
      automation_asset_id: automationAssetId,
      display_name: "浏览器登录策略",
      local_storage_presets: [
        { key: "locale", value: "zh-CN", scope: "ORIGIN", set_before_login: true },
      ],
      refresh_after_local_storage: true,
      captcha_policy: "NONE",
      reason: "通过 AutomationAsset Aggregate 创建登录策略",
    },
  });
  expect(loginStrategy.status()).toBe(201);
  const createdStrategyData = (await loginStrategy.json()).data;
  expect(createdStrategyData.lifecycle_status).toBe("CREATED");
  const draftedStrategy = await request.patch(
    `/api/v1/login-strategy/${createdStrategyData.login_strategy_id}`,
    {
      headers: { ...authorizedHeaders, "Idempotency-Key": `login-draft-${projectCode}` },
      data: {
        expected_version: createdStrategyData.row_version,
        display_name: "浏览器登录策略",
        reason: "通过 AutomationAsset Aggregate 进入 DRAFT",
      },
    },
  );
  expect(draftedStrategy.status()).toBe(200);
  const strategyData = (await draftedStrategy.json()).data;
  expect(strategyData.lifecycle_status).toBe("DRAFT");
  const strategyActivated = await request.post(
    `/api/v1/login-strategy/${strategyData.login_strategy_id}/activate`,
    {
      headers: { ...authorizedHeaders, "Idempotency-Key": `login-activate-${projectCode}` },
      data: { expected_version: strategyData.row_version, reason: "启用聚合内登录策略" },
    },
  );
  expect(strategyActivated.status()).toBe(200);

  await page.getByRole("button", { name: "业务终端" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/business-terminals$`));
  await page.getByRole("button", { name: "创建业务终端" }).click();
  const terminalDialog = page.getByRole("dialog", { name: "创建业务终端" });
  await terminalDialog
    .locator(".el-form-item", { hasText: "Environment" })
    .locator(".el-select__wrapper")
    .click();
  await page.getByRole("option", { name: "真实事务更新环境" }).click();
  const terminalCode = `ADMIN-${projectCode}`;
  await terminalDialog.getByLabel("终端编码").fill(terminalCode);
  await terminalDialog.getByLabel("终端名称").fill("浏览器验收管理端");
  await terminalDialog.getByLabel("原因").fill("验证 Terminal 与初始 DRAFT 分开创建");
  const terminalResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/business-terminal") &&
      response.request().method() === "POST",
  );
  await terminalDialog.getByRole("button", { name: "确认创建" }).click();
  const createdTerminalResponse = await terminalResponse;
  expect(createdTerminalResponse.status()).toBe(201);
  const createdTerminal = (await createdTerminalResponse.json()).data;
  const terminalId = createdTerminal.business_terminal_id as string;
  expect(createdTerminal.current_published_revision_id).toBeNull();
  await expect(page.getByText(terminalCode, { exact: true })).toBeVisible();

  const terminalRow = page.getByRole("row").filter({
    has: page.getByText(terminalCode, { exact: true }),
  });
  await terminalRow.getByRole("button", { name: "详情" }).click();

  await page.getByRole("button", { name: "新建访问修订" }).click();
  const revisionDialog = page.getByRole("dialog", { name: "新建 DRAFT 访问修订" });
  await revisionDialog.getByLabel("入口 URL").fill("https://example.test/app");
  await revisionDialog.getByLabel("登录 URL").fill("https://example.test/login");
  await revisionDialog
    .locator(".el-form-item", { hasText: "Login Strategy" })
    .locator(".el-select__wrapper")
    .click();
  await page.getByRole("option", { name: "浏览器登录策略" }).click();
  await revisionDialog.getByLabel("名称").fill("浏览器访问修订 1");
  await revisionDialog.getByLabel("原因").fill("验证独立 DRAFT 创建");
  const revisionCreated = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/environment-terminal-access-revision") &&
      response.request().method() === "POST",
  );
  await revisionDialog.getByRole("button", { name: "创建 DRAFT" }).click();
  const createdRevisionResponse = await revisionCreated;
  expect(createdRevisionResponse.status()).toBe(201);
  const createdRevision = (await createdRevisionResponse.json()).data;
  const revisionId = createdRevision.environment_terminal_access_revision_id as string;
  expect(createdRevision.lifecycle_status).toBe("DRAFT");

  const revisionRow = page.getByRole("row").filter({
    has: page.getByText("https://example.test/app", { exact: false }),
  });
  const revisionValidated = page.waitForResponse((response) =>
    response.url().endsWith(`/${revisionId}/validate`),
  );
  await revisionRow.getByRole("button", { name: "校验" }).click();
  expect((await revisionValidated).status()).toBe(200);
  const revisionPublished = page.waitForResponse((response) =>
    response.url().endsWith(`/${revisionId}/publish`),
  );
  await revisionRow.getByRole("button", { name: "发布" }).click();
  expect((await revisionPublished).status()).toBe(200);
  const terminalRead = await request.get(`/api/v1/business-terminal/${terminalId}`, {
    headers: authorizedHeaders,
  });
  expect(terminalRead.status()).toBe(200);
  expect((await terminalRead.json()).data.current_published_revision_id).toBe(revisionId);
  await page.getByRole("dialog", { name: "业务终端详情" }).locator(".el-dialog__headerbtn").click();
  await page.getByRole("button", { name: /返回项目详情/ }).click();

  await page.getByRole("button", { name: "测试账号" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/test-accounts$`));
  await page.getByRole("button", { name: "新建测试账号" }).click();
  const accountDialog = page.getByRole("dialog", { name: "新建测试账号" });
  await accountDialog
    .locator(".el-form-item", { hasText: "环境" })
    .locator(".el-select__wrapper")
    .click();
  await page.getByRole("option", { name: "真实事务更新环境" }).click();
  await accountDialog.getByLabel("账号标识").fill(`qa-${projectCode}`);
  await accountDialog.getByLabel("显示名称").fill("浏览器验收测试账号");
  await accountDialog
    .locator(".el-form-item", { hasText: "适用业务终端" })
    .locator(".el-select__wrapper")
    .click();
  await page.getByRole("option", { name: /浏览器验收管理端 \/ MANAGEMENT/ }).click();
  const initialAccountSecret = `initial-test-account-${projectCode}`;
  await accountDialog.getByLabel("登录凭据").fill(initialAccountSecret);
  await accountDialog.getByLabel("创建原因").fill("验证 TestAccount 加密与范围闭环");
  const accountCreated = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/test-account") && response.request().method() === "POST",
  );
  await accountDialog.getByRole("button", { name: "创建" }).click();
  const accountCreatedResponse = await accountCreated;
  const accountCreatedPayload = await accountCreatedResponse.json();
  expect(
    accountCreatedResponse.status(),
    JSON.stringify({
      code: accountCreatedPayload.code,
      title: accountCreatedPayload.title,
      detail: accountCreatedPayload.detail,
    }),
  ).toBe(201);
  expect(JSON.stringify(accountCreatedPayload)).not.toContain(initialAccountSecret);
  expect(accountCreatedPayload.data).not.toHaveProperty("secret_value");
  const accountId = accountCreatedPayload.data.test_account_id as string;
  await expect(page.getByText(`qa-${projectCode}`, { exact: true })).toBeVisible();
  expect(await page.locator("body").textContent()).not.toContain(initialAccountSecret);

  let accountRow = page.getByRole("row").filter({
    has: page.getByText(`qa-${projectCode}`, { exact: true }),
  });
  await accountRow.getByRole("button", { name: "编辑" }).click();
  const accountEditDialog = page.getByRole("dialog", { name: "编辑测试账号" });
  await accountEditDialog.getByLabel("显示名称").fill("浏览器验收测试账号（已更新）");
  await accountEditDialog.getByLabel("修改原因").fill("验证非敏感字段独立修改");
  const accountUpdated = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/test-account/${accountId}`) &&
      response.request().method() === "PATCH",
  );
  await accountEditDialog.getByRole("button", { name: "保存" }).click();
  expect((await accountUpdated).status()).toBe(200);
  await expect(page.getByText("浏览器验收测试账号（已更新）", { exact: true })).toBeVisible();

  accountRow = page.getByRole("row").filter({
    has: page.getByText(`qa-${projectCode}`, { exact: true }),
  });
  await accountRow.getByRole("button", { name: "更新凭据" }).click();
  const secretDialog = page.getByRole("dialog", { name: "更新登录凭据" });
  const rotatedAccountSecret = `rotated-test-account-${projectCode}`;
  const secretInput = secretDialog.getByLabel("新凭据");
  await secretInput.fill(rotatedAccountSecret);
  await secretDialog.getByLabel("轮换原因").fill("验证独立 Secret rotate command");
  const secretRotated = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/test-account/${accountId}/credential-rotate`) &&
      response.request().method() === "POST",
  );
  await secretDialog.getByRole("button", { name: "安全更新" }).click();
  const secretRotatedResponse = await secretRotated;
  expect(secretRotatedResponse.status()).toBe(200);
  expect(JSON.stringify(await secretRotatedResponse.json())).not.toContain(rotatedAccountSecret);
  await expect(secretInput).toHaveValue("");
  expect(await page.locator("body").textContent()).not.toContain(rotatedAccountSecret);

  accountRow = page.getByRole("row").filter({
    has: page.getByText(`qa-${projectCode}`, { exact: true }),
  });
  await accountRow.getByRole("button", { name: "状态操作" }).click();
  await page.getByText("提交校验", { exact: true }).click();
  const lifecycleDialog = page.getByRole("dialog", { name: "提交校验" });
  await lifecycleDialog.getByLabel("操作原因").fill("验证 LC-013 显式生命周期命令");
  const accountValidated = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/test-account/${accountId}/validate`) &&
      response.request().method() === "POST",
  );
  await lifecycleDialog.getByRole("button", { name: "确认" }).click();
  expect((await accountValidated).status()).toBe(200);
  await expect(accountRow.getByText("VALIDATING", { exact: true })).toBeVisible();
  const accountRead = await request.get(`/api/v1/test-account/${accountId}`, {
    headers: authorizedHeaders,
  });
  expect(accountRead.status()).toBe(200);
  const accountReadText = await accountRead.text();
  expect(accountReadText).not.toContain(initialAccountSecret);
  expect(accountReadText).not.toContain(rotatedAccountSecret);
  expect(accountReadText).not.toContain("secret_value");
  await page.getByRole("button", { name: /返回项目详情/ }).click();

  const projectListLoaded = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/project" &&
      response.request().method() === "GET",
  );
  await page.getByRole("button", { name: /返回项目列表/ }).click();
  const projectListResponse = await projectListLoaded;
  expect(projectListResponse.status()).toBe(200);
  expect((await projectListResponse.json()).items).toEqual(
    expect.arrayContaining([expect.objectContaining({ project_code: projectCode })]),
  );
  await expect(page.getByText(projectCode, { exact: true })).toBeVisible({ timeout: 10_000 });
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
