import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:8010", trace: "retain-on-failure" },
  webServer: {
    command:
      "MARKET_LIVE=0 MARKET_DB=../work/browser.sqlite3 ../.venv/bin/python -m uvicorn backend.main:app --app-dir .. --host 127.0.0.1 --port 8010",
    url: "http://127.0.0.1:8010/api/status",
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1050 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
});
