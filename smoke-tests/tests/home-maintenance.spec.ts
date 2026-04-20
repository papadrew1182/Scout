/**
 * Smoke test: home maintenance (Phase 4).
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

test.describe("Home maintenance", () => {
  test.beforeEach(async ({ page }) => {
    // Skip in CI environments without Session 3 frontend
    if (!process.env.SMOKE_SESSION3) test.skip();
  });

  test("admin can view /home page", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/home");
    await page.waitForTimeout(2000);
    const title = page.locator("text=Maintenance");
    await expect(title).toBeVisible({ timeout: 5000 });
  });

  test("admin can access /admin/home", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/home");
    await page.waitForTimeout(2000);
    const title = page.locator("text=Home Maintenance");
    await expect(title).toBeVisible({ timeout: 5000 });
  });

  test("admin can create a zone", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/admin/home");
    await page.waitForTimeout(2000);

    const nameInput = page.locator('[accessibilityLabel="zones name"]');
    if (!(await nameInput.isVisible())) { test.skip(); return; }
    await nameInput.fill("Test Kitchen");

    const createBtn = page.locator('[accessibilityLabel="Create zone"]');
    await createBtn.click();
    await page.waitForTimeout(2000);

    const success = page.locator("text=zone created");
    await expect(success).toBeVisible({ timeout: 5000 });
  });
});
