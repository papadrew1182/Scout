import { test, expect } from "@playwright/test";

const ADULT_EMAIL = process.env.SMOKE_ADULT_EMAIL || "adult@test.com";
const CHILD_EMAIL = process.env.SMOKE_CHILD_EMAIL || "child@test.com";
const PASSWORD = process.env.SMOKE_PASSWORD || "testpass123";

async function login(page: any, email: string, password: string) {
  await page.goto("/");
  await page.fill('input[placeholder="Email"]', email);
  await page.fill('input[placeholder="Password"]', password);
  await page.click("text=Sign In");
  await page.waitForSelector("text=Scout", { timeout: 15000 });
}

test.describe("Login", () => {
  test("adult can sign in", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await expect(page.locator("text=Sign out")).toBeVisible();
  });

  test("child can sign in", async ({ page }) => {
    await login(page, CHILD_EMAIL, PASSWORD);
    await expect(page.locator("text=Scout")).toBeVisible();
  });

  test("bad password shows error", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[placeholder="Email"]', ADULT_EMAIL);
    await page.fill('input[placeholder="Password"]', "wrongpassword");
    await page.click("text=Sign In");
    await expect(page.locator("text=Invalid email or password")).toBeVisible({ timeout: 5000 });
  });

  test("sign out returns to login", async ({ page }) => {
    await login(page, ADULT_EMAIL, PASSWORD);
    await page.click("text=Sign out");
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 5000 });
  });

  test("invalid token clears to login", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.setItem("scout_session_token", "invalid-xxx"));
    await page.reload();
    await expect(page.locator('input[placeholder="Email"]')).toBeVisible({ timeout: 10000 });
  });
});
