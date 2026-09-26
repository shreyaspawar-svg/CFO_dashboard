import { test, expect } from "@playwright/test";

test("loads, picks a sector, picks a company, URL updates", async ({ page }) => {
  await page.goto("/");

  // A default sector + its largest company should resolve into the URL
  // without any interaction (task 3.4's auto-select-largest behaviour).
  await expect(page).toHaveURL(/sector=/);
  await expect(page).toHaveURL(/symbol=/);
  await expect(page.getByRole("combobox", { name: "Select company" })).toBeVisible();

  // Switch sector via the combobox.
  await page.getByRole("combobox", { name: "Select sector" }).click();
  await page.getByRole("option", { name: /Information Technology/ }).click();
  await expect(page).toHaveURL(/sector=Information\+Technology|sector=Information%20Technology/);

  // A company from the new sector should auto-populate.
  await expect(page.getByRole("combobox", { name: "Select company" })).toContainText(/TCS|INFY|HCLTECH|TECHM/);

  // Explicitly pick a company.
  await page.getByRole("combobox", { name: "Select company" }).click();
  await page.getByRole("option", { name: /Infosys/i }).click();
  await expect(page).toHaveURL(/symbol=INFY/);
  await expect(page.getByRole("main").getByText("Infosys Ltd")).toBeVisible();
});

test("command search finds a company by its former name", async ({ page }) => {
  await page.goto("/");
  // Wait for hydration (the keydown listener attaches on mount) before
  // relying on the keyboard shortcut.
  await expect(page.getByRole("button", { name: /Search companies/ })).toBeVisible();
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder(/Search by name/).fill("zomato");
  await expect(page.getByRole("option", { name: /Eternal/i })).toBeVisible();
  await page.getByRole("option", { name: /Eternal/i }).click();
  await expect(page).toHaveURL(/symbol=ETERNAL/);
});

test("shows a warning banner for a company with non-comparable history", async ({ page }) => {
  await page.goto("/?sector=Automobiles&symbol=TMPV");
  // Scoped to role="alert" (the WarningBanner) filtered by its text: a bare
  // text match now also hits the price chart's break-marker label (Phase
  // 4.1 review item 3's "Demerger from Tata Motors" chart annotation, which
  // reads from the same corporate-action data this banner does) -- and
  // Next.js's own route-announcer also has role="alert", so the text
  // filter is still needed to land on the actual banner, not just the role.
  await expect(
    page.getByRole("alert").filter({ hasText: /demerger|not comparable/i })
  ).toBeVisible();
});
