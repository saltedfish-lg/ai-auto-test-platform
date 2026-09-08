import { expect, test, type Locator, type Page } from "@playwright/test";

test.setTimeout(180_000);
test.describe.configure({ mode: "serial" });

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required by the isolated model configuration Gate`);
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

async function logout(page: Page): Promise<void> {
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
}

async function expectSecretNotRendered(page: Page, secret: string): Promise<void> {
  const rendered = await page.evaluate(
    (expected) => document.body.innerText.includes(expected),
    secret,
  );
  expect(rendered, "provider secret must never be rendered").toBe(false);
}

async function selectProvider(page: Page, dialog: Locator, providerLabel: string) {
  const providerSelect = dialog.getByLabel("Provider");
  await providerSelect.focus();
  await providerSelect.press("ArrowDown");
  await page.getByRole("option", { name: providerLabel, exact: true }).click();
}

test("AI model configuration browser closure", async ({ page }) => {
  const managerUsername = requiredEnvironment("ATP_MODEL_E2E_MANAGER_USERNAME");
  const managerPassword = requiredEnvironment("ATP_MODEL_E2E_MANAGER_PASSWORD");
  const reviewerUsername = requiredEnvironment("ATP_MODEL_E2E_REVIEWER_USERNAME");
  const reviewerPassword = requiredEnvironment("ATP_MODEL_E2E_REVIEWER_PASSWORD");
  const configCode = requiredEnvironment("ATP_MODEL_E2E_CONFIG_CODE");
  const providerCode = requiredEnvironment("ATP_MODEL_E2E_PROVIDER").toUpperCase();
  const modelName = requiredEnvironment("ATP_MODEL_E2E_MODEL_NAME");
  const providerSecret = requiredEnvironment("ATP_MODEL_E2E_SECRET");
  const providerLabels: Record<string, string> = {
    OPENAI: "OpenAI",
    ANTHROPIC: "Anthropic",
    DEEPSEEK: "DeepSeek",
    QWEN: "Qwen",
    DOUBAO: "Doubao",
  };
  const providerLabel = providerLabels[providerCode];
  if (!providerLabel) throw new Error("ATP_MODEL_E2E_PROVIDER must be a governed provider code");

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
  expect((await login(page, managerUsername, managerPassword)).status()).toBe(200);
  await page.getByRole("link", { name: "模型配置" }).click();
  await expect(page).toHaveURL(/\/ai-settings\/model-configurations$/);

  await page.getByRole("button", { name: "新增模型配置" }).first().click();
  const createDialog = page.getByRole("dialog", { name: "新增模型配置" });
  await createDialog.getByLabel("配置编码").fill(configCode);
  await createDialog.getByLabel("显示名称").fill("浏览器验收模型");
  await selectProvider(page, createDialog, providerLabel);

  await createDialog.getByLabel("Model", { exact: true }).fill(modelName);
  await createDialog.getByLabel("API Secret", { exact: true }).fill(providerSecret);
  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/model-config") && response.request().method() === "POST",
  );
  await createDialog.getByRole("button", { name: "安全保存" }).click();
  const created = await createResponse;
  expect(created.status()).toBe(201);
  const modelConfigId = (await created.json()).data.model_config_id as string;

  await expect(page.locator("tbody").getByText(configCode, { exact: true })).toBeVisible();
  await expect(page.getByText("已配置", { exact: true }).first()).toBeVisible();
  await expectSecretNotRendered(page, providerSecret);
  await expect(page.getByRole("heading", { name: "模型配置详情" })).toBeVisible();
  await expect(page.getByText("当前 Secret：")).toHaveCount(0);

  const connectionResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname ===
        `/api/v1/model-config/${modelConfigId}/connection-test` &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "测试连接" }).last().click();
  const connection = await connectionResponse;
  expect(connection.status()).toBe(200);
  expect((await connection.json()).data.status).toBe("SUCCESS");
  await expect(page.getByText("SUCCESS", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");

  const submitReviewResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === `/api/v1/model-config/${modelConfigId}/submit-review` &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "提交审核" }).click();
  await page
    .getByRole("dialog", { name: "提交模型配置审核" })
    .getByLabel("操作原因")
    .fill("浏览器验收提交独立审核");
  await page.getByRole("button", { name: "确认提交模型配置审核" }).click();
  expect((await submitReviewResponse).status()).toBe(200);
  await expect(page.getByText("VALIDATING", { exact: true }).first()).toBeVisible();

  await logout(page);
  expect((await login(page, reviewerUsername, reviewerPassword)).status()).toBe(200);
  await page.getByRole("link", { name: "模型配置" }).click();
  const activateResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === `/api/v1/model-config/${modelConfigId}/activate` &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "审核并激活" }).click();
  await page
    .getByRole("dialog", { name: "激活模型配置" })
    .getByLabel("操作原因")
    .fill("独立审核通过");
  await page.getByRole("button", { name: "确认激活模型配置" }).click();
  expect((await activateResponse).status()).toBe(200);
  await expect(page.getByText("已启用", { exact: true }).first()).toBeVisible();

  await logout(page);
  expect((await login(page, managerUsername, managerPassword)).status()).toBe(200);
  await page.getByRole("link", { name: "模型配置" }).click();
  const bindResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/model-capability-default/AI_EXPLORATION" &&
      response.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "设为默认" }).click();
  expect((await bindResponse).status()).toBe(200);
  await expect(page.getByText("当前默认", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.locator("tbody").getByText(configCode, { exact: true })).toBeVisible();
  await expect(page.getByText("当前默认", { exact: true })).toBeVisible();
  await expectSecretNotRendered(page, providerSecret);
  expect(consoleErrors.length, "browser console must have no unexpected errors").toBe(0);
  expect(pageErrors.length, "browser page must have no runtime errors").toBe(0);
});

test("SUPER_ADMIN model configuration self-approval", async ({ page }) => {
  const username = requiredEnvironment("ATP_MODEL_E2E_SUPER_ADMIN_USERNAME");
  const password = requiredEnvironment("ATP_MODEL_E2E_SUPER_ADMIN_PASSWORD");
  const configCode = requiredEnvironment("ATP_MODEL_E2E_SUPER_CONFIG_CODE");
  const providerCode = requiredEnvironment("ATP_MODEL_E2E_PROVIDER").toUpperCase();
  const modelName = requiredEnvironment("ATP_MODEL_E2E_MODEL_NAME");
  const providerSecret = requiredEnvironment("ATP_MODEL_E2E_SECRET");
  const providerLabels: Record<string, string> = {
    OPENAI: "OpenAI",
    ANTHROPIC: "Anthropic",
    DEEPSEEK: "DeepSeek",
    QWEN: "Qwen",
    DOUBAO: "Doubao",
  };
  const providerLabel = providerLabels[providerCode];
  if (!providerLabel) throw new Error("ATP_MODEL_E2E_PROVIDER must be a governed provider code");

  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  expect((await login(page, username, password)).status()).toBe(200);
  await page.getByRole("link", { name: "模型配置" }).click();
  await expect(page).toHaveURL(/\/ai-settings\/model-configurations$/);

  await page.getByRole("button", { name: "新增模型配置" }).first().click();
  const createDialog = page.getByRole("dialog", { name: "新增模型配置" });
  await createDialog.getByLabel("配置编码").fill(configCode);
  await createDialog.getByLabel("显示名称").fill("超级管理员自审模型");
  await selectProvider(page, createDialog, providerLabel);

  await createDialog.getByLabel("Model", { exact: true }).fill(modelName);
  await createDialog.getByLabel("API Secret", { exact: true }).fill(providerSecret);
  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/model-config") && response.request().method() === "POST",
  );
  await createDialog.getByRole("button", { name: "安全保存" }).click();
  const created = await createResponse;
  expect(created.status()).toBe(201);
  const modelConfigId = (await created.json()).data.model_config_id as string;
  await expect(page.locator("tbody").getByText(configCode, { exact: true })).toBeVisible();
  await expectSecretNotRendered(page, providerSecret);

  const connectionResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname ===
        `/api/v1/model-config/${modelConfigId}/connection-test` &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "测试连接" }).last().click();
  const connection = await connectionResponse;
  expect(connection.status()).toBe(200);
  expect((await connection.json()).data.status).toBe("SUCCESS");
  await page.keyboard.press("Escape");

  const submitResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === `/api/v1/model-config/${modelConfigId}/submit-review` &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "提交审核" }).click();
  await page
    .getByRole("dialog", { name: "提交模型配置审核" })
    .getByLabel("操作原因")
    .fill("超级管理员提交自审");
  await page.getByRole("button", { name: "确认提交模型配置审核" }).click();
  expect((await submitResponse).status()).toBe(200);
  await expect(page.getByText("VALIDATING", { exact: true }).first()).toBeVisible();

  const activateResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === `/api/v1/model-config/${modelConfigId}/activate` &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "审核并激活" }).click();
  await page
    .getByRole("dialog", { name: "激活模型配置" })
    .getByLabel("操作原因")
    .fill("超级管理员自审通过");
  await page.getByRole("button", { name: "确认激活模型配置" }).click();
  expect((await activateResponse).status()).toBe(200);
  await expect(page.getByText("已启用", { exact: true }).first()).toBeVisible();
  await expectSecretNotRendered(page, providerSecret);
});

test("AI exploration planning through browser/API/gateway/MySQL", async ({ page }) => {
  const username = requiredEnvironment("ATP_MODEL_E2E_SUPER_ADMIN_USERNAME");
  const password = requiredEnvironment("ATP_MODEL_E2E_SUPER_ADMIN_PASSWORD");
  const projectId = requiredEnvironment("ATP_MODEL_E2E_EXPLORATION_PROJECT_ID");

  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  expect((await login(page, username, password)).status()).toBe(200);
  await page.goto(`/ai-exploration?project_id=${projectId}`);
  await expect(page).toHaveURL(/\/ai-exploration\?project_id=/);
  await page.getByLabel("测试目标").fill("验证合成用户能够进入合成工作台");
  await page.getByLabel("目标页面地址").fill("https://example.test/login");
  const planningResponse = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/v1/ai-exploration-sessions" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "创建并开始规划" }).click();
  const planning = await planningResponse;

  expect(planning.status()).toBe(201);
  const payload = await planning.json();
  expect(payload.data.lifecycle_status).toBe("READY");
  expect(payload.data.ai_task_id).toBeTruthy();
  expect(payload.data.plan.steps).toHaveLength(1);
  await expect(page.getByText("就绪", { exact: true })).toBeVisible();
  await expect(page.getByText("验证合成用户能够进入合成工作台", { exact: true })).toBeVisible();
  await expect(page.getByText("Open the synthetic login page", { exact: true })).toBeVisible();
  await expect(page.getByText("OPENAI / browser-runtime-model", { exact: true })).toBeVisible();
});
