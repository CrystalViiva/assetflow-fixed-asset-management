import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 90_000,
  globalTimeout: 300_000,
  outputDir: process.env.E2E_OUTPUT_DIR || ".codex-browser-results",
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile: `${process.env.E2E_OUTPUT_DIR || ".codex-browser-results"}/report.json`,
      },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:3007",
    headless: true,
    channel: process.env.E2E_BROWSER_EXECUTABLE
      ? undefined
      : process.env.E2E_BROWSER_CHANNEL || "chromium",
    launchOptions: {
      timeout: 30_000,
      executablePath: process.env.E2E_BROWSER_EXECUTABLE,
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
