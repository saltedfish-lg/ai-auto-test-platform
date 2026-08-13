import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
const outputDir = process.env.PLAYWRIGHT_OUTPUT_DIR;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  outputDir: outputDir ?? "./test-results",
  use: {
    baseURL,
    // Authentication flows carry runtime-only credentials and tokens; never persist them in artifacts.
    trace: "off",
    screenshot: "off",
    video: "off",
    launchOptions: {
      executablePath,
      args: ["--no-proxy-server"],
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "npm run dev -- --host 127.0.0.1",
        url: baseURL,
        reuseExistingServer: !process.env.CI,
      },
});
