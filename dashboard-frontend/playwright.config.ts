import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    channel: "msedge",
    headless: true,
  },
  webServer: [
    {
      command:
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \"$env:PYTHONPATH='D:\\CRYPTOTEHNOLOG\\src'; & 'D:\\CRYPTOTEHNOLOG\\.venv\\Scripts\\python.exe' -m cryptotechnolog.dashboard\"",
      url: "http://127.0.0.1:8000/dashboard/settings/bybit-connector-diagnostics",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173 --strictPort",
      url: "http://127.0.0.1:4173/terminal/settings",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
