import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // Generous: the first load of a sector triggers live (uncached) Yahoo
  // quote fetches for every company in it via the backend, and Phase 4's
  // Overview tab fires a further ~8 requests per page load (price/
  // performance history, events, ratios, overview) -- all funnelled
  // through the backend's own Yahoo-request semaphore. Running this
  // suite's tests in parallel multiplies that contention, so each
  // individual `expect(...)`'s timeout needs enough headroom too, not
  // just the overall test timeout.
  timeout: 45_000,
  expect: { timeout: 15_000 },
  // Small suite, heavy per-page backend load -- serial workers avoid the
  // contention slowing any one test past its own timeout.
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
