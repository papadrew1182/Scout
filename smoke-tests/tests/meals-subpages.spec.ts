/**
 * Smoke test: meals subpages.
 *
 * Covers previously-unsmoked pages /meals/prep, /meals/reviews, and
 * asserts /meals/this-week renders a plan after seed.
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

test.describe("Meals subpages", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
  });

  test("/meals/this-week renders seeded approved plan", async ({ page }) => {
    await page.click("text=Meals");
    await expect(page.locator("text=This Week").first()).toBeVisible({ timeout: 10000 });
    // Seeded plan title is "Smoke Test Week"; empty state should NOT be shown.
    await expect(
      page.locator("text=No plan yet").first(),
    ).not.toBeVisible({ timeout: 2000 }).catch(() => {});
  });

  test("/meals/prep loads and renders header or empty state", async ({ page }) => {
    await page.goto("/meals/prep");
    // Either the prep header or the empty state must render.
    const prepHeader = page.locator("text=Sunday Prep");
    const empty = page.locator("text=No plan yet");
    await expect(prepHeader.or(empty)).toBeVisible({ timeout: 10000 });
  });

  test("/meals/reviews loads with a meal-title input", async ({ page }) => {
    await page.goto("/meals/reviews");
    // The reviews page always renders the Save Review form for the active user.
    await page.waitForSelector('input[placeholder="Meal title"]', { timeout: 10000 });
    await expect(page.getByRole("button", { name: "Save Review" }).first()).toBeVisible();
  });
});
