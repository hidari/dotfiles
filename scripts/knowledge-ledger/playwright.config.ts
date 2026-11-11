import { defineConfig } from "@playwright/test";

// ローカル専用の E2E。CI と pre-commit には載せない。
// 起動のたびに固定の fixture からページを組み直して配信する (実データは使わない)
const PORT = 4173;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    command:
      "uv run --directory . python -m knowledge_ledger.build e2e/fixtures/items.json e2e/.build/index.html" +
      ` && node e2e/serve.mjs ${PORT} e2e/.build/index.html`,
    url: `http://127.0.0.1:${PORT}/index.html`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
