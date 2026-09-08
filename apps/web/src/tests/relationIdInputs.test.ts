import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const views = ["ProjectsListView.vue", "RunnersView.vue", "ExecutionBindingsView.vue", "AIExplorationView.vue"];
const relationModels = [
  "project_id",
  "environment_id",
  "business_terminal_id",
  "test_account_id",
  "runner_id",
  "runtime_policy_revision_id",
  "owner_user_id",
  "execution_attempt_id",
  "runner_resource_identity",
  "login_strategy_id",
];

describe("normal business UI does not accept relationship identities as free text", () => {
  for (const name of views) {
    it(`${name} has no editable relationship-ID el-input`, () => {
      const path = fileURLToPath(new URL(`../views/${name}`, import.meta.url));
      const source = readFileSync(path, "utf8");
      for (const model of relationModels) {
        const editableInput = new RegExp(`<el-input[^>]*v-model=["'][^"']*${model}[^"']*["']`, "s");
        expect(source).not.toMatch(editableInput);
      }
    });
  }
});
