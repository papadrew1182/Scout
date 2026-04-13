/**
 * Smoke test: dev-mode ingestion buttons gate.
 *
 * `DEV_MODE = !process.env.EXPO_PUBLIC_API_URL` in scout-ui/lib/config.ts.
 * In any smoke environment (local or CI) EXPO_PUBLIC_API_URL is set, so
 * DEV_MODE is false and the DevToolsPanel on the personal surface must
 * NOT render its Google Calendar / YNAB ingestion buttons.
 *
 * If this test starts failing in CI, something is leaking DEV_MODE=true
 * into a production-shaped build.
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

test.describe("Dev-mode gate", () => {
  test("personal dashboard does NOT render dev ingestion buttons", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.click("text=Personal");
    await expect(page.locator("text=Dashboard")).toBeVisible({ timeout: 10000 });

    // The DevToolsPanel renders "Ingest Google Calendar" and "Ingest YNAB"
    // buttons when DEV_MODE is true. They must be absent in smoke.
    await expect(page.locator("text=Ingest Google Calendar")).toHaveCount(0);
    await expect(page.locator("text=Ingest YNAB")).toHaveCount(0);
  });
});
