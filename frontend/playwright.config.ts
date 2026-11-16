import { defineConfig } from "@playwright/test";
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

// E2E runs against a throwaway COPY of the real store so scenarios never touch database/unlock.rl.
const src = resolve("../database/unlock.rl");
const dst = resolve("../database/e2e/unlock-e2e.rl");
if (!existsSync(src)) throw new Error("Build the store first: python -m unlock build");
mkdirSync(resolve("../database/e2e"), { recursive: true });
copyFileSync(src, dst);
const py = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:8765", viewport: { width: 1920, height: 1080 } },
  webServer: {
    command: `${py} -m unlock serve --port 8765 --store "${dst}"`,
    cwd: "..",
    env: { PYTHONPATH: "backend" },
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
