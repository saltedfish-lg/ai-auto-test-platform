import { expect, test, type Page } from "@playwright/test";

test.setTimeout(120_000);

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required by the isolated AI exploration Gate`);
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

test("bound Browser Loop persists multi-step evidence and reaches SUCCEEDED", async ({ page }) => {
  const username = requiredEnvironment("ATP_AI_EXPLORATION_E2E_USERNAME");
  const password = requiredEnvironment("ATP_AI_EXPLORATION_E2E_PASSWORD");
  const projectId = requiredEnvironment("ATP_AI_EXPLORATION_E2E_PROJECT_ID");
  const attemptId = requiredEnvironment("ATP_AI_EXPLORATION_E2E_ATTEMPT_ID");
  const targetUrl = requiredEnvironment("ATP_AI_EXPLORATION_E2E_TARGET_URL");

  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  expect((await login(page, username, password)).status()).toBe(200);

  await page.goto(`/ai-exploration?project_id=${projectId}&execution_attempt_id=${attemptId}`);
  await expect(page.getByRole("heading", { name: "AI 浏览器探索" })).toBeVisible();
  await page.getByLabel("测试目标").fill("Reach the deterministic exploration dashboard");
  await page.getByLabel("目标页面地址").fill(targetUrl);

  const createResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/ai-exploration-sessions") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "创建并开始规划" }).click();
  expect((await createResponse).status()).toBe(201);
  await expect(page.getByText("READY", { exact: true })).toBeVisible();

  const startResponse = page.waitForResponse(
    (response) =>
      /\/api\/v1\/ai-exploration-sessions\/[^/]+\/start$/.test(new URL(response.url()).pathname) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "启动已绑定 Runner" }).click();
  expect((await startResponse).status()).toBe(202);

  await expect(page.locator(".status-actions").getByText("SUCCEEDED", { exact: true })).toBeVisible(
    {
      timeout: 25_000,
    },
  );
  await expect(page.getByRole("list", { name: "Browser Loop 步骤证据" }).locator("li")).toHaveCount(
    2,
  );
  await expect(page.getByText(/COMPLETION_PROPOSED/)).toBeVisible();
  await expect(page.getByText(targetUrl, { exact: false }).first()).toBeVisible();
});
