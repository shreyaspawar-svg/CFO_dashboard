// PLAN.md Phase 5 Task C.1: scripted loop over all 50 symbols x all tabs,
// checking for console errors and failed API calls. Run with:
//   node scripts/qa_crawl.mjs
import { chromium } from "@playwright/test";

const TABS = [
  "Overview",
  "Income Statement",
  "Balance Sheet",
  "Cash Flow",
  "Ratios",
  "Valuation",
  "Peers",
  "Shareholding & Events",
];

async function main() {
  const universeRes = await fetch("http://localhost:8000/api/universe");
  const universe = await universeRes.json();
  const targets = universe.sectors.flatMap((s) => s.companies.map((c) => ({ symbol: c.symbol, sector: s.name })));
  console.log(`Crawling ${targets.length} symbols x ${TABS.length} tabs...`);

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const failedRequests = [];
  const pageErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push({ text: msg.text().slice(0, 300) });
    }
  });
  page.on("pageerror", (err) => {
    pageErrors.push({ text: String(err).slice(0, 300) });
  });
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/") && res.status() >= 400) {
      failedRequests.push({ url, status: res.status() });
    }
  });
  page.on("requestfailed", (req) => {
    if (req.url().includes("/api/")) {
      failedRequests.push({ url: req.url(), status: "requestfailed", error: req.failure()?.errorText });
    }
  });

  let visited = 0;
  for (const t of targets) {
    const beforeErrors = consoleErrors.length;
    const beforeFailed = failedRequests.length;
    const beforePageErrors = pageErrors.length;

    await page.goto(
      `http://localhost:3000/?sector=${encodeURIComponent(t.sector)}&symbol=${encodeURIComponent(t.symbol)}`,
      { waitUntil: "networkidle", timeout: 30000 }
    );

    for (const tab of TABS) {
      try {
        await page.getByRole("tab", { name: tab, exact: true }).click();
        await page.waitForTimeout(700);
      } catch (e) {
        failedRequests.push({ url: `${t.symbol} tab=${tab}`, status: "click-failed", error: String(e).slice(0, 200) });
      }
    }
    visited++;

    const newErrors = consoleErrors.length - beforeErrors;
    const newFailed = failedRequests.length - beforeFailed;
    const newPageErrors = pageErrors.length - beforePageErrors;
    if (newErrors || newFailed || newPageErrors) {
      console.log(
        `[${visited}/${targets.length}] ${t.symbol}: +${newErrors} console errors, +${newFailed} failed API calls, +${newPageErrors} page errors`
      );
    } else if (visited % 10 === 0) {
      console.log(`[${visited}/${targets.length}] ${t.symbol}: clean`);
    }
  }

  await browser.close();

  console.log("\n=== SUMMARY ===");
  console.log(`Symbols visited: ${visited}`);
  console.log(`Console errors: ${consoleErrors.length}`);
  console.log(`Failed API calls: ${failedRequests.length}`);
  console.log(`Page errors: ${pageErrors.length}`);

  if (consoleErrors.length) {
    console.log("\n--- Console errors (deduped) ---");
    const seen = new Set();
    for (const e of consoleErrors) {
      if (!seen.has(e.text)) {
        seen.add(e.text);
        console.log(e.text);
      }
    }
  }
  if (failedRequests.length) {
    console.log("\n--- Failed API calls (deduped) ---");
    const seen = new Set();
    for (const f of failedRequests) {
      const key = `${f.status} ${f.url}`;
      if (!seen.has(key)) {
        seen.add(key);
        console.log(key, f.error ?? "");
      }
    }
  }
  if (pageErrors.length) {
    console.log("\n--- Page errors (deduped) ---");
    const seen = new Set();
    for (const e of pageErrors) {
      if (!seen.has(e.text)) {
        seen.add(e.text);
        console.log(e.text);
      }
    }
  }

  process.exit(consoleErrors.length || failedRequests.length || pageErrors.length ? 1 : 0);
}

main();
