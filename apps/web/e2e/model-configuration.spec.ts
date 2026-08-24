import { expect, test, type Page } from "@playwright/test";

test.setTimeout(180_000);

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
  await createDialog.getByLabel("Provider").click();
  await page.getByRole("option", { name: providerLabel, exact: true }).click();
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

  await expect(page.getByText(configCode, { exact: true })).toBeVisible();
  await expect(page.getByText("已配置", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(providerSecret, { exact: true })).toHaveCount(0);
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
  await expect(page.getByText("ACTIVE", { exact: true }).first()).toBeVisible();

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
  await expect(page.getByText(configCode, { exact: true })).toBeVisible();
  await expect(page.getByText("当前默认", { exact: true })).toBeVisible();
  await expect(page.getByText(providerSecret, { exact: true })).toHaveCount(0);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
