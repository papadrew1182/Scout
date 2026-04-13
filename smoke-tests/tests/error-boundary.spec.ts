/**
 * Smoke test: global ErrorBoundary render path.
 *
 * Navigates to the DEV-only `/__boom` route, triggers a render crash,
 * and asserts the top-level ErrorBoundary fallback renders.
 *
 * Runs only when the frontend was built with
 * `EXPO_PUBLIC_SCOUT_E2E=true`. Otherwise the `/__boom` route renders
 * a "Not available" stub instead of the trigger button, and this test
 * skips cleanly. That gate keeps the crash route out of real
 * production builds while still giving us a real E2E assertion of the
 * boundary in smoke.
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
  await page.waitForSelector("text=Personal", { timeout: 15000 });
}

test.describe("Global ErrorBoundary", () => {
  test("forces a render crash and renders the boundary fallback", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.goto("/__boom");

    // If E2E hooks are off, the route renders the "Not available" stub
    // and no trigger button is present — skip in that case.
    const trigger = page.locator('[data-testid="boom-trigger"]');
    const triggerVisible = await trigger.isVisible().catch(() => false);
    if (!triggerVisible) {
      test.skip(
        true,
        "EXPO_PUBLIC_SCOUT_E2E=true is not set in the expo export env; /__boom is inert.",
      );
      return;
    }

    // Expect a page-level error event when the crash happens. React's
    // ErrorBoundary catches render errors and renders its fallback;
    // the fallback carries the testID we can assert on.
    let sawPageError = false;
    page.on("pageerror", () => {
      sawPageError = true;
    });

    await trigger.click();

    // Fallback must render after the crash
    await expect(page.locator('[data-testid="scout-error-boundary"]')).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=Something went wrong")).toBeVisible();

    // Optional sanity: React surfaces the underlying error to pageerror.
    expect.soft(sawPageError, "pageerror should fire on render crash").toBeTruthy();
  });
});
