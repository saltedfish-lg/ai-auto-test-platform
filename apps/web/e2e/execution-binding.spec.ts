import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import type { ExecutionBindingSnapshotResource } from "../src/generated/types";

test.setTimeout(120_000);

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required by the isolated execution binding Gate`);
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

function commandBody(binding: ExecutionBindingSnapshotResource) {
  return {
    owner_execution_identity: binding.owner_execution_identity,
    expected_version: binding.row_version,
    identity_lease_generation: binding.identity_lease.fencing_generation,
    runner_lease_generation: binding.runner_lease.fencing_generation,
    reason: "real browser fenced lease acceptance",
  };
}

async function createBinding(
  request: APIRequestContext,
  headers: Record<string, string>,
  payload: Record<string, unknown>,
  key: string,
) {
  return request.post("/api/v1/execution-binding-snapshots", {
    headers: { ...headers, "Idempotency-Key": key },
    data: payload,
  });
}

test("execution binding and fenced lease browser closure", async ({ page, request }) => {
  const username = requiredEnvironment("ATP_BINDING_E2E_USERNAME");
  const password = requiredEnvironment("ATP_BINDING_E2E_PASSWORD");
  const projectId = requiredEnvironment("ATP_BINDING_E2E_PROJECT_ID");
  const environmentId = requiredEnvironment("ATP_BINDING_E2E_ENVIRONMENT_ID");
  const terminalId = requiredEnvironment("ATP_BINDING_E2E_TERMINAL_ID");
  const terminalRevisionId = requiredEnvironment("ATP_BINDING_E2E_TERMINAL_REVISION_ID");
  const accountId = requiredEnvironment("ATP_BINDING_E2E_ACCOUNT_ID");
  const credentialRevisionId = requiredEnvironment("ATP_BINDING_E2E_CREDENTIAL_REVISION_ID");
  const runnerId = requiredEnvironment("ATP_BINDING_E2E_RUNNER_ID");
  const policyId = requiredEnvironment("ATP_BINDING_E2E_POLICY_ID");
  const attemptIds = requiredEnvironment("ATP_BINDING_E2E_ATTEMPT_IDS").split(",");
  const resourceIdentity = requiredEnvironment("ATP_BINDING_E2E_RESOURCE_IDENTITY");
  const ownerIdentity = requiredEnvironment("ATP_BINDING_E2E_OWNER_IDENTITY");
  expect(attemptIds).toHaveLength(4);

  await page.goto("/");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
  expect((await login(page, username, password)).status()).toBe(200);
  await page.goto(`/projects/${projectId}/execution-bindings`);
  await expect(page.getByRole("heading", { name: "执行绑定" })).toBeVisible();
  await page.getByRole("button", { name: "新建执行绑定" }).click();
  const dialog = page.getByRole("dialog", { name: "新建 ExecutionBindingSnapshot" });
  await dialog.getByLabel("ExecutionAttempt ID").fill(attemptIds[0]);
  await dialog.getByLabel("Environment ID").fill(environmentId);
  await dialog.getByLabel("BusinessTerminal ID").fill(terminalId);
  await dialog.getByLabel("TestAccount ID").fill(accountId);
  await dialog.getByLabel("Runner ID").fill(runnerId);
  await dialog
    .locator(".el-form-item", { hasText: "RuntimePolicy Revision" })
    .locator(".el-select__wrapper")
    .click();
  await page.getByRole("option", { name: /Revision 1 · CHROMIUM/ }).click();
  await dialog.getByLabel("Runner Resource Identity").fill(resourceIdentity);
  await dialog.getByLabel("Owner Execution Identity").fill(ownerIdentity);
  const preflightResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/execution-binding-snapshots/preflight") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "执行 Preflight" }).click();
  const preflight = await preflightResponse;
  expect(preflight.status()).toBe(200);
  const preflightPayload = await preflight.json();
  expect(preflightPayload.data.ready, JSON.stringify(preflightPayload.data.checks)).toBe(true);
  await expect(dialog.getByText("Preflight：PASS")).toBeVisible();

  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/execution-binding-snapshots") &&
      response.request().method() === "POST",
  );
  await dialog.getByRole("button", { name: "原子创建" }).click();
  const createdHttp = await createdResponse;
  expect(createdHttp.status()).toBe(201);
  const first = (await createdHttp.json()).data as ExecutionBindingSnapshotResource;
  expect(first).toMatchObject({
    execution_attempt_id: attemptIds[0],
    project_id: projectId,
    environment_id: environmentId,
    business_terminal_id: terminalId,
    terminal_access_revision_id: terminalRevisionId,
    test_account_id: accountId,
    credential_revision_id: credentialRevisionId,
    runner_id: runnerId,
    status: "READY",
  });
  expect(first.runtime_policy.runtime_policy_revision_id).toBe(policyId);
  expect(first.identity_lease).toMatchObject({ status: "ACTIVE", fencing_generation: 1 });
  expect(first.runner_lease).toMatchObject({ status: "ACTIVE", fencing_generation: 1 });
  await expect(page.getByText(`generation ${first.identity_lease.fencing_generation}`)).toHaveCount(
    2,
  );
  expect(await page.locator("body").textContent()).not.toContain(password);

  const directLogin = await request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(directLogin.status()).toBe(200);
  const token = (await directLogin.json()).data.access_token as string;
  const headers = { Authorization: `Bearer ${token}` };
  const basePayload = {
    project_id: projectId,
    environment_id: environmentId,
    business_terminal_id: terminalId,
    test_account_id: accountId,
    runner_id: runnerId,
    runtime_policy_revision_id: policyId,
    runner_resource_type: "FORMAL_EXECUTION_SLOT",
    runner_resource_identity: resourceIdentity,
    owner_execution_identity: ownerIdentity,
    required_capabilities: [],
  };

  const rejectedCompetition = await createBinding(
    request,
    headers,
    { ...basePayload, execution_attempt_id: attemptIds[1] },
    "binding-competition-rejected",
  );
  expect(rejectedCompetition.status()).toBe(409);
  expect((await rejectedCompetition.json()).code).toBe("EXECUTION_BINDING_PREFLIGHT_FAILED");

  const renewResponse = await request.post(
    `/api/v1/execution-binding-snapshots/${first.execution_binding_snapshot_id}/leases/renew`,
    {
      headers: { ...headers, "Idempotency-Key": "binding-renew" },
      data: commandBody(first),
    },
  );
  expect(renewResponse.status()).toBe(200);
  const renewed = (await renewResponse.json()).data as ExecutionBindingSnapshotResource;
  expect(renewed.identity_lease.fencing_generation).toBe(1);
  expect(renewed.runner_lease.fencing_generation).toBe(1);
  expect(new Date(renewed.identity_lease.expires_at).getTime()).toBeGreaterThan(
    new Date(first.identity_lease.expires_at).getTime(),
  );

  const releaseBody = commandBody(renewed);
  const releaseUrl = `/api/v1/execution-binding-snapshots/${first.execution_binding_snapshot_id}/release`;
  const releasedResponse = await request.post(releaseUrl, {
    headers: { ...headers, "Idempotency-Key": "binding-release" },
    data: releaseBody,
  });
  expect(releasedResponse.status()).toBe(200);
  const released = (await releasedResponse.json()).data as ExecutionBindingSnapshotResource;
  expect(released.status).toBe("RELEASED");
  expect(released.identity_lease.status).toBe("RELEASED");
  expect(released.runner_lease.status).toBe("RELEASED");
  const replayedRelease = await request.post(releaseUrl, {
    headers: { ...headers, "Idempotency-Key": "binding-release" },
    data: releaseBody,
  });
  expect(replayedRelease.status()).toBe(200);
  expect((await replayedRelease.json()).data.row_version).toBe(released.row_version);

  const reacquiredResponse = await createBinding(
    request,
    headers,
    { ...basePayload, execution_attempt_id: attemptIds[1] },
    "binding-reacquire",
  );
  expect(reacquiredResponse.status()).toBe(201);
  const second = (await reacquiredResponse.json()).data as ExecutionBindingSnapshotResource;
  expect(second.identity_lease.fencing_generation).toBe(2);
  expect(second.runner_lease.fencing_generation).toBe(2);

  const staleFencing = await request.post(
    `/api/v1/execution-binding-snapshots/${second.execution_binding_snapshot_id}/leases/renew`,
    {
      headers: { ...headers, "Idempotency-Key": "binding-old-fencing" },
      data: {
        ...commandBody(second),
        identity_lease_generation: 1,
        runner_lease_generation: 1,
      },
    },
  );
  expect(staleFencing.status()).toBe(409);
  expect((await staleFencing.json()).code).toBe("RESOURCE_LEASE_FENCING_CONFLICT");

  const secondRelease = await request.post(
    `/api/v1/execution-binding-snapshots/${second.execution_binding_snapshot_id}/release`,
    {
      headers: { ...headers, "Idempotency-Key": "binding-release-second" },
      data: commandBody(second),
    },
  );
  expect(secondRelease.status()).toBe(200);

  const contenders = await Promise.all(
    attemptIds.slice(2).map((executionAttemptId, index) =>
      createBinding(
        request,
        headers,
        { ...basePayload, execution_attempt_id: executionAttemptId },
        `binding-concurrent-${index}`,
      ),
    ),
  );
  expect(contenders.map((response) => response.status()).sort()).toEqual([201, 409]);
  const winner = contenders.find((response) => response.status() === 201);
  const loser = contenders.find((response) => response.status() === 409);
  expect(winner).toBeDefined();
  expect(loser).toBeDefined();
  const winnerBinding = (await winner!.json()).data as ExecutionBindingSnapshotResource;
  expect(winnerBinding.identity_lease.fencing_generation).toBe(3);
  expect(winnerBinding.runner_lease.fencing_generation).toBe(3);
  expect(["EXECUTION_BINDING_PREFLIGHT_FAILED", "RESOURCE_LEASE_CONFLICT"]).toContain(
    (await loser!.json()).code,
  );
});
