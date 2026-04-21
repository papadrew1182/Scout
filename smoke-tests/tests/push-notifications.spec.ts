/**
 * Smoke test: push notifications (Sprint Expansion Phase 1).
 *
 * Verifies the web-rendered /settings/notifications page loads and that
 * admin-only sections (Test push, Family delivery log) are visible for
 * an adult actor. Does NOT assert physical-device delivery — that is
 * manual per the Phase 1 acceptance criteria.
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

test.describe("Push notifications", () => {
  test("settings page links to notifications", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings");
    await page.waitForTimeout(1500);
    const link = page.getByText("Open Notifications", { exact: false });
    await expect(link).toBeVisible({ timeout: 5000 });
  });

  test("notifications page renders core sections", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings/notifications");
    await page.waitForTimeout(2500);

    await expect(page.getByText("Permission status", { exact: true })).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByText("Registered devices", { exact: true })).toBeVisible();
    await expect(page.getByText("My recent notifications", { exact: true })).toBeVisible();
  });

  test("admin sees Test push and Family delivery log cards", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings/notifications");
    await page.waitForTimeout(2500);

    await expect(page.getByText("Send a test push", { exact: true })).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByText("Family delivery log", { exact: true })).toBeVisible();
  });

  test("web build shows an unsupported-platform notice", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/settings/notifications");
    await page.waitForTimeout(2500);
    // usePushRegistration short-circuits to "web" on Platform.OS === 'web'.
    const notice = page.getByText(/Push notifications are not supported in the web build/i);
    await expect(notice).toBeVisible({ timeout: 5000 });
  });
});
