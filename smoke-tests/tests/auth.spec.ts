/**
 * Smoke tests: authentication flows.
 *
 * Prerequisites:
 * - Backend running on localhost:8000
 * - Frontend (web) running on localhost:8081
 * - Test accounts bootstrapped:
 *   - adult: adult@test.com / testpass123
 *   - child: child@test.com / testpass123
 */

import { test, expect } from "@playwright/test";

const ADULT_EMAIL = "adult@test.com";
const CHILD_EMAIL = "child@test.com";
const PASSWORD = "testpass123";

async function login(page: any, email: string, password: string) {
  await page.goto("/");
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  // Wait for nav to appear (sign-in complete)
  await page.waitForSelector("text=Scout", { timeout: 10000 });
}

test.describe("Login", () => {
  test("adult can sign in and sees dashboard", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    // Should see the Scout brand in nav
    await expect(page.locator("text=Scout")).toBeVisible();
    // Should see sign out
    await expect(page.locator("text=Sign out")).toBeVisible();
  });

  test("child can sign in", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);
    await expect(page.locator("text=Scout")).toBeVisible();
  });

  test("bad password shows error", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[placeholder="Email"]', ADULT_EMAIL);
    await page.fill('input[placeholder="Password"]', "wrongpass");
    await page.click("text=Sign In");
    await expect(page.locator("text=Invalid email or password")).toBeVisible({ timeout: 5000 });
  });

  test("sign out returns to login", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.click("text=Sign out");
    // Should see login screen
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Session expiry", () => {
  test("invalid token clears to login", async ({ page }) => {
    await page.goto("/");
    // Inject an invalid token
    await page.evaluate(() => {
      localStorage.setItem("scout_session_token", "invalid-token-xxx");
    });
    await page.reload();
    // Should fall back to login screen after validation fails
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 10000 });
  });
});
