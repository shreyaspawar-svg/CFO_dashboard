import { chromium } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "screenshots");

const TARGETS = [
  { symbol: "TCS", sector: "Information Technology", viewport: "desktop", theme: "dark" },
  { symbol: "HDFCBANK", sector: "Banks & Financial Services", viewport: "desktop", theme: "dark" },
  { symbol: "HDFCLIFE", sector: "Banks & Financial Services", viewport: "desktop", theme: "dark" },
  { symbol: "INDIGO", sector: "Transport & Logistics", viewport: "desktop", theme: "dark" },
  { symbol: "TCS", sector: "Information Technology", viewport: "mobile", theme: "light" },
];
const VIEWPORTS = {
  desktop: { width: 1440, height: 1400 },
  mobile: { width: 390, height: 1600 },
};

const browser = await chromium.launch();

for (const t of TARGETS) {
  const context = await browser.newContext({ viewport: VIEWPORTS[t.viewport], colorScheme: t.theme });
  const page = await context.newPage();
  const url = `http://localhost:3000/?sector=${encodeURIComponent(t.sector)}&symbol=${t.symbol}`;
  await page.goto(url);

  const isLight = await page.evaluate(() => document.documentElement.getAttribute("data-theme") === "light");
  if ((t.theme === "light") !== isLight) {
    await page.getByRole("button", { name: "Toggle theme" }).click();
  }

  await page.getByRole("tab", { name: "Income Statement" }).click();
  await page.getByText("Income statement detail").waitFor({ timeout: 30000 });
  await page.waitForTimeout(800);

  const filename = `${t.symbol}_income_statement_${t.viewport}_${t.theme}.png`;
  await page.screenshot({ path: path.join(outDir, filename), fullPage: true });
  console.log("Saved", filename);
  await context.close();
}

await browser.close();
