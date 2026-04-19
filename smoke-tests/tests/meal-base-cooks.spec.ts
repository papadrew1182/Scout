/**
 * Smoke test: meal base-cooks (Phase 5).
 */

import { test, expect, type Page } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

async function login(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.waitForSelector('input[placeholder="Email"]', { timeout: 10000 });
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await expect(page.locator('input[placeholder="Email"]')).not.toBeVisible({ timeout: 15000 });
}

test.describe("Meal base-cook model", () => {
  test("admin can access meal staple form", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/meals/staples/new");
    await page.waitForTimeout(2000);
    const title = page.locator("text=Add Staple Meal");
    await expect(title).toBeVisible({ timeout: 5000 });
  });

  test("meals page renders", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/meals/this-week");
    await page.waitForTimeout(2000);
    const weekHeader = page.locator("text=Week of");
    await expect(weekHeader).toBeVisible({ timeout: 5000 });
  });
});
